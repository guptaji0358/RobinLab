"""Start / stop / restart / check the local RobinLab dev server in one command.

    python tools/devctl.py start [--port 5500] [--open]
    python tools/devctl.py stop  [--port 5500]
    python tools/devctl.py restart
    python tools/devctl.py status

It runs `dev_server.py` detached (no console window), remembers its PID in
`.dev_server.pid`, and stops it by PID or, failing that, by whatever process is
listening on the port. Nothing else on the machine is touched.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PID_FILE = ROOT / ".dev_server.pid"
LOG_FILE = ROOT / ".dev_server.log"
HOST = "127.0.0.1"


def is_up(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex((HOST, port)) == 0


def pid_on_port(port: int) -> int | None:
    """PID listening on `port` (Windows netstat / POSIX lsof)."""
    try:
        if os.name == "nt":
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
            for line in out.splitlines():
                m = re.search(rf"\s{re.escape(HOST)}:{port}\s+\S+\s+LISTENING\s+(\d+)", line) or re.search(
                    rf"\s(?:0\.0\.0\.0|\[::\]):{port}\s+\S+\s+LISTENING\s+(\d+)", line
                )
                if m:
                    return int(m.group(1))
        else:
            out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
            if out.strip():
                return int(out.split()[0])
    except OSError:
        pass
    return None


def kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        os.kill(pid, 15)


def start(port: int, open_browser: bool) -> int:
    if is_up(port):
        print(f"Already running: http://{HOST}:{port}")
    else:
        log = open(LOG_FILE, "ab")
        flags = 0
        if os.name == "nt":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "dev_server.py"), "--port", str(port)],
            cwd=ROOT, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags,
        )
        PID_FILE.write_text(str(proc.pid))
        for _ in range(40):  # up to ~8 s
            if is_up(port):
                break
            if proc.poll() is not None:
                print(f"Server exited early — see {LOG_FILE.name}")
                return 1
            time.sleep(0.2)
        else:
            print(f"Server did not come up — see {LOG_FILE.name}")
            return 1
        print(f"Started: http://{HOST}:{port}  (pid {proc.pid})")
    if open_browser:
        webbrowser.open(f"http://{HOST}:{port}/")
    return 0


def stop(port: int) -> int:
    pids: set[int] = set()
    if PID_FILE.exists():
        try:
            pids.add(int(PID_FILE.read_text().strip()))
        except ValueError:
            pass
    listener = pid_on_port(port)
    if listener:
        pids.add(listener)
    if not pids:
        print("Not running.")
        PID_FILE.unlink(missing_ok=True)
        return 0
    for pid in pids:
        kill(pid)
    for _ in range(25):
        if not is_up(port):
            break
        time.sleep(0.2)
    PID_FILE.unlink(missing_ok=True)
    print("Stopped." if not is_up(port) else f"Port {port} is still in use.")
    return 0 if not is_up(port) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["start", "stop", "restart", "status"])
    ap.add_argument("--port", type=int, default=5500)
    ap.add_argument("--open", action="store_true", help="open the site in the default browser")
    a = ap.parse_args()
    if a.action == "start":
        return start(a.port, a.open)
    if a.action == "stop":
        return stop(a.port)
    if a.action == "restart":
        stop(a.port)
        return start(a.port, a.open)
    print(f"Running: http://{HOST}:{a.port}" if is_up(a.port) else "Not running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
