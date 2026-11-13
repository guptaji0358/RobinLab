"""Tests for retrieval validity filtering, scoping and FTS escaping."""

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
from lias.database.connection import initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.retrieval import KnowledgeRetrieval
from lias.knowledge.store import KnowledgeStore


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        self.config = LiasConfig(project_root=self.root)
        initialize_database(
            self.config.db_path, PROJECT_ROOT / ".claude" / "lias" / "database" / "schema.sql"
        )
        MigrationManager(self.config.db_path).apply_migrations()
        self.store = KnowledgeStore(self.config.db_path, "TestProject", self.root)
        self.retrieval = KnowledgeRetrieval(self.config.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_unverified_and_expired_are_hidden(self):
        self.store.add("fact", "Verified fact about deployment target.", "test")
        self.store.add("fact", "Unverified claim about deployment target.", "test", verified=False)
        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()
        self.store.add("fact", "Expired fact about deployment target.", "test", expires_at=past)

        ids = {r.record.content for r in self.retrieval.search("deployment target")}
        self.assertEqual(ids, {"Verified fact about deployment target."})

        all_ids = {
            r.record.content
            for r in self.retrieval.search(
                "deployment target", include_unverified=True, include_expired=True
            )
        }
        self.assertEqual(len(all_ids), 3)

    def test_token_and_fts_search_survive_punctuation(self):
        self.store.add(
            "routing",
            "Four main site routes are served from root: index, collection, presentations and skills.",
            "test",
        )
        results = self.retrieval.search("site routes pages? (list all!)")
        self.assertTrue(results)
        self.assertIn("Four main site routes", results[0].record.content)

        # Hyphens and parentheses must not raise an FTS syntax error.
        safe = self.retrieval.search("env-check (tooling) source-file-stats")
        self.assertIsInstance(safe, list)

    def test_project_scoping(self):
        self.store.add("fact", "Project Alpha uses SQLite storage.", "test")
        other = KnowledgeStore(self.config.db_path, "OtherProject", self.root)
        other.add("fact", "Project Beta uses Postgres storage.", "test")

        scoped = self.retrieval.search("storage", project_id="OtherProject")
        self.assertEqual([r.record.content for r in scoped], ["Project Beta uses Postgres storage."])

    def test_context_budget(self):
        for i in range(5):
            self.store.add("doc", f"Chunk {i} " + ("x" * 200), "test")
        results = self.retrieval.search("chunk", max_results=5, max_context_chars=450)
        self.assertLessEqual(len(results), 3)
        self.assertLessEqual(sum(len(r.record.content) for r in results), 450)

    def test_min_score_filter(self):
        self.store.add("fact", "Completely unrelated wording about pandas.", "test")
        self.assertEqual(self.retrieval.search("kubernetes cluster", min_score=0.2), [])


if __name__ == "__main__":
    unittest.main()
