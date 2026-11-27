# Workflows (copy-paste recipes)

## Run locally

```powershell
python scripts/dev_server.py            # http://127.0.0.1:5500 — site + collection API
python scripts/dev_server.py --port 8080
```
Static only (no API): `python -m http.server 5500 --directory scripts/root`.
Collection needs `HF_TOKEN` in env or `scripts/.dev.vars`. Preview configs: `.claude/launch.json`
(`robinlab-root`, `robinlab-collection`).

## Deploy (manual — push does NOT deploy)

```powershell
cmd /c "npx wrangler pages deploy root --project-name=robinlab --branch=master"
```
or double-click `deploy.bat`. Prod: https://roveuth.com (robinlab.pages.dev 301-redirects to it; `<hash>.robinlab.pages.dev` previews still serve). Publishes `scripts/root/` + `scripts/functions/`.
"Change did nothing?" → `wrangler pages deployment list --project-name=robinlab` and compare the
newest commit with `git rev-parse HEAD` before debugging code.

## Add a project

1. `scripts/root/projects/<Name>/index.html` + own assets (relative paths; served at `/projects/<Name>/`).
2. Add a card in `scripts/root/index.html` `.project-grid`; link `projects/<Name>/index.html`
   (encode spaces: `Contact%20Book`; always write `index.html` explicitly).
3. Optional hub icon in `scripts/root/assets/`.

## Add a Claude skill to /skills

Drop a `.md` (with front-matter) into the bucket's `Claude Skills/` folder — appears automatically.

## Regenerate site icons

`python scripts/tools/make_icons.py` (`--source`, `--install-logo` optional).

## Dev server control / tests / other tools

`python scripts/tools/devctl.py start|stop|restart|status` (or `dev.bat start|stop|restart|status`).
`node --test scripts/tests/` — all Node tests. `make_og.py` (OG images), `make_watch_links.py` (anime Watch map).

## Commit etiquette

Small commits, imperative message. Don't commit `.dev.vars`. Ask before pushing.
