"""Tests for deterministic capability routing."""

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.core.config import LiasConfig
from lias.core.policy import PolicyEngine
from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.core.router import CapabilityRouter, normalize_text
from lias.core.runner import LocalRunner
from lias.database.connection import initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.retrieval import KnowledgeRetrieval
from lias.knowledge.store import KnowledgeStore


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        self.config = LiasConfig(project_root=self.root)
        initialize_database(
            self.config.db_path, PROJECT_ROOT / ".claude" / "lias" / "database" / "schema.sql"
        )
        MigrationManager(self.config.db_path).apply_migrations()
        self.registry = AutomationRegistry(self.config.manifests_dir, self.config.db_path)
        self.runner = LocalRunner(
            self.root, self.registry, PolicyEngine(self.root), self.config.db_path
        )
        self.store = KnowledgeStore(self.config.db_path, "TestProject", self.root)
        self.retrieval = KnowledgeRetrieval(self.config.db_path)
        self.router = CapabilityRouter(
            self.registry, self.runner, self.retrieval, project_id="TestProject"
        )

        (self.root / "stats.py").write_text(
            "import json;print(json.dumps({'result': {'files': 3}}))", encoding="utf-8"
        )
        self.registry.register(
            AutomationManifest(
                id="source-file-stats",
                name="Source File Statistics",
                description="Counts source files and lines",
                entry_point="stats.py",
                keywords=["source", "stats", "lines", "files", "count"],
                cache_policy={"enabled": False},
            )
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalization(self):
        self.assertEqual(normalize_text("Run env-check, NOW!"), "run env check now")

    def test_exact_id_and_keywords(self):
        exact = self.router.route("Run source-file-stats")
        self.assertEqual(exact.action_type, "automation")
        self.assertEqual(exact.data["automation_id"], "source-file-stats")
        self.assertGreaterEqual(exact.data["match_score"], 0.9)

        keyword = self.router.route("count files and lines in the repository")
        self.assertEqual(keyword.action_type, "automation")

    def test_knowledge_routing_and_freshness(self):
        self.store.add(
            "routing",
            "The collection page is served from root/collection.html via Cloudflare Pages.",
            "CLAUDE.md:pages",
        )
        result = self.router.route("Which file serves the collection page?")
        self.assertEqual(result.action_type, "knowledge")
        self.assertEqual(len(result.data["matches"]), 1)
        self.assertTrue(result.data["matches"][0]["verified"])

    def test_no_fabricated_token_metrics(self):
        response = self.router.route("Run source-file-stats")
        self.assertFalse(hasattr(response, "tokens_saved_estimate"))
        self.assertIsInstance(response.duration_ms, int)
        self.assertGreater(response.result_chars, 0)

    def test_unmatched(self):
        response = self.router.route("Compose a philosophical poem about starlight")
        self.assertEqual(response.action_type, "unmatched")
        self.assertIn("fall back to claude", response.summary.lower())


if __name__ == "__main__":
    unittest.main()
