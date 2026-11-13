"""LIAS Interaction and Workflow Observer.

Monitors user interactions and local execution logs to detect repetitive
workflows and explicitly declared project facts.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional

from lias.database.connection import db_session
from lias.learning.candidates import CandidateManager, CandidateRecord
from lias.learning.patterns import extract_declared_fact


class WorkflowObserver:
    def __init__(self, candidate_manager: CandidateManager):
        self.candidate_manager = candidate_manager

    def observe_message(self, text: str, role: str = "user") -> Optional[CandidateRecord]:
        """Detect candidate knowledge from explicit user confirmations or decisions."""
        fact = extract_declared_fact(text)
        if not fact:
            return None
        return self.candidate_manager.record_candidate(
            pattern=fact.content,
            category=fact.category,
            estimated_savings=200,
            risk_tier=0,
            metadata={"source_role": role, "observer": "declared_fact", "confidence": fact.confidence},
        )

    def observe_tool_execution(
        self,
        command_name: str,
        arguments: Dict[str, Any],
        duration_ms: int,
    ) -> CandidateRecord:
        """Observe repeated tool execution to identify automation candidates."""
        sig = f"tool_exec:{command_name}:{json.dumps(arguments, sort_keys=True)}"
        return self.candidate_manager.record_candidate(
            pattern=sig,
            category="workflow",
            estimated_savings=300,
            risk_tier=0,
            metadata={"command": command_name, "last_duration_ms": duration_ms},
        )

    def observe_execution_log(self, db_path, min_runs: int = 3) -> List[CandidateRecord]:
        """Find local automations that run repeatedly, which is a reuse signal.

        Read-only over the execution log; recording candidates is a bounded
        Tier 1 write handled by ``CandidateManager``.
        """
        observed: List[CandidateRecord] = []
        with db_session(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT automation_id, COUNT(*) AS runs,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok,
                       MAX(duration_ms) AS max_duration
                FROM execution_log
                WHERE status IN ('success', 'error', 'timeout')
                GROUP BY automation_id
                HAVING runs >= ?
                """,
                (min_runs,),
            )
            rows = cur.fetchall()

        for row in rows:
            ok = row["ok"] or 0
            # Only successful, consistently used automations are reusable.
            if ok < min_runs:
                continue
            observed.append(
                self.candidate_manager.record_candidate(
                    pattern=f"repeated_automation:{row['automation_id']}",
                    category="automation",
                    estimated_savings=400,
                    risk_tier=0,
                    metadata={
                        "automation_id": row["automation_id"],
                        "runs": row["runs"],
                        "successful_runs": ok,
                        "max_duration_ms": row["max_duration"],
                        "observer": "execution_log",
                    },
                )
            )
        return observed
