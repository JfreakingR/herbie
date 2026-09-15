#!/bin/sh
echo "---hat eeprom---"
if [ -d /proc/device-tree/hat ]; then
  echo "HAT PRESENT"
  for f in /proc/device-tree/hat/*; do
    echo -n "$(basename "$f")="
    tr -d '\0' < "$f"; echo
  done
else
  echo "no /proc/device-tree/hat (no HAT EEPROM detected)"
fi
echo "---i2c detect without overlay---"
ls /sys/bus/i2c/devices 2>/dev/null || echo "no i2c devices"
echo "---spi---"
ls /sys/bus/spi/devices 2>/dev/null || echo "no spi devices"
echo "---net---"
ip -6 addr
echo "---dns---"
getent ahosts deb.debian.org 2>/dev/null | head
echo "---clock---"
date -u
timedatectl 2>/dev/null || true
echo "---python mods---"
python3 -c "import sys; print(sys.version); mods=['tkinter','PIL','pygame','gi'];
import importlib
for m in mods:
  try:
    importlib.import_module(m); print(m, 'yes')
  except Exception as e:
    print(m, 'no')"
echo "---lcd info---"
vcgencmd get_lcd_info 2>/dev/null || true
vcgencmd get_config str 2>/dev/null | head -40
