"""Tests for bounded automation generation and activation."""

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.core.cache import CacheManager
from lias.core.config import LiasConfig
from lias.core.policy import PolicyEngine
from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.core.runner import LocalRunner
from lias.database.connection import initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.store import KnowledgeStore
from lias.learning.candidates import CandidateManager
from lias.learning.generator import AutomationGenerator, validate_generated_script


class TestGenerator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        self.config = LiasConfig(project_root=self.root)
        self.config.set(
            "learning",
            {
                **self.config.get("learning"),
                "promotion_frequency_threshold": 2,
                "promotion_estimated_token_savings": 100,
            },
        )
        initialize_database(
            self.config.db_path, PROJECT_ROOT / ".claude" / "lias" / "database" / "schema.sql"
        )
        MigrationManager(self.config.db_path).apply_migrations()
        self.registry = AutomationRegistry(self.config.manifests_dir, self.config.db_path)
        self.store = KnowledgeStore(self.config.db_path, "TestProject", self.root)
        self.candidates = CandidateManager(self.config.db_path, self.store)
        self.generator = AutomationGenerator(self.config, self.registry, self.candidates)
        self.runner = LocalRunner(
            self.root,
            self.registry,
            PolicyEngine(self.root),
            self.config.db_path,
            cache=CacheManager(self.config.db_path, enabled=False),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_static_validation_blocks_unsafe_code(self):
        bad = self.root / "bad.py"
        bad.write_text(
            "import subprocess, json\nsubprocess.run(['cmd'])\nprint(json.dumps({}))\n"
            "if __name__ == '__main__':\n    pass\n",
            encoding="utf-8",
        )
        issues = validate_generated_script(bad)
        self.assertTrue(any("forbidden import: subprocess" in i for i in issues))

        bad.write_text(
            "import json\neval('1')\nprint(json.dumps({}))\nif __name__ == '__main__':\n    pass\n",
            encoding="utf-8",
        )
        self.assertTrue(any("forbidden call: eval" in i for i in validate_generated_script(bad)))

    def test_threshold_and_template_gates(self):
        candidate = self.candidates.record_candidate("Observed manual file counting", category="workflow")
        result = self.generator.generate(candidate.id)
        self.assertEqual(result.status, "rejected")
        self.assertTrue(any("no safe whitelisted template" in r for r in result.reasons))

        self.candidates.record_candidate("Observed manual file counting", category="workflow")
        self.candidates.record_candidate(
            "Count files by extension in root",
            category="workflow",
            estimated_savings=900,
            metadata={"template": "directory-summary"},
        )
        self.candidates.record_candidate(
            "Count files by extension in root",
            category="workflow",
            estimated_savings=900,
            metadata={"template": "directory-summary"},
        )
        template = next(
            c for c in self.candidates.list_candidates()
            if c.workflow_pattern == "Count files by extension in root"
        )
        generated = self.generator.generate(template.id)
        self.assertEqual(generated.status, "generated", generated.reasons)
        manifest = self.registry.get(generated.automation_id)
        self.assertIsNotNone(manifest)
        self.assertTrue(manifest.generated)
        self.assertEqual(manifest.tier, 0)
        self.assertEqual(manifest.validation["isolated_test"], "passed")

        run = self.runner.run(generated.automation_id, {"path": "."})
        self.assertEqual(run.status, "success", run.error)
        self.assertIn("files_scanned", run.result["result"])

    def test_duplicate_and_status_guards(self):
        for _ in range(2):
            self.candidates.record_candidate(
                "Count files in tools",
                category="workflow",
                estimated_savings=900,
                metadata={"template": "directory-summary"},
            )
        candidate = self.candidates.list_candidates()[0]
        first = self.generator.generate(candidate.id)
        self.assertEqual(first.status, "generated", first.reasons)
        again = self.generator.generate(candidate.id)
        self.assertEqual(again.status, "rejected")
        self.assertTrue(any("already" in r for r in again.reasons))

    def test_repeated_automation_reuses_existing(self):
        script = self.root / "existing.py"
        script.write_text("import json;print(json.dumps({'ok': True}))", encoding="utf-8")
        self.registry.register(
            AutomationManifest(
                id="existing-auto",
                name="Existing",
                description="Existing automation",
                entry_point="existing.py",
                keywords=["existing"],
            )
        )
        self.candidates.record_candidate(
            "repeated_automation:existing-auto", category="automation"
        )
        candidate = self.candidates.list_candidates()[0]
        result = self.generator.generate(candidate.id)
        self.assertEqual(result.status, "reused")
        self.assertEqual(result.automation_id, "existing-auto")

    def test_evaluate_candidate(self):
        for _ in range(4):
            self.candidates.record_candidate(
                "Repeated directory counting", category="workflow", estimated_savings=900
            )
        candidate = self.candidates.list_candidates()[0]
        evaluation = self.generator.evaluate_candidate(candidate)
        self.assertTrue(evaluation["eligible"])
        self.assertGreaterEqual(evaluation["value_score"], 0.5)


if __name__ == "__main__":
    unittest.main()
