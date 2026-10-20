# Collection — private Hugging Face bucket viewer

The **Collection** page (`root/collection.html`) lists and previews the artwork in the
private Hugging Face bucket **`robinlabdev/robinvault`**.

Each bucket folder becomes one **pack**: a titled section with its images shown at their
real aspect ratio (never cropped to squares). Only images appear here.

PowerPoint decks are **not** shown in the Collection. They live on their own page,
`/presentations` (`root/presentations.html`), which embeds the deck with
**Microsoft Office Web Viewer** (`view.officeapps.live.com`). Microsoft's servers
download the file themselves, so decks are also exposed on a clean public route,
`/decks/<name>.pptx` (`functions/decks/[[path]].js`), which serves only files from
`presentations/`.

It is **view-only by design**. Every user can browse and enlarge images, but the
Download button is disabled (tooltip: *"Downloads unlock when payments are added"*)
until a payment flow exists.

**Live:** <https://robinlab.pages.dev/collection>

---

## Architecture

**Hugging Face is the storage. Cloudflare only renders.**

The bucket is **private**, so the Hub returns `401` unless a valid access token is sent.
A static page cannot hold that token — anything in client-side JavaScript is public, and
a leaked token would expose the entire vault.

So the browser never talks to Hugging Face directly. It calls a proxy that runs
server-side, holds the token, and streams only the files the bucket actually contains:

```
browser  ──►  /api/collection/*        (your site)
                    │
                    │  Authorization: Bearer $HF_TOKEN   (server-side only)
                    ▼
              huggingface.co/api/buckets/robinlabdev/robinvault/tree
              huggingface.co/buckets/robinlabdev/robinvault/resolve/<path>
                    │
                    ▼  302 → short-lived signed CDN URL
              us.aws.cdn.hf.co  →  image bytes  →  browser
```

No files are copied onto Cloudflare. The Function fetches bytes from the bucket on
demand and streams them straight through.

## API contract

Both endpoints are served by `functions/api/collection/[[path]].js` in production and by
`dev_server.py` locally. The behaviour is identical.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/collection/files` | JSON manifest: `bucket`, `count`, `totalSize`, `folders`, `files[]` |
| `GET` | `/api/collection/file?path=<encoded>` | Streams one file's bytes (`image/*` or `.pptx`), always `Content-Disposition: inline` |
| `GET` | `/decks/<name>.pptx` | Public deck URL for Office Web Viewer; serves `presentations/<name>.pptx` only |

Each entry in `files[]` looks like:

```json
{
  "path": "wallpapers/akane-blushing-+-shy-+-smiling.png",
  "name": "akane-blushing-+-shy-+-smiling.png",
  "folder": "wallpapers",
  "size": 1710231,
  "contentType": "image/png",
  "previewable": true,
  "uploadedAt": "2026-10-19T14:33:50.965Z",
  "url": "/api/collection/file?path=wallpapers%2Fakane-blushing-%2B-shy-%2B-smiling.png",
  "thumbUrl": "/api/collection/file?path=_thumbs%2Fwallpapers%2Fakane-blushing-%2B-shy-%2B-smiling.png.webp"
}
```

`thumbUrl` is the small grid preview, or `null` when no preview exists yet — the client
falls back to `url` in that case, so the page never breaks.

---

## Thumbnails

Bucket files are full resolution (often 1–5 MB). Rendering 64 of them in a grid meant
pulling **~128 MB** just to browse, which no browser handles well.

`tools/make_thumbs.py` generates a small WebP copy of every image and uploads it back
into the **same bucket** under a reserved `_thumbs/` prefix:

```
wallpapers/akane-blushing-+-shy-+-smiling.png
  ->  _thumbs/wallpapers/akane-blushing-+-shy-+-smiling.png.webp
```

The grid uses `thumbUrl`; the lightbox still loads the full-resolution original from
`url`. Current result: **119.6 MB → 1.7 MB (1.4%)**.

Files under `_thumbs/` are **hidden from the listing** — they are not counted in the
file total, the folder chips or the size figure — but they are servable by path.

### Re-running after you add images

New uploads simply have no thumbnail until you re-run the script; the grid falls back to
the full-size image in the meantime, so nothing breaks.

```powershell
python tools/make_thumbs.py                 # add missing thumbnails only
python tools/make_thumbs.py --dry-run       # show what would happen
python tools/make_thumbs.py --force         # rebuild every thumbnail
python tools/make_thumbs.py --width 900     # max edge in px (default 720)
python tools/make_thumbs.py --quality 85    # WebP quality (default 78)
python tools/make_thumbs.py --prune         # also delete orphaned thumbnails
```

Originals are **never** modified or deleted. `--prune` only ever removes paths inside
`_thumbs/`. Requires `pip install Pillow` and a token with write access to the bucket.

---

## Running locally

A plain `python -m http.server 5500 --directory root` serves the static pages but has no
`/api/collection/*` proxy and does not refresh the project mirror in `root/projects/` —
run `python tools/sync_projects.py` first if you use it.

Use the bundled dev server instead. It serves `root/`, mirrors `projects/` into
`root/projects/`, **and** runs the bucket proxy:

```powershell
# 1. Create a token at https://huggingface.co/settings/tokens (a Read token is enough)
# 2. Put it in a .dev.vars file (git-ignored):
#      HF_TOKEN=hf_xxxxxxxxxxxxxxxxx
#    ...or set it for the session:
$env:HF_TOKEN = "hf_xxxxxxxxxxxxxxxxx"

python dev_server.py
```

Then open <http://127.0.0.1:5500/collection>.

Options: `python dev_server.py --port 8080 --host 127.0.0.1 --dir root --no-sync`.

`.claude/launch.json` has two configurations: **`robinlab-root`** (port `5500`) and
**`robinlab-collection`** (port `5501`) — both run this server, so the project mirror and
the API are always available.

> This is a **development convenience only** — production runs on Cloudflare Pages.

---

## Deploying

### Current deployment

| | |
| --- | --- |
| Host | Cloudflare Pages |
| Project | `robinlab` |
| Production URL | <https://robinlab.pages.dev> |
| Source | GitHub repo, Cloudflare builds on push |
| Build command | `python3 tools/sync_projects.py` |
| Build output directory | `root` |
| Config | `wrangler.toml` (`pages_build_output_dir = "root"`) |
| Secret | `HF_TOKEN` (encrypted, Pages → Settings → Environment variables) |

The build command is required. Projects live in `projects/`, outside the published
directory, so `tools/sync_projects.py` copies them into `root/projects/` during the
build. Without it every `/projects/<name>/` link 404s.

Only a **Git-connected** Pages project exposes a build command (Settings → Builds &
deployments → Build configurations). A **Direct Upload** project — the kind created by
`wrangler pages deploy` — has no build step and no build command field, and cannot be
converted in place; create a new Git-connected project from
<https://github.com/guptaji0358/RobinLab> instead.

Deploy manually with:

```powershell
python tools/sync_projects.py
npx wrangler pages deploy root --project-name=robinlab --branch=master
```

`wrangler.toml` points at `root/` for static assets; the Function in `functions/` is
picked up automatically from the project root.

> **Note:** `compatibility_date` in `wrangler.toml` must not be in the future relative to
> Cloudflare's clock, or the deploy fails with *"Can't set compatibility date in the
> future"*.

### Other hosts

The front end only depends on the API contract above, so any runtime works — Vercel
(`api/collection/[...path].js`), Netlify (`netlify/functions/`), a VPS, etc. Keep the
token in the host's secret store; never in `root/`.

### Attaching a custom domain

`robinlab.dev` does not currently resolve. To use it, register the domain and add it in
**Pages → Custom domains**; Cloudflare will issue the certificate automatically and tell
you which DNS records to create.

---

## Security notes

- The token lives only in the server environment (`HF_TOKEN`). It is never sent to the
  browser, and the proxy never redirects the browser to a Hugging Face URL.
- The proxy follows the Hub's `302` itself, so the token is sent to `huggingface.co`
  only — never to the CDN.
- `path` is validated against the live bucket listing, so the endpoint cannot be used
  as an open proxy or to fetch arbitrary paths. This includes `_thumbs/` paths.
- Only `image/*` and PowerPoint (`.pptx`) content types are served. Everything else
  returns `415`.
- Non-`GET`/`HEAD` methods are rejected with `405`.
- `.dev.vars` and `.env*` are git-ignored. **Never commit a token.**
- Consider replacing the broad OAuth token with a **read-only, bucket-scoped** token at
  <https://huggingface.co/settings/tokens>. The write access currently used by
  `make_thumbs.py` is only needed when generating thumbnails.

## Enabling downloads later

When payments are added, the change belongs on the server, not just in the UI. A
reasonable shape:

1. Verify the user's entitlement (e.g. a signed session cookie or license token).
2. Add a `/api/collection/download?path=...` endpoint that returns the same bytes with
   `Content-Disposition: attachment` **only** when the entitlement check passes.
3. Enable the Download button in `root/js/collection.js` / `root/collection.html` and
   point it at that endpoint.

> Note: any "view-only" measure in the browser is a deterrent, not real protection —
> a determined user can always re-capture what is rendered on their screen. Real
> gating has to happen server-side.
