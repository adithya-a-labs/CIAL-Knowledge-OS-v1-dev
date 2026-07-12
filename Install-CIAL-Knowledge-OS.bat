@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if not "%ERRORLEVEL%"=="0" (
  echo CIAL Knowledge OS installer requires Administrator privileges.
  echo Right-click this file and choose "Run as administrator".
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-CIAL-Knowledge-OS.ps1" %*
set EXITCODE=%ERRORLEVEL%
if "%EXITCODE%"=="3010" goto reboot_required
if "%EXITCODE%"=="194" goto reboot_required
if not "%EXITCODE%"=="0" (
  echo.
  echo Installation failed. Review the timestamped log under outputs\installer\logs.
  pause
)
exit /b %EXITCODE%

:reboot_required
  echo.
  echo A Windows restart is required. Installation will resume once at next login.
  echo You can also rerun this BAT manually after restarting.
  pause
  exit /b 0
