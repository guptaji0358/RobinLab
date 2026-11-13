# LIAS Automations

## Manifest contract

Each `.json` file in `automation/manifests/` must have a filename matching its
`id` and at least: `id`, `name`, `description`, `entry_point`. Optional fields:

| Field | Purpose |
| --- | --- |
| `tier` | 0 read-only, 1 local modification, 2 sensitive (default 0) |
| `enabled` | false = disabled/quarantined |
| `version` | also part of the cache key |
| `timeout_seconds` | 1–600, enforced by the runner |
| `working_dir` | project-relative subprocess cwd |
| `keywords` | deterministic natural-language matching |
| `input_schema` / `output_schema` | JSON-schema subset validation |
| `cache_policy` | `{enabled, ttl, fingerprint_paths}` |
| `failure_policy` | `{max_retries, quarantine_on_failures}` |
| `generated`, `validation`, `created_by` | provenance for generated work |

Scripts receive JSON on stdin and must print one JSON object. Non-object output
is wrapped as `{"output": ...}`.

```powershell
python .claude/lias/cli.py run source-file-stats --input "{}"
```

## Failure handling

1. Input schema check (blocking, before execution).
2. Tier and path policy checks.
3. Timeout and bounded stdout/stderr capture.
4. Retry up to `max_retries` (hard cap 3 total attempts).
5. Output schema check (warning; `output_valid: false`).
6. Consecutive failures reach `quarantine_on_failures` → automation disabled.
7. Release manually after review:

   ```powershell
   python .claude/lias/cli.py quarantine list
   python .claude/lias/cli.py quarantine release source-file-stats
   python .claude/lias/cli.py automation disable source-file-stats
   python .claude/lias/cli.py automation enable source-file-stats
   ```

Release inserts a `reset` history row and re-enables the automation.

## Caching

Tier 0 automations with `cache_policy.enabled` are cached by automation id,
version, normalized input and optional fingerprints.

- `fingerprint_paths` accepts globs. Files are hashed by content; directories
  by relative file names, sizes and mtimes.
- Changing any fingerprinted input invalidates the entry.
- Sensitive-looking outputs (`api_key`, bearer tokens, private keys) are not
  cached.
- Default TTL and entry cap come from `config/settings.json`.

## Generated automations

Growth is bounded and deterministic:

```text
observe repeated runs → candidate → threshold + risk check → whitelisted
template → static AST validation → isolated test → register + activate
```

```powershell
python .claude/lias/cli.py learn scan --min-runs 3
python .claude/lias/cli.py candidates
python .claude/lias/cli.py learn generate <candidate_id> --template directory-summary
python .claude/lias/cli.py learn generate-all
```

Refusals are normal:

- repeated use of an existing automation ⇒ `reused` (no duplicate code);
- no whitelisted template ⇒ `rejected`;
- below frequency/value threshold ⇒ `rejected`;
- static scan finds forbidden imports/calls ⇒ rejected and quarantined;
- isolated test failure ⇒ rejected and quarantined;
- generated-count limit ⇒ `quota_exceeded`.

Templates: `directory-summary` (files by extension, read-only) and
`log-summary` (error/warning counts, read-only). Both enforce project-relative
paths and never write to user files.

Generated scripts live in `automation/generated/`; their manifests are ordinary
manifests and can be disabled or deleted like any other.

## Writing a new automation

1. Put the script in `automation/scripts/` and make it read `json.load(sys.stdin)`.
2. Emit `{"status": "success", "result": {...}}`.
3. Add a manifest with `tier: 0`, a timeout, keywords and cache policy.
4. Run `doctor` (validates manifests) and `run <id>`.
5. Add a unittest under `.claude/lias/tests/`.

Never add `shell=True`, network access, credential reads or writes outside the
project. Tier 2 operations require explicit authorization.
