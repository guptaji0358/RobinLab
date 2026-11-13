# LIAS Security Model

## Permission tiers

| Tier | Examples | Behaviour |
| --- | --- | --- |
| 0 | stats, reads, env checks, knowledge search | automatic |
| 1 | LIAS cache/logs/knowledge, tests, candidates | automatic within policy |
| 2 | deleting user files, source edits, installs, network, publish | requires authorization |

`security.tier1_auto_exec` and `security.tier2_auto_exec` in
`config/settings.json` gate automatic execution. The runner refuses a manifest
whose tier is not permitted; it never escalates on its own.

## Boundaries enforced in code

- **Path containment.** Entry points and working directories resolve inside the
  project; `..`, symlink and junction escapes raise `PolicyViolation`.
- **No shell interpolation.** Commands are argument arrays. `.bat/.cmd` run via
  `cmd.exe /d /c`, `.ps1` via `powershell -File`, never through a constructed
  shell string with user input.
- **Bounded execution.** Timeouts, output caps, retry caps and a total attempt
  cap prevent runaway work.
- **Input/output validation.** A manifest's schemas are checked before and
  after execution.
- **Secret scrubbing.** Knowledge input is scanned for API keys, bearer tokens,
  private keys, GitHub/Sketch tokens and quoted credential assignments. The CLI
  rejects secret-bearing knowledge; programmatic redaction replaces matches
  with `[REDACTED_SECRET]`.
- **Untrusted text stays data.** Retrieved knowledge and documents are never
  executed. Generated scripts are checked with an AST scan for forbidden
  imports/calls (`subprocess`, `socket`, `eval`, `exec`, deletes) and must emit
  JSON.
- **Cache hygiene.** Outputs that look sensitive are not cached.
- **Project isolation.** Database, cache, logs, backups and manifests live under
  this project's `.claude/lias/`. Retrieval can additionally filter by
  `project_id`.

## What this is not

The path checks and AST scan are application-level safeguards, **not** an
operating-system sandbox. They do not replace Claude/client permission prompts,
OS permissions, or connector approvals. LIAS must never be used to bypass them.

## Tier 2 handling

Do not add Tier 2 automation without explicit user authorization. Do not store
credentials, `.env` contents or private conversation text in the knowledge
database. Do not commit `.dev.vars`, `.env` or `database/*.sqlite3*`; they are
git-ignored.

## Reporting a suspected issue

1. Disable the automation: `quarantine release` reverses this, so first inspect
   `candidates` and the manifest.
2. Run `python .claude/lias/cli.py fsck`.
3. Create a backup before changing data.
4. Document the affected automation id and caller in the issue.
