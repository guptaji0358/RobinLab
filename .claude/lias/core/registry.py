"""LIAS Automation Registry.

Manages registered automation manifests, validates schemas, and tracks active automations.
"""

from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.database.connection import db_session


@dataclass
class AutomationManifest:
    id: str
    name: str
    description: str
    tier: int = 0
    entry_point: str = ""
    enabled: bool = True
    version: str = "1.0.0"
    timeout_seconds: int = 30
    working_dir: str = "."
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    cache_policy: Dict[str, Any] = field(default_factory=lambda: {"enabled": True, "ttl": 3600})
    failure_policy: Dict[str, Any] = field(default_factory=lambda: {"max_retries": 1, "quarantine_on_failures": 3})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutomationRegistry:
    def __init__(self, manifests_dir: Path, db_path: Path):
        self.manifests_dir = manifests_dir
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.sync_from_disk()

    def sync_from_disk(self) -> int:
        """Load any JSON manifests on disk into the database."""
        count = 0
        for f in self.manifests_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                manifest = AutomationManifest(**data)
                self.register(manifest)
                count += 1
            except Exception:
                continue
        return count

    def register(self, manifest: AutomationManifest) -> None:
        """Register an automation manifest in disk JSON and the SQLite database."""
        manifest_file = self.manifests_dir / f"{manifest.id}.json"
        manifest_data = manifest.to_dict()

        # Atomic file write
        temp_file = manifest_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        temp_file.replace(manifest_file)

        # Database record update
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO automations (id, name, description, tier, entry_point, enabled, version, timeout_seconds, manifest_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    tier = excluded.tier,
                    entry_point = excluded.entry_point,
                    enabled = excluded.enabled,
                    version = excluded.version,
                    timeout_seconds = excluded.timeout_seconds,
                    manifest_json = excluded.manifest_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    manifest.id,
                    manifest.name,
                    manifest.description,
                    manifest.tier,
                    manifest.entry_point,
                    1 if manifest.enabled else 0,
                    manifest.version,
                    manifest.timeout_seconds,
                    json.dumps(manifest_data),
                ),
            )

    def get(self, automation_id: str) -> Optional[AutomationManifest]:
        """Fetch automation manifest by ID."""
        manifest_file = self.manifests_dir / f"{automation_id}.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AutomationManifest(**data)
            except Exception:
                pass

        # Fallback to DB
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT manifest_json FROM automations WHERE id = ?", (automation_id,))
            row = cur.fetchone()
            if row:
                data = json.loads(row["manifest_json"])
                return AutomationManifest(**data)
        return None

    def list_all(self, enabled_only: bool = True) -> List[AutomationManifest]:
        """List all automations."""
        results: List[AutomationManifest] = []
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            query = "SELECT manifest_json FROM automations"
            if enabled_only:
                query += " WHERE enabled = 1"
            cur.execute(query)
            for row in cur.fetchall():
                try:
                    data = json.loads(row["manifest_json"])
                    results.append(AutomationManifest(**data))
                except Exception:
                    continue
        return results

    def set_enabled(self, automation_id: str, enabled: bool) -> bool:
        """Enable or disable an automation."""
        manifest = self.get(automation_id)
        if not manifest:
            return False
        manifest.enabled = enabled
        self.register(manifest)
        return True
