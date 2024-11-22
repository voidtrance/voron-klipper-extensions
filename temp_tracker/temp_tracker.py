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
import math

class TempTracker:
    def __init__(self, config):
        self.name = config.get_name().split()[1]
        self.printer = config.get_printer()
        self.sensor_name = config.get("sensor")
        self.period = config.getint("period")
        self.range_min = config.getfloat("range_min", -1)
        self.range_max = config.getfloat("range_max", -1, above=self.range_min)
        # We can't use 'inf' in the default values above because
        # JSON doesn't support them and Moonraker crashes.
        if self.range_min == -1:
            self.range_min = float('-inf')
        if self.range_max == -1:
            self.range_max = float('inf')
        self.sensor = None
        self._data = []
        gcode = self.printer.lookup_object("gcode")
        gcode.register_mux_command("TEMP_TRACKER_GET", "TRACKER",
                                   self.name, self.query,
                                   desc="Get average tracker temperature")
        gcode.register_mux_command("TEMP_TRACKER_RESET", "TRACKER",
                                   self.name, self.reset,
                                   desc="Reset tracker data")
        self.printer.register_event_handler("klippy:ready", self._klippy_ready)
        self.printer.register_event_handler("klippy:shutdown", self._klippy_shutdown)
        
    def _klippy_ready(self):
        self.sensor = self.printer.lookup_object("temperature_sensor " + self.sensor_name)
        reactor = self.printer.get_reactor()
        eventtime = reactor.monotonic()
        self.tracker_timer = reactor.register_timer(self.tracker_track, eventtime + 1.)

    def _klippy_shutdown(self):
        reactor = self.printer.get_reactor()
        reactor.unregister_timer(self.tracker_timer)

    def tracker_track(self, eventtime):
        temp, target = self.sensor.get_temp(eventtime)
        if temp >= self.range_min and temp <= self.range_max:
            if len(self._data) >= self.period:
                self._data = self._data[1:]
            self._data.append(temp)
        return eventtime + 1.
    
    def _get_period(self, period=math.inf):
        return min(len(self._data) if self._data else 1, period)

    def _get_average(self, period=math.inf):
        period = self._get_period(period)
        return sum(self._data) / period
    
    def get_status(self, eventtime):
        return {"average" : self._get_average(),
                "period" : self.period}

    def query(self, gcmd):
        gcode = self.printer.lookup_object("gcode")
        secs = gcmd.get_int("PERIOD", default=self.period, minval=1, maxval=self.period)
        secs = self._get_period(secs)
        average = self._get_average(secs)
        gcode.respond_info("Average temp for the past %s seconds: %s" % \
                           (secs, average))

    def reset(self, gcmd):
        self._data.clear()

def load_config_prefix(config):
    return TempTracker(config)