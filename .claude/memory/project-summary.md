# RobinLabs — compiled project summary

One-file brain dump so no session has to re-derive the project. Verified against
the tree on 2026-11-23. Details live in the sibling maps; this file is the overview.
If something here contradicts the code, trust the code and fix this file.

## What it is

Robin Gupta's studio site + project portfolio, live at **https://roveuth.com**
(brand **RobinLab**; legal/footer identity **Robin Gupta Studios / RGS™**; keep them
separate). Static HTML/CSS/vanilla JS, **no framework, bundler, package manager or build
step**. Repo: github.com/guptaji0358/RobinLab (branch `master`). Owner: Robin Gupta.

## Repo layout (top level)

| Path | Role |
| --- | --- |
| `scripts/root/` | The ONLY thing Cloudflare publishes: pages, `css/`, `js/`, `assets/`, `data/`, `projects/` |
| `scripts/functions/` | Cloudflare Pages Functions (prod API, middleware, decks route) |
| `scripts/tools/` | Python helpers: `make_icons`, `make_thumbs`, `make_og`, `make_watch_links`, `devctl` |
| `scripts/tests/` | Node tests (`*.test.mjs`): canva (3), globe, middleware, seo, watermark_resilience |
| `scripts/wrangler.toml` | Pages config, `pages_build_output_dir = "root"` |
| `dev_server.py` + `devserver/` | Local mirror of the production API (45 modules, 9 folders) |
| `watermark_service/` | FastAPI+Pillow HF Space that stamps the RGS watermark on downloads |
| `kind_service/` | FastAPI HF Space: image pixel-size ("Kind/Quality") cache in MongoDB |
| `docs/` | `COLLECTION.md` (bucket/API), `GLOBE.md`, `SEO.md` |
| `.claude/` | `CLAUDE.md`, `memory/` (this), `lias/` (local automation), `launch.json` |
| root `.bat` | `deploy.bat` (works), `dev.bat` (see Gotchas) |

## Pages (all in `scripts/root/`)

`index` hub (featured projects, about, contact, JSON-LD) · `projects` (all cards) ·
`collection` (artwork vault, packs) · `logos` (LOGO/ folder, dark+light, Edit in Canva) ·
`certificates` · `presentations` (.pptx via Office Web Viewer) · `skills` (Claude skills
from bucket) · `music` · `404`. Plus `robots.txt`, `sitemap.xml`, `_headers`,
`site.webmanifest`. Sub-projects (each self-contained, served at `/projects/<Name>/`):
**CodeLens, Contact Book (link as `Contact%20Book`), Motiva, Pywix**.

## Architecture in one paragraph

Media (images, `.pptx` decks, skill `.md`) lives in a private Hugging Face bucket
`robinlabdev/robinvault`. The browser never sees `HF_TOKEN`; a Cloudflare Pages Function
(`scripts/functions/api/collection/[[path]].js`) proxies listing/file/share/download/
backdrop/skills. **The same API is re-implemented in Python** (`devserver/`) for local use —
a change to one nearly always needs the other (and `js/fx.js` for the backdrop).
Downloads relay through `watermark_service`. Logos can be sent to the visitor's Canva via
OAuth+PKCE (`/api/canva/*`, also mirrored in `devserver/canva/`).

## Feature facts worth remembering

- **Share links**: HMAC-signed, expiry inside the payload. Images **30 min**, decks
  **90 days**; `410` after expiry. Secret = `SHARE_SECRET` (falls back to `HF_TOKEN`).
- **Servable types**: images + `.pptx` only, else `415`.
- **Decks**: `/decks/<name>.pptx` public route (`functions/decks/[[path]].js`) because
  Microsoft's viewer needs a public URL. Embed only works on the deployed site.
- **Collection backdrop** random per load (`/api/collection/backdrop`), read-only on bucket.
  Logic exists in the Function, `devserver/collection/backdrop*.py` and `js/fx.js`.
- **Image loading**: `collection.js` scheduler (MAX_ACTIVE=3); observe `.col-card-media`,
  never the `<img>` (clip-path makes IntersectionObserver see 0%).
- **Anime Watch buttons**: `AnimeWatchURL.json` (root, source of truth, read-only) →
  `make_watch_links.py` → `scripts/root/data/anime-watch.json`; fallback is Crunchyroll search.
- **Kind/Quality in lightbox**: Function calls `KIND_URL/kinds` with `X-Kind-Key` if both
  env vars are set; otherwise feature is simply off.
- **Canonical host**: `functions/_middleware.js` 301s `www.roveuth.com` and
  `robinlab.pages.dev` to `roveuth.com`; `<hash>.robinlab.pages.dev` previews pass through.
- **SEO**: canonical/OG/Twitter per page; `/collection`, `/logos`, `/certificates` are
  `noindex,follow`; JSON-LD on home + project pages. See `docs/SEO.md`.
- **Visual layers** (all pages): `fx.js/css` (loader, code-rain, hero, cursor, reveal),
  `motion.js/css` (ink trail, spring chips), globe (`globe*.js`, three.js self-hosted),
  `soft-edges.css` (loaded last), `veins.css` (SVG card edges; remove `<link>` to revert).

## Secrets / env (names only, never values)

`HF_TOKEN` (required) · `SHARE_SECRET` · `WATERMARK_URL` + `WATERMARK_KEY` ·
`KIND_URL` + `KIND_KEY` (kind_service also: `MONGODB_URI`, `MONGODB_DB`, `BUCKET_ID`) ·
Canva client id/secret (see `docs/COLLECTION.md` → Edit in Canva). Local: git-ignored
`.dev.vars` (template `.dev.vars.example`). Prod: Pages → Settings → Environment variables.

## Run / test / deploy

```
python dev_server.py [--port 8080]      # http://127.0.0.1:5500 site + API
python scripts/tools/devctl.py start|stop|restart|status [--open]
node --test scripts/tests/              # all Node tests
deploy.bat                              # cd scripts; wrangler pages deploy root ...
```

Deploy is **manual Direct Upload**; `git push` does NOT deploy. If a change "did nothing":
`wrangler pages deployment list --project-name=robinlab` vs `git rev-parse HEAD`.
`npx` may be blocked by PowerShell policy → `cmd /c "npx wrangler ..."`.

## Conventions & rules

- Projects only in `scripts/root/projects/` — one copy, no top-level `projects/`, no sync step.
- Footer identity + `<meta author|publisher|copyright>` change on every page together.
- URLs/social links: edit `js/links.js`, not HTML. Nav/footer: `js/site.js`.
- Ambiguous request (design, scope, data source) → ask with AskUserQuestion first.
- Commits: use the LIAS `git-commit-push` automation, only after user names paths + message.
- Test/evaluate tasks: tester role, no fixing (see global rules in `CLAUDE.md`).
- Use `.claude/lias/cli.py route "<request>"` before scanning the tree.

## Gotchas / known drift

- `dev.bat` calls `python tools\devctl.py` but `tools/` is at `scripts/tools/` — the path
  is stale (verified: no root `tools/`). Use `python scripts/tools/devctl.py` instead.
- `CLAUDE.md` Pages table lists 6 routes; `music`, `projects`, `404` also exist.
- `scripts/.wrangler/tmp/` and `.cache/` hold generated junk — ignore when searching.
- Uncommitted at snapshot: SEO/middleware, `kind_service/`, `make_og.py`, new tests,
  `canva-logo.png`, memory edits.

## Where to go next

`frontend-map.md` (pages/JS/CSS lines) · `backend-map.md` (routes, mirrors) ·
`workflows.md` (recipes) · `token-saving.md` (cheap-search rules).
