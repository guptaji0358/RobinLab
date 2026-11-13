"""LIAS Candidate Manager.

Records candidate facts observed during interactions and manages automatic
promotion into persistent knowledge when validation and frequency criteria are met.
"""

from __future__ import annotations
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.database.connection import db_session
from lias.knowledge.store import KnowledgeRecord, KnowledgeStore
from lias.knowledge.validation import KnowledgeValidator


@dataclass
class CandidateRecord:
    id: str
    workflow_pattern: str
    frequency: int
    estimated_savings: int
    risk_tier: int
    status: str  # 'observed', 'approved', 'promoted', 'quarantined'
    metadata: Dict[str, Any]


class CandidateManager:
    def __init__(self, db_path: Path, store: KnowledgeStore):
        self.db_path = db_path
        self.store = store
        self.validator = KnowledgeValidator(store)

    def record_candidate(
        self,
        pattern: str,
        category: str = "observation",
        estimated_savings: int = 150,
        risk_tier: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CandidateRecord:
        """Record or increment occurrence of an observed pattern or candidate."""
        meta = dict(metadata or {})
        meta["category"] = category

        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, frequency, status, metadata_json FROM candidates WHERE workflow_pattern = ?", (pattern,))
            row = cur.fetchone()

            if row:
                candidate_id = row["id"]
                new_freq = row["frequency"] + 1
                try:
                    merged_meta = json.loads(row["metadata_json"] or "{}")
                except Exception:
                    merged_meta = {}
                merged_meta.update(meta)
                cur.execute(
                    """
                    UPDATE candidates
                    SET frequency = ?, estimated_savings = ?, risk_tier = ?, metadata_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (new_freq, estimated_savings, risk_tier, json.dumps(merged_meta), candidate_id),
                )
                status = row["status"]
                meta = merged_meta
            else:
                candidate_id = f"cand_{uuid.uuid4().hex[:10]}"
                new_freq = 1
                status = "observed"
                cur.execute(
                    """
                    INSERT INTO candidates (id, workflow_pattern, frequency, estimated_savings, risk_tier, status, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (candidate_id, pattern, 1, estimated_savings, risk_tier, status, json.dumps(meta)),
                )

        return CandidateRecord(
            id=candidate_id,
            workflow_pattern=pattern,
            frequency=new_freq,
            estimated_savings=estimated_savings,
            risk_tier=risk_tier,
            status=status,
            metadata=meta,
        )

    def evaluate_and_promote(self, candidate_id: str, min_frequency: int = 2) -> Optional[KnowledgeRecord]:
        """Evaluate candidate and automatically promote to knowledge store if valid."""
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = cur.fetchone()

        if not row:
            return None

        pattern = row["workflow_pattern"]
        freq = row["frequency"]
        status = row["status"]
        meta = json.loads(row["metadata_json"] or "{}")
        category = meta.get("category", "observation")

        # Already promoted or quarantined: never re-promote automatically.
        if status in ("promoted", "quarantined"):
            return None
        if freq < min_frequency:
            return None

        # Validate before promotion
        val_result = self.validator.validate_candidate(category=category, content=pattern)
        if not val_result.is_valid:
            with db_session(self.db_path) as conn:
                conn.execute("UPDATE candidates SET status = 'quarantined' WHERE id = ?", (candidate_id,))
            return None

        # Promote to knowledge outside the candidate transaction to avoid
        # holding a write lock on the same database file.
        rec = self.store.add(
            category=category,
            content=pattern,
            provenance=f"promoted_candidate:{candidate_id}",
            confidence=0.95,
            verified=True,
            on_secret="reject",
        )

        with db_session(self.db_path) as conn:
            conn.execute(
                "UPDATE candidates SET status = 'promoted', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (candidate_id,),
            )
        return rec

    def list_candidates(self, status: Optional[str] = None) -> List[CandidateRecord]:
        """List recorded candidates."""
        query = "SELECT * FROM candidates"
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY frequency DESC"

        candidates: List[CandidateRecord] = []
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            for r in cur.fetchall():
                candidates.append(
                    CandidateRecord(
                        id=r["id"],
                        workflow_pattern=r["workflow_pattern"],
                        frequency=r["frequency"],
                        estimated_savings=r["estimated_savings"],
                        risk_tier=r["risk_tier"],
                        status=r["status"],
                        metadata=json.loads(r["metadata_json"] or "{}"),
                    )
                )
        return candidates
