@echo off
rem Deploy RobinLab to Cloudflare Pages (Direct Upload).
rem Uploads root/ + functions/
cd /d "%~dp0"

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
