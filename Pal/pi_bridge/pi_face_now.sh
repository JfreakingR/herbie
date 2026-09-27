#!/bin/sh
echo HOST=$(hostname)
echo LCD=$(vcgencmd get_lcd_info)
echo ---drm---
for s in /sys/class/drm/card*-*/status; do
  [ -f "$s" ] || continue
  echo "$s=$(cat "$s")"
  d=$(dirname "$s")
  [ -f "$d/enabled" ] && echo "  enabled=$(cat "$d/enabled")"
  [ -f "$d/modes" ] && echo "  modes=$(tr '\n' ' ' < "$d/modes")"
done
echo ---fb---
ls -l /dev/fb* 2>/dev/null || echo nofb
if [ -e /sys/class/graphics/fb0 ]; then
  echo name=$(cat /sys/class/graphics/fb0/name)
  echo virt=$(cat /sys/class/graphics/fb0/virtual_size)
  echo bits=$(cat /sys/class/graphics/fb0/bits_per_pixel)
fi
echo ---svc---
systemctl is-active pal-pi-bridge.service || true
systemctl is-active herbie-fb-face.service || true
systemctl --no-pager -l status herbie-fb-face.service | tail -25
echo ---proc---
ps aux | grep -E 'herbie_fb|pal_pi_bridge' | grep -v grep
echo ---journal---
journalctl -u herbie-fb-face.service -n 30 --no-pager
