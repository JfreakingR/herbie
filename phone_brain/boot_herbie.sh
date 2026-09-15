#!/data/data/com.termux/files/usr/bin/bash
# Installed to ~/.termux/boot/boot_herbie.sh by install_pal_brain.sh.
#
# The Termux:Boot addon runs everything in ~/.termux/boot/ after the phone
# starts. Without the addon installed this file is inert and Herbie's brain
# must be started by hand after every reboot.
set -u
exec "$HOME/pal-phone-brain/herbie_supervisor.sh"
