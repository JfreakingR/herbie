@echo off
cd /d "C:\Users\Phyllis\ai-bot-face"
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\Phyllis\ai-bot-face\Show-Face-On-Extra-Monitor.ps1"
if errorlevel 1 pause
