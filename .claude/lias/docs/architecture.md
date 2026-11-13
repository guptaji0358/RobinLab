# LIAS v2.0 Architecture Specification
**Local Intelligence & Automation System for RobinLabs**

## 1. System Overview
LIAS (Local Intelligence & Automation System) is a project-local automation and knowledge-retrieval layer embedded within `RobinLabs/.claude/lias/`. Its primary purpose is to reduce redundant Claude model operations by offloading deterministic, repetitive, and retrieval-intensive tasks to verified local execution while preserving full isolation, security, and project context.

## 2. Architectural Decisions Compliance
- **D-001 (Project-Local Runtime)**: The runtime, SQLite database, automation scripts, manifests, and cache strictly live within `<PROJECT_ROOT>/.claude/lias/`. Zero cross-project knowledge leakage.
- **D-002 (Hybrid Automatic Learning)**: Confirmed facts, architecture decisions, and tested commands persist to SQLite with provenance and confidence scores. Speculative or sensitive data (secrets, passwords) are automatically rejected.
- **D-003 (Hybrid Triggering)**: Natural-language routing orchestrates capability identification -> automation execution -> local RAG search -> compact result delivery to Claude.
- **D-004 (Permission Tiers)**:
  - **Tier 0 (Read-Only)**: File statistics, knowledge search, environment checks. Automatic execution permitted.
  - **Tier 1 (Controlled Local Modification)**: LIAS cache, knowledge updates, test execution, candidate logging within `.claude/lias/`. Automatic execution permitted within project policy.
  - **Tier 2 (Sensitive / Consequential)**: Modifying production source code, deleting project files, network publishing. Requires explicit user authorization.
- **D-005 (Autonomous Automation Growth)**: Reusable workflows are observed, scored, statically analyzed via Python AST, tested in isolation, and only activated upon passing validation.

## 3. Directory Layout
```text
<PROJECT_ROOT>/.claude/lias/
├── cli.py                     # Unified CLI entry point
├── core/
│   ├── __init__.py
│   ├── config.py              # Project root detection & config management
│   ├── policy.py              # Security tier enforcement & sandboxing
│   ├── registry.py            # Automation registry & JSON manifest validation
│   ├── runner.py              # Safe subprocess executor with timeouts
│   ├── router.py              # Capability routing & progressive disclosure
│   ├── diagnostics.py         # System health & doctor checks
│   ├── cache.py               # Deterministic caching with hash invalidation
│   └── recovery.py            # Self-healing, rollback & quarantine
├── database/
│   ├── __init__.py
│   ├── schema.sql             # Relational DDL + FTS5 full-text indexing
│   ├── connection.py          # SQLite connection manager with WAL mode
│   └── migrations.py          # Versioned schema migrations
├── knowledge/
│   ├── __init__.py
│   ├── store.py               # Knowledge CRUD & provenance tracking
│   ├── retrieval.py           # Multi-stage retrieval (exact + FTS5 search)
│   ├── validation.py          # Contradiction detection & secret scrubbing
│   └── indexing.py            # Incremental project indexing
├── learning/
│   ├── __init__.py
│   ├── observer.py            # Pattern & workflow observation
│   ├── candidates.py          # Cost-benefit scoring & promotion criteria
│   └── generator.py           # Safe automation generation & isolated testing
├── automation/
│   ├── manifests/             # Automation JSON manifests
│   ├── scripts/               # Deterministic Python/BAT automations
│   └── generated/             # Autonomous validated automations
├── docs/                      # Technical & operational documentation
└── tests/                     # Automated test suite
```

## 4. Component Data Flow
```text
[User Prompt / Client]
          │
          ▼
   [LIAS Router]
    ├── 1. Exact Automation Match ──> [Runner] ──> [Automation Script] ──┐
    ├── 2. Exact Knowledge Match   ──> [Knowledge Store] ────────────────┤
    ├── 3. FTS5 Full-Text Search   ──> [Knowledge Retrieval] ────────────┤
    └── 4. Learning Observer       ──> [Candidate Tracker]               │
                                                                         ▼
                                                            [Compact JSON Result]
                                                                         │
                                                                         ▼
                                                             [Delivered to Claude]
```

## 5. Security & Isolation Boundaries
1. **Path Sandboxing**: Scripts and file operations must resolve strictly within `<PROJECT_ROOT>` unless explicitly granted. Path traversal (`..`) attempts are blocked.
2. **Untrusted Data Isolation**: Retrieved knowledge and external documents are treated as untrusted text and never executed directly as shell commands.
3. **Execution Safety**: Subprocess execution uses argument lists (`sys.executable, script_path, ...`), disables `shell=True` on dynamic inputs, enforces timeouts (default 30s), and bounds stdout/stderr captures.
4. **Secret Scrubbing**: Knowledge input is filtered against regex patterns for API keys, bearer tokens, private keys, and `.env` formats.

## 6. Testing Strategy
A modular unittest suite will verify:
- Path normalization and project isolation
- Security tier enforcement
- Knowledge store persistence, FTS5 retrieval, expiration, and contradiction checks
- Subprocess timeouts and bounded capture
- Automation registration and manifest schemas
- Autonomous growth lifecycle (discover -> score -> generate -> validate -> test -> activate)
- Caching hit/miss and invalidation
- Self-healing, quarantine, and database migrations
