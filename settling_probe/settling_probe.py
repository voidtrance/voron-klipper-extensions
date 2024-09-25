# Custom Z-Probe object that allow for a single settling probe
# prior to sampling.
#
# Copyright (C) 2023 Mitko Haralanov <voidtrance@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
from .probe import ProbeEndstopWrapper, PrinterProbe, ProbeOffsetsHelper, \
    ProbeCommandHelper, ProbeSessionHelper
import configparser
import logging

class SettlingProbeEndstopWrapper(ProbeEndstopWrapper):
    def __init__(self, config, mcu_endstop=None):
        self.printer = config.get_printer()
        self.position_endstop = config.getfloat('z_offset')
        self.stow_on_each_sample = config.getboolean(
            'deactivate_on_each_sample', True)
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.activate_gcode = gcode_macro.load_template(
            config, 'activate_gcode', '')
        self.deactivate_gcode = gcode_macro.load_template(
            config, 'deactivate_gcode', '')
        # Create an "endstop" object to handle the probe pin
        if not mcu_endstop:
            ppins = self.printer.lookup_object('pins')
            self.mcu_endstop = ppins.setup_pin('endstop', config.get('pin'))
        else:
            self.mcu_endstop = mcu_endstop
        # Wrappers
        self.get_mcu = self.mcu_endstop.get_mcu
        self.add_stepper = self.mcu_endstop.add_stepper
        self.get_steppers = self.mcu_endstop.get_steppers
        self.home_start = self.mcu_endstop.home_start
        self.home_wait = self.mcu_endstop.home_wait
        self.query_endstop = self.mcu_endstop.query_endstop
        # multi probes state
        self.multi = 'OFF'

class SettlingProbeCommandHelper(ProbeCommandHelper):
    def cmd_PROBE_ACCURACY(self, gcmd):
        settling_sample = gcmd.get_int("SETTLING_SAMPLE", self.probe.probe_session.settling_sample)
        # Turn off the probe sessions settling_sample setting. We'll handle it
        # ourselfs. Otherwise, the probe session will do a setlling sampel for
        # each accuracy sample, which is not what we want.
        session_setting = self.probe.probe_session.settling_sample
        self.probe.probe_session.settling_sample = False
        if settling_sample:
            self.probe.probe_session._run_settling_probe(gcmd)
        ret = ProbeCommandHelper.cmd_PROBE_ACCURACY(self, gcmd)
        self.probe.probe_session.settling_sample = session_setting
        return ret

class SettlingProbeSessionHelper(ProbeSessionHelper):
    def __init__(self, probe_config, config, mcu_probe):
        ProbeSessionHelper.__init__(self, probe_config, mcu_probe)
        self.settling_sample = config.getboolean('settling_sample', False)

    def _run_settling_probe(self, gcmd):
        toolhead = self.printer.lookup_object('toolhead')
        gcmd.respond_info("Settling sample (ignored)...")
        speed = gcmd.get_float("PROBE_SPEED", self.speed, above=0.)
        lift_speed = self.get_probe_params(gcmd)["lift_speed"]
        sample_retract_dist = gcmd.get_float("SAMPLE_RETRACT_DIST",
                                             self.sample_retract_dist, minval=0.)
        probexy = toolhead.get_position()[:2]
        pos = self._probe(speed)
        toolhead.manual_move(probexy + [pos[2] + sample_retract_dist], lift_speed)

    def run_probe(self, gcmd):
        settling_sample = gcmd.get_int("SETTLING_SAMPLE", self.settling_sample)
        logging.info("Settling sample: %s" % settling_sample)
        if settling_sample:
            self._run_settling_probe(gcmd)
        return ProbeSessionHelper.run_probe(self, gcmd)


class SettlingProbe(PrinterProbe):
    def __init__(self, config):
        self.printer = config.get_printer()
        probe_config = config.getsection('probe')

        try:
            probe_obj = self.printer.lookup_object('probe')
            mcu_probe = probe_obj.mcu_probe
        except configparser.Error:
            raise configparser.Error(
                "Section 'settling_probe' should appear after 'probe' section")

        # Unregister any pre-existing probe commands first.
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('PROBE', None)
        gcode.register_command('QUERY_PROBE', None)
        gcode.register_command('PROBE_CALIBRATE', None)
        gcode.register_command('PROBE_ACCURACY', None)
        gcode.register_command('Z_OFFSET_APPLY_PROBE', None)

        # Remove the already-registered 'probe' pin. It will be
        # replaced by this instance.
        pins = self.printer.lookup_object('pins')
        pins.chips.pop('probe')
        pins.pin_resolvers.pop('probe')

        self.printer = config.get_printer()
        self.mcu_probe = SettlingProbeEndstopWrapper(probe_config, mcu_probe)
        self.cmd_helper = SettlingProbeCommandHelper(probe_config, self,
                                                     self.mcu_probe.query_endstop)
        self.probe_offsets = ProbeOffsetsHelper(probe_config)
        self.probe_session = SettlingProbeSessionHelper(probe_config, config, self.mcu_probe)
        self.printer.register_event_handler("klippy:mcu_identify", self.handle_mcu_identify)

    def handle_mcu_identify(self):
        # This is the hacky bit:
        # The "klippy:ready" event is sent after all configuration has been
        # read and all object created. So, we are sure that the 'probe'
        # object already exists.
        # So, we can reach into the printer object and replace the existing 'probe'
        # object with this one.
        probe_obj = self.printer.objects.pop('probe', None)
        self.printer.objects['probe'] = self
        del probe_obj

def load_config(config):
    return SettlingProbe(config)
