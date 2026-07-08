@echo off
setlocal

set "ROOT=%~dp0.."
set "SERVICE_ROOT=%ROOT%\services\knowledge-engine"

pushd "%ROOT%" >nul

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker CLI was not found. Nothing was stopped.
  popd >nul
  exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
  echo Docker is not running. Nothing was stopped.
  popd >nul
  exit /b 1
)

cd /d "%SERVICE_ROOT%"
echo Stopping Qdrant from services\knowledge-engine\docker-compose.qdrant.yml
docker compose -f docker-compose.qdrant.yml down
set "EXIT_CODE=%ERRORLEVEL%"

popd >nul
exit /b %EXIT_CODE%
