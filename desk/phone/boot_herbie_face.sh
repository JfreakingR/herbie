#!/data/data/com.termux/files/usr/bin/sh
# Installed to ~/.termux/boot/ by install_face_autostart.sh. Termux:Boot runs
# it after the phone starts, alongside boot_herbie.sh (his brain).
exec "$HOME/herbie-desk/desk/phone/herbie_face_supervisor.sh" >/dev/null 2>&1
