# Smoothly transition RGB LEDs between two colors
#
# Copyright (C) 2022-2023 Mitko Haralanov <voidtrance@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

FRAME_COUNT = 24
INTERPOLATE_STEP_TIME = 1.0 / FRAME_COUNT


class LedInterpolate:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.gcode.register_command("LED_INTERPOLATE",
                                    self.cmd_LED_INTERPOLATE, False,
                                    desc=self.cmd_LED_INTERPOLATE_help)
        self.printer.register_event_handler("klippy:ready", self.setup)

    def setup(self):
        # Klipper no longer uses the "led" module as the object which
        # collects all the configured LED objects. As a result, we can't
        # use it to lookup the LED object specified in the
        # LED_INTERPOLATE command. We have to get the list of all the
        # different LED types.
        #
        # In order to avoid doing this lookup all the time, cache the
        # sets of objects here.
        self.leds = self.printer.lookup_objects("led") + \
                self.printer.lookup_objects("neopixel") + \
                self.printer.lookup_objects("dotstar") + \
                self.printer.lookup_objects("pca9533") + \
                self.printer.lookup_objects("pca9632")

    def compute_color(self, start, end, runtime):
        factor = self.step / self.runtime
        return [round((end[x] - start[x]) * factor + start[x], 5) \
                for x in range(len(start))]

    def interpolate_leds(self, eventtime):
        reactor = self.printer.get_reactor()
        if self.printer.is_shutdown():
            return reactor.NEVER
        led_count = self.target.led_helper.led_count
        if self.current_state == [self.target_colors] * led_count:
            return reactor.NEVER
        now = reactor.monotonic()
        runtime = now - self.timestep
        self.timestep = now
        self.step = min(self.step + runtime, self.runtime)
        for index in range(led_count):
            self.current_state[index] = self.compute_color(self.current_state[index],
                                                           self.target_colors,
                                                           runtime)
            self.target.led_helper._set_color(index, self.current_state[index])
        self.target.led_helper._check_transmit()
        return reactor.monotonic() + INTERPOLATE_STEP_TIME

    def find_leds(self, name):
        try:
            module, name = name.split(maxsplit=1)
        except ValueError:
            module = None
        leds = [led for led in self.leds if led[0].endswith(name)]
        if len(leds) == 1:
            return leds[0][1]
        if module is None:
            return None
        leds = [led for led in leds if led[0] == f"{module} {name}"]
        if len(leds) != 1:
            return None
        return leds[0][1]
    
    cmd_LED_INTERPOLATE_help = "Smootly transition LEDs between two colors"
    def cmd_LED_INTERPOLATE(self, gcmd):
        target_name = gcmd.get("LED")
        self.target = self.find_leds(target_name)
        if self.target is None:
            gcmd.error(f"Could not find LED object '{target_name}'." + \
                       "only the name, try using the type as well, i.e. " + \
                       "'LED=\"neopixel <name>\"'")
            return
        
        self.target_colors = [
            gcmd.get_float("RED", 0., minval=0.0, maxval=1.0),
            gcmd.get_float("GREEN", 0., minval=0.0, maxval=1.0),
            gcmd.get_float("BLUE", 0., minval=0.0, maxval=1.0),
            gcmd.get_float("WHITE", 0., minval=0.0, maxval=1.0)]
        self.runtime = gcmd.get_float("DURATION", 1., minval=1.)

        self.current_state = self.target.get_status(0)["color_data"]
        self.step = 0
        reactor = self.printer.get_reactor()
        self.timestep = reactor.monotonic()
        self.timer = reactor.register_timer(self.interpolate_leds,
                                            reactor.NOW)

def load_config(config):
    return LedInterpolate(config)
