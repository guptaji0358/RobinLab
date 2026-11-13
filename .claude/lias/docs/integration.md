# LIAS Client Integration (actual behaviour)

## Environment verified

This project is used through a coding agent (OpenCode / Claude-style agent with
filesystem and shell access) on Windows 11 with PowerShell 5.1 and Python 3.13.
The `.claude/` directory is a filesystem resource, not a registered Claude
Desktop connector.

## What is automatic

- **Capability discovery by the agent.** `.claude/CLAUDE.md` tells the agent to
  prefer LIAS before scanning the tree. The agent chooses `route`, `run`, or
  `knowledge search` based on the request.
- **Caching, retries, quarantine, logging** inside each LIAS command.
- **Knowledge promotion** when an explicit fact is repeated to the threshold.

## What is not automatic

- **No prompt interception.** There is no supported pre-model hook that can
  inspect every user message in this environment, so LIAS cannot silently route
  arbitrary prompts. Do not claim it does.
- **No lifecycle hooks are installed.** No `.claude/settings.json` hook block
  was added, because the current client does not execute Claude Code hooks.
  Hooks must not be invented. If the project is later used through Claude Code
  with a verified hook schema, `learn scan` and `learn note` are the intended
  hook entry points.
- **No background daemon.** Every operation is on demand.

## Recommended agent loop

1. Read `.claude/CLAUDE.md` (and the memory index).
2. For a request with a known local capability, call the CLI first:

   ```powershell
   python .claude/lias/cli.py route "<user request>"
   ```

3. If `action` is `automation`, use the returned structured result.
4. If `action` is `knowledge`, answer from `matches` and cite `provenance`;
   do not present unverified records as confirmed.
5. If `action` is `unmatched`, use normal reasoning and tools, then record any
   durable confirmed fact:

   ```powershell
   python .claude/lias/cli.py learn note "Confirmed: <fact>"
   ```

6. After repeated local runs, inspect growth:

   ```powershell
   python .claude/lias/cli.py learn scan
   python .claude/lias/cli.py candidates
   ```

## Complete example

User: “How many files and lines are in this repo?”

```powershell
python .claude/lias/cli.py route "how many files and lines in the repo?"
```

LIAS matches the `source-file-stats` keywords, runs the script locally, and
returns a compact JSON result:

```json
{
  "action": "automation",
  "summary": "Executed local automation 'Source File Statistics' (source-file-stats) with status 'success'.",
  "duration_ms": 95,
  "data": {
    "automation_id": "source-file-stats",
    "status": "success",
    "cached": false,
    "result": { "result": { "files_scanned": 128, "total_lines": 18420 } }
  }
}
```

The agent reads the numbers and answers the user. No source files enter the
model context. On a repeated identical call the cache returns the stored result
(`cached: true`) without starting Python again.

## Setup costs vs recurring costs

Authoring a manifest/script and indexing documents are one-time costs. Cached
reuse and local retrieval are recurring savings in wall-clock time and context
size. LIAS reports both separately and does not subtract one from the other.
