#!/bin/bash

# Force script to exit if an error occurs
set -e

KLIPPER_PATH="${HOME}/klipper"
SYSTEMDDIR="/etc/systemd/system"
EXTENSION_LIST="gcode_shell_command.py settling_probe.py"
SRCDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"

# Step 1:  Verify Klipper has been installed
function check_klipper() {
    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F "klipper.service")" ]; then
        echo "Klipper service found!"
    else
        echo "Klipper service not found, please install Klipper first"
        exit -1
    fi
}

# Step 2: Link gcode_shell_command.py file to Klipper
function link_gcode_shell_command_extension()
{
    echo "Linking extension to Klipper..."
    ln -sf "${SRCDIR}/gcode_shell_command.py" "${KLIPPER_PATH}/klippy/extras/gcode_shell_command.py"
}

# Step 2: Link settling_probe.py file to Klipper
function link_settling_probe_command_extension()
{
    echo "Linking extension to Klipper..."
    ln -sf "${SRCDIR}/settling_probe.py" "${KLIPPER_PATH}/klippy/extras/settling_probe.py"
}

### Step 2: Link extension to Klipper
##function link_extension() {
##    echo "Linking extensions to Klipper..."
##    for extension in ${EXTENSION_LIST}; do
##        ln -sf "${SRCDIR}/${extensions}" "${KLIPPER_PATH}/klippy/extras/${extension}"
##    done
##}

# Step 3: restarting Klipper
function restart_klipper()
{
    echo "Restarting Klipper..."
    sudo systemctl restart klipper
}

function verify_ready() {
    if [ "$(id -u)" -eq 0 ]; then
        echo "This script must not run as root"
        exit -1
    fi
}

while getopts "k:" arg; do
    case ${arg} in
        k) KLIPPER_PATH=${OPTARG} ;;
    esac
done

verify_ready
#link_extension
link_gcode_shell_command_extension
link_settling_probe_command_extension
restart_klipper