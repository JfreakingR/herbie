#!/bin/sh
xset s off
xset -dpms
xset s noblank
unclutter -idle 0.2 -root &
exec chromium --kiosk --noerrdialogs --disable-infobars --incognito \
  --check-for-update-interval=31536000 --disable-session-crashed-bubble \
  --disable-restore-session-state --disable-features=Translate \
  "http://127.0.0.1:8766/face/?kiosk=1"
