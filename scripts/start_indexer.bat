@echo off
setlocal
set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
set "SERVICE=%ROOT%\services\knowledge-engine"

if not exist "%PYTHON%" (
  echo Missing .venv. Run the installer first.
  exit /b 1
)
set "PYTHONPATH=%SERVICE%;%SERVICE%\src"
pushd "%SERVICE%" >nul
echo Starting the standalone CIAL continuous indexer.
"%PYTHON%" "backend\indexer_main.py"
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
