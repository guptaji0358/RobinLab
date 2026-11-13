"""Tests for LIAS hybrid learning: observation, validation, promotion, expiry."""

import datetime
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.core.config import LiasConfig
from lias.database.connection import db_session, initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.indexing import ProjectIndexer
from lias.knowledge.store import KnowledgeStore
from lias.knowledge.validation import KnowledgeValidator
from lias.learning.candidates import CandidateManager
from lias.learning.observer import WorkflowObserver
from lias.learning.patterns import extract_declared_fact, should_generate


class TestLearning(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        self.config = LiasConfig(project_root=self.root)
        schema = PROJECT_ROOT / ".claude" / "lias" / "database" / "schema.sql"
        initialize_database(self.config.db_path, schema)
        MigrationManager(self.config.db_path).apply_migrations()

        self.store = KnowledgeStore(
            db_path=self.config.db_path, project_id="TestProject", project_root=self.root
        )
        self.validator = KnowledgeValidator(self.store)
        self.candidates = CandidateManager(self.config.db_path, self.store)
        self.observer = WorkflowObserver(self.candidates)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_declared_fact_extraction(self):
        fact = extract_declared_fact("Confirm: Projects live in root/projects/.")
        self.assertIsNotNone(fact)
        self.assertEqual(fact.category, "decision")
        self.assertGreaterEqual(fact.confidence, 0.9)

        speculative = extract_declared_fact("Rule: maybe projects move to src/ later")
        self.assertIsNotNone(speculative)
        self.assertLess(speculative.confidence, 0.9)

        self.assertIsNone(extract_declared_fact("Just a normal question about routing?"))

    def test_duplicate_and_contradiction_detection(self):
        self.store.add("rule", "Projects live in root/projects as the single copy.", "test")
        dup = self.validator.validate_candidate("rule", "Projects live in root/projects as the single copy.")
        self.assertEqual(dup.status, "duplicate")
        self.assertFalse(dup.is_valid)

        contradiction = self.validator.validate_candidate(
            "rule", "Projects never live in root/projects as the single copy."
        )
        self.assertEqual(contradiction.status, "contradiction")

    def test_secret_handling(self):
        with self.assertRaises(ValueError):
            self.store.add(
                category="config",
                content='api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"',
                provenance="test",
                on_secret="reject",
            )

        rec = self.store.add(
            category="config",
            content='api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"',
            provenance="test",
        )
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", rec.content)

        blocked = self.validator.validate_candidate(
            "config", 'token = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"'
        )
        self.assertEqual(blocked.status, "sensitive")

    def test_candidate_promotion_and_guard(self):
        self.observer.observe_message("Confirmed: Deploys use wrangler pages deploy root.")
        candidate = self.candidates.list_candidates()[0]
        self.assertEqual(candidate.frequency, 1)
        self.assertIsNone(self.candidates.evaluate_and_promote(candidate.id, min_frequency=3))

        self.observer.observe_message("Confirmed: Deploys use wrangler pages deploy root.")
        self.observer.observe_message("Confirmed: Deploys use wrangler pages deploy root.")
        promoted = self.candidates.evaluate_and_promote(candidate.id, min_frequency=3)
        self.assertIsNotNone(promoted)
        self.assertEqual(promoted.provenance, f"promoted_candidate:{candidate.id}")

        # Re-evaluating a promoted candidate must not duplicate or quarantine it.
        self.assertIsNone(self.candidates.evaluate_and_promote(candidate.id, min_frequency=3))
        statuses = {c.id: c.status for c in self.candidates.list_candidates()}
        self.assertEqual(statuses[candidate.id], "promoted")
        self.assertEqual(len(self.store.list_all(category="decision")), 1)

    def test_invalid_candidate_quarantined(self):
        self.observer.observe_message(
            'Confirmed: api_token = "sk-abcdefghijklmnopqrstuvwxyz123456"'
        )
        candidate = self.candidates.list_candidates()[0]
        result = self.candidates.evaluate_and_promote(candidate.id, min_frequency=1)
        self.assertIsNone(result)
        self.assertEqual(self.candidates.list_candidates(status="quarantined")[0].id, candidate.id)

    def test_observe_execution_log(self):
        with db_session(self.config.db_path) as conn:
            for _ in range(3):
                conn.execute(
                    """INSERT INTO execution_log
                       (automation_id, duration_ms, status, exit_code, caller)
                       VALUES ('source-file-stats', 40, 'success', 0, 'test')"""
                )
        observed = self.observer.observe_execution_log(self.config.db_path, min_runs=3)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].workflow_pattern, "repeated_automation:source-file-stats")

    def test_expiration_purge(self):
        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
        self.store.add("temporary", "Temporary note about a scratch branch.", "test", expires_at=past)
        self.assertEqual(self.store.purge_expired(), 1)

    def test_audit_trail(self):
        rec = self.store.add("fact", "The site publishes only the root directory.", "test")
        self.store.add("fact", "The site publishes only the root directory.", "test")
        self.store.delete(rec.id)
        with db_session(self.config.db_path) as conn:
            rows = conn.execute(
                "SELECT action FROM audit_log WHERE entity_type = 'knowledge' ORDER BY id"
            ).fetchall()
        self.assertEqual([r["action"] for r in rows], ["create", "update", "delete"])

    def test_indexer_and_project_root_binding(self):
        indexer = ProjectIndexer(store=self.store, project_root=self.root)
        self.assertEqual(indexer.index_foundational(), 6)
        self.assertEqual(len(self.store.list_all(category="architecture")), 1)
        self.assertEqual(self.store.policy.project_root, self.root.resolve())

    def test_automation_value_gate(self):
        self.assertFalse(should_generate(frequency=1, estimated_savings=900, risk_tier=0))
        self.assertTrue(should_generate(frequency=4, estimated_savings=900, risk_tier=0))
        self.assertFalse(should_generate(frequency=9, estimated_savings=900, risk_tier=1))


if __name__ == "__main__":
    unittest.main()
