@echo off
set "PAL_ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PAL_ROOT%tools\Test-Pal-Phone-Brain.ps1"
if errorlevel 1 pause

