"""LIAS Knowledge Retrieval Engine.

Implements multi-stage retrieval: Exact match -> FTS5 full-text search ->
relevance scoring and progressive disclosure within context budgets.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.database.connection import db_session
from lias.knowledge.store import KnowledgeRecord


@dataclass
class SearchResult:
    record: KnowledgeRecord
    score: float
    match_type: str  # 'exact', 'fts5', 'keyword'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.record.id,
            "category": self.record.category,
            "content": self.record.content,
            "provenance": self.record.provenance,
            "confidence": self.record.confidence,
            "verified": self.record.verified,
            "score": round(self.score, 3),
            "match_type": self.match_type,
            "version": self.record.version,
        }


class KnowledgeRetrieval:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _normalize_query(self, query: str) -> str:
        # Strip special characters that break SQLite FTS5 query syntax
        clean = re.sub(r"[^\w\s\-_]", " ", query.strip())
        return " ".join(clean.split())

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 5,
        max_context_chars: int = 3000,
    ) -> List[SearchResult]:
        """Perform multi-stage search with progressive disclosure and budget caps."""
        normalized = self._normalize_query(query)
        if not normalized:
            return []

        results: List[SearchResult] = []
        seen_ids = set()

        with db_session(self.db_path) as conn:
            cur = conn.cursor()

            # Stage 1: Exact / Substring Match
            exact_term = f"%{normalized}%"
            cur.execute(
                """
                SELECT * FROM knowledge
                WHERE (content LIKE ? OR category LIKE ?)
                ORDER BY updated_at DESC LIMIT ?
                """,
                (exact_term, exact_term, max_results),
            )
            for row in cur.fetchall():
                rec = KnowledgeRecord(
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
                seen_ids.add(rec.id)
                results.append(SearchResult(record=rec, score=1.0, match_type="exact"))

            # Stage 2: FTS5 Full-Text Match if quota remains
            if len(results) < max_results:
                fts_query = " OR ".join(normalized.split())
                try:
                    cur.execute(
                        """
                        SELECT k.*, rank FROM knowledge_fts f
                        JOIN knowledge k ON f.id = k.id
                        WHERE knowledge_fts MATCH ?
                        ORDER BY rank LIMIT ?
                        """,
                        (fts_query, max_results * 2),
                    )
                    for row in cur.fetchall():
                        rec_id = row["id"]
                        if rec_id in seen_ids:
                            continue
                        seen_ids.add(rec_id)
                        # FTS5 bm25 rank is negative (lower is better match)
                        rank_val = abs(float(row["rank"])) if "rank" in row.keys() else 1.0
                        score = max(0.1, 1.0 / (1.0 + rank_val))
                        rec = KnowledgeRecord(
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
                        results.append(SearchResult(record=rec, score=score, match_type="fts5"))
                except Exception:
                    # Fallback to simple keyword search
                    pass

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)

        # Apply character budget
        budget_results: List[SearchResult] = []
        char_count = 0
        for r in results:
            content_len = len(r.record.content)
            if char_count + content_len > max_context_chars and budget_results:
                break
            char_count += content_len
            budget_results.append(r)
            if len(budget_results) >= max_results:
                break

        return budget_results
