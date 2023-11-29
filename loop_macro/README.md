# Looping Macros
Looping macros are a special variation of GCode macros that can loop
their execution until a certain condition has been met. In every loop
iteration, the body of the macro is re-evaluated allowing the macro
to make use of up-to-date printer state.

Loop macros enable the building of `while(not <condition>) do ... end`
style macros, which can loop for a non-pre-determined number of
iterations. This is possible because the loop body template gets
re-evaluated at the beginning of each loop iteration. Compare that to
the existing `{% for i in range(N) %} ... {% endfor %}` construct. The
number of loop iterations are pre-computed at the first time the macro
is evaluated. Based on that the loop body G-Code is repeated `N` number
of times. If more iterations are required, the macro has to be called
again.

Loop macros are very similar to what can be done with delayed G-Code.
However, unlike delayed G-Code, which executes in the background and
allows for other G-Code commands to execute, loop macros execute in
the foreground. Therefore, they block any other G-Code from executing,
including delayed G-Code. This is due to the fact that loop macros
hold the G-Code execution lock while running, which prevents all other
G-Code from executing.

## Configuration
The `loop_macro` extension enables a new section (`[loop_macro MACRO_NAME]`)
with the following configuration:

```ini
[loop_macro my_cmd]
#entry:
#   A list of G-Code commands to execute prior to the the looping
#   G-Code commands in the `gcode` section. These commands can be
#   used for any setup needed for the main loop body commands. See
#   docs/Command_Templates.md for G-Code format.
#gcode:
#   A list of G-Code commands to execute as the loop's body. These
#   commands will continue to be executed until the special 'BREAK'
#   command is encountered. This section als supports the 'CONTINUE'
#   special command that will jump to the next loop iteration. See
#   docs/Command_Templates.md for G-Code format. This parameter must
#   be provided.
#exit:
#   A list of G-Code commands to execute after the completion of the
#   looping commands in `gcode`. See docs/Command_Templates.md for
#   G-Code format.
#iteration_limit:
#   The maximum number of time the macro will execute. This can be
#   used in order to avoid infinite loops. If the macro reaches this
#   number of iterations without hiting a termination point, it will
#   stop execution. Default is 0 (no limit).
#variable_<name>:
#   One may specify any number of options with a "variable_" prefix.
#   The given variable name will be assigned the given value (parsed
#   as a Python literal) and will be available during macro expansion.
#   For example, a config with "variable_fan_speed = 75" might have
#   gcode commands containing "M106 S{ fan_speed * 255 }". Variables
#   can be changed at run-time using the SET_GCODE_VARIABLE command
#   (see docs/Command_Templates.md for details). Variable names may
#   not use upper case characters.
#rename_existing:
#   This option will cause the macro to override an existing G-Code
#   command and provide the previous definition of the command via the
#   name provided here. This can be used to override builtin G-Code
#   commands. Care should be taken when overriding commands as it can
#   cause complex and unexpected results. The default is to not
#   override an existing G-Code command.
#description: G-Code macro
#   This will add a short description used at the HELP command or while
#   using the auto completion feature. Default "G-Code macro"
```

Each of the GCode templates (`entry`, `gcode`, and `exit`) can make use of
the following variables, which are defined by the loop macro, itself:

| Variable | Description |
| :- | :- |
| `iter` | The current iteration count. |
| `limit` | The maximum iteration limit. |

In addition, the `gcode` template supports two special commands - `CONTINUE`
and `BREAK`:

* `CONTINUE` stops the execution of the current loop interation and jumps to
the next iteration.
* `BREAK` terminates the entire loop.

## Usage
Loop macros are used just like any other GCode macro defined with the
`gcode_macro` section.

In addition to the normal macro parameters supported by GCode macros, loop
macros also accept the `LIMIT` parameter, which can be used to change the
maximum iteration count. Note that the `LIMIT` parameter is not available
in the `params` object like other macro parameters as it is handled internally. Instead, the value can be obtained through the `limit` variable provided by `loop_macro`.

> [!note]
> In order to prevent infinite loops, a `LIMIT` value of `0` is ignored.

## Examples
The following is a simple example that prints a message to the console
until the `count` variable reaches the value 5:

```ini
[loop_macro MSG_LOOP]
variable_count: 0
gcode:
    {% if count < 5 %}
        RESPOND MSG="Count is {count}"
    {% else %}
        BREAK
    {% endif %}
    SET_GCODE_VARIABLE MACRO=MSG_LOOP VARIABLE=count VALUE={count + 1}
```

The above example will produce the output on the console:

```
echo: Count is 0
echo: Count is 1
echo: Count is 2
echo: Count is 4
```

As you can see, the `gcode` template gets re-evaluated on every loop
iteration, allowing each iteration to see the new value of the `count`
variable.

With loop macros, re-implementing `TEMPERATURE_WAIT` is very easy as
well:

```ini
[loop_macro MY_TEMPERATURE_WAIT]
variable_sensor_name: ""
entry:
    {% set sensor_name = params["SENSOR"] %}
    SET_GCODE_VARIABLE MACRO=MY_TEMPERATURE_WAIT VARIABLE=sensor_name VALUE="'{sensor_name}'"
gcode:
    {% set sensor = printer[sensor_name] %}
    {% if sensor.temperature >= params["MINIMUM"] %}
        BREAK
    {% endif %}
```

To demonstrate the use of the `CONTINUE` special command, the above
example can be changed to:

```ini
[loop_macro MY_TEMPERATURE_WAIT]
variable_sensor_name: ""
entry:
    {% set sensor_name = params["SENSOR"] %}
    SET_GCODE_VARIABLE MACRO=MY_TEMPERATURE_WAIT VARIABLE=sensor_name VALUE="'{sensor_name}'"
gcode:
    {% set sensor = printer[sensor_name] %}
    {% if sensor.temperature < params["MINIMUM"] %}
        CONTINUE
    {% endif %}
    BREAK
```

The example above is interesting in that when the sensor's temperature is less than the
specified minimum, the resulting set of G-Code commands is:

```ini
CONTINUE
BREAK
```

Both the `CONTINUE` and `BREAK` commands are in the set of G-Code commands that the macro
would execute. However, due to the `CONTINUE` command appearing first, the loop jumps to
the next iteration before the `BREAK` command is executed. When the sensor's temperature
becomes equal or greater than the minimum, the set of G-Code commands becomes

```ini
BREAK
```

and the loop macro terminates.

The next example show the use of the `LIMIT` parameter:
```ini
[loop_macro MY_LOOP_MACRO]
iteration_limit: 5
entry:
    RESPOND MSG="Iteration limit: {limit}"
gcode:
    RESPOND MSG="Current iteration: {iter} out of {limit}
```

If the above loop macro is called without the `LIMIT` parameter, it will execute
`iteration_limit` number of times, producing the following output:

```
echo: Iteration limit: 5
echo: Current iteration: 0 out of 5
echo: Current iteration: 1 out of 5
echo: Current iteration: 2 out of 5
echo: Current iteration: 3 out of 5
echo: Current iteration: 4 out of 5
```

However, if the same macro is executed with the command `MY_LOOP_MACRO LIMIT=7`, the
output changes to:

```
echo: Iteration limit: 7
echo: Current iteration: 0 out of 7
echo: Current iteration: 1 out of 7
echo: Current iteration: 2 out of 7
echo: Current iteration: 3 out of 7
echo: Current iteration: 4 out of 7
echo: Current iteration: 5 out of 7
echo: Current iteration: 6 out of 7
```

## WARNING!!!! WARNING!!!! WARNING!!!

> [!caution]
> **Care must be taken when using loop macros in order to avoid locking up Klipper!**

Due to the fact that loop macros take the G-Code execution lock and loop macros don't have
a built-in termination mechanism, it is possible (and easy) to write a macro that loops
forever.

A loop macro will only terminate if it encounters the `BREAK` command at some point
of its execution or its iteration limit is reached. What this means is that:
 * either a condition must exist under which the `BREAK` command will be executed, or
 * the loop macro must set a non-zero value for `iteration_limit` in its configuration.

A good example of this is the `MY_TEMPERATURE_WAIT` loop macro above. While the `BREAK`
special command does appear in the looping G-Code template, the processing will never
get there if the chamber temperature is not rising.

If an infinite loop macro is triggered, the only way to recover the system is by
**manually** restarting Klipper or rebooting the RaspberyPi. Attempting to do so through
the web UI will not work since that UI uses Moonraker to talk to Klipper. Since Klipper
is stuck executing the looping macro forever, it can never process the requests from
Moonraker.