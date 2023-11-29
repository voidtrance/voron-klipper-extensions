import logging
from extras.gcode_macro import GCodeMacro

def log(fmt, *args):
    logging.info("loop_macro: " + fmt % args)

class LoopMacro(GCodeMacro):
    def __init__(self, config):
        name = config.get_name().split()[1]
        self.log = lambda fmt, *args: log(f"[{name}]: " + fmt, *args)
        GCodeMacro.__init__(self, config)
        self.gcode = self.printer.lookup_object("gcode")
        macro_obj = self.printer.load_object(config, 'gcode_macro')
        self.entry_template = macro_obj.load_template(config, 'entry', '')
        self.exit_template = macro_obj.load_template(config, 'exit', '')
        self.iteration_limit = config.getint("iteration_limit", 0)

    def _create_context(self, gcmd, template):
        context = dict(self.variables)
        context.update(template.create_template_context())
        context['params'] = gcmd.get_command_parameters()
        context['rawparams'] = gcmd.get_raw_command_parameters()
        return context

    def cmd(self, gcmd):
        if self.printer.is_shutdown():
            return
        
        limit = gcmd.get_int("LIMIT", None)
        if limit is None:
            limit = self.iteration_limit

        # LIMIT is a special argument that is provided by the
        # implementation. So, reach into the GCode command
        # parameters and remove it.
        gcmd._params.pop("LIMIT", None)
        parts = gcmd._commandline.split()
        parts = [x for x in parts if not x.startswith("LIMIT")]
        gcmd._commandline = " ".join(parts)

        self.variables["iter"] = 0
        self.variables["limit"] = limit

        context = self._create_context(gcmd, self.entry_template)
        self.entry_template.run_gcode_from_command(context)

        stop_execution = False
        while not self.printer.is_shutdown() and \
            not stop_execution:
            context = self._create_context(gcmd, self.template)
            script = self.template.render(context)
            for gcode in script.split("\n"):
                self.log("Running GCode: '%s'", gcode)
                if gcode.lower() in ('continue', 'break'):
                    if gcode.lower() == 'break':
                        stop_execution = True
                    break
                self.gcode.run_script_from_command(gcode)
            self.variables["iter"] += 1
            if limit > 0 and self.variables["iter"] >= limit:
                break

        context = self._create_context(gcmd, self.exit_template)
        self.exit_template.run_gcode_from_command(context)


def load_config_prefix(config):
    return LoopMacro(config)
