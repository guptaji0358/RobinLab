# LIAS Setup and Diagnostics

## Requirements

- Python 3.10+ (validated on 3.13 on Windows 11).
- No third-party packages. SQLite FTS5 ships with CPython.
- Writable project root and `.claude/lias/`.

## First run

```powershell
python .claude/lias/cli.py doctor
```

The first run creates config, database, cache, logs and backup directories.
If the project has no `schema.sql` yet (new or relocated project), the CLI uses
the schema shipped with LIAS to bootstrap it.

## Health checks

```powershell
python .claude/lias/cli.py doctor   # component-by-component checks
python .claude/lias/cli.py status   # counts, recent executions
python .claude/lias/cli.py fsck     # integrity, config issues, quarantine
```

`doctor` returns `HEALTHY` only when every check passes; warnings (invalid
manifest, quarantine, config drift) produce `DEGRADED` with details.

## Backups

```powershell
python .claude/lias/cli.py backup --reason before-upgrade
python .claude/lias/cli.py restore .claude/lias/backups/lias-...sqlite3
```

- Backups use SQLite's online backup API and are integrity-checked before restore.
- Restore is restricted to `.claude/lias/backups/` and creates a `pre-restore`
  safety copy first.
- The newest 10 backups are kept.

## Configuration

`config/settings.json` is created from defaults and merged on load. Existing
keys are preserved; missing defaults are added in memory. Validate with
`fsck`. Unknown keys are left untouched.

## Relocating or copying a project

The runtime is path-local. A copied project gets its own `.claude/lias/`
database; knowledge is not imported automatically. Delete the copied
`database/lias.sqlite3*` if you want a clean store.

## Tests

```powershell
python -m unittest discover -s .claude\lias\tests -t .claude
```

Tests create their own temporary projects; failure-path tests never touch real
project files.
