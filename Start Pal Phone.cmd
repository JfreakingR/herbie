@echo off
set "PAL_ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PAL_ROOT%tools\Start-Pal-Phone.ps1"
if errorlevel 1 pause

