"""LIAS Intelligent Capability Router.

Routes incoming queries or intents through:
1. Exact automation execution
2. Knowledge retrieval (Exact -> FTS5)
3. Structured compact result formatting for Claude
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from lias.core.registry import AutomationRegistry
from lias.core.runner import ExecutionResult, LocalRunner
from lias.knowledge.retrieval import KnowledgeRetrieval, SearchResult


@dataclass
class RoutedResponse:
    action_type: str  # 'automation', 'knowledge', 'unmatched'
    summary: str
    data: Dict[str, Any]
    tokens_saved_estimate: int = 0


class CapabilityRouter:
    def __init__(
        self,
        registry: AutomationRegistry,
        runner: LocalRunner,
        retrieval: KnowledgeRetrieval,
    ):
        self.registry = registry
        self.runner = runner
        self.retrieval = retrieval

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> RoutedResponse:
        """Process intent and dispatch to the most cost-effective local capability."""
        normalized = query.strip().lower()

        # Step 1: Check for exact automation intent or match
        all_automations = self.registry.list_all(enabled_only=True)
        for auto in all_automations:
            # Match by id or explicit command keywords
            if auto.id.lower() in normalized or auto.name.lower() in normalized:
                exec_res = self.runner.run(auto.id, input_data=context or {}, caller="router")
                return RoutedResponse(
                    action_type="automation",
                    summary=f"Executed local automation '{auto.name}' ({auto.id}) with status '{exec_res.status}'.",
                    data=exec_res.to_dict(),
                    tokens_saved_estimate=350,
                )

        # Step 2: Knowledge retrieval via RAG
        search_results = self.retrieval.search(query, max_results=3)
        if search_results:
            top_res = search_results[0]
            # Verify that at least one substantive query word appears in the record
            stop_words = {
                "a", "an", "the", "about", "for", "with", "in", "on", "at", "by", "from",
                "to", "of", "and", "or", "is", "are", "was", "were", "what", "where", "how",
                "can", "you", "me", "this", "that", "these", "those", "have", "has", "had"
            }
            query_keywords = [w for w in normalized.split() if len(w) > 3 and w not in stop_words]
            has_keyword_match = any(
                kw in top_res.record.content.lower() or kw in top_res.record.category.lower()
                for kw in query_keywords
            )

            if (top_res.match_type == "exact" or has_keyword_match) and top_res.score >= 0.3:
                return RoutedResponse(
                    action_type="knowledge",
                    summary=f"Found {len(search_results)} verified knowledge records for query.",
                    data={
                        "query": query,
                        "matches": [r.to_dict() for r in search_results if (
                            r.match_type == "exact" or any(
                                kw in r.record.content.lower() or kw in r.record.category.lower()
                                for kw in query_keywords
                            )
                        )],
                    },
                    tokens_saved_estimate=200 * len(search_results),
                )

        # Step 3: Unmatched -> Claude handles reasoning
        return RoutedResponse(
            action_type="unmatched",
            summary="No deterministic local automation or direct knowledge match found. Fall back to Claude reasoning.",
            data={"query": query},
            tokens_saved_estimate=0,
        )
