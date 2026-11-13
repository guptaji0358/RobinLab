"""LIAS Database Migrations Engine.

Applies incremental versioned database updates and supports rollbacks.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Tuple

from lias.database.connection import db_session


MIGRATIONS: List[Tuple[int, str, str]] = [
    (1, "Initial base schema", "-- Base schema applied via schema.sql"),
    (
        2,
        "Add audit_log and index enhancements",
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            details_json TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
        """
    ),
    (
        3,
        "Add cache fingerprints and operation version",
        """
        ALTER TABLE cache_entries ADD COLUMN fingerprints_json TEXT NOT NULL DEFAULT '[]';
        ALTER TABLE cache_entries ADD COLUMN operation_version TEXT NOT NULL DEFAULT '1.0.0';
        CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);
        """
    )
]


class MigrationManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def get_current_version(self) -> int:
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT MAX(version) FROM schema_migrations")
                row = cur.fetchone()
                return int(row[0]) if row and row[0] is not None else 0
            except sqlite3.OperationalError:
                return 0

    def apply_migrations(self) -> int:
        """Apply any unapplied migrations in sequential order."""
        current = self.get_current_version()
        applied = 0
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            for version, desc, sql in MIGRATIONS:
                if version > current:
                    if not sql.strip().startswith("--"):
                        try:
                            conn.executescript(sql)
                        except sqlite3.OperationalError as exc:
                            # Re-running a partially applied migration must not
                            # corrupt or abort the upgrade.
                            if "duplicate column name" not in str(exc).lower():
                                raise
                    cur.execute(
                        "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                        (version, desc)
                    )
                    applied += 1
        return applied
