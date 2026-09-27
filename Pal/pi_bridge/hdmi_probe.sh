#!/bin/sh
echo "HOST=$(hostname)"
echo "---lcd---"
vcgencmd get_lcd_info
echo "---display_power---"
vcgencmd display_power
echo "---drm---"
for s in /sys/class/drm/card*-*/status; do
  [ -f "$s" ] || continue
  echo "$s=$(cat "$s")"
  modes="$(dirname "$s")/modes"
  if [ -f "$modes" ]; then
    echo "  modes=$(tr '\n' ' ' < "$modes")"
  fi
done
echo "---cmdline---"
cat /proc/cmdline
echo "---config---"
if [ -f /boot/firmware/config.txt ]; then CFG=/boot/firmware/config.txt; else CFG=/boot/config.txt; fi
echo "CFG=$CFG"
grep -vE '^#|^$' "$CFG" || true
echo "---cmdline.txt---"
if [ -f /boot/firmware/cmdline.txt ]; then cat /boot/firmware/cmdline.txt; else cat /boot/cmdline.txt; fi
echo "---face---"
python3 -c "import urllib.request,json; print(json.loads(urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=2).read()))"
echo "---apt cog chromium---"
command -v cog || true
command -v chromium || true
command -v chromium-browser || true
dpkg -l cog chromium chromium-browser xserver-xorg 2>/dev/null | awk '/^ii/{print $2,$3}'
echo "---mem---"
free -m | head -2
