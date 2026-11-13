# RobinLabs

Static site and project portfolio. Each project is a self-contained static site
with its own `assets/`, `css/` and `js/`. There is no framework or bundler and no
package manager and no build step.

**Agents: read `AgentMemory/INDEX.md` first** — file/function maps and token-saving
rules. Don't scan the tree or open big files whole.

## Layout

```
root/               main site — the ONLY directory Cloudflare publishes
  index.html        project hub (links into projects/<name>/)
  collection.html   artwork vault — one section ("pack") per bucket folder
  presentations.html  .pptx decks, embedded via Microsoft Office Web Viewer
  css/ js/ assets/  site styles, scripts, and the icons used on the hub
  projects/         every project, one folder each — the single copy
    CodeLens/
    Contact Book/   (space in the folder name → link as Contact%20Book)
    Motiva/
    Pywix/
functions/          Cloudflare Pages Function: /api/collection/* proxy
tools/
  make_thumbs.py    bucket thumbnail generator
  make_icons.py     favicon / manifest icon set from the studio logo
dev_server.py       local server for root/ + the collection API
wrangler.toml       Cloudflare Pages config (pages_build_output_dir = "root")
```

## The one rule

**Projects live in `root/projects/`. There is no second copy.**

Cloudflare only publishes `root/`, so projects sit inside it and are deployed and
served locally as they are. Do not recreate a top-level `projects/` folder or a
sync/mirror step.

- Edit projects in `root/projects/<name>/`.
- `root/index.html` links to `projects/<name>/index.html` (relative to the site root).

## Adding a new project

1. Create `root/projects/<Name>/` with an `index.html` and its own assets. Use
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
4. Commit.

No other file needs to change: the deploy picks the folder up automatically.

## Pages

Four routes, all served from `root/`:

| Route | File | Content |
| --- | --- | --- |
| `/` | `index.html` | Project hub, about, contact |
| `/collection` | `collection.html` | Images from the bucket, grouped by folder ("packs") |
| `/presentations` | `presentations.html` | `.pptx` decks, embedded via Microsoft Office Web Viewer |
| `/skills` | `skills.html` | Claude skills from the bucket's `Claude Skills/` folder, plus a how-to-use method |

The footer identity is the same on all three pages — **Robin Gupta Studios /
RGS™ / Built & maintained by Robin Gupta / Copyright © <year> Robin Gupta** —
plus `<meta name="author|publisher|copyright">` in each `<head>`. Change all
three together; `index.html` also carries the Organization JSON-LD block.

### Site icons

The tab icon is the studio emblem, committed to `root/assets/` — the site never
points at a file outside the repo. All three pages link the same set (plus
`<meta name="theme-color" content="#0b0d10">`):

| File | Used for |
| --- | --- |
| `assets/favicon.ico` | browser tab — 16/32/48/64, emblem zoomed in so it reads small |
| `assets/robinlab-icon-192.png` | Android / PWA (192×192) |
| `assets/apple-touch-icon.png` | iOS home screen (180×180, opaque) |
| `assets/robinlab-mark.png` | PWA 512×512 (`site.webmanifest`) |
| `assets/robinlab-logo.png` | the full logo with wordmark — `logo` in the JSON-LD |

`python tools/make_icons.py` regenerates them from `root/assets/robinlab-logo.png`:
it keeps only the emblem block (a wordmark is unreadable at 16–48 px), centres
it on the artwork's own background and feathers the join. Pass `--source` to read
a different logo, or `--install-logo` to also refresh `robinlab-logo.png`.

Both vault pages read `/api/collection/files` (the Pages Function in
`functions/`, or `dev_server.py` locally). Images load through
`/api/collection/file?path=…`; the proxy serves **images** and **`.pptx`** only,
everything else is rejected with `415`.

The lightbox's **Share** button calls `POST /api/collection/share`, which mints an
HMAC-signed link (`/collection?share=<token>`) for that one image. The expiry is
part of the signed payload, so links die after **30 minutes** and `GET
/api/collection/share?token=…` answers `410` afterwards. `SHARE_SECRET` is the
signing key (falls back to `HF_TOKEN`). See `docs/COLLECTION.md` → Share links.

The lightbox's **Download** button calls `GET /api/collection/download?path=…`, which
relays `watermark_service/` (FastAPI + Pillow, deployed as a Hugging Face Space,
read-only on the bucket) and returns the image stamped with the RGS watermark.
Needs `WATERMARK_URL` + `WATERMARK_KEY` (Pages secrets / `.dev.vars`). See
`docs/COLLECTION.md` → Downloads.

Decks also have a clean public route, `/decks/<name>.pptx`
(`functions/decks/[[path]].js`), because Microsoft's viewer downloads the file
itself and needs a public URL ending in `.pptx`. That route serves files from
`presentations/` only; the Hugging Face token stays server-side either way.

- `/skills` reads `GET /api/collection/skills`, which returns only each skill's title, description and `##` outline. The full text is served one skill at a time by `GET /api/collection/skill?id=…` (public, fetched only on **Copy skill** or when a card is dragged out as a `.md` file; `&download=1` adds `Content-Disposition`). Drag sets only a `DownloadURL` payload (Chrome/Edge) so it can't paste into text fields. New `.md` files in `Claude Skills/` appear automatically.
- Collection backdrop (`body.col-page`, `sceneBackground` in `js/fx.js`) is **random**: it
  fetches `GET /api/collection/backdrop[?prev=scene]` (scene, hue, speed, density, and for
  the `wallpaper` scene one random image path from the bucket's `wallpapers/` folder, shown
  full-screen via `/api/collection/file`). Read-only on the bucket — never upload to it.
  Logic exists twice — `pick_backdrop` in `dev_server.py` and `handleBackdrop` in the
  Function; keep both and `fx.js` in sync. Other pages keep the code-rain canvas.
  **Agents: when a request is ambiguous (design choice, scope, data source), ask the user
  with AskUserQuestion before building.**
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
```

A plain `python -m http.server 5500 --directory root` also works for the static
pages, but it has no `/api/collection/*` proxy. `.claude/launch.json` has both
configurations (`robinlab-root`, `robinlab-collection`).

The collection API needs `HF_TOKEN` in the environment or in a git-ignored
`.dev.vars` file. See `docs/COLLECTION.md`.

## Deployment

Cloudflare Pages, project `robinlab` — **Direct Upload, not Git-connected**
(`wrangler pages project list` shows `Git Provider: No`). Pushing to GitHub does
**not** deploy anything; a deploy is always a local command.

| Setting | Value |
| --- | --- |
| Project type | Direct Upload (no Git integration, no Cloudflare build step) |
| Publish directory | `root` (`pages_build_output_dir` in `wrangler.toml`) |
| Build step | none |
| Production URL | https://robinlab.pages.dev |
| Secret | `HF_TOKEN` (Pages → Settings → Environment variables) |
| Optional secret | `SHARE_SECRET` for 30-minute share links (falls back to `HF_TOKEN`) |

```powershell
npx wrangler pages deploy root --project-name=robinlab --branch=master
```

`npx` is blocked by PowerShell's execution policy on this machine; use
`cmd /c "npx wrangler pages deploy ..."` if you hit `npx.ps1 cannot be loaded`.

Wrangler uploads `functions/` from the repo root automatically, so the collection
proxy goes out with the same deploy.

Repository: <https://github.com/guptaji0358/RobinLab> (branch `master`). The repo
is the source of truth, but a `git push` alone never reaches production.

> **Why this matters.** On 2026-10-21 a push landed on GitHub while the live site
> kept serving an older commit; the newest Pages deployment was two commits
> behind. Nothing was broken — the project simply never built on push. If a change
> "did nothing", run `wrangler pages deployment list --project-name=robinlab` and
> compare the newest deployment's commit with `git rev-parse HEAD` before
> debugging the code.

> **Converting to Git-connected.** Direct Upload projects cannot be converted in
> place. Create a new Git-connected project (delete the old one first if you want
> to keep the `robinlab` name and `robinlab.pages.dev` URL), leave the build
> command empty, set the output directory to `root`, then
> re-add `HF_TOKEN` (and `SHARE_SECRET`). After that, pushes deploy themselves.

## Docs

- `docs/COLLECTION.md` — bucket architecture, API contract, thumbnails, deploy
  details, security notes.

## Local Intelligence & Automation System (LIAS)

LIAS is embedded in `.claude/lias/` to eliminate repetitive manual operations and retrieve project knowledge locally:
- CLI command: `python .claude/lias/cli.py [doctor|status|knowledge|run|route]`
- Windows wrapper: `.\.claude\lias\lias.bat [doctor|status|knowledge|run|route]`
- Key Capabilities:
  - `run source-file-stats`: scans files and lines of code without reading files into LLM context.
  - `run env-check`: verifies Python, Git, Node, and Wrangler toolchains.
  - `knowledge search "<query>"`: instantly retrieves project architecture, rules, and deployment facts via local SQLite FTS5.
  - `route "<natural language query>"`: routes user prompts directly to local automation or knowledge before invoking complex LLM reasoning.
Agents should execute local LIAS capabilities first instead of performing full-tree searches or rediscovering known project rules.

