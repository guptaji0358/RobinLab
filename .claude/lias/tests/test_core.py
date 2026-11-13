"""Unit tests for LIAS Core Infrastructure."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.core.config import LiasConfig, find_project_root
from lias.core.diagnostics import LiasDiagnostics
from lias.core.policy import PolicyEngine, PolicyViolation, SecurityTier
from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.core.router import CapabilityRouter
from lias.core.runner import LocalRunner
from lias.database.connection import db_session, initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.retrieval import KnowledgeRetrieval
from lias.knowledge.store import KnowledgeStore


class TestLiasCore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        (self.test_root / ".claude").mkdir(parents=True, exist_ok=True)
        self.config = LiasConfig(project_root=self.test_root)
        self.schema_file = PROJECT_ROOT / ".claude" / "lias" / "database" / "schema.sql"
        initialize_database(self.config.db_path, self.schema_file)
        MigrationManager(self.config.db_path).apply_migrations()

        self.policy = PolicyEngine(project_root=self.test_root, allow_tier1_auto=True, allow_tier2_auto=False)
        self.registry = AutomationRegistry(manifests_dir=self.config.manifests_dir, db_path=self.config.db_path)
        self.runner = LocalRunner(
            project_root=self.test_root,
            registry=self.registry,
            policy=self.policy,
            db_path=self.config.db_path,
        )
        self.store = KnowledgeStore(db_path=self.config.db_path, project_id="TestProject")
        self.retrieval = KnowledgeRetrieval(db_path=self.config.db_path)
        self.router = CapabilityRouter(registry=self.registry, runner=self.runner, retrieval=self.retrieval)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_find_project_root(self):
        sub = self.test_root / "nested" / "subfolder"
        sub.mkdir(parents=True, exist_ok=True)
        detected = find_project_root(sub)
        self.assertEqual(detected, self.test_root.resolve())

    def test_policy_path_traversal(self):
        outside = self.test_root.parent / "outside.txt"
        with self.assertRaises(PolicyViolation):
            self.policy.validate_path(outside)

    def test_policy_scrub_secrets(self):
        sample = "My api_key = 'sk-1234567890abcdef1234567890' for testing."
        cleaned, had_secrets = self.policy.scrub_secrets(sample)
        self.assertTrue(had_secrets)
        self.assertNotIn("sk-1234567890", cleaned)
        self.assertIn("[REDACTED_SECRET]", cleaned)

        env_sample = "HF_TOKEN=hf_abcdefghijklmnopqrstuvwxyz123456"
        env_cleaned, env_secrets = self.policy.scrub_secrets(env_sample)
        self.assertTrue(env_secrets)
        self.assertNotIn("hf_abcdefghijklmnopqrstuvwxyz123456", env_cleaned)

    def test_knowledge_crud_and_fts5(self):
        rec = self.store.add(
            category="architecture",
            content="Static site hosted on Cloudflare Pages with Functions proxy.",
            provenance="CLAUDE.md",
        )
        self.assertIsNotNone(rec.id)
        fetched = self.store.get(rec.id)
        self.assertEqual(fetched.content, rec.content)

        # FTS5 search
        matches = self.retrieval.search("Cloudflare Pages")
        self.assertTrue(len(matches) >= 1)
        self.assertEqual(matches[0].record.id, rec.id)

    def test_automation_registration_and_runner(self):
        # Create a tiny test script in test_root
        script_path = self.test_root / "test_script.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("import json; print(json.dumps({'status': 'success', 'hello': 'world'}))\n")

        manifest = AutomationManifest(
            id="test-auto",
            name="Test Auto",
            description="A test automation",
            tier=0,
            entry_point="test_script.py",
        )
        self.registry.register(manifest)

        # Run automation
        res = self.runner.run("test-auto")
        self.assertEqual(res.status, "success")
        self.assertEqual(res.result.get("hello"), "world")

    def test_runner_timeout(self):
        script_path = self.test_root / "hang.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("import time; time.sleep(5)\n")

        manifest = AutomationManifest(
            id="hang-auto",
            name="Hanging Auto",
            description="Times out",
            tier=0,
            entry_point="hang.py",
            timeout_seconds=1,
        )
        self.registry.register(manifest)

        res = self.runner.run("hang-auto")
        self.assertEqual(res.status, "timeout")

    def test_router_dispatch(self):
        self.store.add(
            category="decision",
            content="Projects live in root/projects/ with no second copy.",
            provenance="user",
        )
        routed = self.router.route("Where do projects live?")
        self.assertEqual(routed.action_type, "knowledge")
        self.assertTrue(len(routed.data["matches"]) > 0)


if __name__ == "__main__":
    unittest.main()
