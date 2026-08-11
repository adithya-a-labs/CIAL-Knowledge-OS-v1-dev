@echo off
setlocal
call "%~dp0..\..\..\scripts\start_qdrant.bat" -ShowStatus
exit /b %errorlevel%
