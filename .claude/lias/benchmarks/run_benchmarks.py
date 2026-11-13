#!/usr/bin/env python3
"""LIAS reproducible local benchmarks.

Measures real wall-clock time for local work and real cache/automation
outcomes. It deliberately reports no token-savings numbers: model token usage
cannot be measured from inside a local script, so such a number would be
fabricated.

Usage:
    python .claude/lias/benchmarks/run_benchmarks.py [--samples 3] [--out PATH]
"""

from __future__ import annotations
import argparse
import datetime
import json
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List

LIAS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = LIAS_DIR.parent
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.cli import init_subsystems
from lias.database.connection import db_session


def timed(fn: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    value = fn()
    return value, (time.perf_counter() - started) * 1000


def summarize(samples: List[float]) -> Dict[str, float]:
    ordered = sorted(samples)
    if not ordered:
        return {"samples": 0}
    return {
        "samples": len(ordered),
        "min_ms": round(ordered[0], 2),
        "median_ms": round(statistics.median(ordered), 2),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))], 2),
        "max_ms": round(ordered[-1], 2),
    }


def bench_automation(runner, automation_id: str, samples: int) -> Dict[str, Any]:
    cold: List[float] = []
    warm: List[float] = []
    last_payload: Dict[str, Any] = {}
    for _ in range(samples):
        payload = {"_benchmark_nonce": uuid.uuid4().hex}
        last_payload = payload
        _, elapsed = timed(lambda: runner.run(automation_id, payload, caller="benchmark"))
        cold.append(elapsed)

        _, elapsed = timed(lambda: runner.run(automation_id, payload, caller="benchmark"))
        warm.append(elapsed)

    result = runner.run(automation_id, {"_benchmark_nonce": uuid.uuid4().hex}, caller="benchmark")
    return {
        "cold": summarize(cold),
        "warm": summarize(warm),
        "speedup_cold_vs_warm": (
            round(summarize(cold)["median_ms"] / summarize(warm)["median_ms"], 2)
            if summarize(warm)["median_ms"]
            else None
        ),
        "result_valid": result.output_valid,
    }


def bench_retrieval(retrieval, queries: List[str], repeats: int = 20) -> Dict[str, Any]:
    timings: List[float] = []
    top_matches: Dict[str, Any] = {}
    for query in queries:
        for _ in range(repeats):
            results, elapsed = timed(lambda q=query: retrieval.search(q, max_results=5))
            timings.append(elapsed)
        top = results[0] if results else None
        top_matches[query] = None if not top else {
            "provenance": top.record.provenance,
            "score": round(top.score, 3),
            "match_type": top.match_type,
            "content_chars": len(top.record.content),
        }
    return {
        "queries": len(queries),
        "repeats_per_query": repeats,
        "latency": summarize(timings),
        "top_matches": top_matches,
    }


def bench_router(router, query: str, repeats: int = 10) -> Dict[str, Any]:
    timings: List[float] = []
    action = None
    for _ in range(repeats):
        response, elapsed = timed(lambda: router.route(query))
        timings.append(elapsed)
        action = response.action_type
    return {"query": query, "action": action, **summarize(timings)}


def automation_success_rate(db_path: Path) -> Dict[str, Any]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS n FROM execution_log
            WHERE status IN ('success', 'error', 'timeout', 'denied', 'quarantined')
            GROUP BY status
            """
        ).fetchall()
    counts = {row["status"]: row["n"] for row in rows}
    total = sum(counts.values())
    successes = counts.get("success", 0)
    return {
        "total_executions": total,
        "by_status": counts,
        "success_rate": round(successes / total, 3) if total else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LIAS local benchmarks")
    parser.add_argument("--samples", type=int, default=3, help="Cold/warm samples per automation")
    parser.add_argument(
        "--out",
        default=str(LIAS_DIR / "benchmarks" / "results" / "latest.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    cfg, registry, runner, store, retrieval, router, diag, cache, recovery = init_subsystems()

    registry_ids = {m.id for m in registry.list_all(enabled_only=True)}
    automations: Dict[str, Any] = {}
    if "source-file-stats" in registry_ids:
        automations["source-file-stats"] = bench_automation(runner, "source-file-stats", args.samples)
    if "env-check" in registry_ids:
        automations["env-check"] = bench_automation(runner, "env-check", args.samples)

    report = {
        "measured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "project_root": str(cfg.project_root),
        "samples": args.samples,
        "automations": automations,
        "knowledge": bench_retrieval(
            retrieval,
            [
                "cloudflare pages deployment command",
                "where do projects live",
                "collection api proxy",
            ],
        ),
        "routing": [
            bench_router(router, "run source file stats"),
            bench_router(router, "where do projects live"),
            bench_router(router, "compose a poem about starlight"),
        ],
        "cache": cache.stats(),
        "executions": automation_success_rate(cfg.db_path),
        "database": recovery.integrity_check(),
        "limitations": [
            "Wall-clock timings only; model token usage is not measurable from a local script.",
            "Warm timings include the cache lookup path and deferred work avoided.",
            "Numbers vary with disk, CPU and antivirus; compare runs on the same machine.",
        ],
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
