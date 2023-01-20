# Run a shell command via gcode
#
# Copyright (C) 2019  Eric Callahan <arksine.code@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import os
import shlex
import subprocess
import logging
import ast


class ShellCommand:
    def __init__(self, config):
        self.name = config.get_name().split()[-1]
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        gcode_macro = self.printer.lookup_object('gcode_macro')
        cmd = config.get('command')
        cmd = os.path.expanduser(cmd)
        self.command = shlex.split(cmd)
        self.timeout = config.getfloat('timeout', 2., above=0.)
        self.verbose = config.getboolean('verbose', False)
        self.on_success_template = self.on_failure_template = None
        if config.get("success", None) is not None:
            self.on_success_template = gcode_macro.load_template(
                config, 'success', '')
        if config.get("failure", None) is not None:
            self.on_failure_template = gcode_macro.load_template(
                config, 'failure', '')
        self.proc_fd = None
        self.partial_output = ""
        self.values = {}
        prefix = 'value_'
        for option in config.get_prefix_options(prefix):
            try:
                self.values[option[len(prefix):]] = \
                    ast.literal_eval(config.get(option))
            except ValueError as e:
                raise config.error(
                    "Option '%s' in section '%s' is not a valid literal" % (
                        option, config.get_name()))
        self.output_var_values = {}
        self.gcode.register_mux_command(
            "RUN_SHELL_COMMAND", "CMD", self.name,
            self.cmd_RUN_SHELL_COMMAND,
            desc=self.cmd_RUN_SHELL_COMMAND_help)

    def _process_output(self, eventime):
        if self.proc_fd is None:
            return
        try:
            data = os.read(self.proc_fd, 4096)
        except Exception:
            pass
        data = self.partial_output + data.decode()
        if '\n' not in data:
            self.partial_output = data
            return
        elif data[-1] != '\n':
            split = data.rfind('\n') + 1
            self.partial_output = data[split:]
            data = data[:split]
        else:
            self.partial_output = ""
        prefix = "VALUE_UPDATE:"
        for line in [x.strip() for x in data.split("\n")]:
            if line and line.startswith(prefix):
                var, value = line[len(prefix):].split("=")
                if var in self.values:
                    self.values[var] = value
        if self.verbose:
            self.gcode.respond_info(data)

    cmd_RUN_SHELL_COMMAND_help = "Run a linux shell command"

    def cmd_RUN_SHELL_COMMAND(self, params):
        gcode_params = params.get('PARAMS', '')
        gcode_params = shlex.split(gcode_params)
        reactor = self.printer.get_reactor()
        try:
            logging.info("%s", self.command + gcode_params)
            proc = subprocess.Popen(
                self.command + gcode_params, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except Exception:
            logging.exception(
                "shell_command: Command {%s} failed" % (self.name))
            raise self.gcode.error("Error running command {%s}" % (self.name))
        self.proc_fd = proc.stdout.fileno()
        hdl = reactor.register_fd(self.proc_fd, self._process_output)
        if self.verbose:
            self.gcode.respond_info("Running Command {%s}...:" % (self.name))
        eventtime = reactor.monotonic()
        endtime = eventtime + self.timeout
        complete = False
        while eventtime < endtime:
            eventtime = reactor.pause(eventtime + .05)
            if proc.poll() is not None:
                complete = True
                break
        if not complete:
            proc.terminate()
        status = proc.wait()
        if self.verbose:
            if self.partial_output:
                self.gcode.respond_info(self.partial_output)
                self.partial_output = ""
        reactor.unregister_fd(hdl)
        self.proc_fd = None
        kwparams = dict(self.values)
        if status == 0 and self.on_success_template:
            kwparams.update(self.on_success_template.create_template_context())
            self.on_success_template.run_gcode_from_command(kwparams)
        elif self.on_failure_template:
            kwparams.update(self.on_failure_template.create_template_context())
            self.on_failure_template.run_gcode_from_command(kwparams)
        if self.verbose:
            if complete:
                msg = "Command {%s} finished\n" % (self.name)
            else:
                msg = "Command {%s} timed out" % (self.name)
            self.gcode.respond_info(msg)


def load_config_prefix(config):
    return ShellCommand(config)
