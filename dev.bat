@echo off
rem Local dev server control:  dev start | stop | restart | status   [--port N] [--open]
cd /d "%~dp0"
rem Send Python bytecode to out/ instead of __pycache__ folders in the tree.
set "PYTHONPYCACHEPREFIX=%~dp0out\__pycache__"
if "%~1"=="" (
  python scripts\tools\devctl.py status
  echo Usage: dev start^|stop^|restart^|status [--port N] [--open]
  exit /b 0
)
python scripts\tools\devctl.py %*
