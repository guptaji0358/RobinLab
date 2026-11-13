"""Tests for the hardened automation runner."""

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


class TestRunner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / ".claude").mkdir(parents=True, exist_ok=True)
        self.config = LiasConfig(project_root=self.root)
        initialize_database(
            self.config.db_path, PROJECT_ROOT / ".claude" / "lias" / "database" / "schema.sql"
        )
        MigrationManager(self.config.db_path).apply_migrations()
        self.policy = PolicyEngine(self.root, allow_tier1_auto=True, allow_tier2_auto=False)
        self.registry = AutomationRegistry(self.config.manifests_dir, self.config.db_path)
        self.cache = CacheManager(self.config.db_path, enabled=True, default_ttl=60)
        self.runner = LocalRunner(
            self.root, self.registry, self.policy, self.config.db_path, cache=self.cache
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _script(self, name: str, body: str) -> str:
        path = self.root / name
        path.write_text(body, encoding="utf-8")
        return name

    def _manifest(self, **kwargs) -> AutomationManifest:
        defaults = dict(
            id="t-auto",
            name="Test Auto",
            description="Test automation",
            tier=0,
            entry_point="auto.py",
            enabled=True,
        )
        defaults.update(kwargs)
        return AutomationManifest(**defaults)

    def test_input_schema_validation(self):
        self._script("auto.py", "import json;print(json.dumps({'ok': True}))")
        self.registry.register(
            self._manifest(
                input_schema={
                    "type": "object",
                    "required": ["path"],
                    "properties": {"path": {"type": "string"}},
                }
            )
        )
        denied = self.runner.run("t-auto", {})
        self.assertEqual(denied.status, "error")
        self.assertIn("Input validation failed", denied.error)

        ok = self.runner.run("t-auto", {"path": "root"})
        self.assertEqual(ok.status, "success")
        self.assertTrue(ok.output_valid)

    def test_output_schema_mismatch_is_warned(self):
        self._script("auto.py", "import json;print(json.dumps({'count': 'not-a-number'}))")
        self.registry.register(
            self._manifest(
                output_schema={
                    "type": "object",
                    "required": ["count"],
                    "properties": {"count": {"type": "integer"}},
                }
            )
        )
        result = self.runner.run("t-auto")
        self.assertEqual(result.status, "success")
        self.assertFalse(result.output_valid)
        self.assertTrue(any("Output schema mismatch" in w for w in result.warnings))

    def test_retry_then_success(self):
        state = self.root / "state.txt"
        self._script(
            "auto.py",
            f"""
import json, pathlib
p = pathlib.Path({str(state)!r})
n = int(p.read_text()) if p.exists() else 0
p.write_text(str(n + 1))
print(json.dumps({{"attempt": n + 1}}))
raise SystemExit(1 if n == 0 else 0)
""",
        )
        self.registry.register(
            self._manifest(failure_policy={"max_retries": 1, "quarantine_on_failures": 5})
        )
        result = self.runner.run("t-auto")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.result["attempt"], 2)
        self.assertEqual(result.attempts, 2)

    def test_quarantine_after_repeated_failure(self):
        self._script("auto.py", "import sys;sys.exit(2)")
        self.registry.register(
            self._manifest(failure_policy={"max_retries": 0, "quarantine_on_failures": 2})
        )
        first = self.runner.run("t-auto")
        self.assertEqual(first.status, "error")
        second = self.runner.run("t-auto")
        self.assertEqual(second.status, "error")
        self.assertFalse(self.registry.get("t-auto").enabled)
        third = self.runner.run("t-auto")
        self.assertEqual(third.status, "quarantined")

    def test_cache_hit_and_invalidation(self):
        marker = self.root / "runs.txt"
        self._script(
            "auto.py",
            f"""
import json, pathlib
p = pathlib.Path({str(marker)!r})
n = int(p.read_text()) if p.exists() else 0
p.write_text(str(n + 1))
print(json.dumps({{"runs": n + 1}}))
""",
        )
        self.registry.register(
            self._manifest(cache_policy={"enabled": True, "ttl": 60})
        )
        first = self.runner.run("t-auto")
        second = self.runner.run("t-auto")
        self.assertFalse(first.cached)
        self.assertTrue(second.cached)
        self.assertEqual(second.result["runs"], 1)
        self.assertEqual(marker.read_text(), "1")

        third = self.runner.run("t-auto", {"variant": "different"})
        self.assertFalse(third.cached)
        self.assertEqual(third.result["runs"], 2)

    def test_batch_entrypoint(self):
        (self.root / "auto.bat").write_text('@echo {"ok": true}\n', encoding="utf-8")
        self.registry.register(self._manifest(entry_point="auto.bat"))
        result = self.runner.run("t-auto")
        self.assertEqual(result.status, "success", result.error)
        self.assertTrue(result.result.get("ok"))

    def test_path_traversal_entrypoint_blocked(self):
        outside = Path(self.temp_dir.name).parent / "outside.py"
        outside.write_text("print('{}')", encoding="utf-8")
        self.registry.register(self._manifest(entry_point=str(outside)))
        result = self.runner.run("t-auto")
        self.assertEqual(result.status, "denied")
        self.assertIn("escapes project root", result.error)

    def test_manifest_id_traversal_rejected(self):
        with self.assertRaises(ValueError):
            self.registry.register(self._manifest(id="../../evil"))
        (self.config.manifests_dir / "evil.json").write_text(
            '{"id": "../../evil", "name": "Evil", "description": "x", "entry_point": "auto.py"}',
            encoding="utf-8",
        )
        self.registry.sync_from_disk()
        self.assertTrue(self.registry.load_errors)
        self.assertFalse(any(m.id.endswith("evil") for m in self.registry.list_all(enabled_only=False)))
        self.assertFalse((self.root / "evil.json").exists())

    def test_invalid_output_is_not_cached(self):
        marker = self.root / "runs2.txt"
        self._script(
            "auto.py",
            f"""
import json, pathlib
p = pathlib.Path({str(marker)!r})
n = int(p.read_text()) if p.exists() else 0
p.write_text(str(n + 1))
print(json.dumps({{"count": "bad"}}))
""",
        )
        self.registry.register(
            self._manifest(
                cache_policy={"enabled": True, "ttl": 60},
                output_schema={
                    "type": "object",
                    "required": ["count"],
                    "properties": {"count": {"type": "integer"}},
                },
            )
        )
        self.assertFalse(self.runner.run("t-auto").output_valid)
        self.assertFalse(self.runner.run("t-auto").cached)
        self.assertEqual(marker.read_text(), "2")


if __name__ == "__main__":
    unittest.main()
