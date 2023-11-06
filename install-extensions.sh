#!/bin/bash

# Force script to exit if an error occurs
set -e

KLIPPER_PATH="${HOME}/klipper"
SYSTEMDDIR="/etc/systemd/system"
EXTENSION_LIST="gcode_shell_command.py settling_probe.py led_interpolate.py state_notify.py"
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

# Step 2: Check if the extensions are already present.
# This is a way to check if this is the initial installation.
function check_existing() {
    local -i existing=0
    for extension in ${EXTENSION_LIST}; do
        [ -e "${KLIPPER_PATH}/klippy/extras/${extension}" ] && existing=1 || existing=0
        [ ${existing} -eq 0 ] && break
    done
    echo ${existing}
}

# Step 3: Link extension to Klipper
function link_extensions() {
    echo "Linking extensions to Klipper..."
    for extension in ${EXTENSION_LIST}; do
        ln -sf "${SRCDIR}/${extension}" "${KLIPPER_PATH}/klippy/extras/${extension}"
    done
}

function unlink_extensions() {
    echo "Unlinking extensions from Klipper..."
    for extension in ${EXTENSION_LIST}; do
        rm -f "${KLIPPER_PATH}/klippy/extras/${extension}"
    done
}

# Step 4: Restart Klipper
function restart_klipper() {
    echo "Restarting Klipper..."
    sudo systemctl restart klipper
}

function verify_ready() {
    if [ "$(id -u)" -eq 0 ]; then
        echo "This script must not run as root"
        exit -1
    fi
}

do_uninstall=0

while getopts "k:u" arg; do
    case ${arg} in
        k) KLIPPER_PATH=${OPTARG} ;;
        u) do_uninstall=1 ;;
    esac
done

verify_ready
existing=$(check_existing)
if [ ${existing} -eq 0 ]; then
    link_extensions
else
    if [ ${do_uninstall} -eq 1 ]; then
        unlink_extensions
    fi
fi
restart_klipper
exit 0
