# AgentMemory — read this first

Map of the RobinLabs repo so you can jump straight to the right file instead of
scanning the tree. Snapshot: 2026-11-06. Line numbers are approximate; if one is
off, `grep -n` the function name (cheap) rather than reading the whole file.

## Task → where to look

| I need to…                                   | Open                         |
| -------------------------------------------- | ---------------------------- |
| change a page, JS behaviour or CSS           | `frontend-map.md`            |
| change an `/api/collection/*` route          | `backend-map.md`             |
| run, deploy, add a project, set secrets      | `workflows.md`               |
| spend fewer tokens/credits on this repo      | `token-saving.md`            |
| bucket / API contract / thumbnails (long)    | `docs/COLLECTION.md` (only if the above is not enough) |

## 10-line mental model

- Static site, **no build step, no package manager**. Only `root/` is published.
- Projects live in `root/projects/<Name>/` — one copy, never a top-level `projects/`.
- Pages: `index` (hub, 3 featured projects), `projects` (all project cards), `collection`, `presentations`, `skills`, `music`, `certificates`.
- Images/decks/skills live in a Hugging Face bucket, proxied by a Cloudflare Pages Function.
- **The API exists twice**: `functions/api/collection/[[path]].js` (production) and
  `dev_server.py` (local). A change to one almost always needs the other.
- Watermarked downloads go through `watermark_service/` (FastAPI, separate HF Space).
- Deploy is manual (`deploy.bat`); `git push` does not deploy.

## Known doc drift

`CLAUDE.md` lists 4 routes, but `music.html` and `certificates.html` also exist, and
`js/links.js` (central URLs), `js/fx.js` + `css/fx.css` (visual effects),
`js/names.js` (Title Case display names) and `css/theme.css` are not mentioned there.

## Keep this folder honest

When you add/rename a page, JS file or API route, update the matching file here in
the same commit. Wrong memory costs more than none.
