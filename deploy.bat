@echo off
rem Deploy RobinLab to Cloudflare Pages (Direct Upload).
rem 1) refresh the projects/ mirror  2) upload root/ + functions/
cd /d "%~dp0"

echo.
echo === Syncing projects mirror ===
python tools\sync_projects.py
if errorlevel 1 (
  echo Sync failed - deploy cancelled.
  pause
  exit /b 1
)

echo.
echo === Deploying to Cloudflare Pages ===
call npx wrangler pages deploy root --project-name=robinlab --branch=master
if errorlevel 1 (
  echo Deploy failed.
  pause
  exit /b 1
)

echo.
echo Done: https://robinlab.pages.dev
pause
