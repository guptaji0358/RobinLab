-- LIAS Relational Database Schema v2.0
-- Project-local persistence with SQLite and FTS5

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    provenance TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    verified INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_verified ON knowledge(verified);
CREATE INDEX IF NOT EXISTS idx_knowledge_expires ON knowledge(expires_at);

-- Virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
    id UNINDEXED,
    category,
    content,
    tokenize = 'porter unicode61'
);

-- Triggers to maintain knowledge_fts
CREATE TRIGGER IF NOT EXISTS trg_knowledge_ai AFTER INSERT ON knowledge BEGIN
    INSERT INTO knowledge_fts(id, category, content) VALUES (new.id, new.category, new.content);
END;

CREATE TRIGGER IF NOT EXISTS trg_knowledge_ad AFTER DELETE ON knowledge BEGIN
    DELETE FROM knowledge_fts WHERE id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_knowledge_au AFTER UPDATE ON knowledge BEGIN
    DELETE FROM knowledge_fts WHERE id = old.id;
    INSERT INTO knowledge_fts(id, category, content) VALUES (new.id, new.category, new.content);
END;

CREATE TABLE IF NOT EXISTS automations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    tier INTEGER NOT NULL DEFAULT 0,
    entry_point TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    version TEXT NOT NULL DEFAULT '1.0.0',
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    manifest_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    automation_id TEXT NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    exit_code INTEGER NOT NULL,
    stdout_summary TEXT,
    error_summary TEXT,
    caller TEXT
);

CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    workflow_pattern TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 1,
    estimated_savings INTEGER NOT NULL DEFAULT 100,
    risk_tier INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'observed',
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 0
);
