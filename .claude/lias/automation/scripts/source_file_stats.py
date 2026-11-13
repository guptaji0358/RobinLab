#!/usr/bin/env python3
"""LIAS Built-in Automation: Source File Statistics.

Analyzes file and line counts across RobinLabs subdirectories.
Outputs structured JSON.
"""

import json
import os
import sys
from pathlib import Path

EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".md": "Markdown",
    ".toml": "TOML",
}

def analyze():
    # Assume working directory is project root
    root = Path.cwd()
    stats = {
        "files_scanned": 0,
        "total_lines": 0,
        "languages": {},
        "directories": {},
    }

    ignore_dirs = {".git", ".wrangler", "node_modules", "__pycache__", "cache", "logs", "backups", "Skills"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, root)
        top_level = rel_dir.split(os.sep)[0] if rel_dir != "." else "root_files"

        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in EXTENSIONS:
                lang = EXTENSIONS[ext]
                stats["files_scanned"] += 1
                stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
                stats["directories"][top_level] = stats["directories"].get(top_level, 0) + 1

                file_path = os.path.join(dirpath, f)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                        line_count = sum(1 for _ in fh)
                        stats["total_lines"] += line_count
                except Exception:
                    pass

    return {
        "status": "success",
        "result": stats
    }

if __name__ == "__main__":
    result = analyze()
    print(json.dumps(result))
