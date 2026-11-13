"""LIAS Policy and Security Engine.

Enforces execution tiers (Tier 0, Tier 1, Tier 2), path isolation,
and prevents execution of untrusted or leaking code.
"""

from __future__ import annotations
import enum
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple


class SecurityTier(enum.IntEnum):
    TIER_0_READ_ONLY = 0
    TIER_1_LOCAL_MODIFICATION = 1
    TIER_2_SENSITIVE = 2


# Regex patterns that identify sensitive data (secrets, API keys, passwords)
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|auth[_-]?token)\s*[:=]\s*['\"][a-zA-Z0-9_\-\.]{8,}['\"]"),
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{15,}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----"),
    re.compile(r"(?i)ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
]


class PolicyViolation(Exception):
    """Raised when an operation violates security policy."""
    pass


class PolicyEngine:
    def __init__(self, project_root: Path, allow_tier1_auto: bool = True, allow_tier2_auto: bool = False):
        self.project_root = project_root.resolve()
        self.allow_tier1_auto = allow_tier1_auto
        self.allow_tier2_auto = allow_tier2_auto

    def validate_path(self, target_path: str | Path, allow_claude_internal: bool = True) -> Path:
        """Ensure path is within project root and cannot escape via traversal."""
        resolved = Path(target_path).resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError:
            raise PolicyViolation(f"Path '{target_path}' escapes project root '{self.project_root}'. Path traversal blocked.")
        
        if not allow_claude_internal and ".claude" in resolved.parts:
            raise PolicyViolation(f"Access to internal .claude directory denied for path '{target_path}'.")
        return resolved

    def can_auto_execute(self, tier: SecurityTier | int) -> bool:
        """Check whether the given security tier is permitted to execute automatically."""
        if tier == SecurityTier.TIER_0_READ_ONLY:
            return True
        elif tier == SecurityTier.TIER_1_LOCAL_MODIFICATION:
            return self.allow_tier1_auto
        elif tier == SecurityTier.TIER_2_SENSITIVE:
            return self.allow_tier2_auto
        return False

    def scrub_secrets(self, text: str) -> Tuple[str, bool]:
        """Detect and redact sensitive keys/passwords. Returns (cleaned_text, had_secrets)."""
        had_secrets = False
        cleaned = text
        for pattern in SECRET_PATTERNS:
            if pattern.search(cleaned):
                had_secrets = True
                cleaned = pattern.sub("[REDACTED_SECRET]", cleaned)
        return cleaned, had_secrets

    def validate_command_safety(self, command_args: List[str]) -> None:
        """Validate that subprocess arguments do not contain forbidden destructive commands."""
        forbidden_substrings = [
            "rm -rf /", "rmdir /s /q c:\\", "format ", "dd if=",
            ":(){ :|:& };:", "drop database", "shutdown",
        ]
        joined = " ".join(command_args).lower()
        for forbidden in forbidden_substrings:
            if forbidden in joined:
                raise PolicyViolation(f"Command contains forbidden destructive instruction: '{forbidden}'")
