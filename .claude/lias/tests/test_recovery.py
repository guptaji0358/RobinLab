"""Tests for LIAS recovery: backup, restore, integrity, quarantine, cleanup."""

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
from lias.core.recovery import RecoveryManager, validate_settings
from lias.core.registry import AutomationManifest, AutomationRegistry
from lias.core.runner import LocalRunner
from lias.database.connection import initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.store import KnowledgeStore


class TestRecovery(unittest.TestCase):
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
        self.recovery = RecoveryManager(self.config, self.registry)
        self.store = KnowledgeStore(self.config.db_path, "TestProject", self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_backup_and_integrity(self):
        rec = self.store.add("fact", "Backup roundtrip fact about the root directory.", "test")
        backup = self.recovery.backup("test")
        self.assertTrue(backup.exists())
        self.assertTrue(self.recovery.integrity_check()["ok"])
        self.assertEqual(len(self.recovery.list_backups()), 1)

        self.store.delete(rec.id)
        self.assertIsNone(self.store.get(rec.id))

        safety = self.recovery.restore(backup)
        self.assertTrue(safety.exists())
        restored = self.store.get(rec.id)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.content, rec.content)

    def test_restore_outside_backups_blocked(self):
        outside = self.root / "not-a-backup.sqlite3"
        outside.write_bytes(b"")
        with self.assertRaises(ValueError):
            self.recovery.restore(outside)

    def test_config_validation(self):
        self.assertEqual(self.recovery.validate_config(), [])
        issues = validate_settings(
            {"version": 2, "retrieval": {"max_results": 500}, "security": "yes"}
        )
        self.assertTrue(any("version" in i for i in issues))
        self.assertTrue(any("security" in i for i in issues))
        self.assertTrue(any("max_results" in i for i in issues))

    def test_quarantine_list_and_release(self):
        script = self.root / "fail.py"
        script.write_text("import sys;sys.exit(3)", encoding="utf-8")
        self.registry.register(
            AutomationManifest(
                id="fail-auto",
                name="Fail Auto",
                description="Always fails",
                entry_point="fail.py",
                failure_policy={"max_retries": 0, "quarantine_on_failures": 1},
            )
        )
        runner = LocalRunner(
            self.root,
            self.registry,
            PolicyEngine(self.root),
            self.config.db_path,
        )
        self.assertEqual(runner.run("fail-auto").status, "error")
        quarantined = self.recovery.quarantined()
        self.assertEqual([q["automation_id"] for q in quarantined], ["fail-auto"])

        self.assertTrue(self.recovery.release("fail-auto"))
        self.assertTrue(self.registry.get("fail-auto").enabled)
        self.assertEqual(runner._consecutive_failures("fail-auto", 5), 0)

    def test_cleanup_temp_files(self):
        stale = self.config.manifests_dir / "stale.tmp"
        stale.write_text("partial", encoding="utf-8")
        keep = self.config.manifests_dir / "keep.json"
        keep.write_text("{}", encoding="utf-8")
        removed = self.recovery.cleanup_temp_files()
        self.assertIn(str(stale), removed)
        self.assertTrue(keep.exists())

    def test_log_rotation(self):
        self.config.set("resource_limits", {**self.config.get("resource_limits"), "max_log_mb": 0})
        (self.config.logs_dir / "runner.log").write_text("x" * 100, encoding="utf-8")
        result = self.recovery.rotate_logs()
        self.assertIsNotNone(result["rotated"])
        self.assertFalse((self.config.logs_dir / "runner.log").exists())


if __name__ == "__main__":
    unittest.main()
