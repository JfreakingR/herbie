@echo off
rem Mirror Herbie's Galaxy S21. Herbie's own board is also on ADB, so scrcpy
rem must be told which device to show or it exits immediately.
rem --no-audio: by default scrcpy captures the phone's audio and plays it on the
rem PC, so Herbie's voice would never reach his Bluetooth speaker.
cd /d "%~dp0tools\scrcpy-win64-v4.1\scrcpy-win64-v4.1"
scrcpy.exe -s R5CR11QCHPY --no-audio
if errorlevel 1 pause
