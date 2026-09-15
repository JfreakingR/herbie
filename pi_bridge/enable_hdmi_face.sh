#!/bin/sh
# Force Melba's HDMI connector on and prepare the BMO face kiosk.
# Does not touch motors. Idempotent.
set -eu

CFG=/boot/firmware/config.txt
CMD=/boot/firmware/cmdline.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
[ -f "$CMD" ] || CMD=/boot/cmdline.txt

sudo cp -a "$CFG" "$CFG.bak-herbie-hdmi"
sudo cp -a "$CMD" "$CMD.bak-herbie-hdmi"

python3 - "$CFG" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
needle = "hdmi_force_hotplug=1"
block = """
# Herbie face: force HDMI even if EDID is missing (small HDMI panels often omit it)
hdmi_force_hotplug=1
hdmi_drive=2
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 480 60 6 0 0 0
config_hdmi_boost=7
"""
if needle not in text:
    text = text.rstrip() + "\n" + block
    Path("/tmp/config.txt.herbie").write_text(text, encoding="utf-8")
    print("config: will add hdmi force")
else:
    print("config: hdmi force already present")
PY
if [ -f /tmp/config.txt.herbie ]; then
  sudo cp /tmp/config.txt.herbie "$CFG"
fi

python3 - "$CMD" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
line = p.read_text(encoding="utf-8").strip()
flag = "video=HDMI-A-1:800x480@60D"
if flag not in line:
    line = line + " " + flag
    Path("/tmp/cmdline.txt.herbie").write_text(line + "\n", encoding="utf-8")
    print("cmdline: will add", flag)
else:
    print("cmdline: video= already present")
PY
if [ -f /tmp/cmdline.txt.herbie ]; then
  sudo cp /tmp/cmdline.txt.herbie "$CMD"
fi

echo "---config tail---"
grep -E 'hdmi_|cvt|boost' "$CFG" || true
echo "---cmdline---"
cat "$CMD"
echo "HDMI config applied. Reboot separately after packages."
