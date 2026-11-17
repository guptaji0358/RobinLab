#!/usr/bin/env python3
"""LIAS Automation: git commit + push.

stdin JSON: {"paths": [...], "message": "...", "log": "short|long|none",
             "no_push": false, "branch": "<name>"}
Stages ONLY the listed paths (never '.' or -A), commits, pushes, prints JSON.
"""
import json
import subprocess
import sys

FORBIDDEN = {".", "-A", "-a", "--all", "*", ":/", "./"}
TRAILER = "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"


def git(*args):
    p = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout + p.stderr).strip()


def out(status, **kw):
    print(json.dumps({"status": status, "result": kw}))
    sys.exit(0 if status == "success" else 1)


def main():
    data = json.loads(sys.stdin.read() or "{}")
    paths = data.get("paths") or []
    message = (data.get("message") or "").strip()
    log = data.get("log", "short")
    if not paths or not message:
        out("error", error="STOP: 'paths' and 'message' are required")
    bad = [p for p in paths if p.strip() in FORBIDDEN or p.startswith("-")]
    if bad:
        out("error", error=f"STOP: refused broad/unsafe paths: {bad}")

    code, o = git("rev-parse", "--show-toplevel")
    if code:
        out("error", error="STOP: not a git repository: " + o)

    code, o = git("add", "--", *paths)
    if code:
        out("error", error="FAILED: git add: " + o)
    code, o = git("diff", "--cached", "--quiet", "--", *paths)
    if code == 0:
        out("error", error="STOP: nothing staged for the given paths")
    code, o = git("commit", "-m", message, "-m", TRAILER, "--only", "--", *paths)
    if code:
        out("error", error="FAILED: git commit: " + o)

    pushed = None
    if not data.get("no_push"):
        branch = data.get("branch")
        if not branch:
            _, branch = git("rev-parse", "--abbrev-ref", "HEAD")
        code, o = git("push", "origin", branch)
        if code:
            out("error", error="FAILED: git push (commit is local): " + o)
        pushed = branch

    _, head = git("log", "-1", "--format=%h %s")
    res = {"commit": head, "pushed": pushed}
    if log == "short":
        res["log"] = git("log", "--oneline", "-5")[1]
    elif log == "long":
        res["log"] = git("log", "-5", "--stat")[1]
    out("success", **res)


if __name__ == "__main__":
    main()
