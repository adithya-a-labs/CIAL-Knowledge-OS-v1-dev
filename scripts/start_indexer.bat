@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_indexer.ps1" %*
exit /b %errorlevel%
