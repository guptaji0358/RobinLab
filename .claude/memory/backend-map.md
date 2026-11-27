# Backend map (API + services)

## Golden rule: the API exists TWICE

| Production (Cloudflare Pages Function)         | Local mirror (`scripts/dev_server.py` → `scripts/devserver/` package) |
| ---------------------------------------------- | ----------------------------------------- |
| `scripts/functions/api/collection/[[path]].js` (≈760)  | `scripts/devserver/` — 9 category folders, see below |

`scripts/devserver/` folders: `core` (config, paths, settings, caches) · `web` (handler, api_router,
responses) · `hf` (http, stream, listing, lqip) · `collection` (file/listing/backdrop/decks
routes) · `share` · `download` · `skills` · `canva` · `app` (server, cli, banner).

Change one → check the other. Both talk to the Hugging Face bucket
`robinlabdev/robinvault` with `HF_TOKEN` (never exposed to the browser).

## Route table (`onRequest` dispatches by pathname suffix)

| Route                          | JS handler (functions/…)  | Python (`scripts/devserver/…`)           |
| ------------------------------ | ------------------------- | -------------------------------- |
| `GET /api/collection/files`    | `handleList` → `getListing`, `getLqip` | `collection/listing_route`, `hf/listing`, `hf/lqip` |
| `GET /api/collection/file?path=` | `handleFile` → `streamBucketFile` | `collection/file_route`, `hf/stream` |
| `POST/GET …/share`             | `handleShare`, `createShare`, `resolveShare` | `share/route`, `share/create`, `share/resolve` |
| `GET …/download?path=`         | `handleDownload`          | `download/route` (+ `local`, `relay`) |
| `GET …/backdrop[?prev=]`       | `handleBackdrop`          | `collection/backdrop`, `collection/backdrop_route` |
| `GET …/skills`                 | `handleSkills`, `getSkills` | `skills/routes`, `skills/store`, `skills/summary` |
| `GET …/skill?id=`              | `handleSkill`             | `skills/routes`                  |
| `GET /decks/<name>.pptx`       | `scripts/functions/decks/[[path]].js` | `collection/decks_route`   |
| `/api/canva/*`                 | `scripts/functions/api/canva/` | `canva/` (route, login, callback, edit) |

Share tokens: HMAC-signed, expiry inside payload, **30 min** for images, **90 days** for decks (`DECK_SHARE_TTL_SECONDS`); `410` after expiry.
Also: `scripts/functions/_middleware.js` (www/pages.dev → roveuth.com 301), `scripts/kind_service/` (HF Space; Function reads `KIND_URL`+`KIND_KEY`).
JS: `createShareToken` 111 / `readShareToken` 121. Python: `share/tokens.py`.
Servable types: images + `.pptx` only; everything else → `415` (`core/content_types.py`, `PPTX_TYPE` js 32).
Skill front-matter parsing: `skills/frontmatter.py`.

## Watermark service (`scripts/watermark_service/`, FastAPI + Pillow, HF Space)

- `app.py` — `/health`, `/download` (key-checked via `_check_key`, fetches original read-only via `_fetch_original`).
- `watermark.py` — `apply_watermark` 120 (tiled text 43 + corner badge 80).
- The site relays to it from `handleDownload`; needs `WATERMARK_URL` + `WATERMARK_KEY`.

## Secrets / env

`HF_TOKEN` (required) · `SHARE_SECRET` (optional, falls back to `HF_TOKEN`) ·
`WATERMARK_URL`, `WATERMARK_KEY`. Local: git-ignored `scripts/.dev.vars` (template `scripts/.dev.vars.example`).
Prod: Cloudflare Pages → Settings → Environment variables. Never print or commit values.

## Tools

`scripts/tools/make_icons.py` — favicon/manifest set from `scripts/root/assets/robinlab-logo.png`.
`scripts/tools/make_thumbs.py` — bucket thumbnails (LQIP source). Both are Python, run on demand.
