# LIAS v2.0 Architecture Specification

**Local Intelligence & Automation System for RobinLabs** — implemented in
`.claude/lias/`. Each project keeps its own runtime, database, manifests,
cache, logs and backups.

## 1. Design decisions

- **D-001 Project-local runtime.** Everything lives under
  `<PROJECT_ROOT>/.claude/lias/`. No cross-project knowledge access.
- **D-002 Hybrid learning.** Explicitly confirmed facts and validated
  resolutions are stored automatically with provenance. Speculation is not.
- **D-003 Hybrid triggering.** The agent identifies capabilities from
  `.claude/CLAUDE.md` and calls the CLI; deterministic hooks are not installed
  because no supported hook mechanism exists in this environment.
- **D-004 Tiered permissions.** Tier 0 automatic, Tier 1 automatic inside LIAS
  state, Tier 2 requires authorization.
- **D-005 Bounded growth.** Execution-log observation → scored candidate →
  whitelisted template → static AST validation → isolated test → registration.

## 2. Components

| Module | Responsibility |
| --- | --- |
| `core/config.py` | project-root detection, merged settings, atomic writes |
| `core/policy.py` | tiers, path containment, secret scrubbing, command checks |
| `core/validation.py` | dependency-free JSON-schema subset for I/O |
| `core/registry.py` | manifest validation, atomic JSON + SQLite registration |
| `core/runner.py` | policy/schema checks, timeouts, retries, quarantine, caching |
| `core/cache.py` | TTL cache, input hashing, file/directory fingerprints |
| `core/router.py` | deterministic automation-name/keyword match, then knowledge |
| `core/recovery.py` | verified backup/restore, integrity, config checks, logs |
| `core/diagnostics.py` | doctor/status checks and counts |
| `knowledge/store.py` | CRUD, provenance, versions, expiry, audit trail |
| `knowledge/retrieval.py` | exact → keyword → FTS5, validity filters, budgets |
| `knowledge/validation.py` | duplicate/contradiction/sensitive-candidate checks |
| `knowledge/indexing.py` | foundational facts + markdown chunk indexing |
| `learning/patterns.py` | declared-fact extraction, value scoring, thresholds |
| `learning/observer.py` | message and execution-log observation |
| `learning/candidates.py` | candidate frequency, promotion, quarantine |
| `learning/generator.py` | template rendering, static scan, isolated test, activation |
| `cli.py` | single entry point for every operation above |

## 3. Data flow

```text
user request
   │
   ▼
agent reads .claude/CLAUDE.md
   │
   ▼
cli.py route "<request>"
   ├─ 1 exact id/name ─────────────► runner ─► automation script
   ├─ 2 keyword threshold ─────────► runner
   ├─ 3 verified knowledge ────────► SQLite + FTS5
   └─ 4 unmatched ─────────────────► Claude reasoning
                                        │
                              compact structured JSON
                                        │
                                        ▼
                                 answer to the user
```

## 4. Storage

SQLite `database/lias.sqlite3` (git-ignored) with:

- `knowledge` + `knowledge_fts` (triggers keep FTS in sync)
- `automations`, `execution_log`, `candidates`, `cache_entries`
- `audit_log`, `schema_migrations`

Schema version 3 adds cache fingerprints and operation version. Migrations run
idempotently on every CLI start.

## 5. Security boundaries

1. Path containment for entry points and working directories.
2. Argument-array subprocess execution; no shell interpolation.
3. Timeouts, bounded output, bounded retries and generation quotas.
4. Secret scrubbing and secret-rejecting knowledge writes.
5. Generated code is template-only and AST-scanned before isolated execution.
6. Application checks are not an OS sandbox; client/OS permissions still apply.

## 6. Testing strategy

`tests/` contains unit and integration coverage for root detection, isolation,
policy, registry, runner I/O schemas, timeouts, retries, quarantine, caching and
invalidation, knowledge persistence, expiry, contradictions, audit, candidates,
generation, recovery, routing and CLI integration. Tests use temporary projects
for destructive and failure paths.

## 7. Known limitations

- No automatic prompt interception or Claude Code hooks in this environment.
- No semantic/vector retrieval; deliberately FTS5 + deterministic matching.
- Generated automations are limited to audited templates, not arbitrary code.
- Token usage is not measurable locally, so only wall-clock and size metrics
  are reported.
- No background daemon, scheduler, network access or package installation.
