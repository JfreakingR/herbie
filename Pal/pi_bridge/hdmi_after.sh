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
echo ---fbinfo---
if [ -e /sys/class/graphics/fb0 ]; then
  echo name=$(cat /sys/class/graphics/fb0/name 2>/dev/null)
  echo virt=$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null)
  echo bits=$(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null)
  echo state=$(cat /sys/class/graphics/fb0/state 2>/dev/null)
fi
echo ---cmdline---
cat /proc/cmdline
echo ---dmesg hdmi---
dmesg | grep -iE 'hdmi|fb0|simple-framebuffer|crtc' | tail -25
echo ---face---
python3 -c "import urllib.request,json; print(json.loads(urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=2).read()))"
