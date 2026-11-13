"""LIAS Core Configuration module.

Handles project root resolution, project isolation, and runtime settings.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "version": "2.0.0",
    "project_name": "RobinLabs",
    "runner": {
        "default_timeout_seconds": 30,
        "max_output_bytes": 100000,
        "max_memory_mb": 512,
    },
    "retrieval": {
        "max_results": 5,
        "max_context_chars": 4000,
        "min_relevance_score": 0.2,
    },
    "learning": {
        "auto_learn_facts": True,
        "require_verification_above_tier": 0,
        "promotion_frequency_threshold": 3,
        "promotion_estimated_token_savings": 500,
    },
    "cache": {
        "enabled": True,
        "default_ttl_seconds": 3600,
        "max_cache_entries": 1000,
    },
    "security": {
        "tier0_auto_exec": True,
        "tier1_auto_exec": True,
        "tier2_auto_exec": False,
        "allow_network_scripts": False,
    },
    "resource_limits": {
        "max_generated_automations": 50,
        "max_log_mb": 10,
        "max_db_mb": 100,
    }
}


def find_project_root(start_path: Optional[str | Path] = None) -> Path:
    """Find the root directory of the project containing .claude or .git."""
    current = Path(start_path or os.getcwd()).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".claude").exists() or (parent / ".git").exists():
            return parent
    return current


class LiasConfig:
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = (project_root or find_project_root()).resolve()
        self.claude_dir = self.project_root / ".claude"
        self.lias_dir = self.claude_dir / "lias"
        self.config_dir = self.lias_dir / "config"
        self.config_file = self.config_dir / "settings.json"
        self.database_dir = self.lias_dir / "database"
        self.cache_dir = self.lias_dir / "cache"
        self.logs_dir = self.lias_dir / "logs"
        self.backups_dir = self.lias_dir / "backups"
        self.automation_dir = self.lias_dir / "automation"
        self.scripts_dir = self.automation_dir / "scripts"
        self.generated_dir = self.automation_dir / "generated"
        self.manifests_dir = self.automation_dir / "manifests"

        self._settings: Dict[str, Any] = {}
        self.ensure_directories()
        self.load()

    def ensure_directories(self) -> None:
        """Create necessary project-local runtime directories."""
        for path in [
            self.config_dir,
            self.database_dir,
            self.cache_dir,
            self.logs_dir,
            self.backups_dir,
            self.scripts_dir,
            self.generated_dir,
            self.manifests_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Load configuration from disk or initialize with defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    user_cfg = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                for k, v in user_cfg.items():
                    if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                        merged[k] = {**merged[k], **v}
                    else:
                        merged[k] = v
                self._settings = merged
                return self._settings
            except Exception:
                self._settings = DEFAULT_CONFIG.copy()
        else:
            self._settings = DEFAULT_CONFIG.copy()
            self.save()
        return self._settings

    def save(self) -> None:
        """Save configuration to disk atomically."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        temp_file = self.config_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=2)
        temp_file.replace(self.config_file)

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self.save()

    @property
    def db_path(self) -> Path:
        return self.database_dir / "lias.sqlite3"
