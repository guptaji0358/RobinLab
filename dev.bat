@echo off
rem Local dev server control:  dev start | stop | restart | status   [--port N] [--open]
cd /d "%~dp0"
if "%~1"=="" (
  python tools\devctl.py status
  echo Usage: dev start^|stop^|restart^|status [--port N] [--open]
  exit /b 0
)
python tools\devctl.py %*
