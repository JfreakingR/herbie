#!/bin/sh
echo "---usb---"
lsusb || true
echo "---usb-tree---"
lsusb -t || true
echo "---video---"
ls -l /dev/video* /dev/dri/* 2>/dev/null || true
echo "---gpio overlays---"
vcgencmd get_config int 2>/dev/null | grep -iE 'spi|i2c|display|hdmi|dpi|lcd' || true
vcgencmd display_power 2>/dev/null || true
tvservice -s 2>/dev/null || true
echo "---hdmi detect---"
vcgencmd display_power 0 2>/dev/null || true
cat /sys/class/drm/card0-HDMI-A-1/status 2>/dev/null || true
cat /sys/class/drm/card0-HDMI-A-1/edid 2>/dev/null | wc -c
echo "---dt---"
ls /proc/device-tree/soc 2>/dev/null | grep -iE 'hdmi|dsi|spi|i2c|dpi|panel' || true
ls /proc/device-tree 2>/dev/null | grep -iE 'hdmi|dsi|panel|display' || true
echo "---cmdline---"
cat /proc/cmdline
echo "---connected cables guess---"
# GPIO header present?
ls /sys/class/gpio 2>/dev/null | head
echo "---apt display pkgs---"
dpkg -l | grep -iE 'chromium|xserver|lightdm|wayland|weston|unclutter|xinit' || true
echo "---home---"
ls -la /home/jfreakingr | head -40
echo "---pal---"
ls -la /home/jfreakingr/pal-pi-bridge 2>/dev/null || echo "no pal-pi-bridge dir"
systemctl is-active pal-pi-bridge.service 2>/dev/null || true
