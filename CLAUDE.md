# RobinLabs

Static site and project portfolio. Each project is a self-contained static site
with its own `assets/`, `css/` and `js/`. There is no framework or bundler and no
package manager — the only build step is the project mirror described below.

## Layout

```
root/               main site — the ONLY directory Cloudflare publishes
  index.html        project hub (links into projects/<name>/)
  collection.html   artwork vault — one section ("pack") per bucket folder
  presentations.html  .pptx decks, embedded via Microsoft Office Web Viewer
  css/ js/ assets/  site styles, scripts, and the icons used on the hub
  projects/         GENERATED mirror of ../projects — git-ignored, never edit
projects/           source of truth for every project
  CodeLens/
  Contact Book/     (space in the folder name → link as Contact%20Book)
  Motiva/
  Pywix/
functions/          Cloudflare Pages Function: /api/collection/* proxy
tools/
  sync_projects.py  mirrors projects/ → root/projects/
  make_thumbs.py    bucket thumbnail generator
dev_server.py       local server for root/ + the collection API
wrangler.toml       Cloudflare Pages config (pages_build_output_dir = "root")
```

## The one rule

**Projects live in `projects/`. Cloudflare only publishes `root/`.**

`projects/` sits outside the published directory, so `tools/sync_projects.py`
copies it into `root/projects/` before every deploy (Cloudflare build command)
and before every local preview (`dev_server.py` runs it automatically).

- Edit projects in `projects/<name>/`.
- Never edit `root/projects/` — it is generated and git-ignored.
- `root/index.html` links to `projects/<name>/index.html` (relative to the site root).

## Adding a new project

1. Create `projects/<Name>/` with an `index.html` and its own assets. Use
   relative paths inside the project — assume it is served from
   `/projects/<Name>/`.
2. Add a card to `root/index.html` in the `.project-grid` section:
   - watermark + logo images → `projects/<Name>/…`
   - link → `projects/<Name>/index.html` (URL-encode spaces, e.g.
     `projects/Contact%20Book/index.html`). Always name `index.html` explicitly —
     a bare `projects/<Name>/` breaks when the page is opened from disk
     (`file://`), because browsers list the directory instead of loading it.
3. Optionally drop a hub icon in `root/assets/` (the existing ones are
   `pywix-icon.ico`, `codelens-icon.ico`, `contactbook-icon.png`; Motiva pulls
   its favicon straight from `projects/Motiva/Assets/logo/`).
4. Re-run `python tools/sync_projects.py` (or just start `dev_server.py`).
5. Commit — never commit `root/projects/`.

No other file needs to change: the mirror and deploy pick the folder up
automatically.

## Pages

Three routes, all served from `root/`:

| Route | File | Content |
| --- | --- | --- |
| `/` | `index.html` | Project hub, activity, about, contact |
| `/collection` | `collection.html` | Images from the bucket, grouped by folder ("packs") |
| `/presentations` | `presentations.html` | `.pptx` decks, embedded via Microsoft Office Web Viewer |

Both vault pages read `/api/collection/files` (the Pages Function in
`functions/`, or `dev_server.py` locally). Images load through
`/api/collection/file?path=…`; the proxy serves **images** and **`.pptx`** only,
everything else is rejected with `415`.

Decks also have a clean public route, `/decks/<name>.pptx`
(`functions/decks/[[path]].js`), because Microsoft's viewer downloads the file
itself and needs a public URL ending in `.pptx`. That route serves files from
`presentations/` only; the Hugging Face token stays server-side either way.

- Collection shows images only — presentations never appear there.
- Each bucket folder becomes one pack section, images keep their real aspect
  ratio (nothing is cropped).
- Collection is full-bleed on purpose: `body.col-page` lifts the 1080px
  `.container` cap so the media grid uses the whole window (`root/css/style.css`,
  under `.container`). Text pages keep the reading width.
- `/presentations` embeds `view.officeapps.live.com`; nothing is rendered by this
  repo, so there is no JS bundle to maintain. Microsoft caches the file briefly.
- Decks are meant to be shared: the viewer has a **Download .pptx** button and the
  page invites visitors to email Robin for a new deck. The `/decks/*` route is
  therefore public by design.
- Office Web Viewer needs the deck to be publicly reachable — it cannot see
  localhost, so the embed only works on the deployed site (or a public tunnel).
- Layout is responsive from 320 px up; the nav wraps to a second row below 560 px.

## Running locally

```powershell
python dev_server.py            # http://127.0.0.1:5500  (site + collection API)
python dev_server.py --port 8080
python dev_server.py --no-sync  # don't refresh the projects/ mirror
```

A plain `python -m http.server 5500 --directory root` also works for the static
pages, but it has no `/api/collection/*` proxy and does not refresh the mirror,
so run `python tools/sync_projects.py` first. `.claude/launch.json` has both
configurations (`robinlab-root`, `robinlab-collection`).

The collection API needs `HF_TOKEN` in the environment or in a git-ignored
`.dev.vars` file. See `COLLECTION.md`.

## Deployment

Cloudflare Pages, project `robinlab`, connected to GitHub.

| Setting | Value |
| --- | --- |
| Build command | `python3 tools/sync_projects.py` |
| Build output directory | `root` |
| Production URL | https://robinlab.pages.dev |
| Secret | `HF_TOKEN` (Pages → Settings → Environment variables) |

The build command is mandatory: without it `root/projects/` is empty and every
project link 404s. `wrangler.toml` pins the output directory, and the Function
in `functions/` is picked up from the repo root automatically.

Repository: <https://github.com/guptaji0358/RobinLab> (branch `master`).

> **Pages project type matters.** Only a *Git-connected* Pages project has
> Settings → Builds & deployments → Build configurations. A *Direct Upload*
> project (created by `wrangler pages deploy`) has no build step at all, so no
> build command field ever appears. Direct Upload projects **cannot** be
> converted — create a new Git-connected project (delete the old one first if you
> want to keep the `robinlab` name and the `robinlab.pages.dev` URL), then re-add
> the `HF_TOKEN` variable.

Manual deploy instead:

```powershell
python tools/sync_projects.py
npx wrangler pages deploy root --project-name=robinlab --branch=master
```

`compatibility_date` in `wrangler.toml` must not be in the future relative to
Cloudflare's clock or the deploy fails.

## Docs

- `COLLECTION.md` — bucket architecture, API contract, thumbnails, deploy
  details, security notes.
