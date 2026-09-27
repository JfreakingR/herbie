@echo off
setlocal
cd /d "%~dp0"
set "HERBIE_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%HERBIE_PYTHON%" goto run
where py.exe >nul 2>&1 && set "HERBIE_PYTHON=py.exe" && goto run
where python.exe >nul 2>&1 && set "HERBIE_PYTHON=python.exe" && goto run
echo Python is unavailable. Install Python or use the Codex bundled runtime.
pause
exit /b 1
:run
"%HERBIE_PYTHON%" "tools\herbie_presence.py"
pause
