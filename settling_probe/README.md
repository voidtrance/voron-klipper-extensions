# Settling Probe
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

To enable the module, add the following to your `printer.cfg` file right after
the `[probe]` section:

```ini
[settling_probe]
#settling_sample:
#   Globally enable the throw-away settling sample. Default is 'False'.
#   Setting this to 'True' will enable the throw-away sample for all
#   commands/operations that perform Z probing (QGL, Z tilt, Bed Mesh,
#   Screw Tilt, etc.)
```

The module also augments the `PROBE` and `PROBE_ACCURACY` commands with an
extra parameter - `SETTLING_SAMPLE` - which can be used to control whether
the commands perform a settling sample independently from the
`settling_sample` setting.
