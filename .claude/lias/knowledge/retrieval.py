"""LIAS Knowledge Retrieval Engine.

Multi-stage retrieval with progressive disclosure:

1. exact phrase match
2. per-token keyword match
3. FTS5 full-text search (quoted terms, safely escaped)

Only verified, non-expired records are returned by default. Results are
deduplicated, relevance-filtered and capped by a context-character budget.
"""

from __future__ import annotations
import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.database.connection import db_session
from lias.knowledge.store import KnowledgeRecord


STOP_WORDS = {
    "a", "an", "the", "about", "for", "with", "in", "on", "at", "by", "from",
    "to", "of", "and", "or", "is", "are", "was", "were", "what", "where", "how",
    "can", "you", "me", "this", "that", "these", "those", "have", "has", "had",
    "do", "does", "did", "please", "show", "tell", "run", "use", "our",
}


@dataclass
class SearchResult:
    record: KnowledgeRecord
    score: float
    match_type: str  # 'exact', 'keyword', 'fts5'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.record.id,
            "category": self.record.category,
            "content": self.record.content,
            "provenance": self.record.provenance,
            "confidence": self.record.confidence,
            "verified": self.record.verified,
            "expires_at": self.record.expires_at,
            "score": round(self.score, 3),
            "match_type": self.match_type,
            "version": self.record.version,
        }


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _row_to_record(row) -> KnowledgeRecord:
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


class KnowledgeRetrieval:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @staticmethod
    def _normalize_query(query: str) -> str:
        # Strip characters that break SQLite LIKE/FTS5 query syntax.
        clean = re.sub(r"[^\w\s\-_]", " ", query.strip())
        return " ".join(clean.split())

    @staticmethod
    def _tokens(normalized: str) -> List[str]:
        return [
            t for t in re.split(r"[\s_\-]+", normalized.lower())
            if len(t) > 2 and t not in STOP_WORDS
        ]

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 5,
        max_context_chars: int = 3000,
        min_score: float = 0.2,
        include_unverified: bool = False,
        include_expired: bool = False,
        project_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Perform multi-stage search with progressive disclosure and budget caps."""
        normalized = self._normalize_query(query)
        if not normalized:
            return []

        results: List[SearchResult] = []
        seen_ids: set[str] = set()
        now = _now_iso()

        # Build the common validity filter once.
        filters = ["1=1"]
        fts_filters = ["1=1"]
        base_params: List[Any] = []
        fts_params: List[Any] = []
        if category:
            filters.append("category = ?")
            fts_filters.append("k.category = ?")
            base_params.append(category)
            fts_params.append(category)
        if not include_unverified:
            filters.append("verified = 1")
            fts_filters.append("k.verified = 1")
        if not include_expired:
            filters.append("(expires_at IS NULL OR expires_at > ?)")
            fts_filters.append("(k.expires_at IS NULL OR k.expires_at > ?)")
            base_params.append(now)
            fts_params.append(now)
        if project_id:
            filters.append("project_id = ?")
            fts_filters.append("k.project_id = ?")
            base_params.append(project_id)
            fts_params.append(project_id)
        where_clause = " AND ".join(filters)
        fts_where_clause = " AND ".join(fts_filters)

        with db_session(self.db_path) as conn:
            cur = conn.cursor()

            # Stage 1: exact phrase substring match.
            cur.execute(
                f"""
                SELECT * FROM knowledge
                WHERE {where_clause} AND (content LIKE ? OR category LIKE ?)
                ORDER BY updated_at DESC LIMIT ?
                """,
                (*base_params, f"%{normalized}%", f"%{normalized}%", max_results),
            )
            for row in cur.fetchall():
                rec = _row_to_record(row)
                seen_ids.add(rec.id)
                results.append(SearchResult(record=rec, score=1.0, match_type="exact"))

            # Stage 2: per-token keyword match, scored by token coverage.
            tokens = self._tokens(normalized)
            if tokens and len(results) < max_results:
                token_clauses = " OR ".join(
                    ["content LIKE ? OR category LIKE ?" for _ in tokens]
                )
                token_params: List[Any] = []
                for tok in tokens:
                    token_params.extend([f"%{tok}%", f"%{tok}%"])
                cur.execute(
                    f"""
                    SELECT * FROM knowledge
                    WHERE {where_clause} AND ({token_clauses})
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (*base_params, *token_params, max_results * 2),
                )
                for row in cur.fetchall():
                    rec = _row_to_record(row)
                    if rec.id in seen_ids:
                        continue
                    haystack = f"{rec.category} {rec.content}".lower()
                    hits = sum(1 for tok in tokens if tok in haystack)
                    if hits == 0:
                        continue
                    coverage = hits / len(tokens)
                    seen_ids.add(rec.id)
                    results.append(
                        SearchResult(
                            record=rec,
                            score=round(0.45 + 0.45 * coverage, 3),
                            match_type="keyword",
                        )
                    )

            # Stage 3: FTS5 full-text match for ranking beyond literal substrings.
            if tokens and len(results) < max_results:
                fts_query = " OR ".join(f'"{tok}"' for tok in tokens)
                try:
                    cur.execute(
                        f"""
                        SELECT k.*, f.rank AS fts_rank
                        FROM knowledge_fts f
                        JOIN knowledge k ON f.id = k.id
                        WHERE knowledge_fts MATCH ? AND {fts_where_clause}
                        ORDER BY f.rank LIMIT ?
                        """,
                        (fts_query, *fts_params, max_results * 2),
                    )
                    for row in cur.fetchall():
                        rec = _row_to_record(row)
                        if rec.id in seen_ids:
                            continue
                        seen_ids.add(rec.id)
                        # bm25 rank is negative; closer to 0 means a better match.
                        rank_val = abs(float(row["fts_rank"]))
                        score = max(0.2, 1.0 / (1.0 + rank_val))
                        results.append(
                            SearchResult(record=rec, score=score, match_type="fts5")
                        )
                except Exception:
                    # FTS5 is an optimisation; keyword search above still works.
                    pass

        # Relevance filter and deterministic ordering.
        results = [r for r in results if r.score >= min_score]
        results.sort(key=lambda r: (-r.score, r.match_type != "exact", r.record.id))

        # Apply context budget.
        budget_results: List[SearchResult] = []
        char_count = 0
        for r in results:
            content_len = len(r.record.content)
            if budget_results and char_count + content_len > max_context_chars:
                continue
            char_count += content_len
            budget_results.append(r)
            if len(budget_results) >= max_results:
                break

        return budget_results

    def get_by_category(self, category: str, limit: int = 20) -> List[KnowledgeRecord]:
        """List fresh, verified records in a category (newest first)."""
        with db_session(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM knowledge
                WHERE category = ? AND verified = 1
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY updated_at DESC LIMIT ?
                """,
                (category, _now_iso(), limit),
            ).fetchall()
        return [_row_to_record(r) for r in rows]
