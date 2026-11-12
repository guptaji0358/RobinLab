# Frontend map (root/)

Plain HTML + vanilla JS (IIFEs, no modules). Line numbers ≈ 2026-11-06.

## Pages → scripts

| Page (route)               | HTML (lines)            | JS it loads                       |
| -------------------------- | ----------------------- | --------------------------------- |
| `index.html` `/`           | 636 — hub, about, contact, JSON-LD | `main.js`, `fx.js`, `site.js`, `links.js` |
| `collection.html`          | 196                     | `collection.js`, `names.js`       |
| `presentations.html`       | 142                     | `presentations.js`, `names.js`    |
| `skills.html`              | 150                     | `skills.js`, `names.js`           |
| `music.html`               | 101                     | `music.js`                        |
| `projects.html`            | ~290                    | none (links.js, site.js, fx.js)   |
| `certificates.html`        | 173                     | —                                 |

(Verify the exact `<script>` list with `grep -n "<script" root/<page>.html`.)

## JS files

- `links.js` (74) — `window.RL_LINKS`: the single place for site/social URLs. Change URLs here, not in HTML.
- `site.js` (79) — builds shared header/nav/footer (`el`, `icon`, `local`, `resolve`). Nav and footer identity edits start here.
- `names.js` (31) — `pretty()` Title Case display names, `ext()`.
- `main.js` (12) — tiny hub bootstrap.
- `fx.js` (601) — visual effects: `boot` loader 20, `background` canvas 64, `hero` 213, `marquee` 292, `cursor` 308, `reveal` 394, `hscroll` 489, `scrollFx` 540. Pair: `css/fx.css`.
- `music.js` (163) — audio player: `load` 59, `step` 78, `stopAll` 53.
- `skills.js` (158) — `buildCard` 48, `copySkill` 111, `load` 130 (calls `/api/collection/skills`, `/skill`).
- `presentations.js` (319) — `buildCard` 120, `render` 156, `openDeck` 182 (Office Web Viewer embed), `closeDeck` 243, `load` 284.
- `collection.js` (1188) — the big one:
  - names/labels 142–172 · toast/copy 202–214 · search & chips 251–320
  - pack covers/slideshows 323–425 · pack tree & list 477–557 · tabs/stats 558–581
  - `buildCard` 582 · title→character grouping (`titleAndCharacter`, `buildGroups`: h1 anime / h2 character, collapsible, jump bar) ~652 · `render` ~770 · "All images" is the default tab
  - lightbox 748–853 (`openLightbox`, `paintLightbox`, `step`)
  - **share** `shareCurrent` 854 · **download** `downloadCurrent` 892
  - data: `buildPacks` 996 · `ingest` 1031 · cached manifest 1064–1081 · `load` 1082 · `openShared` 1131 · `boot` 1181

## CSS files

- `style.css` (2070) — shared by all pages. Sections (grep `^/\* ` to refresh):
  header 71 · hero 182 · projects 260–400 · about/contact 401–580 · footer 580–643 ·
  collection toolbar 691 · tabs 787 · pack covers 879 · packs tree 1001 · chips 1026 ·
  grid/landscape 1101–1218 · states 1275 · **lightbox 1317** · toast 1556 ·
  **deck viewer 1724** · responsive 1898 · skills page 1990 · nav 2060.
- `theme.css` (164) — colour/theme variables.
- `profile.css` (191) — about/profile blocks.
- `fx.css` (477) — effects (pairs with `fx.js`). `music.css` (54) — music page.

## Projects (root/projects/, each self-contained)

`CodeLens/` (index+style) · `Contact Book/` (index+script+style; link as `Contact%20Book`) ·
`Motiva/` (css/, js/, Assets/) · `Pywix/` (css/, js/main.js).
Hub icons: `root/assets/`. See `workflows.md` → Add a project.

## Footer identity (change all pages together)

Robin Gupta Studios / RGS™ / Built & maintained by Robin Gupta / Copyright © year —
plus `<meta name="author|publisher|copyright">` in every `<head>`; `index.html` also has JSON-LD.
