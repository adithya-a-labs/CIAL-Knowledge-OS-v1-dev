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
if not "%EXITCODE%"=="0" (
  echo.
  echo Installation failed. Review the timestamped log under outputs\installer\logs.
  pause
)
exit /b %EXITCODE%
