# voron-klipper-extensions
A set of Klipper extensions designed to improve operation of Voron printers.

## Available Extensions
### Settling Probe
For some currently unknown reason, Voron printers seem to suffer from an issue
where the first probing sample is off by some margin. Subsequent samples are
much closer (or the same) to each other. The current theory is that there is
some toolhead/axis settling on the first sample.

In order to avoid polluting the probe samples, the first sample should be
thrown away.

This extension adds support for performing a single, throw-away, settling
probe sample that is not part of the sample set used for calculating Z
positions.

The extension replaces the default `probe` Klipper object with the modified
one in order to allow all commands/operations that perform Z probing to
benefit from this.

To enable the module, add the following to your `printer.cfg` file:

```
[settling_probe]
#settling_sample:
#   Globally enable the throw-away settling sample. Default is 'False'.
#   Setting this to 'True' will enable the throw-away sample for all
#   commands/operations that perform Z probing (QUAD_GANTRY_LEVEL,
#   Z_TILT_ADJUST, BED_MESH_CALIBRATE, SCREWS_TILT_CALCULATE, etc.)
```

The module also augments the `PROBE`, `PROBE_ACCURACY`, and `PROBE_CALIBRATE`
commands with an extra parameter - `SETTLING_SAMPLE` - which can be used to
control whether the commands perform a settling sample independently of the
`settling_sample` setting in the `[settling_prob]` section.

#### Examples for Settling Probe

In your printer.cfg file add the `settling_probe` section:
```
[settling_probe]
settling_sample: True
```

Within the Mainsail/Fluidd UI console panel, you can perform any of the following commands:
```
PROBE
PROBE SETTLING_SAMPLE=0
PROBE SETTLING_SAMPLE=1

PROBE_ACCURACY
PROBE_ACCURACY SETTLING_SAMPLE=0
PROBE_ACCURACY SETTLING_SAMPLE=1

PROBE_CALIBRATE
PROBE_CALIBRATE SETTLING_SAMPLE=0
PROBE_CALIBRATE SETTLING_SAMPLE=1

QUAD_GANTRY_LEVEL
BED_MESH_CALIBRATE
```

The commands `QUAD_GANTRY_LEVEL` and `BED_MESH_CALIBRATE` will ignore the first sample if `settling_sample:` option is set to `True` in the `[settling_probe]` section.  If `settling_sample:` option is set to `False` then all the commands will use the DEFAULT Klipper behavior and include the first sample.

The following commands are not effected by `Settling_Probe` extension:
```gcode
PROBE_Z_ACCURACY
CALIBRATE_Z
```

---

### GCode Shell Command
The original extension is part of the Kiauh repo
(https://github.com/th33xitus/kiauh/blob/master/resources/gcode_shell_command.py).
I've modified it to add support for custom GCode execution on either success
or failure:

#### Usage
```
[gcode_shell_command COMMAND]
#value_<var>: <value>
#   Output value that can be updated by the command. <value>
#   serves as a default.
command:
#   The command line to be executed. This option is required.
#   The command can update the values for any of the value_*
#   variables above. In order to do so, the command should
#   output the update value in the following format:
#      VALUE_UPDATE:<var>=<value>
#   Only one value can be updated on a single line. The updated
#   values are processes as strings.
#timeout: 2.0
#   The amount of time (in seconds) to wait before forcefully
#   terminating the command.
#verbose: True
#   Enable verbose output to the console.
#success:
#   A list of G-Code commands to execute if the command
#   completes successfully. If this option is not present
#   nothing will be executed.
#   This section is evaluated as a template and can
#   reference the value_* values.
#failure:
#   A list of G-Code commands to execute if the command
#   does not complete successfully. If this option is not
#   present nothing will be executed.
#   This section is evaluated as a template and can
#   reference the value_* values.
```
#### Examples
```
[gcode_shell_command my_command]
command: echo my_command executing
success:
    M117 my_command executed successfully.
failure:
    M117 my_command failed.

[gcode_macro exec_my_command]
gcode:
    RUN_SHELL_COMMAND CMD=my_command
```

```
[gcode_shell_command my_command]
value_var1: 0
command: echo "VALUE_UPDATE:var1=10"
success:
    {action_respnd_info("var1=%s" % var1)}
```

## **Warning** **Infinite Loops**
>
> Since the G-Code executed on success/failure can be arbitrary, on top of
> all the other issues resulting from using external commands, it is now
> possible to create an infinite loop that will prevent the printer from
> continuing.
>
> For example, the following will cause an infinite loop:
>
> ```
> [gcode_shell_command my_command]
> command: echo my_command executing
> success:
>     exec_my_command
>
> [gcode_macro exec_my_command]
> gcode:
>     RUN_SHELL_COMMAND CMD=my_command
> ```

---

### How To Install Settling Probe and Gcode Shell Command Extensions

To install these extensions, you need to copy the `settling_probe.py` file and `gcode_shell_command.py` into the `extras` folder of klipper. Like:

```bash
/home/pi/klipper/klippy/extras/settling_probe.py
/home/pi/klipper/klippy/extras/gcode_shell_command.py
```

An alternative would be to clone this repo and run the `install-extensions.sh` script. Like:

```bash
cd /home/pi
git clone https://github.com/voidtrance/voron-klipper-extensions
./voron-klipper-extensions/install-extensions.sh
```

---

## Moonraker's Update Manager setting:

Add the following section to `moonraker.conf`:
```
[update_manager voron-klipper-extensions]
type: git_repo
path: ~/voron-klipper-extensions
origin: https://github.com/voidtrance/voron-klipper-extensions.git
install_script: install-extensions.sh
managed_services: klipper
```

## Contributing
If you'd like to contribute, please submit a pull request with your suggested
changes. When submitting changes, please follow the [coding style](coding-style.md).