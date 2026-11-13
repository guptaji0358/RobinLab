"""LIAS Bounded Automation Generation.

Only deterministic, whitelisted templates are generated; LIAS never writes
arbitrary model-authored code and never activates an automation before it
passes static validation and an isolated test run.

Lifecycle: discover -> evaluate -> generate -> static validation -> isolated
test -> safety review -> register -> activate -> monitor.
"""

from __future__ import annotations
import ast
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lias.core.config import LiasConfig
from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.learning.candidates import CandidateManager
from lias.learning.patterns import estimate_automation_value, should_generate


FORBIDDEN_IMPORTS = {
    "socket", "ssl", "requests", "httpx", "urllib", "http", "ftplib",
    "smtplib", "ctypes", "subprocess", "shutil", "pty",
}
FORBIDDEN_CALLS = {"eval", "exec", "__import__", "compile", "input", "breakpoint"}


@dataclass
class GenerationResult:
    status: str  # generated | reused | rejected | not_found | quota_exceeded
    candidate_id: str
    reasons: List[str] = field(default_factory=list)
    automation_id: Optional[str] = None
    manifest_path: Optional[str] = None
    script_path: Optional[str] = None
    test_output: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "candidate_id": self.candidate_id,
            "reasons": self.reasons,
            "automation_id": self.automation_id,
            "manifest_path": self.manifest_path,
            "script_path": self.script_path,
            "test_output": self.test_output,
        }


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ----------------------------------------------------------------- templates
def _directory_summary_source(description: str) -> str:
    return f'''#!/usr/bin/env python3
"""LIAS generated automation: {description}

Read-only file counting. Generated from a whitelisted template.
"""

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{{}}")
    except Exception:
        payload = {{}}
    rel = str(payload.get("path", "."))
    root = Path.cwd().resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        print(json.dumps({{"status": "error", "error": "path escapes project root"}}))
        return 2
    if not target.exists():
        print(json.dumps({{"status": "error", "error": "path does not exist"}}))
        return 3

    by_extension = {{}}
    total = 0
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        if any(part in (".git", "node_modules", "__pycache__") for part in path.parts):
            continue
        ext = path.suffix.lower() or "<none>"
        by_extension[ext] = by_extension.get(ext, 0) + 1
        total += 1

    print(json.dumps({{"status": "success", "result": {{
        "path": rel,
        "files_scanned": total,
        "by_extension": dict(sorted(by_extension.items())),
    }}}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _log_summary_source(description: str) -> str:
    return f'''#!/usr/bin/env python3
"""LIAS generated automation: {description}

Read-only log summarisation. Generated from a whitelisted template.
"""

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{{}}")
    except Exception:
        payload = {{}}
    rel = str(payload.get("path", ""))
    max_samples = int(payload.get("max_samples", 5))
    root = Path.cwd().resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        print(json.dumps({{"status": "error", "error": "path escapes project root"}}))
        return 2
    if not target.is_file():
        print(json.dumps({{"status": "error", "error": "log file does not exist"}}))
        return 3

    counts = {{"error": 0, "warning": 0, "total_lines": 0}}
    samples = []
    with open(target, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            counts["total_lines"] += 1
            lowered = line.lower()
            if "error" in lowered or "failed" in lowered:
                counts["error"] += 1
                if len(samples) < max_samples:
                    samples.append(line.strip()[:200])
            elif "warn" in lowered:
                counts["warning"] += 1

    print(json.dumps({{"status": "success", "result": {{
        "path": rel,
        "counts": counts,
        "error_samples": samples,
    }}}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


TEMPLATES: Dict[str, Dict[str, Any]] = {
    "directory-summary": {
        "name": "Directory Summary",
        "description": "Counts files by extension under a project-relative directory.",
        "source": _directory_summary_source,
        "keywords": ["directory", "files", "count", "summary"],
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
        "output_schema": {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}, "result": {"type": "object"}},
        },
        "test_input": {"path": ".claude/lias/cache"},
    },
    "log-summary": {
        "name": "Log Summary",
        "description": "Summarises errors and warnings in a project-relative log file.",
        "source": _log_summary_source,
        "keywords": ["log", "errors", "warnings", "summary"],
        "input_schema": {
            "type": "object",
            "required": ["path"],
            "properties": {"path": {"type": "string"}, "max_samples": {"type": "integer"}},
        },
        "output_schema": {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}, "result": {"type": "object"}},
        },
        "test_input": {"path": ".claude/lias/cache/generator-fixture.log"},
    },
}


# -------------------------------------------------------------- static checks
def validate_generated_script(script_path: Path) -> List[str]:
    """Static safety validation. Returns a list of blocking issues."""
    issues: List[str] = []
    if not script_path.exists():
        return ["generated script is missing"]
    if script_path.stat().st_size > 24 * 1024:
        issues.append("generated script exceeds 24 KB limit")

    text = script_path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
        compile(text, str(script_path), "exec")
    except SyntaxError as exc:
        return [f"generated script has a syntax error: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORTS:
                    issues.append(f"forbidden import: {root}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in FORBIDDEN_IMPORTS:
                issues.append(f"forbidden import: {root}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                issues.append(f"forbidden call: {func.id}()")
            if isinstance(func, ast.Attribute):
                if func.attr in ("system", "popen", "rmtree", "remove", "unlink", "spawnl"):
                    issues.append(f"forbidden call: {func.attr}()")

    # Generated automations must emit JSON, not raw text.
    if "json.dumps" not in text:
        issues.append("generated script does not emit structured JSON")
    if "__main__" not in text:
        issues.append("generated script has no __main__ entry point")
    return issues


class AutomationGenerator:
    MAX_GENERATED = 50
    TEST_TIMEOUT = 15

    def __init__(
        self,
        config: LiasConfig,
        registry: AutomationRegistry,
        candidates: CandidateManager,
    ):
        self.config = config
        self.registry = registry
        self.candidates = candidates
        self.max_generated = config.get("resource_limits", {}).get(
            "max_generated_automations", self.MAX_GENERATED
        )
        self.promotion_threshold = config.get("learning", {}).get(
            "promotion_frequency_threshold", 3
        )
        self.min_savings = config.get("learning", {}).get(
            "promotion_estimated_token_savings", 500
        )

    # ------------------------------------------------------------- discovery
    def evaluate_candidate(self, candidate) -> Dict[str, Any]:
        value = estimate_automation_value(
            candidate.frequency, candidate.estimated_savings, candidate.risk_tier
        )
        eligible = should_generate(
            candidate.frequency,
            candidate.estimated_savings,
            candidate.risk_tier,
            min_frequency=int(self.promotion_threshold),
            min_score=0.4,
        )
        return {
            "candidate_id": candidate.id,
            "pattern": candidate.workflow_pattern,
            "frequency": candidate.frequency,
            "value_score": value,
            "eligible": eligible,
            "risk_tier": candidate.risk_tier,
        }

    def generate(
        self,
        candidate_id: str,
        template: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> GenerationResult:
        """Run the bounded generation lifecycle for one candidate."""
        candidate = next(
            (c for c in self.candidates.list_candidates() if c.id == candidate_id), None
        )
        if not candidate:
            return GenerationResult("not_found", candidate_id, ["candidate does not exist"])
        if candidate.status in ("promoted", "quarantined"):
            return GenerationResult(
                "rejected", candidate_id, [f"candidate is already {candidate.status}"]
            )

        # Repeated use of a verified automation is a reuse signal, not new code.
        if candidate.workflow_pattern.startswith("repeated_automation:"):
            automation_id = candidate.workflow_pattern.split(":", 1)[1]
            manifest = self.registry.get(automation_id)
            if manifest and manifest.enabled:
                return GenerationResult(
                    "reused",
                    candidate_id,
                    ["verified automation is already registered; reuse it"],
                    automation_id=automation_id,
                )
            return GenerationResult(
                "rejected", candidate_id, ["referenced automation is missing or disabled"]
            )

        template_name = template or (candidate.metadata or {}).get("template")
        if not template_name or template_name not in TEMPLATES:
            return GenerationResult(
                "rejected",
                candidate_id,
                ["no safe whitelisted template applies to this workflow"],
            )

        if not should_generate(
            candidate.frequency,
            candidate.estimated_savings,
            candidate.risk_tier,
            min_frequency=int(self.promotion_threshold),
            min_score=0.4,
        ):
            return GenerationResult(
                "rejected",
                candidate_id,
                [
                    "promotion threshold not met "
                    f"(frequency={candidate.frequency}, threshold={self.promotion_threshold})"
                ],
            )

        existing = self.registry.list_all(enabled_only=False)
        if len(existing) >= self.max_generated:
            return GenerationResult(
                "quota_exceeded",
                candidate_id,
                [f"generated automation limit reached ({self.max_generated})"],
            )

        template_def = TEMPLATES[template_name]
        automation_id = self._automation_id(template_name, candidate.workflow_pattern)
        if any(a.id == automation_id or a.entry_point.endswith(f"{automation_id}.py") for a in existing):
            return GenerationResult(
                "rejected", candidate_id, [f"duplicate automation '{automation_id}' already exists"]
            )

        script_path = self.config.generated_dir / f"{automation_id}.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(template_def["source"](candidate.workflow_pattern), encoding="utf-8")

        static_issues = validate_generated_script(script_path)
        if static_issues:
            script_path.unlink(missing_ok=True)
            self._mark_candidate(candidate_id, "quarantined", {"static_issues": static_issues})
            return GenerationResult(
                "rejected", candidate_id, ["static validation failed: " + "; ".join(static_issues)]
            )

        test_output, test_issues = self._isolated_test(template_name, script_path)
        if test_issues:
            script_path.unlink(missing_ok=True)
            self._mark_candidate(
                candidate_id, "quarantined", {"test_issues": test_issues, "test_output": test_output}
            )
            return GenerationResult(
                "rejected", candidate_id, ["isolated test failed: " + "; ".join(test_issues)], test_output=test_output
            )

        entry_point = script_path.relative_to(self.config.project_root).as_posix()
        manifest = AutomationManifest(
            id=automation_id,
            name=f"Generated: {template_def['name']}",
            description=f"{template_def['description']} Generated for observed workflow: {candidate.workflow_pattern}.",
            tier=0,
            entry_point=entry_point,
            enabled=True,
            version="1.0.0",
            timeout_seconds=30,
            keywords=template_def["keywords"],
            input_schema=template_def["input_schema"],
            output_schema=template_def["output_schema"],
            generated=True,
            created_by=f"lias-generator:{candidate_id}",
            validation={
                "static": "passed",
                "isolated_test": "passed",
                "tested_at": _now(),
                "test_output": test_output,
            },
            cache_policy={"enabled": True, "ttl": 300},
            failure_policy={"max_retries": 0, "quarantine_on_failures": 3},
        )
        self.registry.register(manifest)
        self._mark_candidate(
            candidate_id,
            "promoted",
            {"automation_id": automation_id, "template": template_name},
        )

        return GenerationResult(
            "generated",
            candidate_id,
            [f"validated and activated '{automation_id}'"],
            automation_id=automation_id,
            manifest_path=str(self.config.manifests_dir / f"{automation_id}.json"),
            script_path=str(script_path),
            test_output=test_output,
        )

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _automation_id(template_name: str, pattern: str) -> str:
        digest = hashlib.sha256(f"{template_name}:{pattern}".encode("utf-8")).hexdigest()[:8]
        return f"gen-{template_name}-{digest}"

    def _mark_candidate(self, candidate_id: str, status: str, meta: Dict[str, Any]) -> None:
        from lias.database.connection import db_session

        with db_session(self.config.db_path) as conn:
            row = conn.execute(
                "SELECT metadata_json FROM candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            merged = json.loads(row["metadata_json"] or "{}") if row else {}
            merged.update(meta)
            conn.execute(
                "UPDATE candidates SET status = ?, metadata_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, json.dumps(merged), candidate_id),
            )

    def _isolated_test(
        self, template_name: str, script_path: Path
    ) -> Tuple[Dict[str, Any], List[str]]:
        fixture_dir = self.config.cache_dir / "generator-fixture"
        fixture_dir.mkdir(parents=True, exist_ok=True)
        log_fixture = self.config.cache_dir / "generator-fixture.log"
        log_fixture.write_text(
            "INFO start\nWARNING slow call\nERROR boom\nTraceback failed\n", encoding="utf-8"
        )
        payload = dict(TEMPLATES[template_name].get("test_input", {}))
        output: Dict[str, Any] = {}
        issues: List[str] = []
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path)],
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                cwd=str(self.config.project_root),
                timeout=self.TEST_TIMEOUT,
            )
            if proc.returncode != 0:
                issues.append(f"script exited {proc.returncode}: {proc.stderr.strip()[:300]}")
            try:
                output = json.loads(proc.stdout.strip() or "{}")
            except Exception:
                issues.append("script did not emit valid JSON")
            if output.get("status") != "success":
                issues.append(f"script returned status {output.get('status')!r}")
        except subprocess.TimeoutExpired:
            issues.append(f"script exceeded the {self.TEST_TIMEOUT}s test timeout")
        except Exception as exc:
            issues.append(f"test harness error: {exc}")
        finally:
            shutil.rmtree(fixture_dir, ignore_errors=True)
            log_fixture.unlink(missing_ok=True)
        return output, issues
