"""LIAS Knowledge Storage Engine.

Provides persistent, project-local knowledge management with SQLite and FTS5 indexing.
"""

from __future__ import annotations
import datetime
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.database.connection import db_session
from lias.core.policy import PolicyEngine


@dataclass
class KnowledgeRecord:
    id: str
    category: str
    content: str
    provenance: str
    confidence: float = 1.0
    verified: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    project_id: str = "RobinLabs"
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _project_root_for(db_path: Path) -> Path:
    """Resolve the project root from a database path without relying on cwd."""
    current = db_path.resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".claude").is_dir() or (parent / ".git").exists():
            return parent
    # Fallback: <root>/.claude/lias/database/<db>
    return db_path.resolve().parents[3]


class KnowledgeStore:
    def __init__(
        self,
        db_path: Path,
        project_id: str = "RobinLabs",
        project_root: Optional[Path] = None,
    ):
        self.db_path = db_path
        self.project_id = project_id
        self.policy = PolicyEngine(project_root=project_root or _project_root_for(db_path))

    def _generate_id(self, category: str, content: str) -> str:
        h = hashlib.sha256(f"{category}:{content.strip().lower()}".encode("utf-8")).hexdigest()[:12]
        slug = category.lower().replace(" ", "_")[:12]
        return f"{slug}_{h}"

    def add(
        self,
        category: str,
        content: str,
        provenance: str,
        confidence: float = 1.0,
        verified: bool = True,
        expires_at: Optional[str] = None,
        custom_id: Optional[str] = None,
        on_secret: str = "redact",
    ) -> KnowledgeRecord:
        """Add or update a knowledge record safely.

        ``on_secret`` controls handling of detected credentials: ``redact``
        (default) removes them before persistence, ``reject`` refuses the write.
        """
        clean_content, had_secrets = self.policy.scrub_secrets(content)
        if had_secrets and on_secret == "reject":
            raise ValueError("Knowledge content contains sensitive credentials and was rejected.")
        record_id = custom_id or self._generate_id(category, clean_content)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        action = "update"

        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, version FROM knowledge WHERE id = ?", (record_id,))
            existing = cur.fetchone()
            if existing:
                action = "update"
                new_version = existing["version"] + 1
                cur.execute(
                    """
                    UPDATE knowledge
                    SET category = ?, content = ?, provenance = ?, confidence = ?,
                        verified = ?, updated_at = ?, expires_at = ?, version = ?
                    WHERE id = ?
                    """,
                    (
                        category,
                        clean_content,
                        provenance,
                        confidence,
                        1 if verified else 0,
                        now_iso,
                        expires_at,
                        new_version,
                        record_id,
                    ),
                )
                version = new_version
            else:
                action = "create"
                version = 1
                cur.execute(
                    """
                    INSERT INTO knowledge (id, category, content, provenance, confidence, verified, created_at, updated_at, expires_at, project_id, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        category,
                        clean_content,
                        provenance,
                        confidence,
                        1 if verified else 0,
                        now_iso,
                        now_iso,
                        expires_at,
                        self.project_id,
                        version,
                    ),
                )

            self._audit(cur, action, record_id, {
                "category": category,
                "provenance": provenance,
                "version": version,
                "secrets_redacted": had_secrets,
            })

        return KnowledgeRecord(
            id=record_id,
            category=category,
            content=clean_content,
            provenance=provenance,
            confidence=confidence,
            verified=verified,
            created_at=now_iso,
            updated_at=now_iso,
            expires_at=expires_at,
            project_id=self.project_id,
            version=version,
        )

    @staticmethod
    def _audit(cur, action: str, entity_id: str, details: Dict[str, Any]) -> None:
        """Append an audit row; never let auditing break the primary write."""
        try:
            cur.execute(
                """
                INSERT INTO audit_log (action, entity_type, entity_id, details_json)
                VALUES (?, 'knowledge', ?, ?)
                """,
                (action, entity_id, json.dumps(details)),
            )
        except Exception:
            pass

    def get(self, record_id: str) -> Optional[KnowledgeRecord]:
        """Retrieve a specific record by its ID."""
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM knowledge WHERE id = ?", (record_id,))
            row = cur.fetchone()
            if not row:
                return None
            return KnowledgeRecord(
                id=row["id"],
                category=row["category"],
                content=row["content"],
                provenance=row["provenance"],
                confidence=row["confidence"],
                verified=bool(row["verified"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                expires_at=row["expires_at"],
                project_id=row["project_id"],
                version=row["version"],
            )

    def delete(self, record_id: str) -> bool:
        """Delete a record by ID and record the action in the audit log."""
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM knowledge WHERE id = ?", (record_id,))
            deleted = cur.rowcount > 0
            if deleted:
                self._audit(cur, "delete", record_id, {})
            return deleted

    def list_all(
        self,
        category: Optional[str] = None,
        only_verified: bool = True,
        limit: int = 50,
    ) -> List[KnowledgeRecord]:
        """List knowledge records with optional filters."""
        query = "SELECT * FROM knowledge WHERE 1=1"
        params: List[Any] = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if only_verified:
            query += " AND verified = 1"
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        records: List[KnowledgeRecord] = []
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            for row in cur.fetchall():
                records.append(
                    KnowledgeRecord(
                        id=row["id"],
                        category=row["category"],
                        content=row["content"],
                        provenance=row["provenance"],
                        confidence=row["confidence"],
                        verified=bool(row["verified"]),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        expires_at=row["expires_at"],
                        project_id=row["project_id"],
                        version=row["version"],
                    )
                )
        return records

    def purge_expired(self) -> int:
        """Purge records past their expires_at timestamp."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM knowledge WHERE expires_at IS NOT NULL AND expires_at < ?", (now_iso,))
            return cur.rowcount
