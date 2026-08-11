@echo off
setlocal
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8000"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_backend.ps1" -Port %PORT%
exit /b %errorlevel%
