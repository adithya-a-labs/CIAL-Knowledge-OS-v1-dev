@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-CIAL-Knowledge-OS.ps1" %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo Launch failed or the installed system did not pass strict readiness checks.
  echo Review outputs\launcher\logs for details, then rerun the installer to repair it.
  pause
)
exit /b %EXITCODE%
