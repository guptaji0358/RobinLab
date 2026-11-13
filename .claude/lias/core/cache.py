"""LIAS Deterministic Cache.

Caches repeatable local operations keyed by automation id, version, normalized
input and file fingerprints. Entries expire by TTL and are invalidated when a
fingerprinted input changes. Sensitive outputs are never cached by default.
"""

from __future__ import annotations
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from lias.database.connection import db_session


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def file_fingerprint(path: Path) -> Dict[str, Any]:
    """Content fingerprint for a file; missing files invalidate cache entries."""
    try:
        stat = path.stat()
    except OSError:
        return {"path": str(path), "exists": False}
    if not path.is_file():
        return {"path": str(path), "exists": False}
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return {"path": str(path), "exists": False}
    return {
        "path": str(path),
        "exists": True,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest.hexdigest(),
    }


class CacheManager:
    def __init__(
        self,
        db_path: Path,
        enabled: bool = True,
        default_ttl: int = 3600,
        max_entries: int = 1000,
    ):
        self.db_path = db_path
        self.enabled = enabled
        self.default_ttl = default_ttl
        self.max_entries = max_entries

    # ------------------------------------------------------------------ keys
    @staticmethod
    def make_key(
        operation_id: str,
        input_data: Optional[Dict[str, Any]],
        version: str = "1.0.0",
        fingerprints: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[str, str]:
        """Return ``(cache_key, input_hash)`` for an operation invocation."""
        normalized_input = json.dumps(input_data or {}, sort_keys=True, separators=(",", ":"))
        input_hash = hashlib.sha256(normalized_input.encode("utf-8")).hexdigest()
        fp_digest = hashlib.sha256(
            json.dumps(fingerprints or [], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        raw = f"{operation_id}|{version}|{input_hash}|{fp_digest}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest(), input_hash

    # ------------------------------------------------------------------ read
    def get(
        self,
        operation_id: str,
        input_data: Optional[Dict[str, Any]],
        version: str = "1.0.0",
        fingerprints: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        key, _ = self.make_key(operation_id, input_data, version, fingerprints)
        now = _now().isoformat()
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT output_json, expires_at FROM cache_entries WHERE cache_key = ?",
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            if row["expires_at"] <= now:
                cur.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
                return None
            cur.execute(
                "UPDATE cache_entries SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (key,),
            )
            try:
                return json.loads(row["output_json"])
            except Exception:
                cur.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
                return None

    # ----------------------------------------------------------------- write
    def set(
        self,
        operation_id: str,
        input_data: Optional[Dict[str, Any]],
        result: Dict[str, Any],
        ttl: Optional[int] = None,
        version: str = "1.0.0",
        fingerprints: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not self.enabled:
            return False
        # Never cache obvious credentials or tokens.
        try:
            serialized = json.dumps(result)
        except Exception:
            return False
        lowered = serialized.lower()
        for marker in ("api_key", "authorization:", "bearer ", "private key", "ghp_", "sk-"):
            if marker in lowered:
                return False

        key, input_hash = self.make_key(operation_id, input_data, version, fingerprints)
        ttl = ttl if ttl is not None else self.default_ttl
        expires = (_now() + datetime.timedelta(seconds=max(ttl, 1))).isoformat()
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO cache_entries
                    (cache_key, operation_id, input_hash, output_json, created_at,
                     expires_at, fingerprints_json, operation_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    output_json = excluded.output_json,
                    expires_at = excluded.expires_at,
                    fingerprints_json = excluded.fingerprints_json,
                    operation_version = excluded.operation_version
                """,
                (
                    key,
                    operation_id,
                    input_hash,
                    serialized,
                    _now().isoformat(),
                    expires,
                    json.dumps(fingerprints or []),
                    version,
                ),
            )
            self._enforce_limit(cur)
        return True

    def _enforce_limit(self, cur) -> None:
        cur.execute("SELECT COUNT(*) FROM cache_entries")
        count = cur.fetchone()[0]
        if count > self.max_entries:
            cur.execute(
                """
                DELETE FROM cache_entries WHERE cache_key IN (
                    SELECT cache_key FROM cache_entries
                    ORDER BY created_at ASC LIMIT ?
                )
                """,
                (count - self.max_entries,),
            )

    # -------------------------------------------------------------- lifecycle
    def purge_expired(self) -> int:
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (_now().isoformat(),))
            return cur.rowcount

    def clear(self) -> int:
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM cache_entries")
            return cur.rowcount

    def stats(self) -> Dict[str, Any]:
        with db_session(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) AS entries, COALESCE(SUM(hit_count), 0) AS hits,
                       COALESCE(SUM(LENGTH(output_json)), 0) AS bytes
                FROM cache_entries WHERE expires_at > ?
                """,
                (_now().isoformat(),),
            )
            row = cur.fetchone()
        return {
            "enabled": self.enabled,
            "entries": row["entries"],
            "hits": row["hits"],
            "bytes": row["bytes"],
            "max_entries": self.max_entries,
            "default_ttl_seconds": self.default_ttl,
        }
