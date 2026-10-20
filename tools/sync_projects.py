#!/usr/bin/env python3
"""Mirror every project in `projects/` into the published site at `root/projects/`.

`projects/` is the single source of truth. Cloudflare Pages only publishes the
contents of `root/`, so the projects are copied into it before a deploy or a
local preview. The generated mirror is git-ignored — never edit files under
`root/projects/` directly, edit `projects/<name>/` and re-run this script.

Usage:
    python tools/sync_projects.py            # mirror projects/ -> root/projects/
    python tools/sync_projects.py --force    # re-copy every file, even unchanged
    python tools/sync_projects.py --check    # exit 1 if the mirror is out of date

Cloudflare Pages build command:
    python3 tools/sync_projects.py
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "projects"
DEST_DIR = REPO_ROOT / "root" / "projects"

# Editor/OS/tooling noise that should never reach the published site.
SKIP_DIRS = {"__pycache__", ".git", ".github", "node_modules", ".wrangler", ".vscode"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def _iter_files(root: Path) -> list[Path]:
    """Every publishable file under `root`, as paths relative to `root`."""
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        files.append(rel)
    return files


def sync(source: Path = SOURCE_DIR, dest: Path = DEST_DIR, force: bool = False) -> tuple[int, int, int]:
    """Copy `source` onto `dest`, removing anything that no longer exists.

    Returns `(copied, removed, unchanged)`.
    """
    if not source.is_dir():
        raise SystemExit(f"error: project source directory not found: {source}")

    wanted = _iter_files(source)
    wanted_dirs = {rel.parent for rel in wanted}

    copied = removed = unchanged = 0

    # Remove anything in the mirror that is not in the source.
    if dest.is_dir():
        for existing in _iter_files(dest):
            if existing not in wanted:
                (dest / existing).unlink()
                removed += 1

    for rel in wanted:
        src_file = source / rel
        dst_file = dest / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        if not force and dst_file.is_file() and filecmp.cmp(src_file, dst_file, shallow=True):
            unchanged += 1
            continue
        shutil.copy2(src_file, dst_file)
        copied += 1

    # Drop directories that became empty (e.g. a renamed project folder).
    if dest.is_dir():
        for existing_dir in sorted(dest.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if not existing_dir.is_dir():
                continue
            rel_dir = existing_dir.relative_to(dest)
            if rel_dir in wanted_dirs:
                continue
            try:
                existing_dir.rmdir()
            except OSError:
                continue  # not empty — still holds files we copied

    dest.mkdir(parents=True, exist_ok=True)
    return copied, removed, unchanged


def is_in_sync(source: Path = SOURCE_DIR, dest: Path = DEST_DIR) -> bool:
    """True when the mirror already matches the source exactly."""
    if not source.is_dir() or not dest.is_dir():
        return False
    wanted = _iter_files(source)
    current = _iter_files(dest)
    if set(wanted) != set(current):
        return False
    return all(filecmp.cmp(source / rel, dest / rel, shallow=True) for rel in wanted)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", type=Path, default=SOURCE_DIR, help="project source root")
    parser.add_argument("--dest", type=Path, default=DEST_DIR, help="published mirror directory")
    parser.add_argument("--force", action="store_true", help="re-copy files even when unchanged")
    parser.add_argument("--check", action="store_true", help="verify only; exit 1 if stale")
    parser.add_argument("--quiet", action="store_true", help="only print on change")
    args = parser.parse_args()

    if args.check:
        if is_in_sync(args.source, args.dest):
            if not args.quiet:
                print(f"up to date: {args.dest}")
            return 0
        print(f"out of date: {args.dest} (run: python tools/sync_projects.py)", file=sys.stderr)
        return 1

    copied, removed, unchanged = sync(args.source, args.dest, force=args.force)

    if not args.quiet or copied or removed:
        projects = sorted(p.name for p in args.source.iterdir() if p.is_dir())
        print(f"synced {len(projects)} project(s) -> {args.dest}")
        print(f"  projects:  {', '.join(projects) if projects else '(none)'}")
        print(f"  copied:    {copied}")
        print(f"  removed:   {removed}")
        print(f"  unchanged: {unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
