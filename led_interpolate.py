# Smoothly transition RGB LEDs between two colors
#
# Copyright (C) 2022 Mitko Haralanov <voidtrance@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

FRAME_RATE = 24
INTERPOLATE_STEP_TIME = 1.0 / FRAME_RATE


class LedInterpolate:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.led = self.printer.load_object(config, 'led')
        self.gcode.register_command("LED_INTERPOLATE",
                                    self.cmd_LED_INTERPOLATE, False,
                                    desc=self.cmd_LED_INTERPOLATE_help)

    def compute_color(self, start, end, factor):
        return round(((end - start) * factor) + start, 5)

    cmd_LED_INTERPOLATE_help = "Smootly transition LEDs between two colors"

    def _interpolate_leds(self, eventtime):
        all_done = False
        reactor = self.printer.get_reactor()
        led_count = self.led_helper.get_led_count()
        for index in range(led_count):
            current_state = [round(c * 255)
                             for c in self.led_helper.led_state[index]]

            if current_state == self.interpolation_params[0]:
                all_done = True
                continue

            target_colors, factor = self.interpolation_params
            colors = self.current_colors[index]
            red = self.compute_color(colors[0], target_colors[0], factor)
            green = self.compute_color(colors[1], target_colors[1], factor)
            blue = self.compute_color(colors[2], target_colors[2], factor)
            white = self.compute_color(colors[3], target_colors[3], factor)

            self.led_helper.set_color(index,
                                      (round(red / 255, 2),
                                       round(green / 255, 2),
                                       round(blue / 255, 2),
                                       round(white / 255, 2)))
            self.current_colors[index] = [red, green, blue, white]
            all_done = False
        self.led_helper.check_transmit(None)
        if all_done or self.printer.is_shutdown():
            return reactor.NEVER
        return reactor.monotonic() + INTERPOLATE_STEP_TIME

    def cmd_LED_INTERPOLATE(self, gcmd):
        target_name = gcmd.get("LED")
        target_colors = [
            round(gcmd.get_float("RED", 0., minval=0.0, maxval=1.0) * 255),
            round(gcmd.get_float("GREEN", 0., minval=0.0, maxval=1.0) * 255),
            round(gcmd.get_float("BLUE", 0., minval=0.0, maxval=1.0) * 255),
            round(gcmd.get_float("WHITE", 0., minval=0.0, maxval=1.0) * 255)]
        runtime = gcmd.get_float("DURATION", 0.)

        factor = (100 / (runtime / INTERPOLATE_STEP_TIME)) / 100
        if target_name not in self.led.led_helpers:
            raise gcmd.error("Unknown LED object '%s'" % target_name)

        self.led_helper = self.led.led_helpers[target_name]
        self.interpolation_params = (target_colors, factor)
        self.current_colors = [[round(c * 255, 2) for c in led]
                               for led in self.led_helper.led_state]
        reactor = self.printer.get_reactor()
        self.timer = reactor.register_timer(self._interpolate_leds,
                                            reactor.NOW)


def load_config(config):
    return LedInterpolate(config)
