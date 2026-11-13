"""Tests for the LIAS deterministic cache."""

import datetime
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"
if str(CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(CLAUDE_DIR))

from lias.core.cache import CacheManager, file_fingerprint
from lias.core.config import LiasConfig
from lias.database.connection import db_session, initialize_database
from lias.database.migrations import MigrationManager
from lias.knowledge.store import KnowledgeStore


class TestCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        self.config = LiasConfig(project_root=self.root)
        initialize_database(
            self.config.db_path, PROJECT_ROOT / ".claude" / "lias" / "database" / "schema.sql"
        )
        MigrationManager(self.config.db_path).apply_migrations()
        self.cache = CacheManager(self.config.db_path, enabled=True, default_ttl=60, max_entries=3)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_hit_and_input_separation(self):
        self.assertIsNone(self.cache.get("op", {"a": 1}))
        self.assertTrue(self.cache.set("op", {"a": 1}, {"value": 42}))
        self.assertEqual(self.cache.get("op", {"a": 1}), {"value": 42})
        self.assertIsNone(self.cache.get("op", {"a": 2}))
        self.assertEqual(self.cache.stats()["hits"], 1)

    def test_fingerprint_invalidation(self):
        target = self.root / "input.txt"
        target.write_text("one", encoding="utf-8")
        fp = [file_fingerprint(target)]
        self.cache.set("scan", {}, {"count": 1}, fingerprints=fp)
        self.assertEqual(self.cache.get("scan", {}, fingerprints=fp), {"count": 1})

        target.write_text("one two", encoding="utf-8")
        changed = [file_fingerprint(target)]
        self.assertNotEqual(fp, changed)
        self.assertIsNone(self.cache.get("scan", {}, fingerprints=changed))

    def test_expired_entries_are_removed(self):
        key, input_hash = CacheManager.make_key("op", {})
        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
        with db_session(self.config.db_path) as conn:
            conn.execute(
                """INSERT INTO cache_entries
                   (cache_key, operation_id, input_hash, output_json, expires_at)
                   VALUES (?, 'op', ?, '{}', ?)""",
                (key, input_hash, past),
            )
        self.assertIsNone(self.cache.get("op", {}))
        self.assertTrue(self.cache.set("op2", {}, {"ok": True}))
        self.assertEqual(self.cache.purge_expired(), 0)

    def test_sensitive_outputs_are_not_cached(self):
        self.assertFalse(self.cache.set("op", {}, {"api_key": "sk-secret-value"}))
        self.assertIsNone(self.cache.get("op", {}))

    def test_entry_limit(self):
        for i in range(5):
            self.assertTrue(self.cache.set("op", {"i": i}, {"value": i}))
        self.assertEqual(self.cache.stats()["entries"], 3)

    def test_disabled_cache(self):
        disabled = CacheManager(self.config.db_path, enabled=False)
        self.assertFalse(disabled.set("op", {}, {"ok": True}))
        self.assertIsNone(disabled.get("op", {}))

    def test_migration_version(self):
        self.assertEqual(MigrationManager(self.config.db_path).get_current_version(), 3)


if __name__ == "__main__":
    unittest.main()
