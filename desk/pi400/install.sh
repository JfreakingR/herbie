#!/bin/sh
# Make this Pi 400 Herbie's desk body: his face fullscreen on the 7" LCD at
# every boot, his brain on the Galaxy over USB. Run as your normal user from
# inside the herbie checkout:   sh desk/pi400/install.sh
#
# Before running, copy two things over from the Windows PC (USB stick is fine):
#   C:\Users\<you>\.herbie\api-token      -> ~/.herbie/api-token
#   C:\Users\<you>\.android\adbkey        -> ~/.android/adbkey
#   C:\Users\<you>\.android\adbkey.pub    -> ~/.android/adbkey.pub
# The adb key matters: the Galaxy already trusts the PC's key, and approving a
# new one needs a tap on the phone's screen.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
VOICE="${HERBIE_VOICE:-galaxy}"

say() { printf '\n== %s\n' "$*"; }
warn() { printf '!! %s\n' "$*" >&2; }

say "Installing adb, Chromium and Python"
sudo apt-get update -qq
sudo apt-get install -y adb python3
if ! command -v chromium >/dev/null 2>&1 && ! command -v chromium-browser >/dev/null 2>&1; then
    sudo apt-get install -y chromium || sudo apt-get install -y chromium-browser
fi
# The adb package's udev rules give the plugdev group access to the phone.
sudo usermod -aG plugdev "$USER"

say "Checking the files copied from the PC"
missing=0
if [ -s "$HOME/.herbie/api-token" ]; then
    chmod 700 "$HOME/.herbie"; chmod 600 "$HOME/.herbie/api-token"
    echo "brain token: present"
else
    warn "missing ~/.herbie/api-token (copy it from the PC; see the top of this script)"
    missing=1
fi
if [ -s "$HOME/.android/adbkey" ]; then
    chmod 700 "$HOME/.android"; chmod 600 "$HOME/.android/adbkey"
    echo "adb key: present"
else
    warn "missing ~/.android/adbkey (copy it and adbkey.pub from the PC)"
    missing=1
fi

say "Starting Herbie's desk server at boot (voice: $VOICE)"
mkdir -p "$HOME/.config/systemd/user"
cat >"$HOME/.config/systemd/user/herbie-desk.service" <<EOF
[Unit]
Description=Herbie desk face server (brain on the Galaxy)

[Service]
ExecStart=/usr/bin/python3 $REPO/desk/herbie_desk.py --voice $VOICE
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable herbie-desk.service
systemctl --user restart herbie-desk.service
sudo loginctl enable-linger "$USER"

say "Opening his face fullscreen when the desktop starts"
chmod +x "$HERE/herbie-face-kiosk.sh"
mkdir -p "$HOME/.config/autostart"
cat >"$HOME/.config/autostart/herbie-face.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Herbie's face
Exec=$HERE/herbie-face-kiosk.sh
X-GNOME-Autostart-enabled=true
EOF

say "Keeping the screen awake"
if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_blanking 1 || warn "could not turn off screen blanking"
    sudo raspi-config nonint do_boot_behaviour B4 || warn "could not set desktop autologin"
fi

say "Done"
if [ "$missing" -eq 1 ]; then
    warn "Copy the missing files above, then: systemctl --user restart herbie-desk"
fi
echo "Reboot to see him come up on his own:  sudo reboot"
echo "Logs:  journalctl --user -u herbie-desk -f      Face now:  $HERE/herbie-face-kiosk.sh"
