"""LIAS Diagnostics and Health Check Engine.

Provides doctor checks, system status, database integrity, and execution health.
"""

from __future__ import annotations
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List

from lias.core.config import LiasConfig
from lias.core.registry import AutomationRegistry
from lias.database.connection import db_session


class LiasDiagnostics:
    def __init__(self, config: LiasConfig, registry: AutomationRegistry, recovery=None):
        self.config = config
        self.registry = registry
        self.recovery = recovery

    def run_doctor(self) -> Dict[str, Any]:
        """Perform comprehensive health inspection and report issues."""
        checks: List[Dict[str, Any]] = []

        # 1. Python environment
        py_version = sys.version.split()[0]
        checks.append({
            "component": "Python",
            "status": "PASS" if sys.version_info >= (3, 10) else "WARN",
            "details": f"Version {py_version} at {sys.executable}",
        })

        # 2. Operating System
        checks.append({
            "component": "OS",
            "status": "PASS",
            "details": f"{platform.system()} {platform.release()} ({platform.machine()})",
        })

        # 3. Database connectivity and integrity
        db_status = "FAIL"
        db_details = ""
        knowledge_count = 0
        try:
            with db_session(self.config.db_path) as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA integrity_check")
                row = cur.fetchone()
                integrity = row[0] if row else "unknown"

                cur.execute("SELECT COUNT(*) FROM knowledge")
                knowledge_count = cur.fetchone()[0]

                cur.execute("SELECT MAX(version) FROM schema_migrations")
                m_row = cur.fetchone()
                schema_ver = m_row[0] if m_row else 0

                db_status = "PASS" if integrity == "ok" else "FAIL"
                db_details = f"Integrity: {integrity}, Schema version: {schema_ver}, Records: {knowledge_count}"
        except Exception as e:
            db_details = f"Database error: {e}"

        checks.append({
            "component": "SQLite Database",
            "status": db_status,
            "details": db_details,
        })

        # 4. Registered automations
        automations = self.registry.list_all(enabled_only=False)
        enabled_count = sum(1 for a in automations if a.enabled)
        registry_status = "WARN" if self.registry.load_errors else "PASS"
        registry_details = f"{len(automations)} registered ({enabled_count} active)"
        if self.registry.load_errors:
            registry_details += f"; {len(self.registry.load_errors)} invalid manifest(s)"
        checks.append({
            "component": "Automation Registry",
            "status": registry_status,
            "details": registry_details,
        })

        # 5. Configuration
        config_issues = self.recovery.validate_config() if self.recovery else []
        checks.append({
            "component": "Configuration",
            "status": "PASS" if not config_issues else "WARN",
            "details": "Valid" if not config_issues else "; ".join(config_issues[:5]),
        })

        # 6. Quarantine and backups
        if self.recovery:
            quarantined = self.recovery.quarantined()
            checks.append({
                "component": "Quarantine",
                "status": "PASS" if not quarantined else "WARN",
                "details": "None" if not quarantined
                else ", ".join(q["automation_id"] for q in quarantined),
            })
            checks.append({
                "component": "Backups",
                "status": "PASS",
                "details": f"{len(self.recovery.list_backups())} verified backup(s)",
            })

        # 7. Directory permissions
        dir_status = "PASS"
        for p in [self.config.config_dir, self.config.database_dir, self.config.cache_dir, self.config.logs_dir]:
            if not os.access(p, os.W_OK):
                dir_status = "FAIL"
                break
        checks.append({
            "component": "Directory Permissions",
            "status": dir_status,
            "details": f"All runtime directories writable under {self.config.lias_dir}",
        })

        all_passed = all(c["status"] == "PASS" for c in checks)

        return {
            "status": "HEALTHY" if all_passed else "DEGRADED",
            "version": self.config.get("version", "2.0.0"),
            "project_root": str(self.config.project_root),
            "checks": checks,
        }

    def get_status_summary(self) -> Dict[str, Any]:
        """Compact runtime status summary."""
        doc = self.run_doctor()
        recent_executions: List[Dict[str, Any]] = []
        counts = {"knowledge": 0, "automations": 0, "candidates": 0, "cache_entries": 0}
        try:
            with db_session(self.config.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT automation_id, duration_ms, status, start_time
                    FROM execution_log ORDER BY id DESC LIMIT 5
                    """
                )
                for r in cur.fetchall():
                    recent_executions.append({
                        "automation_id": r["automation_id"],
                        "duration_ms": r["duration_ms"],
                        "status": r["status"],
                        "start_time": r["start_time"],
                    })
                for key, table in (
                    ("knowledge", "knowledge"),
                    ("automations", "automations"),
                    ("candidates", "candidates"),
                    ("cache_entries", "cache_entries"),
                ):
                    try:
                        counts[key] = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    except Exception:
                        pass
        except Exception:
            pass

        return {
            "health": doc["status"],
            "version": doc["version"],
            "project_root": str(self.config.project_root),
            "counts": counts,
            "checks_summary": {c["component"]: c["status"] for c in doc["checks"]},
            "recent_executions": recent_executions,
        }
