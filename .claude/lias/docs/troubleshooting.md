# LIAS Troubleshooting

## `doctor` says DEGRADED

```powershell
python .claude/lias/cli.py doctor
```

- **Invalid manifest** — filename must equal `id`; `id`, `name`, `description`
  and `entry_point` are required; tier 0/1/2; timeout 1–600.
- **Quarantine** — inspect and release only after fixing the cause:
  `quarantine list`, then `quarantine release <id>`.
- **Configuration** — `fsck` lists missing or wrongly-typed keys. Fix
  `config/settings.json`; unknown user keys are preserved.

## `database is locked`

LIAS uses WAL with a 10 s busy timeout. A long external SQLite session can still
block writes. Close it, or run `fsck` and retry. Do not delete WAL files while a
process is running.

## FTS5 unavailable

`knowledge_fts` requires a CPython build with FTS5 (standard on Windows/macOS
and most Linux distributions). Without it, `knowledge_fts MATCH` is skipped
silently and keyword retrieval still works. `doctor` reports database errors.

## Stale automation result

Results are cached only when the manifest enables caching. Check:

```powershell
python .claude/lias/cli.py cache stats
python .claude/lias/cli.py cache clear
```

If a `fingerprint_paths` glob does not cover changed inputs, add it. TTL expiry
also invalidates entries automatically.

## Automation not found / disabled

- `candidates` shows learned work; `status` shows registered automations.
- A manifest that fails validation is not registered; `doctor` reports it.
- Disabled automations return `denied` or `quarantined` with the reason.

## Timeout

Raise `timeout_seconds` (max 600) only after confirming the script is not
looping. The runner kills the direct child; grandchildren launched by a script
are the script's responsibility.

## `.bat` or `.ps1` fails under the runner

The runner invokes `cmd.exe /d /c` and `powershell -NoProfile -NonInteractive
-ExecutionPolicy Bypass -File`. Check the script's own exit code and stderr; the
runner includes stderr in `warnings` and `error`.

## Generated automation rejected

Reasons are returned in `reasons`:

- no safe whitelisted template — supply `--template` only with a supported one;
- threshold not met — a one-off is not worth generating;
- static validation — forbidden import/call, missing JSON output, syntax error;
- isolated test — script exited non-zero, timed out, or returned non-success.

Rejected candidates are marked `quarantined`; inspect with
`candidates --status quarantined`.

## Knowledge search returns nothing

- Default filters hide unverified and expired records.
- Run `knowledge index` if the database is empty.
- `knowledge add` refuses duplicates and contradictions; re-run with `--force`
  only after review.
- Use `--limit` to widen results; the context budget may drop large records.

## Restore refused

`restore` accepts files only inside `.claude/lias/backups/` that pass
`PRAGMA integrity_check`. Use `backup` to create a fresh one first.

## PowerShell `npx.ps1 cannot be loaded`

Unrelated to LIAS: use `cmd /c "npx ..."` for Wrangler deploys.

## Resetting LIAS

Stop using LIAS, create a backup if the knowledge matters, then delete
`.claude/lias/database/lias.sqlite3*` and run `doctor` again. Never delete
`.claude/lias/automation/scripts/` or manifests unless you intend to remove
those capabilities.
