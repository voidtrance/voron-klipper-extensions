# Klipper module for tracking printer state.
#
# The module improves on the current printer state tracking and
# notification by collecting the states from various other modules
# into a single place.
#
# In addition, it allows running of custom Gcode templates on some
# state transitions.
#
# Copyright (C) 2023 Mitko Haralanov <voidtrance@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging
from extras.gcode_macro import TemplateWrapper

TIMER_DURATION = 0.1
GCODE_MUTEX_DELAY = 0.2


def log(eventtime, fmt, *args):
    logging.info("state_notify[%s]: " % eventtime + fmt % args)


class StateNotify:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.inactive_timeout = config.getfloat("inactive_timeout", 0.)
        self.heaters_keep_active = config.getboolean("heaters_active", False)
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode_macro = self.printer.load_object(config, "gcode_macro")
        self.idle_timeout = self.printer.load_object(config, "idle_timeout")
        self.idle_gcode = config.get("on_idle_gcode", '')
        self.gcode_templates = {
            'ready': self.gcode_macro.load_template(config, "on_ready_gcode", ''),
            'active': self.gcode_macro.load_template(config, "on_active_gcode", ''),
            'inactive': self.gcode_macro.load_template(config, "on_inactive_gcode", ''),
            'noop': TemplateWrapper(self.printer, self.gcode_macro.env,
                                    "state_notify:noop", "G4 P1"),
        }
        self.ignore_change = False
        self.state = "none"
        self.menu = self.sdcard = self.print_stats = None
        self.menu_check_timer = self.inactive_timer = self.delayed_gcode_timer = \
            self.pause_timer = None
        self.gcode.register_command("STATE_NOTIFY_STATE", self.cmd_STATE_NOTIFY_STATE,
                                    False, desc=self.cmd_STATE_NOTIFY_STATE_help)
        self.printer.register_event_handler("klippy:mcu_identify",
                                            self._register_ready_handler)
        self.printer.register_event_handler("klippy:shutdown",
                                            lambda: self._klippy_handler("shutdown"))
        self.printer.register_event_handler("klippy:disconnect",
                                            lambda: self._klippy_handler("disconnect"))

    def _register_ready_handler(self):
        # Look up the objects below when the printer has reached the "Ready"
        # state. Doing so before this point may result in errors due to the
        # fact that Klipper creates objects as it parses the configuration and
        # the object might not have been created by the time this module is
        # initialized.
        self.sdcard = self.printer.lookup_object("virtual_sdcard")
        self.print_stats = self.printer.lookup_object("print_stats")
        self.pheaters = self.printer.lookup_object("heaters")
        self.menu = self.printer.lookup_object("menu", None)

        # Any "idle" gcode specified in the 'state_notife:on_idle_gcode' config
        # needs to be executed as part of the 'idle_timeout:gcode' config. Otherwise,
        # the printer jumps out of "idle" state because the 'state_notify:on_idle_gcode'
        # GCode gets executed after the 'idle_timeout' state changes to "Idle".
        configfile = self.printer.lookup_object("configfile")
        config_status = configfile.get_status(self.reactor.monotonic())
        idle_config = config_status["config"].get("idle_timeout", {})
        idle_gcode = idle_config.get("gcode", "") + self.idle_gcode
        self.idle_timeout.idle_gcode = TemplateWrapper(self.printer, self.gcode_macro.env,
                                                  "idle_timeout:gcode", idle_gcode)

        self.inactive_timer = self.reactor.register_timer(self._inactive_timer_handler,
                                                      self.reactor.monotonic() + 
                                                      self.inactive_timeout)
        self.pause_timer = self.reactor.register_timer(self._print_pause_handler)
        self.printer.register_event_handler("idle_timeout:idle",
                                        lambda e: self._state_handler("idle_idle", e))
        self.printer.register_event_handler("idle_timeout:ready",
                                        lambda e: self._state_handler("idle_ready", e))
        self.printer.register_event_handler("idle_timeout:printing",
                                        lambda e: self._state_handler("idle_printing", e))
        if self.menu:
            self.printer.register_event_handler("menu:begin",
                                        lambda e: self._state_handler("menu_begin",
                                                                      self.reactor.monotonic()))
            self.printer.register_event_handler("menu:exit",
                                        lambda e: self._state_handler("menu_exit",
                                                                      self.reactor.monotonic()))
            self.menu_check_timer = self.reactor.register_timer(self._menu_check_timer_handler)
    
        self.printer.register_event_handler("klippy:ready",
                                            lambda: self._klippy_handler("ready"))

    def _klippy_handler(self, state):
        self.handle_state_change(state, self.reactor.monotonic())
        if state == "ready":
            # Automaticaly transition from "ready" to "active".
            # If `on_ready_gcode` is present, it would have already
            # transition the state to "ready" during the execution of
            # the template.
            if self.state != "active":
                self.handle_state_change("active", self.reactor.monotonic())
        if state == "shutdown":
            if self.inactive_timer:
                self.reactor.unregister_timer(self.inactive_timer)
            if self.menu_check_timer:
                self.reactor.unregister_timer(self.menu_check_timer)
            if self.pause_timer:
                self.reactor.unregister_timer(self.pause_timer)

    def _check_printer_printing(self):
        # VirtualSD.is_active() only returns True if the printer is actively
        # printing. If it is paused, it returns False. So, in order to correctly
        # determine if the printer is currently printing, we can also use
        # VirtualSD.file_path() and VirtualSD.progress() since the class does store
        # the currently printing file, the file size, and position across pauses.
        return self.sdcard.is_active() or \
            (self.sdcard.file_path() is not None and self.sdcard.progress() > 0.)
    
    def _state_handler(self, state, eventtime):
        log(eventtime, "State: %s, Substate: %s", self.state, state)
        template = None
        if state == "idle_idle":
            self.reactor.update_timer(self.pause_timer, self.reactor.NEVER)
            self.reactor.update_timer(self.inactive_timer, self.reactor.NEVER)
            state = "idle"
            if self.menu:
                self.reactor.update_timer(self.menu_check_timer,
                                          self.reactor.NEVER)
                self.menu.exit()
        elif state in ("idle_ready", "menu_exit"):
            menu_is_running = False
            if self.menu:
                menu_is_running = self.menu.is_running()
            if self.state in ("ready", "active", "printing"):
                if self.state != "active":
                    self.reactor.update_timer(self.pause_timer, self.reactor.NEVER)
                if not menu_is_running:
                    self.reactor.update_timer(self.inactive_timer,
                                              self.reactor.monotonic() + self.inactive_timeout)
            return
        elif state == "idle_printing" or state == "menu_begin":
            self.reactor.update_timer(self.inactive_timer, self.reactor.NEVER)
            if state == "menu_begin":
                self.reactor.update_timer(self.menu_check_timer,
                                          self.reactor.monotonic() + TIMER_DURATION)
            state = "active"
            self.reactor.update_timer(self.pause_timer, self.reactor.NEVER)
            if self._check_printer_printing():
                state = "printing"
                # There is no way for us to get a notification that the
                # print has been paused other than to monitor the
                # print_stats.
                self.reactor.update_timer(self.pause_timer,
                                          self.reactor.monotonic() + TIMER_DURATION)
                if self.state not in ("paused", "active"):
                    template = "active"
        if self.state != state and not self.ignore_change:
            self.handle_state_change(state, eventtime, template)
        return

    # Timer to check whether the menu is still active. It runs every TIMER_DURATION
    # interval. If the menu is no longer active, it triggers the "menu_exit" state
    # transition.
    def _menu_check_timer_handler(self, eventtime):
        if not self.menu.is_running():
            self._state_handler("menu_exit", eventtime)
            return self.reactor.NEVER
        if self.state not in ("paused", "printing"):
            self._run_template(eventtime, "noop")
        return self.reactor.monotonic() + TIMER_DURATION

    # Timer to monitor print statistics for state changes. This is needed to catch
    # print pauses/resumes.
    def _print_pause_handler(self, eventtime):
        print_state = self.print_stats.get_status(eventtime).get("state")
        if print_state in ("paused", "printing"):
            if self.state != print_state:
                self.handle_state_change(print_state, eventtime, "__invalid__")
            return eventtime + TIMER_DURATION
        return self.reactor.NEVER

    def _run_gcode(self, template):
        try:
            script = self.gcode_templates[template].render()
            res = self.gcode.run_script(script)
        except Exception as err:
            logging.exception("state_notify: '%s' gcode error: %s" %
                              (template, str(err)))
            res = None
        return res

    def _delayed_gcode_handler(self, eventtime, template):
        if self.gcode.get_mutex().test():
            return eventtime + GCODE_MUTEX_DELAY
        self._run_gcode(template)
        self.reactor.unregister_timer(self.delayed_gcode_timer)
        return self.reactor.NEVER

    # Attempt to run the gcode template. If the gcode mutex is not taken, run the
    # template directly. Otherwise, schedule a timer to run the gcode at a later
    # time.
    def _run_template(self, eventtime, template):
        if not self.gcode.get_mutex().test():
            return self._run_gcode(template)
        self.delayed_gcode_timer = \
            self.reactor.register_timer(lambda e: self._delayed_gcode_handler(e, template),
                                        self.reactor.monotonic() + GCODE_MUTEX_DELAY)
        return None

    # Check whether the printer is still active. This is used to detect
    # activity, which is not readily detectable from the idle_timeout
    # state.
    #
    # When it comes to printer activity tracked by the idle_timeout
    # module, Klipper only considers toolhead updates as activity.
    # If we want to keep the printer in the "active" state when
    # heaters are active, we need special handling.
    def _check_printer_active(self, eventtime):
        heaters = self.pheaters.get_all_heaters()
        heaters_active = False
        for heater_name in heaters:
            heater = self.pheaters.lookup_heater(heater_name)
            status = heater.get_status(eventtime)
            if status["target"] > 0.:
                log(eventtime, f"Heater '{heater_name}' target: {status['target']}")
                heaters_active = True
                break
        if heaters_active and self.state not in ("paused", "printing"):
            self._run_template(eventtime, "noop")
        return heaters_active

    # Transition to the "inactive" state. This callback is called when the
    # inactive timeout elapses.
    def _inactive_timer_handler(self, eventtime):
        if self._check_printer_active(eventtime):
            if self.heaters_keep_active:
                self._run_template(eventtime, 'noop')
            return eventtime + self.inactive_timeout

        self.ignore_change = True
        self.handle_state_change("inactive", eventtime)
        self.ignore_change = False
        return self.reactor.NEVER

    def handle_state_change(self, state, eventtime, template=None):
        log(eventtime, "changing state from %s to %s", self.state, state)
        self.state = state
        self.printer.send_event("state_notify:%s" % self.state)
        if template is None:
            template = self.state
        if template in self.gcode_templates and \
                self.gcode_templates[template]:
            log(eventtime, "  running template: %s", template)
            return self._run_template(eventtime, template)
        return None

    def get_status(self, eventtime):
        return {'state': self.state,
                'inactive_timeout': self.inactive_timeout,
                }

    cmd_STATE_NOTIFY_STATE_help = "Get current printer status"

    def cmd_STATE_NOTIFY_STATE(self, gcmd):
        self.gcode.respond_info("State Notify state: %s" % self.state)

def load_config(config):
    return StateNotify(config)
