#!/bin/sh
echo "HOST=$(hostname)"
echo "---lcd---"
vcgencmd get_lcd_info
echo "---drm---"
for s in /sys/class/drm/card*-*/status; do
  [ -f "$s" ] || continue
  echo "$s=$(cat "$s")"
  d=$(dirname "$s")
  [ -f "$d/enabled" ] && echo "  enabled=$(cat "$d/enabled")"
  [ -f "$d/modes" ] && echo "  modes=$(tr '\n' ' ' < "$d/modes")"
done
echo "---fb---"
ls -l /dev/fb* 2>/dev/null || echo "no fb"
echo "---face---"
python3 -c "import urllib.request,json; print(json.loads(urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=2).read()))"
echo "---bins---"
command -v cog; command -v chromium; command -v xinit; command -v python3
