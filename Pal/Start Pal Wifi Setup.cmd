@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0software\pal-wifi-setup\Start-Pal-Wifi-Setup.ps1"
if errorlevel 1 pause
