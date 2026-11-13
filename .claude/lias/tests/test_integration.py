"""Integration tests for LIAS Client Integration and natural-language discovery."""

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.cli import init_subsystems


class TestClientIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg, cls.registry, cls.runner, cls.store, cls.retrieval, cls.router, cls.diag = init_subsystems()

    def test_doctor_healthy(self):
        doc = self.diag.run_doctor()
        self.assertEqual(doc["status"], "HEALTHY")
        self.assertGreaterEqual(len(doc["checks"]), 4)

    def test_natural_language_knowledge_routing(self):
        resp = self.router.route("What are the site routes and pages in RobinLabs?")
        self.assertEqual(resp.action_type, "knowledge")
        self.assertGreater(len(resp.data["matches"]), 0)

    def test_natural_language_automation_routing(self):
        resp = self.router.route("Run env-check to verify toolchains")
        self.assertEqual(resp.action_type, "automation")
        self.assertEqual(resp.data["automation_id"], "env-check")
        self.assertEqual(resp.data["status"], "success")

    def test_unmatched_fallback(self):
        resp = self.router.route("Compose a philosophical poem about starlight")
        self.assertEqual(resp.action_type, "unmatched")
        self.assertIn("fall back to claude", resp.summary.lower())


if __name__ == "__main__":
    unittest.main()
