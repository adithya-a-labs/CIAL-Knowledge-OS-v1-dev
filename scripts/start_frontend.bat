@echo off
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%" >nul

if not exist "frontend" (
  echo Missing frontend directory.
  popd >nul
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo Missing frontend dependencies. Run: cd frontend ^&^& pnpm install
  popd >nul
  exit /b 1
)

cd /d "frontend"
echo Starting CIAL Knowledge OS frontend.
pnpm run dev
set "EXIT_CODE=%ERRORLEVEL%"

popd >nul
exit /b %EXIT_CODE%
