---
name: rate-codelens
description: Use when the user says "rate codelens", "retest codelens" or "review codelens". Runs a read-only test of the Code-Lens MCP (code-lens tools) as a real user, rates it honestly, and saves the review privately. Never edits Code-Lens.
---

# Rate Code-Lens

Code-Lens is the user's own MCP server. I am its **user/tester, not its developer**.

## Rules
- Read-only. NEVER edit, create or fix Code-Lens code, and never commit. Only report.
- Ratings are my own judgment, not Code-Lens output; say so. No encouragement ratings.
- Save results to `D:/Apps/MyApps/RobinLabs/.claude/.private/evaluations/codelens-review-<YYYY-MM-DD>.md` (git-ignored; never commit or publish).
- Start by reading the previous review in that folder and compare: which reported bugs are fixed, which remain, any regressions.

## Steps
1. Load the tools: ToolSearch `select:mcp__code-lens__get_capabilities,...` (all 8 code-lens tools). If the server is missing/disconnected, say so and stop; do not claim results.
2. `get_capabilities` (check version change).
3. `list_files` (extensions + exclude + detail + pagination cursor).
4. `get_file_outline`: Python (`dev_server.py`), JS (`scripts/root/js/motion.js`, `scripts/functions/api/collection/[[path]].js`), HTML (`scripts/root/index.html`, expect "unsupported").
5. `search_symbols` (e.g. `pick_backdrop`, `handleBackdrop`) WITHOUT `exclude` first, to check whether `.wrangler/` is still scanned.
6. `find_references` (`handleBackdrop`, context=1).
7. `search_code`: word + files_only; flexible; literal; count_only; pagination; check warning noise (binary-skip spam).
8. `read_file`: ranges, `around`, and `../outside.txt` (must be refused).
9. `get_file_info` on a known file.
10. Untested-before extras when time allows: stale cursor, multiline, regex attempt (unsupported by design), large file.

## Report format
Per tool: rating /10, status (Working / Partially / Broken), evidence. Then: overall /10, confirmed bugs (what happened, likely cause, possible fix), limitations, new ideas, still untested. Distinguish confirmed bugs from suspicions. Tell the user the file path of the saved review.

## Pitfall
Drain stdout if probing the server directly over stdio (tools/list is ~11 KB); bisect with a trivial control server before blaming Code-Lens. Prefer the MCP tools over raw probing.
