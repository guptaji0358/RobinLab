# LIAS Knowledge Management

## Storage

SQLite at `.claude/lias/database/lias.sqlite3` with an FTS5 mirror table kept
in sync by triggers. All records carry provenance, confidence, verification
state, timestamps, expiry, `project_id` and a version.

## Categories

Facts, architecture decisions, preferences/conventions, build and toolchain
configuration, validated commands, known errors and resolutions, automation
metadata, temporary information (with expiry), and historical decisions.

## Adding knowledge

```powershell
python .claude/lias/cli.py knowledge add --category rule --content "Projects live in root/projects/." --provenance "CLAUDE.md:The one rule"
```

- Secrets are rejected (`on_secret=reject` in the CLI path). The store can
  redact instead when called programmatically with `on_secret="redact"`.
- Exact duplicates and high-similarity duplicates are refused.
- Contradictions (subject overlap with opposite negation polarity) are refused.
- `--force` overrides a duplicate/contradiction result after manual review, but
  never overrides secret rejection.
- `--expires` takes an ISO timestamp; expired records are queued for purge.

## Retrieval pipeline

1. Exact phrase substring.
2. Per-token keyword match, ranked by token coverage.
3. FTS5 (quoted terms; punctuation cannot break the query).
4. Relevance floor, verification/expiry filtering, context-character budget.

Only verified, non-expired records are returned by default. `include_unverified`
and `include_expired` exist for maintenance, not for normal answers.

```powershell
python .claude/lias/cli.py knowledge search "cloudflare deploy" --limit 5
python .claude/lias/cli.py knowledge list --category routing
python .claude/lias/cli.py knowledge delete decision_abc123
```

## Automatic learning

- `learn note "Confirmed: ..."` records a candidate with confidence.
- Repeating the same fact increments frequency.
- `learn promote --min-frequency 2` validates and stores it with provenance
  `promoted_candidate:<id>`.
- Speculative markers (“maybe”, “probably”, “for now”) lower confidence, and
  candidates are still validated before promotion.
- Already promoted or quarantined candidates are never re-promoted.

## Seeding and indexing

```powershell
python .claude/lias/cli.py knowledge index --seed-only
python .claude/lias/cli.py knowledge index
```

Foundational facts come from `.claude/lias/knowledge/indexing.py`. Full indexing
chunks `.claude/CLAUDE.md` and `docs/COLLECTION.md` by heading. Chunks are
truncated to 1200 characters to keep retrieval compact.

## Audit trail

`audit_log` records knowledge create/update/delete with category, provenance,
version and whether secrets were redacted. Execution history is in
`execution_log`.
