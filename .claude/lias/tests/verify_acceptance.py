#!/usr/bin/env python3
"""LIAS acceptance verification (scenarios A-G from the master prompt).

Runs real code against temporary projects and prints measured outcomes. Exit
code is non-zero if any scenario fails. Results are written to
``benchmarks/results/acceptance.json`` (git-ignored).
"""

from __future__ import annotations
import datetime
import json
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

LIAS_DIR = Path(__file__).resolve().parent.parent
CLAUDE_DIR = LIAS_DIR.parent
REAL_ROOT = CLAUDE_DIR.parent
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.cli import init_subsystems
from lias.core.registry import AutomationManifest
from lias.learning.candidates import CandidateManager
from lias.learning.generator import AutomationGenerator
from lias.learning.observer import WorkflowObserver


class Scenarios:
    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
        self.temp_dirs: List[tempfile.TemporaryDirectory] = []

    def temp_project(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.temp_dirs.append(tmp)
        root = Path(tmp.name)
        (root / ".claude").mkdir(parents=True, exist_ok=True)
        return root

    def record(self, scenario: str, passed: bool, details: Dict[str, Any]) -> None:
        self.results.append(
            {
                "scenario": scenario,
                "passed": passed,
                "details": details,
                "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )

    # ------------------------------------------------------------------- A
    def scenario_a(self) -> None:
        root = self.temp_project()
        (cfg, registry, runner, store, retrieval, *rest) = init_subsystems(root)
        rec = store.add(
            "rule",
            "All project pages must keep the Robin Gupta Studios footer.",
            "verification:A",
        )
        # Simulate a new session by re-initialising every subsystem.
        (cfg2, _r2, _run2, store2, retrieval2, *rest2) = init_subsystems(root)
        found = retrieval2.search("Robin Gupta Studios footer")
        passed = bool(found) and found[0].record.id == rec.id
        self.record(
            "A persistent knowledge",
            passed,
            {
                "record_id": rec.id,
                "retrieved": [r.record.provenance for r in found],
                "db_path": str(cfg2.db_path),
            },
        )

    # ------------------------------------------------------------------- B
    def scenario_b(self) -> None:
        root = self.temp_project()
        (cfg, registry, runner, store, retrieval, *rest) = init_subsystems(root)
        (root / "repeat.py").write_text(
            "import json;print(json.dumps({'status': 'success', 'result': {'ok': True}}))",
            encoding="utf-8",
        )
        registry.register(
            AutomationManifest(
                id="repeat-check",
                name="Repeat Check",
                description="Verification automation",
                entry_point="repeat.py",
                keywords=["repeat", "check"],
                cache_policy={"enabled": False},
            )
        )
        runs = [runner.run("repeat-check").status for _ in range(3)]
        candidates = CandidateManager(cfg.db_path, store)
        observed = WorkflowObserver(candidates).observe_execution_log(cfg.db_path, min_runs=3)
        generator = AutomationGenerator(cfg, registry, candidates)
        reuse = generator.generate(observed[0].id) if observed else None
        passed = (
            runs == ["success"] * 3
            and bool(observed)
            and reuse is not None
            and reuse.status == "reused"
        )
        self.record(
            "B repeated automation",
            passed,
            {
                "runs": runs,
                "candidates": [c.workflow_pattern for c in observed],
                "generation_status": reuse.status if reuse else None,
                "automation_id": reuse.automation_id if reuse else None,
            },
        )

    # ------------------------------------------------------------------- C
    def scenario_c(self) -> None:
        root = self.temp_project()
        (cfg, registry, runner, store, retrieval, router, *rest) = init_subsystems(root)
        cfg.set(
            "learning",
            {
                **cfg.get("learning"),
                "promotion_frequency_threshold": 2,
                "promotion_estimated_token_savings": 500,
            },
        )
        candidates = CandidateManager(cfg.db_path, store)
        for _ in range(2):
            candidates.record_candidate(
                "Count files by extension in root",
                category="workflow",
                estimated_savings=900,
                metadata={"template": "directory-summary"},
            )
        candidate = candidates.list_candidates()[0]
        generator = AutomationGenerator(cfg, registry, candidates)
        result = generator.generate(candidate.id)
        manifest = registry.get(result.automation_id) if result.automation_id else None
        run = runner.run(result.automation_id, {"path": "."}) if result.automation_id else None
        routed = router.route("count files in the repository")
        passed = (
            result.status == "generated"
            and manifest is not None
            and manifest.enabled
            and manifest.generated
            and run is not None
            and run.status == "success"
            and routed.action_type == "automation"
            and routed.data.get("automation_id") == result.automation_id
        )
        self.record(
            "C autonomous growth",
            passed,
            {
                "generation": result.to_dict(),
                "registered": bool(manifest),
                "run_status": run.status if run else None,
                "reused_via_router": routed.action_type,
                "router_automation": routed.data.get("automation_id"),
            },
        )

    # ------------------------------------------------------------------- D
    def scenario_d(self) -> None:
        root = self.temp_project()
        (cfg, registry, runner, store, retrieval, *rest) = init_subsystems(root)
        (root / "fail.py").write_text("import sys;sys.exit(4)", encoding="utf-8")
        registry.register(
            AutomationManifest(
                id="failing-check",
                name="Failing Check",
                description="Controlled failure",
                entry_point="fail.py",
                failure_policy={"max_retries": 0, "quarantine_on_failures": 2},
            )
        )
        first = runner.run("failing-check")
        second = runner.run("failing-check")
        third = runner.run("failing-check")
        disabled_after_threshold = not registry.get("failing-check").enabled
        recovery = rest[-1]
        released = recovery.release("failing-check")
        after_release = runner.run("failing-check")
        passed = (
            first.status == "error"
            and second.status == "error"
            and third.status == "quarantined"
            and disabled_after_threshold
            and released
            and registry.get("failing-check").enabled
            and after_release.status == "error"
        )
        self.record(
            "D failure recovery",
            passed,
            {
                "statuses": [first.status, second.status, third.status, after_release.status],
                "disabled_after_threshold": disabled_after_threshold,
                "released": released,
            },
        )

    # ------------------------------------------------------------------- E
    def scenario_e(self) -> None:
        root_a = self.temp_project()
        root_b = self.temp_project()
        cfg_a, _ra, _runa, store_a, retrieval_a, *rest_a = init_subsystems(root_a)
        cfg_b, _rb, _runb, store_b, retrieval_b, *rest_b = init_subsystems(root_b)
        store_a.add("fact", "Project A stores its notes in SQLite.", "verification:E")
        leak = retrieval_b.search("Project A stores its notes in SQLite.")
        passed = (
            cfg_a.db_path != cfg_b.db_path
            and bool(retrieval_a.search("Project A notes"))
            and not leak
        )
        self.record(
            "E project isolation",
            passed,
            {
                "project_a_db": str(cfg_a.db_path),
                "project_b_db": str(cfg_b.db_path),
                "leaked_records": len(leak),
            },
        )

    # ------------------------------------------------------------------- F
    def scenario_f(self) -> None:
        root = self.temp_project()
        (cfg, registry, runner, store, *rest) = init_subsystems(root)
        (root / "tier2.py").write_text(
            "import json;print(json.dumps({'status': 'success'}))", encoding="utf-8"
        )
        registry.register(
            AutomationManifest(
                id="tier2-action",
                name="Tier 2 Action",
                description="Requires authorization",
                entry_point="tier2.py",
                tier=2,
            )
        )
        tier2 = runner.run("tier2-action")
        registry.register(
            AutomationManifest(
                id="escape-action",
                name="Escape",
                description="Path traversal attempt",
                entry_point=str(root.parent / "outside.py"),
            )
        )
        escape = runner.run("escape-action")
        secret_status = "not-tested"
        try:
            store.add(
                "config",
                'api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"',
                "verification:F",
                on_secret="reject",
            )
        except ValueError:
            secret_status = "rejected"
        passed = (
            tier2.status == "denied"
            and escape.status == "denied"
            and "escapes project root" in (escape.error or "")
            and secret_status == "rejected"
        )
        self.record(
            "F permission compliance",
            passed,
            {
                "tier2_status": tier2.status,
                "tier2_error": tier2.error,
                "traversal_status": escape.status,
                "traversal_error": escape.error,
                "secret_write": secret_status,
            },
        )

    # ------------------------------------------------------------------- G
    def scenario_g(self) -> None:
        cfg, registry, runner, store, retrieval, router, diag, cache, recovery = init_subsystems(
            REAL_ROOT
        )
        nonce = uuid.uuid4().hex
        payload = {"_acceptance_nonce": nonce}
        started = time.perf_counter()
        cold = runner.run("source-file-stats", payload, caller="acceptance")
        cold_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        warm = runner.run("source-file-stats", payload, caller="acceptance")
        warm_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        search = retrieval.search("cloudflare deployment command")
        search_ms = (time.perf_counter() - started) * 1000
        passed = (
            cold.status == "success"
            and warm.status == "success"
            and warm.cached
            and warm_ms < cold_ms
            and bool(search)
        )
        self.record(
            "G efficiency",
            passed,
            {
                "cold_ms": round(cold_ms, 2),
                "warm_ms": round(warm_ms, 2),
                "cache_hit": warm.cached,
                "knowledge_search_ms": round(search_ms, 2),
                "knowledge_results": len(search),
                "token_savings": "not measured - not observable locally",
            },
        )

    def run(self) -> Dict[str, Any]:
        for name in ("scenario_a", "scenario_b", "scenario_c", "scenario_d", "scenario_e", "scenario_f", "scenario_g"):
            try:
                getattr(self, name)()
            except Exception as exc:
                self.record(name.replace("_", " ").upper(), False, {"exception": repr(exc)})
        for tmp in self.temp_dirs:
            tmp.cleanup()
        passed = all(r["passed"] for r in self.results)
        return {
            "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "all_passed": passed,
            "scenarios": self.results,
        }


def main() -> int:
    report = Scenarios().run()
    out_path = LIAS_DIR / "benchmarks" / "results" / "acceptance.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
