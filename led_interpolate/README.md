# LED Interpolation
A small extension that can be used to smootly transition (interpolate) RGB(W)
LEDs between colors.

While planning/working on adding LEDs to my printer case, I wanted to be able
to have the LEDs dim. However, rather than just setting the color and have the
dimming happen immediately, I thought it will be much nicer if they transition
smoothly.

The led_interpolate.py extension does that. It will smoothly transition a set
of LEDs from their current color/brightness to a given color/brightness.

## Setup

After installing the extention, add the following to your config file to enable
the `LED_INTERPOLATE` command:

```ini
[led_interpolate]
```

## Usage

```gcode
LED_INTERPOLATE LED=<config_name> RED=<value> GREEN=<value> BLUE=<value> [WHITE=<value>] [FACTOR=<value>]
```

The command will transition the LED `<config_name>` to the values specified by
`RED`, `GREEN`, `BLUE`, and `WHITE`. `WHITE` is optional and valid only for RGBW
LEDs. If the LEDs are chained, the entire chain will be transitioned. `FACTOR`
can be used to alter the amount by which each step in the transition will change
 the current color.

## Known Issues

* The algorithm is not perfect when it comes to interpolating a chain of LEDs
  which have different starting values. It does its best to get all LEDs in the
  chain to arrive at the desired color at the same time but it's not perfect.
* While the extension manipulates the LEDs Klipper objects directly, bypassing
  any GCode, it may still interfere with normal command processing if the LEDs
  are connected to the MCU controlling the printing operations.

