"""LIAS Local Automation Runner.

Executes automations with input/output schema validation, policy checks,
timeouts, bounded output, retries, failure quarantine, deterministic caching
and execution logging.
"""

from __future__ import annotations
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lias.core.cache import CacheManager, path_fingerprint
from lias.core.policy import PolicyEngine, PolicyViolation
from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.core.validation import validate_against_schema
from lias.database.connection import db_session


@dataclass
class ExecutionResult:
    automation_id: str
    status: str  # 'success', 'cached', 'error', 'timeout', 'denied', 'quarantined'
    duration_ms: int
    exit_code: int
    result: Dict[str, Any]
    warnings: List[str]
    error: Optional[str] = None
    attempts: int = 1
    cached: bool = False
    output_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "result": self.result,
            "warnings": self.warnings,
            "error": self.error,
            "attempts": self.attempts,
            "cached": self.cached,
            "output_valid": self.output_valid,
        }


class LocalRunner:
    MAX_ATTEMPTS = 3

    def __init__(
        self,
        project_root: Path,
        registry: AutomationRegistry,
        policy: PolicyEngine,
        db_path: Path,
        max_output_bytes: int = 100000,
        cache: Optional[CacheManager] = None,
    ):
        self.project_root = project_root.resolve()
        self.registry = registry
        self.policy = policy
        self.db_path = db_path
        self.max_output_bytes = max_output_bytes
        self.cache = cache

    # ------------------------------------------------------------------ public
    def run(
        self,
        automation_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        caller: str = "cli",
    ) -> ExecutionResult:
        """Run an automation by ID within policy, schema and timeout limits."""
        manifest = self.registry.get(automation_id)
        if not manifest:
            return self._fail(automation_id, "error", -1, f"Automation '{automation_id}' not found in registry.")

        failure_policy = manifest.failure_policy or {}
        quarantine_after = int(failure_policy.get("quarantine_on_failures", 3) or 3)
        previous_failures = self._consecutive_failures(automation_id, quarantine_after)

        if not manifest.enabled:
            return self._fail(
                automation_id,
                "quarantined" if previous_failures >= quarantine_after else "denied",
                -2,
                f"Automation '{automation_id}' is disabled"
                + (" after repeated failures." if previous_failures >= quarantine_after else "."),
            )

        if previous_failures >= quarantine_after:
            self.registry.set_enabled(automation_id, False)
            return self._fail(
                automation_id,
                "quarantined",
                -3,
                f"Automation '{automation_id}' was quarantined after {previous_failures} consecutive failures.",
            )

        if not self.policy.can_auto_execute(manifest.tier):
            return self._fail(
                automation_id,
                "denied",
                -4,
                f"Automation '{automation_id}' requires Tier {manifest.tier} authorization.",
            )

        payload = input_data or {}
        input_ok, input_errors = validate_against_schema(payload, manifest.input_schema, "input")
        if not input_ok:
            return self._fail(
                automation_id, "error", -7, "Input validation failed: " + "; ".join(input_errors)
            )

        paths = self._resolve_paths(manifest)
        if isinstance(paths, ExecutionResult):
            self._log_execution(automation_id, paths.duration_ms, paths.status, paths.exit_code, None, paths.error, caller)
            return paths
        work_dir, script_path = paths

        cmd = self._build_command(script_path)
        try:
            self.policy.validate_command_safety(cmd)
        except PolicyViolation as pv:
            return self._fail(automation_id, "denied", -8, str(pv))

        fingerprints = self._fingerprints(manifest)
        cached_result, _ = self._cache_lookup(manifest, payload, fingerprints)
        if cached_result is not None:
            return ExecutionResult(
                automation_id=automation_id,
                status="success",
                duration_ms=0,
                exit_code=0,
                result=cached_result,
                warnings=[],
                attempts=0,
                cached=True,
            )

        max_retries = int(failure_policy.get("max_retries", 1) or 0)
        total_attempts = max(1, min(max_retries + 1, self.MAX_ATTEMPTS))
        timeout = manifest.timeout_seconds or 30

        result: Optional[ExecutionResult] = None
        for attempt in range(1, total_attempts + 1):
            result = self._execute_once(
                automation_id=automation_id,
                cmd=cmd,
                work_dir=work_dir,
                script_path=script_path,
                payload=payload,
                timeout=timeout,
                attempt=attempt,
                caller=caller,
            )
            if result.status in ("success", "denied"):
                break

        assert result is not None
        result.attempts = total_attempts if result.status != "success" else attempt

        if result.status == "success":
            ok, output_errors = validate_against_schema(
                result.result, manifest.output_schema, "output"
            )
            result.output_valid = ok
            if not ok:
                result.warnings.append("Output schema mismatch: " + "; ".join(output_errors))
            self._cache_store(manifest, payload, result.result, fingerprints)
        elif result.status in ("error", "timeout"):
            failures = self._consecutive_failures(automation_id, quarantine_after)
            if failures >= quarantine_after:
                self.registry.set_enabled(automation_id, False)
                result.warnings.append(
                    f"Automation disabled after {failures} consecutive failures."
                )
        return result

    # ------------------------------------------------------------- execution
    def _execute_once(
        self,
        automation_id: str,
        cmd: List[str],
        work_dir: Path,
        script_path: Path,
        payload: Dict[str, Any],
        timeout: int,
        attempt: int,
        caller: str,
    ) -> ExecutionResult:
        start_time = time.perf_counter()
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(work_dir),
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            stdout, stderr = proc.communicate(input=json.dumps(payload), timeout=timeout)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            exit_code = proc.returncode

            if len(stdout) > self.max_output_bytes:
                stdout = stdout[: self.max_output_bytes] + "... [TRUNCATED]"

            warnings: List[str] = []
            if stderr:
                warnings.append(stderr.strip()[:1000])

            parsed_result: Dict[str, Any] = {}
            error_msg: Optional[str] = None

            if exit_code == 0:
                try:
                    parsed = json.loads(stdout.strip())
                except Exception:
                    parsed = {"output": stdout.strip()}
                if not isinstance(parsed, dict):
                    parsed = {"output": parsed}
                parsed_result = parsed
                status = "success"
            else:
                status = "error"
                error_msg = f"Script exited with code {exit_code}: {stderr.strip() or stdout.strip()}"

        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=2)
            except Exception:
                pass
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            exit_code = -124
            status = "timeout"
            parsed_result = {}
            warnings = []
            error_msg = f"Automation timed out after {timeout} seconds."
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            exit_code = -999
            status = "error"
            parsed_result = {}
            warnings = []
            error_msg = f"Runner failed with unexpected exception: {e}"

        self._log_execution(
            automation_id=automation_id,
            duration_ms=duration_ms,
            status=status,
            exit_code=exit_code,
            stdout=str(parsed_result)[:500],
            error=error_msg[:500] if error_msg else None,
            caller=f"{caller}:attempt{attempt}",
        )

        return ExecutionResult(
            automation_id=automation_id,
            status=status,
            duration_ms=duration_ms,
            exit_code=exit_code,
            result=parsed_result,
            warnings=warnings,
            error=error_msg,
        )

    # ---------------------------------------------------------------- helpers
    def _fail(self, automation_id: str, status: str, code: int, error: str) -> ExecutionResult:
        return ExecutionResult(
            automation_id=automation_id,
            status=status,
            duration_ms=0,
            exit_code=code,
            result={},
            warnings=[],
            error=error,
        )

    def _resolve_paths(self, manifest: AutomationManifest) -> Tuple[Path, Path] | ExecutionResult:
        work_dir = (self.project_root / manifest.working_dir).resolve()
        try:
            self.policy.validate_path(work_dir)
        except PolicyViolation as pv:
            return self._fail(manifest.id, "denied", -5, str(pv))

        script_path = (self.project_root / manifest.entry_point).resolve()
        try:
            self.policy.validate_path(script_path)
        except PolicyViolation as pv:
            return self._fail(manifest.id, "denied", -6, str(pv))

        if not script_path.exists():
            return self._fail(manifest.id, "error", -9, f"Entry point script '{script_path}' does not exist.")
        return work_dir, script_path

    @staticmethod
    def _build_command(script_path: Path) -> List[str]:
        suffix = script_path.suffix.lower()
        if suffix == ".py":
            return [sys.executable, str(script_path)]
        if suffix in (".bat", ".cmd"):
            return ["cmd.exe", "/d", "/c", str(script_path)]
        if suffix == ".ps1":
            return [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(script_path),
            ]
        return [str(script_path)]

    def _fingerprints(self, manifest: AutomationManifest) -> List[Dict[str, Any]]:
        cache_policy = manifest.cache_policy or {}
        patterns = cache_policy.get("fingerprint_paths") or []
        fingerprints: List[Dict[str, Any]] = []
        for pattern in patterns:
            try:
                for path in self.project_root.glob(pattern):
                    fingerprints.append(path_fingerprint(path))
            except (OSError, ValueError):
                continue
        return fingerprints

    def _cache_lookup(
        self,
        manifest: AutomationManifest,
        payload: Dict[str, Any],
        fingerprints: List[Dict[str, Any]],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        cache_policy = manifest.cache_policy or {}
        if not self.cache or not cache_policy.get("enabled") or manifest.tier != 0:
            return None, None
        return (
            self.cache.get(manifest.id, payload, manifest.version, fingerprints),
            manifest.id,
        )

    def _cache_store(
        self,
        manifest: AutomationManifest,
        payload: Dict[str, Any],
        result: Dict[str, Any],
        fingerprints: List[Dict[str, Any]],
    ) -> None:
        cache_policy = manifest.cache_policy or {}
        if not self.cache or not cache_policy.get("enabled") or manifest.tier != 0:
            return
        self.cache.set(
            manifest.id,
            payload,
            result,
            ttl=int(cache_policy.get("ttl", 300)),
            version=manifest.version,
            fingerprints=fingerprints,
        )

    def _consecutive_failures(self, automation_id: str, limit: int) -> int:
        failures = 0
        try:
            with db_session(self.db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT status FROM execution_log
                    WHERE automation_id = ? ORDER BY id DESC LIMIT ?
                    """,
                    (automation_id, max(limit, 1)),
                ).fetchall()
        except Exception:
            return 0
        for row in rows:
            if row["status"] in ("error", "timeout"):
                failures += 1
            else:
                break
        return failures

    def _log_execution(
        self,
        automation_id: str,
        duration_ms: int,
        status: str,
        exit_code: int,
        stdout: Optional[str],
        error: Optional[str],
        caller: str,
    ) -> None:
        try:
            with db_session(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO execution_log (automation_id, duration_ms, status, exit_code, stdout_summary, error_summary, caller)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (automation_id, duration_ms, status, exit_code, stdout, error, caller),
                )
        except Exception as exc:
            self._log_file(
                f"execution log write failed for {automation_id}: {exc} "
                f"(status={status}, exit={exit_code}, caller={caller})"
            )

    def _log_file(self, message: str) -> None:
        try:
            logs_dir = self.project_root / ".claude" / "lias" / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            with open(logs_dir / "runner.log", "a", encoding="utf-8") as fh:
                fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n")
        except Exception:
            pass
