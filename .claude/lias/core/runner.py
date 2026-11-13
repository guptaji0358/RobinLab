"""LIAS Local Automation Runner.

Executes automations with timeout protection, bounded output,
execution logging, and strict error handling.
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.core.policy import PolicyEngine, PolicyViolation, SecurityTier
from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.database.connection import db_session


@dataclass
class ExecutionResult:
    automation_id: str
    status: str  # 'success', 'error', 'timeout', 'denied'
    duration_ms: int
    exit_code: int
    result: Dict[str, Any]
    warnings: List[str]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "result": self.result,
            "warnings": self.warnings,
            "error": self.error,
        }


class LocalRunner:
    def __init__(
        self,
        project_root: Path,
        registry: AutomationRegistry,
        policy: PolicyEngine,
        db_path: Path,
        max_output_bytes: int = 100000,
    ):
        self.project_root = project_root.resolve()
        self.registry = registry
        self.policy = policy
        self.db_path = db_path
        self.max_output_bytes = max_output_bytes

    def run(
        self,
        automation_id: str,
        input_data: Optional[Dict[str, Any]] = None,
        caller: str = "cli",
    ) -> ExecutionResult:
        """Run an automation by ID within policy constraints and timeouts."""
        manifest = self.registry.get(automation_id)
        if not manifest:
            return ExecutionResult(
                automation_id=automation_id,
                status="error",
                duration_ms=0,
                exit_code=-1,
                result={},
                warnings=[],
                error=f"Automation '{automation_id}' not found in registry.",
            )

        if not manifest.enabled:
            return ExecutionResult(
                automation_id=automation_id,
                status="denied",
                duration_ms=0,
                exit_code=-2,
                result={},
                warnings=[],
                error=f"Automation '{automation_id}' is currently disabled.",
            )

        # Policy tier authorization check
        if not self.policy.can_auto_execute(manifest.tier):
            return ExecutionResult(
                automation_id=automation_id,
                status="denied",
                duration_ms=0,
                exit_code=-3,
                result={},
                warnings=[],
                error=f"Automation '{automation_id}' requires Tier {manifest.tier} authorization.",
            )

        # Determine target working directory
        work_dir = (self.project_root / manifest.working_dir).resolve()
        try:
            self.policy.validate_path(work_dir)
        except PolicyViolation as pv:
            return ExecutionResult(
                automation_id=automation_id,
                status="denied",
                duration_ms=0,
                exit_code=-4,
                result={},
                warnings=[],
                error=str(pv),
            )

        # Determine script entry point
        script_path = (self.project_root / manifest.entry_point).resolve()
        try:
            self.policy.validate_path(script_path)
        except PolicyViolation as pv:
            return ExecutionResult(
                automation_id=automation_id,
                status="denied",
                duration_ms=0,
                exit_code=-5,
                result={},
                warnings=[],
                error=str(pv),
            )

        if not script_path.exists():
            return ExecutionResult(
                automation_id=automation_id,
                status="error",
                duration_ms=0,
                exit_code=-6,
                result={},
                warnings=[],
                error=f"Entry point script '{script_path}' does not exist.",
            )

        # Prepare invocation command safely as a list
        if script_path.suffix.lower() == ".py":
            cmd = [sys.executable, str(script_path)]
        elif script_path.suffix.lower() in [".bat", ".cmd"]:
            cmd = [str(script_path)]
        elif script_path.suffix.lower() == ".ps1":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
        else:
            cmd = [str(script_path)]

        # Serialize inputs as JSON payload via stdin or argument
        payload = json.dumps(input_data or {})
        start_time = time.perf_counter()
        timeout = manifest.timeout_seconds or 30

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
            stdout, stderr = proc.communicate(input=payload, timeout=timeout)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            exit_code = proc.returncode

            # Bound output size
            if len(stdout) > self.max_output_bytes:
                stdout = stdout[: self.max_output_bytes] + "... [TRUNCATED]"

            warnings: List[str] = []
            if stderr:
                warnings.append(stderr.strip()[:1000])

            parsed_result: Dict[str, Any] = {}
            error_msg: Optional[str] = None

            if exit_code == 0:
                # Try parsing JSON output if script emitted JSON
                try:
                    parsed_result = json.loads(stdout.strip())
                except Exception:
                    parsed_result = {"output": stdout.strip()}
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

        # Record in execution log
        self._log_execution(
            automation_id=automation_id,
            duration_ms=duration_ms,
            status=status,
            exit_code=exit_code,
            stdout=str(parsed_result)[:500],
            error=error_msg[:500] if error_msg else None,
            caller=caller,
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
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO execution_log (automation_id, duration_ms, status, exit_code, stdout_summary, error_summary, caller)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (automation_id, duration_ms, status, exit_code, stdout, error, caller),
                )
        except Exception:
            pass
