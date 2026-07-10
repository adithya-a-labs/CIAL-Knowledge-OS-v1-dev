@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-CIAL-Knowledge-OS.ps1" %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo Launch failed. Review outputs\launcher\logs for details.
  pause
)
exit /b %EXITCODE%
