@echo off
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%" >nul

if not exist ".venv\Scripts\activate.bat" (
  echo Missing .venv. Create it with: py -3.11 -m venv .venv
  popd >nul
  exit /b 1
)

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8000"

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo Failed to activate .venv.
  popd >nul
  exit /b 1
)

cd /d "services\knowledge-engine"
echo Starting CIAL Knowledge OS backend on http://127.0.0.1:%PORT%
echo Backend source: services\knowledge-engine\backend\app
echo Corpus indexing is handled by scripts\start_indexer.bat.
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port %PORT%
set "EXIT_CODE=%ERRORLEVEL%"

popd >nul
exit /b %EXIT_CODE%
