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

TIMER_DURATION = 0.1
GCODE_MUTEX_DELAY = 0.2


def log(fmt, *args):
    logging.info("state_notify:" + fmt % args)


class StateNotify:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.inactive_timeout = config.getfloat("inactive_timeout", 0.)
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object("gcode")
        gcode_macro = self.printer.load_object(config, "gcode_macro")
        self.gcode_templates = {
            'ready': gcode_macro.load_template(config, "on_ready_gcode", ''),
            'idle': gcode_macro.load_template(config, "on_idle_gcode", ''),
            'active': gcode_macro.load_template(config, "on_active_gcode", ''),
            'inactive': gcode_macro.load_template(config, "on_inactive_gcode", '')
        }
        self.ignore_change = False
        self.state = "none"
        self.menu = self.sdcard = self.print_stats = None
        self.menu_check_timer = self.inactive_timer = self.delayed_gcode_timer = \
            self.pause_timer = None
        self.gcode.register_command("STATE_NOTIFY_STATE", self.cmd_STATE_NOTIFY_STATE,
                                    False, desc=self.cmd_STATE_NOTIFY_STATE_help)
        self.printer.register_event_handler("klippy:ready",
                                            lambda: self._klippy_handler("ready"))
        self.printer.register_event_handler("klippy:shutdown",
                                            lambda: self._klippy_handler("shutdown"))
        self.printer.register_event_handler("klippy:disconnect",
                                            lambda: self._klippy_handler("disconnect"))

    def _klippy_handler(self, state):
        self.handle_state_change(state, self.reactor.monotonic())
        if state == "ready":
            # Look up the objects below when the printer has reached the "Ready"
            # state. Doing so before this point may result in errors due to the
            # fact that Klipper creates objects as it parses the configuration and
            # the object might not have been created by the time this module is
            # initialized.
            self.menu = self.printer.lookup_object("menu")
            self.sdcard = self.printer.lookup_object("virtual_sdcard")
            self.print_stats = self.printer.lookup_object("print_stats")
            self.printer.register_event_handler("idle_timeout:idle",
                                                lambda e: self._state_handler("idle_idle", e))
            self.printer.register_event_handler("idle_timeout:ready",
                                                lambda e: self._state_handler("idle_ready", e))
            self.printer.register_event_handler("idle_timeout:printing",
                                                lambda e: self._state_handler("idle_printing", e))
            self.printer.register_event_handler("menu:begin",
                                                lambda e: self._state_handler("menu_begin", e))
            self.printer.register_event_handler("menu:exit",
                                                lambda e: self._state_handler("menu_exit", e))
            self.menu_check_timer = \
                self.reactor.register_timer(self._menu_check_timer_handler)
            self.inactive_timer = \
                self.reactor.register_timer(self._inactive_timer_handler,
                                            self.reactor.monotonic() + self.inactive_timeout)
            self.pause_timer = \
                self.reactor.register_timer(self._print_pause_handler)
        elif state == "shutdown":
            if self.inactive_timer:
                self.reactor.unregister_timer(self.inactive_timer)
            if self.menu_check_timer:
                self.reactor.unregister_timer(self.menu_check_timer)
            if self.pause_timer:
                self.reactor.unregister_timer(self.pause_timer)

    def _state_handler(self, state, eventtime):
        log("Substate: %s", state)
        template = None
        if state == "idle_idle":
            self.reactor.update_timer(self.pause_timer, self.reactor.NEVER)
            self.reactor.update_timer(self.inactive_timer, self.reactor.NEVER)
            self.reactor.update_timer(self.menu_check_timer,
                                      self.reactor.NEVER)
            state = "idle"
            self.menu.exit()
        elif (state == "idle_ready" or state == "menu_exit"):
            if self.state in ("ready", "active", "printing") and not self.menu.is_running():
                self.reactor.update_timer(self.inactive_timer,
                                          self.reactor.monotonic() + self.inactive_timeout)
                if self.state == "printing":
                    self.reactor.update_timer(self.pause_timer,
                                              self.reactor.NEVER)
                    self.handle_state_change("active", eventtime,
                                             "__invalid__")
            return
        elif state == "idle_printing" or state == "menu_begin":
            self.reactor.update_timer(self.inactive_timer, self.reactor.NEVER)
            if state == "menu_begin":
                self.reactor.update_timer(self.menu_check_timer,
                                          self.reactor.monotonic() + TIMER_DURATION)
            state = "active"
            self.reactor.update_timer(self.pause_timer, self.reactor.NEVER)
            if self.sdcard.is_active():
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
        return self.reactor.monotonic() + TIMER_DURATION

    # Timer to monitor print statistics for state changes. This is needed to catch
    # print pauses.
    def _print_pause_handler(self, eventtime):
        if self.print_stats.state == "paused":
            if self.state != self.print_stats.state:
                self.handle_state_change("paused", eventtime, "__invalid__")
        return eventtime + TIMER_DURATION

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
                                        eventtime + GCODE_MUTEX_DELAY)
        return None

    # Transition o the "inactive" state. This callback is called when the
    # inactive timeout elapses.
    def _inactive_timer_handler(self, eventtime):
        self.ignore_change = True
        self.handle_state_change("inactive", eventtime)
        self.ignore_change = False
        return self.reactor.NEVER

    def handle_state_change(self, state, eventtime, template=None):
        log("changing state from %s to %s", self.state, state)
        self.state = state
        self.printer.send_event("state_notify:%s" % self.state)
        if template is None:
            template = self.state
        if template in self.gcode_templates and \
                self.gcode_templates[template]:
            log("  running template: %s", template)
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
