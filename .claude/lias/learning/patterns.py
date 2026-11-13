"""LIAS Pattern Definitions.

Central, deterministic heuristics for deciding what is worth remembering and
which repeated local work is worth turning into an automation. Kept free of
I/O so it can be unit tested directly.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Explicit, user-authored facts. These are the safest automatic knowledge
# candidates: the user already stated them as a decision, rule or resolution.
DECLARED_KNOWLEDGE_PATTERNS: List[Tuple[str, str]] = [
    (r"(?i)^(?:confirmed|confirm)\s*[:\-]\s*(.+)$", "decision"),
    (r"(?i)^architecture decision\s*[:\-]\s*(.+)$", "architecture"),
    (r"(?i)^always remember\s*[:\-]\s*(.+)$", "convention"),
    (r"(?i)^(?:project )?rule\s*[:\-]\s*(.+)$", "rule"),
    (r"(?i)^known (?:resolution|fix)\s*[:\-]\s*(.+)$", "resolution"),
]

# Phrases that mark speculation. These must never be promoted automatically.
SPECULATION_MARKERS = (
    "maybe", "perhaps", "possibly", "i think", "might be", "probably",
    "not sure", "unclear", "temporary", "for now", "todo",
)

# Categories that describe reusable behaviour rather than project facts.
WORKFLOW_CATEGORIES = {"workflow", "observation", "automation"}


@dataclass
class DeclaredFact:
    category: str
    content: str
    confidence: float


def extract_declared_fact(text: str) -> Optional[DeclaredFact]:
    """Return a fact if the message declares one explicitly, else ``None``."""
    stripped = text.strip()
    if not stripped:
        return None
    lowered = stripped.lower()
    for regex, category in DECLARED_KNOWLEDGE_PATTERNS:
        match = re.search(regex, stripped)
        if not match:
            continue
        fact = match.group(1).strip()
        if len(fact) < 10:
            return None
        confidence = 0.6 if any(marker in lowered for marker in SPECULATION_MARKERS) else 0.95
        return DeclaredFact(category=category, content=fact, confidence=confidence)
    return None


def estimate_automation_value(frequency: int, estimated_savings: int, risk_tier: int) -> float:
    """Deterministic score in [0, 1] used to decide whether to generate automation.

    Deliberately simple: frequency and estimated local-work savings raise the
    score, risk lowers it. No model calls are involved.
    """
    freq_score = min(frequency, 10) / 10 * 0.55
    savings_score = min(max(estimated_savings, 0), 1000) / 1000 * 0.35
    risk_penalty = min(max(risk_tier, 0), 2) * 0.15
    return round(max(0.0, min(1.0, freq_score + savings_score - risk_penalty)), 3)


def should_generate(
    frequency: int,
    estimated_savings: int,
    risk_tier: int,
    min_frequency: int = 3,
    min_score: float = 0.5,
) -> bool:
    """Promotion threshold check for autonomous automation generation."""
    if risk_tier > 0:
        return False
    if frequency < min_frequency:
        return False
    return estimate_automation_value(frequency, estimated_savings, risk_tier) >= min_score
