# LIAS Benchmarks

`run_benchmarks.py` measures **local** behaviour on this machine:

| Metric | What it actually measures |
| --- | --- |
| Automation cold/warm | Subprocess wall-clock time vs. a cache hit for the same input |
| Knowledge retrieval | `search()` wall-clock latency over the project database |
| Routing | End-to-end `router.route()` latency and chosen action |
| Cache | Live entries, cumulative hits, stored bytes |
| Executions | Success/error/timeout counts recorded in `execution_log` |
| Database | SQLite integrity, size, table list |

```powershell
python .claude/lias/benchmarks/run_benchmarks.py --samples 3
```

Results are written to `benchmarks/results/latest.json` (git-ignored).

## What is deliberately not reported

- **Token savings.** A local script cannot see Claude's token usage. Reporting
  a number such as "350 tokens saved" would be fabricated, so LIAS reports
  measured wall-clock time and result size instead.
- **Model latency or credit usage.** These depend on the client, model and
  plan, and are not observable from inside the project.

## Methodology

1. Cold runs use a unique benchmark input so the cache cannot hit.
2. Warm runs repeat the same input immediately, exercising the cache key,
   TTL and fingerprint checks.
3. Medians and p95 are reported; timings vary with disk, CPU and antivirus.
4. Compare runs on the same machine and the same power profile.

Setup costs (authoring automations, indexing knowledge) are separate from
recurring execution costs and are not netted out of the numbers above.
