"""LIAS Knowledge Validation Engine.

Provides contradiction detection, duplicate detection, and validation rules
for incoming knowledge candidates.
"""

from __future__ import annotations
import difflib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from lias.knowledge.store import KnowledgeRecord, KnowledgeStore


@dataclass
class ValidationResult:
    is_valid: bool
    status: str  # 'valid', 'duplicate', 'contradiction', 'sensitive', 'invalid'
    reason: str
    conflicting_record: Optional[KnowledgeRecord] = None


class KnowledgeValidator:
    def __init__(self, store: KnowledgeStore):
        self.store = store

    def validate_candidate(
        self,
        category: str,
        content: str,
        confidence: float = 1.0,
    ) -> ValidationResult:
        """Validate candidate fact against secrets, duplicates, and contradictions."""
        clean_text, had_secrets = self.store.policy.scrub_secrets(content)
        if had_secrets:
            return ValidationResult(
                is_valid=False,
                status="sensitive",
                reason="Candidate contains sensitive credentials or secret tokens.",
            )

        if len(content.strip()) < 10:
            return ValidationResult(
                is_valid=False,
                status="invalid",
                reason="Content is too brief to be meaningful knowledge.",
            )

        # Check existing records in category
        existing_records = self.store.list_all(category=category, only_verified=False, limit=100)

        normalized_new = " ".join(content.strip().lower().split())

        for rec in existing_records:
            normalized_rec = " ".join(rec.content.strip().lower().split())

            # 1. Contradiction check first: a contradicting statement is not a duplicate.
            if self._detect_contradiction(normalized_new, normalized_rec):
                return ValidationResult(
                    is_valid=False,
                    status="contradiction",
                    reason="Contradicts existing verified project knowledge.",
                    conflicting_record=rec,
                )

            # 2. Duplicate check (Exact or very high similarity)
            if normalized_new == normalized_rec:
                return ValidationResult(
                    is_valid=False,
                    status="duplicate",
                    reason="Exact duplicate record already exists.",
                    conflicting_record=rec,
                )

            similarity = difflib.SequenceMatcher(None, normalized_new, normalized_rec).ratio()
            if similarity > 0.9:
                return ValidationResult(
                    is_valid=False,
                    status="duplicate",
                    reason=f"High similarity ({similarity:.2f}) duplicate detected.",
                    conflicting_record=rec,
                )

        return ValidationResult(
            is_valid=True,
            status="valid",
            reason="Candidate passed all validation checks.",
        )

    def _detect_contradiction(self, new_text: str, existing_text: str) -> bool:
        """Heuristic contradiction detector looking for subject overlap with opposing polarities."""
        # Split into words of length > 3
        words_new = set(re.findall(r"\b[a-zA-Z]{4,}\b", new_text))
        words_exist = set(re.findall(r"\b[a-zA-Z]{4,}\b", existing_text))
        overlap = words_new.intersection(words_exist)

        # If significant subject overlap
        if len(overlap) >= 3:
            negations = ["not", "never", "cannot", "no", "disabled", "false", "prohibited", "banned"]
            new_has_neg = any(f" {neg} " in f" {new_text} " for neg in negations)
            exist_has_neg = any(f" {neg} " in f" {existing_text} " for neg in negations)

            if new_has_neg != exist_has_neg:
                return True
        return False
