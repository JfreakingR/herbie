@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Send-Herbie-Face-To-Phone.ps1" %*
pause
