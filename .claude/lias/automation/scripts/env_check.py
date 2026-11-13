#!/usr/bin/env python3
"""LIAS Built-in Automation: Environment Check.

Checks availability of Python, Git, and project tools.
Outputs structured JSON.
"""

import json
import shutil
import subprocess
import sys

def check_command(cmd, version_flag="--version"):
    exe = shutil.which(cmd)
    if not exe:
        return {"available": False, "version": None}
    try:
        res = subprocess.run([exe, version_flag], capture_output=True, text=True, timeout=5)
        out = (res.stdout or res.stderr).strip().splitlines()[0] if (res.stdout or res.stderr) else "available"
        return {"available": True, "path": exe, "version": out}
    except Exception as e:
        return {"available": True, "path": exe, "version": f"Error: {e}"}

def main():
    report = {
        "python": {
            "available": True,
            "path": sys.executable,
            "version": sys.version.split()[0]
        },
        "git": check_command("git"),
        "node": check_command("node"),
        "wrangler": check_command("wrangler")
    }
    print(json.dumps({"status": "success", "result": report}))

if __name__ == "__main__":
    main()
