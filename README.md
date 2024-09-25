# voron-klipper-extensions
A set of Klipper extensions designed to improve operation of Voron printers.

## Available Extensions
The repository provide the following Klipper extensions:

| Name | Description |
|-|-|
| [gcode_shell_command](/gcode_shell_command) | Execute shell commands from GCode |
| [led_interpolate](/led_interpolate) | Smootly transition LEDS between colors |
| [loop_macro](/loop_macro) | Looping G-Code macro variant |
| [settling_probe](/settling_probe) | Execute a "settling" probe sample to settle the gantry |
| [state_notify](/state_notify) | Improved printer state notifications |
| [temp_tracker](/temp_tracker) | Average temperature tracking |

## Setup and Removal
### Installation
1. Login to your RaspberryPi.
2. Clone this repository:
```sh
git clone https://github.com/voidtrance/voron-klipper-extensions.git
```
3. Change directory to the new cloned repository:
```sh
cd voron-klipper-extensions
```
4. Run the install script:
```sh
./install-extensions.sh
```
5. Add the following section to `moonraker.conf`:
```ini
[update_manager voron-klipper-extensions]
type: git_repo
path: ~/voron-klipper-extensions
origin: https://github.com/voidtrance/voron-klipper-extensions.git
install_script: install-extensions.sh
managed_services: klipper
```

### Removal
1. Login to your RaspberryPi.
2. Change directory to the repository:
```sh
cd voron-klipper-extensions
```
3. Run the uninstall script:
```sh
./install-extensions.sh -u
```
4. (Optional) Remove the repository:
```sh
cd ..
rm -rf voron-klipper-extensions
```
5. (Optional) If you have removed the repository in step 4, you'll have to
remove the Moonraker update manager setup as well. Edit `moonraker.conf` and
remove the `[update_manager voron-klipper-exteions]` section.


## Contributing
If you'd like to contribute, please submit a pull request with your suggested
changes. When submitting changes, please follow the [coding style](coding-style.md).
