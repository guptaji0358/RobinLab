# Token / credit saving rules for agents

## Before reading anything
1. Read `AgentMemory/INDEX.md`, then **one** topic file. Don't open the others.
2. Locate by name: `Grep` a function (`grep -n "function openLightbox" root/js/collection.js`),
   then `Read` with `offset`/`limit` ≈ 60–120 lines around the hit.

## Never read in full (big files)
`root/css/style.css` (2070) · `root/js/collection.js` (1188) · `dev_server.py` (832) ·
`root/index.html` (636) · `root/js/fx.js` (601) · `functions/api/collection/[[path]].js` (~760).
Use the section/line maps in `frontend-map.md` / `backend-map.md`.

## Never read at all
Images, `.ico`, `.pptx`, fonts, `.git/`, `docs/COLLECTION.md` (long; only for API-contract questions).

## Cheap habits
- Edit with targeted `Edit`, don't rewrite whole files. Don't re-read a file after editing.
- Batch independent tool calls in one message.
- Use `Explore`/subagents only for wide sweeps; for a known file a direct grep is cheaper.
- `git diff --stat` before `git diff`; `git log --oneline -5`, not full logs.
- Prefer `wc -l` / `grep -c` to learn size before opening.
- Don't run the dev server or take screenshots unless the change is visual/behavioural.
- Pages are independent: a CSS change in one section rarely needs the others loaded.

## Ask before guessing
If the request is ambiguous (which page? production or local only? which route?), ask one
short question first. A wrong 1000-line edit costs far more than a question.

## Parity checklist (prevents rework)
API change → both `functions/api/collection/[[path]].js` and `dev_server.py`.
Footer/identity change → all page `<head>`/footers. New page → nav in `site.js`, route list in `CLAUDE.md`, this folder.
