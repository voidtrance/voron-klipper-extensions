# Custom Z-Probe object that allow for a single settling probe
# prior to sampling.
#
# Copyright (C) 2023 Mitko Haralanov <voidtrance@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import probe
import pins


class SettlingProbe(probe.PrinterProbe):
    def __init__(self, config):
        self.printer = config.get_printer()
        probe_config = config.getsection('probe')
        probe_obj = self.printer.lookup_object('probe')

        if probe_obj:
            mcu_probe = probe_obj.mcu_probe
        else:
            mcu_probe = probe.ProbeEndstopWrapper(config)

        # Unregister any pre-existing probe commands first.
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('PROBE', None)
        gcode.register_command('QUERY_PROBE', None)
        gcode.register_command('PROBE_CALIBRATE', None)
        gcode.register_command('PROBE_ACCURACY', None)
        gcode.register_command('Z_OFFSET_APPLY_PROBE', None)

        pins = self.printer.lookup_object('pins')
        if 'probe' in pins.chips:
            pins.chips.pop('probe')
            pins.pin_resolvers.pop('probe')

        probe.PrinterProbe.__init__(self, probe_config, mcu_probe)
        self.settling_sample = config.getboolean('settling_sample', False)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)

    def handle_ready(self):
        # This is the hacky bit:
        # The "klippy:ready" event is sent after all configuration has been
        # read and all object created. So, we are sure that the 'probe'
        # object already exists.
        # So, we can reach into the printer object and replace the existing 'probe'
        # object with this one.
        probe_obj = self.printer.objects.pop('probe', None)
        self.printer.objects['probe'] = self
        del probe_obj

    def _run_settling_probe(self, gcmd):
        gcmd.respond_info("Settling sample (ignored)...")
        speed = gcmd.get_float("PROBE_SPEED", self.speed, above=0.)
        lift_speed = self.get_lift_speed(gcmd)
        sample_retract_dist = gcmd.get_float("SAMPLE_RETRACT_DIST",
                                             self.sample_retract_dist, minval=0.)
        pos = self._probe(speed)
        pos[2] += sample_retract_dist
        self._move(pos, lift_speed)

    def run_probe(self, gcmd):
        if self.settling_sample:
            self._run_settling_probe(gcmd)
        return probe.PrinterProbe.run_probe(self, gcmd)

    def cmd_PROBE(self, gcmd):
        settling_sample = gcmd.get_int("SETTLING_SAMPLE", self.settling_sample)
        global_settling_sample = self.settling_sample
        self.settling_sample = settling_sample
        ret = probe.PrinterProbe.cmd_PROBE(self, gcmd)
        self.settling_sample = global_settling_sample
        return ret

    def cmd_PROBE_ACCURACY(self, gcmd):
        settling_sample = gcmd.get_int("SETTLING_SAMPLE", self.settling_sample)
        if settling_sample:
            self._run_settling_probe(gcmd)
        return probe.PrinterProbe.cmd_PROBE_ACCURACY(self, gcmd)

    def cmd_PROBE_CALIBRATE(self, gcmd):
        settling_sample = gcmd.get_int("SETTLING_SAMPLE", self.settling_sample)
        global_settling_sample = self.settling_sample
        self.settling_sample = settling_sample
        ret = probe.PrinterProbe.cmd_PROBE_CALIBRATE(self, gcmd)
        self.settling_sample = global_settling_sample
        return ret


def load_config(config):
    return SettlingProbe(config)
