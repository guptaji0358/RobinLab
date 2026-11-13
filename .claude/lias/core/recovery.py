"""LIAS Self-Healing and Recovery.

Bounded, explicit recovery operations: verified database backups, restore with
rollback, integrity checks, configuration validation, quarantine release,
interrupted-write cleanup and log rotation. Nothing here installs packages,
touches unrelated project files or runs unattended in the background.
"""

from __future__ import annotations
import datetime
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.core.config import DEFAULT_CONFIG, LiasConfig
from lias.core.registry import AutomationRegistry
from lias.database.connection import db_session, get_db_connection


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class RecoveryManager:
    MAX_BACKUPS = 10

    def __init__(self, config: LiasConfig, registry: AutomationRegistry):
        self.config = config
        self.registry = registry
        self.backups_dir = config.backups_dir
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------- backups
    def backup(self, reason: str = "manual") -> Path:
        """Create a consistent SQLite backup using the online backup API."""
        safe_reason = "".join(c for c in reason if c.isalnum() or c in "-_")[:32] or "manual"
        target = self.backups_dir / f"lias-{_timestamp()}-{safe_reason}.sqlite3"
        source = get_db_connection(self.config.db_path)
        dest = sqlite3.connect(str(target))
        try:
            source.backup(dest)
            dest.commit()
        finally:
            dest.close()
            source.close()
        self._prune_backups()
        return target

    def _prune_backups(self) -> None:
        backups = sorted(self.backups_dir.glob("lias-*.sqlite3"))
        for old in backups[: max(0, len(backups) - self.MAX_BACKUPS)]:
            try:
                old.unlink()
            except OSError:
                pass

    def list_backups(self) -> List[Dict[str, Any]]:
        items = []
        for path in sorted(self.backups_dir.glob("lias-*.sqlite3")):
            stat = path.stat()
            items.append(
                {
                    "path": str(path),
                    "bytes": stat.st_size,
                    "created_at": datetime.datetime.fromtimestamp(
                        stat.st_mtime, datetime.timezone.utc
                    ).isoformat(),
                }
            )
        return items

    def restore(self, backup_path: Path) -> Path:
        """Restore a verified backup, keeping a safety copy of current state."""
        backup_path = Path(backup_path).resolve()
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        if self.backups_dir.resolve() not in backup_path.parents:
            raise ValueError("Restore is restricted to the LIAS backups directory.")

        ok, details = self._integrity_of(backup_path)
        if not ok:
            raise ValueError(f"Backup failed integrity check: {details}")

        safety = self.backup("pre-restore")
        source = get_db_connection(backup_path)
        dest = get_db_connection(self.config.db_path)
        try:
            source.backup(dest)
            dest.commit()
        finally:
            dest.close()
            source.close()
        return safety

    # ------------------------------------------------------------ integrity
    @staticmethod
    def _integrity_of(db_path: Path) -> tuple[bool, str]:
        try:
            conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
            finally:
                conn.close()
            if integrity != "ok":
                return False, f"integrity_check={integrity}"
            if fk:
                return False, f"foreign_key_check reported {len(fk)} issues"
            return True, "ok"
        except Exception as exc:
            return False, str(exc)

    def integrity_check(self) -> Dict[str, Any]:
        ok, details = self._integrity_of(self.config.db_path)
        size_mb = self.config.db_path.stat().st_size / (1024 * 1024) if self.config.db_path.exists() else 0
        with db_session(self.config.db_path) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            ]
            cache_entries = 0
            try:
                cache_entries = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
            except sqlite3.OperationalError:
                pass
        return {
            "ok": ok,
            "details": details,
            "db_bytes": int(size_mb * 1024 * 1024),
            "db_mb": round(size_mb, 2),
            "max_db_mb": self.config.get("resource_limits", {}).get("max_db_mb", 100),
            "over_size_limit": size_mb > self.config.get("resource_limits", {}).get("max_db_mb", 100),
            "tables": tables,
            "cache_entries": cache_entries,
        }

    # ---------------------------------------------------------------- config
    def validate_config(self) -> List[str]:
        return validate_settings(self.config.load())

    # ------------------------------------------------------------ quarantine
    def quarantined(self) -> List[Dict[str, Any]]:
        items = []
        for manifest in self.registry.list_all(enabled_only=False):
            if manifest.enabled:
                continue
            last_error = None
            with db_session(self.config.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT status, error_summary, start_time FROM execution_log
                    WHERE automation_id = ? ORDER BY id DESC LIMIT 1
                    """,
                    (manifest.id,),
                ).fetchone()
                if row:
                    last_error = {
                        "status": row["status"],
                        "error": row["error_summary"],
                        "at": row["start_time"],
                    }
            items.append(
                {
                    "automation_id": manifest.id,
                    "name": manifest.name,
                    "enabled": manifest.enabled,
                    "last_execution": last_error,
                }
            )
        return items

    def release(self, automation_id: str) -> bool:
        """Re-enable a quarantined automation and reset its failure streak."""
        if not self.registry.set_enabled(automation_id, True):
            return False
        with db_session(self.config.db_path) as conn:
            conn.execute(
                """
                INSERT INTO execution_log
                    (automation_id, duration_ms, status, exit_code, error_summary, caller)
                VALUES (?, 0, 'reset', 0, 'Failure streak reset by recovery', 'recovery:release')
                """,
                (automation_id,),
            )
        return True

    # --------------------------------------------------------------- cleanup
    def cleanup_temp_files(self) -> List[str]:
        """Remove stale LIAS-owned ``*.tmp`` files left by interrupted writes."""
        removed: List[str] = []
        for directory in (
            self.config.config_dir,
            self.config.manifests_dir,
            self.config.database_dir,
            self.config.generated_dir,
        ):
            if not directory.exists():
                continue
            for tmp in directory.glob("*.tmp"):
                try:
                    tmp.unlink()
                    removed.append(str(tmp))
                except OSError:
                    continue
        return removed

    def rotate_logs(self) -> Dict[str, Any]:
        """Archive an oversized runner log instead of deleting evidence."""
        max_mb = self.config.get("resource_limits", {}).get("max_log_mb", 10)
        log_path = self.config.logs_dir / "runner.log"
        rotated = None
        if log_path.exists():
            size_mb = log_path.stat().st_size / (1024 * 1024)
            if size_mb > max_mb:
                archive = self.config.logs_dir / f"runner-{_timestamp()}.log"
                shutil.move(str(log_path), str(archive))
                rotated = str(archive)
        return {"rotated": rotated, "max_log_mb": max_mb}

    def self_check(self) -> Dict[str, Any]:
        return {
            "integrity": self.integrity_check(),
            "config_issues": self.validate_config(),
            "quarantined": self.quarantined(),
            "backups": len(self.list_backups()),
        }


def validate_settings(settings: Dict[str, Any]) -> List[str]:
    """Validate merged settings; returns a list of human-readable issues."""
    issues: List[str] = []
    if not isinstance(settings, dict):
        return ["settings root must be an object"]
    if not isinstance(settings.get("version"), str):
        issues.append("version must be a string")

    defaults = DEFAULT_CONFIG
    for section, default_value in defaults.items():
        if not isinstance(default_value, dict):
            continue
        value = settings.get(section, {})
        if not isinstance(value, dict):
            issues.append(f"{section} must be an object")
            continue
        for key, default in default_value.items():
            if key not in value:
                issues.append(f"missing setting {section}.{key}")
                continue
            actual = value[key]
            if isinstance(default, bool) and not isinstance(actual, bool):
                issues.append(f"{section}.{key} must be a boolean")
            elif isinstance(default, int) and not isinstance(default, bool):
                if not isinstance(actual, int) or actual < 0:
                    issues.append(f"{section}.{key} must be a non-negative integer")
            elif isinstance(default, float) and not isinstance(actual, (int, float)):
                issues.append(f"{section}.{key} must be a number")
            elif isinstance(default, str) and not isinstance(actual, str):
                issues.append(f"{section}.{key} must be a string")

    if settings.get("retrieval", {}).get("max_results", 5) > 50:
        issues.append("retrieval.max_results should be <= 50")
    return issues
