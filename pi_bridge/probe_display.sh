#!/bin/sh
set -eu
echo "HOST=$(hostname)"
echo "UNAME=$(uname -a)"
echo "USER=$(id)"
echo "---env---"
echo "DISPLAY=${DISPLAY-}"
echo "WAYLAND=${WAYLAND_DISPLAY-}"
echo "XDG=${XDG_SESSION_TYPE-}"
echo "---fb---"
ls -l /dev/fb* 2>/dev/null || echo "no framebuffer nodes"
echo "---drm---"
if [ -d /sys/class/drm ]; then
  for c in /sys/class/drm/card*; do
    [ -e "$c/status" ] || continue
    echo "$c status=$(cat "$c/status" 2>/dev/null) enabled=$(cat "$c/enabled" 2>/dev/null)"
    if [ -f "$c/modes" ]; then
      echo "  modes=$(tr '\n' ' ' < "$c/modes")"
    fi
  done
else
  echo "no drm class"
fi
echo "---config---"
if [ -f /boot/firmware/config.txt ]; then
  grep -vE '^#|^$' /boot/firmware/config.txt || true
elif [ -f /boot/config.txt ]; then
  grep -vE '^#|^$' /boot/config.txt || true
fi
echo "---gui---"
systemctl is-active lightdm 2>/dev/null || true
systemctl is-active gdm3 2>/dev/null || true
systemctl is-active graphical.target 2>/dev/null || true
who || true
echo "---bins---"
command -v chromium-browser || true
command -v chromium || true
command -v midori || true
command -v firefox-esr || true
command -v python3 || true
command -v unclutter || true
command -v xinit || true
command -v startx || true
command -v weston || true
command -v wlr-randr || true
echo "---dmesg display---"
dmesg 2>/dev/null | grep -iE 'hdmi|dsi|panel|fb[0-9]|waveshare|tft|ili9|ads784|vc4' | tail -40 || true
echo "---spi i2c---"
ls /dev/spidev* /dev/i2c-* 2>/dev/null || echo "no spi/i2c nodes"
echo "---modules---"
lsmod | grep -iE 'fb_|spi|i2c|vc4|drm|ili|fbtft|ads784' || true
echo "---mem---"
free -h
echo "---os---"
cat /etc/os-release
