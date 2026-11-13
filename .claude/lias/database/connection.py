"""LIAS Database Connection and Initialization.

Provides thread-safe SQLite connections with WAL mode and foreign key integrity.
"""

from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Create and configure a SQLite connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 10000;")
    return conn


@contextmanager
def db_session(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite transactions."""
    conn = get_db_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(db_path: Path, schema_file: Path) -> None:
    """Initialize SQLite database with base schema."""
    with db_session(db_path) as conn:
        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        # Record migration version 1
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 1")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (1, 'Initial base schema with FTS5')"
            )
