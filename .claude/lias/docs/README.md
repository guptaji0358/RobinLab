# LIAS v2.0 — Local Intelligence & Automation System

Project-local automation and knowledge layer for **RobinLabs**. Runs inside
`<PROJECT_ROOT>/.claude/lias/`; it never reads another project's database and
never writes outside this project.

## What it actually does

| Capability | Implementation |
| --- | --- |
| Retrieval of verified project facts | SQLite + FTS5, exact → keyword → FTS stages |
| Deterministic local work | Python automations, JSON in/out, timeouts, retries |
| Reuse of repeated work | Execution-log observation → candidate → generated automation |
| Cache of repeatable results | SQLite cache with TTL + file/directory fingerprints |
| Safety | Tier policy, path containment, secret scrubbing, static AST scan |
| Recovery | Verified backups, restore, integrity/config checks, quarantine release |
| Measurement | Real wall-clock benchmarks; no invented token numbers |

## Quick start

```powershell
python .claude/lias/cli.py doctor          # health
python .claude/lias/cli.py status          # compact counts + recent runs
python .claude/lias/cli.py route "how many files and lines in the repo?"
python .claude/lias/cli.py knowledge search "cloudflare deployment"
python .claude/lias/cli.py run source-file-stats
```

The `.bat` wrapper is equivalent: `.\.claude\lias\lias.bat status`.

## Layout

```text
.claude/lias/
├── cli.py                 # single entry point
├── lias.bat               # Windows wrapper
├── core/                  # config, policy, registry, runner, router,
│                          # cache, recovery, validation, diagnostics
├── knowledge/             # store, retrieval, validation, indexing
├── learning/              # patterns, observer, candidates, generator
├── automation/            # manifests/, scripts/, generated/
├── database/              # schema.sql, migrations, lias.sqlite3 (ignored)
├── benchmarks/            # reproducible local measurements
├── docs/                  # this documentation
└── tests/                 # unittest suite
```

## Natural-language use

An agent should consult `.claude/CLAUDE.md` and prefer existing LIAS
capabilities before re-deriving project facts or scanning the tree. LIAS does
**not** intercept prompts by itself — no supported hook exists in this
environment (see `docs/integration.md`). The agent invokes `route`, `run` or
`knowledge search` explicitly.

## Honest limitations

- Local execution reduces repeated work; it does not eliminate model tokens.
- Token savings are **not** reported because they cannot be measured locally.
- Automatic knowledge promotion requires repeated confirmation or explicit
  `Confirmed:` / `Rule:` phrasing; speculation is not promoted.
- Generated automations come only from audited templates and are rejected if
  static validation or the isolated test fails.

See `docs/setup.md`, `docs/knowledge.md`, `docs/automation.md`,
`docs/security.md`, `docs/troubleshooting.md`, and `docs/integration.md`.
