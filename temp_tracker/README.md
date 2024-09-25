# Average Temperature Tracker
This extension provides average temperature tracking for temperature sensors.
The main motivation for it is to be able to skip heat-soaking the enclosure if
the average temperature for some pre-defined period is above a certina value.

There are two main use cases where this extension can help by saving time:

1. If the printer chamber has been pre-heated and pre-soaked before any prints
are started.
2. If a previous print has pre-heated and pre-soaked the chamber.

In both of the above cases, the average chamber temperature could be queried in
the `PRINT_START` macro and if above a certain value, the heat-soaking could be
skipped.

## Configuration and Usage
The extension has the following configuration settings:

```ini
[temp_tracker <name>]
#sensor: <temp sensor>
#     The temperature sensor to monitor. This setting is required.
#period: <seconds>
#     The time period over which to track temperatures. This setting
#     is required.
#range_min: <temp>
#     The minimum temperature which to track. Temperature readings
#     below this value are ignored.
#range_max: <temp>
#     The maximum temperature which to track. Temperature readings
#     above this value are ignored.
```

The extension provides the average through the `printer` status state:
* `printer["temp_tracker <name>"].average` provides the average temperature
over the defined period.
* `printer["temp_tracker <name>"].period` provides the defined period.

The extension also adds the following two commands:
* `TEMP_TRACKER_GET TRACKER=<name> [PERIOD=<secs]` shows the average tracker
temperature. The optional `PERIOD` argument can be used to limit the time
period to `<sec>` seconds. `<secs>` has to be less than or equal to the time
period specified in the tracker's configuration.

As described above, the primary use of this extension is to be able to add a
"smart" heat-soak. Below is an example of this:

```gcode
[temp_tracker chamber]
sensor: chamber_temp
period: 300

[gcode_macro PRINT_START]
gcode:
    ...
    {% if printer["temp_tracker chamber].average < 50.0 %}
        HEAT_SOAK_CHAMBER
    {% endif %}
    ...
```
