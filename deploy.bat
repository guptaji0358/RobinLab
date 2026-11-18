@echo off
rem Deploy RobinLab to Cloudflare Pages (Direct Upload).
rem Uploads scripts/root/ + scripts/functions/ (wrangler must run from scripts/)
cd /d "%~dp0"
rem Keep wrangler's cache under .cache/ instead of cluttering the repo root.
set "WRANGLER_CACHE_DIR=%~dp0.cache\.wrangler\cache"

echo.
echo === Deploying to Cloudflare Pages ===
pushd "%~dp0scripts"
call npx wrangler pages deploy root --project-name=robinlab --branch=master
set DEPLOY_RC=%errorlevel%
popd
if not "%DEPLOY_RC%"=="0" (
  echo Deploy failed.
  pause
  exit /b 1
)

echo.
echo Done: https://robinlab.pages.dev
pause
