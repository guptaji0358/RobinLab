"""LIAS Capability Router.

Deterministic, cheapest-first routing:

1. exact automation id/name
2. automation keyword match
3. verified local knowledge (retrieval handles relevance + freshness)
4. unmatched -> Claude reasoning

The router reports measured local work (duration, result size). It does not
estimate token savings, because that cannot be measured reliably here.
"""

from __future__ import annotations
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.core.runner import ExecutionResult, LocalRunner
from lias.knowledge.retrieval import KnowledgeRetrieval, SearchResult


def normalize_text(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(clean.split())


@dataclass
class RoutedResponse:
    action_type: str  # 'automation', 'knowledge', 'unmatched'
    summary: str
    data: Dict[str, Any]
    duration_ms: int = 0
    result_chars: int = 0


class CapabilityRouter:
    def __init__(
        self,
        registry: AutomationRegistry,
        runner: LocalRunner,
        retrieval: KnowledgeRetrieval,
        max_results: int = 5,
        max_context_chars: int = 4000,
        min_relevance_score: float = 0.2,
        project_id: Optional[str] = None,
    ):
        self.registry = registry
        self.runner = runner
        self.retrieval = retrieval
        self.max_results = max_results
        self.max_context_chars = max_context_chars
        self.min_relevance_score = min_relevance_score
        self.project_id = project_id

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> RoutedResponse:
        """Process intent and dispatch to the most cost-effective local capability."""
        started = time.perf_counter()
        normalized = normalize_text(query)
        if not normalized:
            return self._unmatched(query, started)

        # Step 1: deterministic automation match.
        automation, match_score = self._match_automation(normalized)
        if automation:
            exec_res = self.runner.run(automation.id, input_data=context or {}, caller="router")
            return self._automation_response(automation, exec_res, match_score, started)

        # Step 2: verified knowledge retrieval.
        search_results = self.retrieval.search(
            query,
            max_results=self.max_results,
            max_context_chars=self.max_context_chars,
            min_score=self.min_relevance_score,
            project_id=self.project_id,
        )
        if search_results:
            return self._knowledge_response(query, search_results, started)

        # Step 3: unmatched -> Claude handles reasoning.
        return self._unmatched(query, started)

    # ---------------------------------------------------------------- matching
    def _match_automation(self, normalized_query: str) -> Tuple[Optional[AutomationManifest], float]:
        query_tokens = set(normalized_query.split())
        best: Optional[AutomationManifest] = None
        best_score = 0.0

        for automation in self.registry.list_all(enabled_only=True):
            score = 0.0
            id_norm = normalize_text(automation.id)
            name_norm = normalize_text(automation.name)

            if id_norm and (id_norm == normalized_query or f" {id_norm} " in f" {normalized_query} "):
                score = 1.0

            id_tokens = set(id_norm.split())
            if id_tokens and id_tokens.issubset(query_tokens):
                score = max(score, 0.9)

            if name_norm and f" {name_norm} " in f" {normalized_query} ":
                score = max(score, 0.85)

            keywords = {normalize_text(k).replace(" ", "") for k in automation.keywords}
            keywords = {k for k in keywords if k}
            hits = sum(1 for kw in keywords if kw in normalized_query.replace(" ", ""))
            if hits >= 2 and keywords:
                score = max(score, 0.6 + 0.3 * min(hits / len(keywords), 1.0))

            if score > best_score:
                best_score = score
                best = automation

        if best is not None and best_score >= 0.6:
            return best, round(best_score, 3)
        return None, 0.0

    # --------------------------------------------------------------- responses
    def _automation_response(
        self,
        automation: AutomationManifest,
        exec_res: ExecutionResult,
        match_score: float,
        started: float,
    ) -> RoutedResponse:
        data = exec_res.to_dict()
        data["match_score"] = match_score
        summary = (
            f"Executed local automation '{automation.name}' ({automation.id}) "
            f"with status '{exec_res.status}'"
            + (" from cache" if exec_res.cached else "")
            + "."
        )
        return RoutedResponse(
            action_type="automation",
            summary=summary,
            data=data,
            duration_ms=int((time.perf_counter() - started) * 1000),
            result_chars=len(str(data)),
        )

    def _knowledge_response(
        self, query: str, results: List[SearchResult], started: float
    ) -> RoutedResponse:
        matches = [r.to_dict() for r in results]
        data = {"query": query, "matches": matches}
        return RoutedResponse(
            action_type="knowledge",
            summary=(
                f"Found {len(results)} verified knowledge record(s); "
                f"top match: {results[0].record.provenance}."
            ),
            data=data,
            duration_ms=int((time.perf_counter() - started) * 1000),
            result_chars=len(str(data)),
        )

    def _unmatched(self, query: str, started: float) -> RoutedResponse:
        data = {"query": query}
        return RoutedResponse(
            action_type="unmatched",
            summary="No local automation or verified knowledge match; fall back to Claude reasoning.",
            data=data,
            duration_ms=int((time.perf_counter() - started) * 1000),
            result_chars=len(str(data)),
        )
