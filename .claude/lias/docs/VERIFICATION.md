# LIAS Verification Record

Run on 2026-11-13, Windows 11 (AMD64), Python 3.13.15, PowerShell 5.1.

## Test suite

```powershell
python -m unittest discover -s .claude\lias\tests -t .claude
```

Result: **59 tests passed**. Coverage includes root detection, policy and path
containment (including unquoted secrets), registry/manifest validation and
manifest-ID safety, runner I/O schemas, timeouts, retries, quarantine, caching
and invalidation, partial-migration tolerance, knowledge CRUD/FTS5/expiry,
duplicates and contradictions, audit trail, candidate promotion with metadata
merging, bounded generation, recovery/backup/restore, routing and CLI
integration.

## Acceptance scenarios

```powershell
python .claude/lias/tests/verify_acceptance.py
```

Result: **all seven scenarios passed** (machine-readable output in
`benchmarks/results/acceptance.json`, git-ignored).

| Scenario | Check | Result |
| --- | --- | --- |
| A persistent knowledge | Fact added, subsystems re-initialised, retrieved by search | PASS |
| B repeated automation | 3 successful runs → execution-log candidate → `reused` | PASS |
| C autonomous growth | Candidate → template → static check → isolated test → registered → routed | PASS |
| D failure recovery | error → error → quarantined → released → runs again | PASS |
| E project isolation | Two temp projects, separate DBs, 0 leaked records | PASS |
| F permission compliance | Tier 2 `denied`, traversal `denied`, secret write `rejected` | PASS |
| G efficiency | Cold → warm with a real cache hit (latest run 116 ms → 26 ms); search 2.8 ms | PASS |

Scenario G is wall-clock evidence from this machine. It does **not** claim
token savings; that number is not observable from a local process.

## Benchmarks

```powershell
python .claude/lias/benchmarks/run_benchmarks.py --samples 3
```

Measured on this machine (medians, 2–3 samples during development):

| Metric | Measured |
| --- | --- |
| `source-file-stats` cold vs warm | ~91 ms → ~21 ms (≈4.4×) |
| `env-check` cold vs warm | ~980 ms → ~4.8 ms (≈200×) |
| Knowledge retrieval latency | ~2.3 ms median, ~3.1 ms p95 |
| Router knowledge/unmatched | ~4–5 ms |
| Recorded execution success rate | 100% (20/20 at time of run) |
| SQLite integrity | `ok`, ~0.2 MB |

These numbers vary with disk, CPU and antivirus. The benchmark script is the
reproducible source; do not copy stale values into other documents.

## Manual checks

- `doctor` → `HEALTHY` with valid manifests and directories.
- `fsck` → integrity `ok`, no config issues, no quarantine, ≥1 backup.
- `backup` → verified file under `.claude/lias/backups/`.
- `cache stats` → entries and cumulative hits.
- `learn note` + `learn promote` in a scratch project → record promoted and
  retrievable.
- New-project bootstrap from the bundled schema succeeded (no `schema.sql` in
  the scratch project).
