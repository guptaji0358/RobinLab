# Backend map (API + services)

## Golden rule: the API exists TWICE

| Production (Cloudflare Pages Function)         | Local mirror (`dev_server.py`)            |
| ---------------------------------------------- | ----------------------------------------- |
| `functions/api/collection/[[path]].js` (≈760)  | `dev_server.py` (832)                     |

Change one → check the other. Both talk to the Hugging Face bucket
`robinlabdev/robinvault` with `HF_TOKEN` (never exposed to the browser).

## Route table (`onRequest` dispatches by pathname suffix)

| Route                          | JS handler (functions/…)  | Python (dev_server.py)           |
| ------------------------------ | ------------------------- | -------------------------------- |
| `GET /api/collection/files`    | `handleList` 271 → `getListing` 203, `getLqip` 187 | `_serve_listing` 655, `get_listing` 192, `get_lqip` 171 |
| `GET /api/collection/file?path=` | `handleFile` 408 → `streamBucketFile` 325 | `_serve_file` 704, `open_file_stream` 257 |
| `POST/GET …/share`             | `handleShare` 537, `createShare` 454, `resolveShare` 488 | `_serve_share` 539, `_create_share` 558, `_resolve_share` 603 |
| `GET …/download?path=`         | `handleDownload` 570      | `_serve_download` 385            |
| `GET …/skills`                 | `handleSkills` 692, `getSkills` 674 | `get_skills` 331, `summarise_skill` 302 |
| `GET …/skill?id=`              | `handleSkill` 709         | `_serve_skill` 432               |
| `GET /decks/<name>.pptx`       | `functions/decks/[[path]].js` (51 lines) | `_serve_file(..., decks_only=True)` |

Share tokens: HMAC-signed, expiry inside payload, **30 min**; `410` after expiry.
JS: `createShareToken` 111 / `readShareToken` 121. Python: `create_share_token` 127 / `read_share_token` 134.
Servable types: images + `.pptx` only; everything else → `415` (`is_servable` py 67, `PPTX_TYPE` js 32).
Skill front-matter parsing: `parse_front_matter` py 281.

## Watermark service (`watermark_service/`, FastAPI + Pillow, HF Space)

- `app.py` — `/health`, `/download` (key-checked via `_check_key`, fetches original read-only via `_fetch_original`).
- `watermark.py` — `apply_watermark` 120 (tiled text 43 + corner badge 80).
- The site relays to it from `handleDownload`; needs `WATERMARK_URL` + `WATERMARK_KEY`.

## Secrets / env

`HF_TOKEN` (required) · `SHARE_SECRET` (optional, falls back to `HF_TOKEN`) ·
`WATERMARK_URL`, `WATERMARK_KEY`. Local: git-ignored `.dev.vars` (template `.dev.vars.example`).
Prod: Cloudflare Pages → Settings → Environment variables. Never print or commit values.

## Tools

`tools/make_icons.py` — favicon/manifest set from `root/assets/robinlab-logo.png`.
`tools/make_thumbs.py` — bucket thumbnails (LQIP source). Both are Python, run on demand.
