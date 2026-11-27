# SEO notes

Production URL: https://roveuth.com (www redirects to apex via functions/_middleware.js; robinlab.pages.dev 301s to it). Migrated 2026-11-22 — every canonical, `og:url`, sitemap entry
and JSON-LD `url` uses it. Brand: **RobinLab** (WebSite node); **Robin Gupta Studios / RGS** is the
Organization. Do not merge or rename them.

## What is in place
- `scripts/root/robots.txt`, `sitemap.xml` (indexable canonical URLs only), `_headers`.
- Per page: canonical, Open Graph, Twitter card. `/collection`, `/logos`, `/certificates` are `noindex, follow`.
- JSON-LD: home = WebSite + Organization; each project page = SoftwareApplication (facts from the page only).
- Static HTML nav + real `href`s on hub/project cards (`js/site.js` still replaces them).
- Fifth hub card (no page, no facts) is intentionally not marked up.

## Manual steps (need your Google account)
1. Search Console -> add a **Domain** property for `roveuth.com` (DNS TXT) or a URL-prefix property `https://roveuth.com/`
   (ownership file `google94352492b05c9384.html` is already served by `functions/google94352492b05c9384.html.js`).
2. Sitemaps -> submit `https://roveuth.com/sitemap.xml`. URL Inspection -> request indexing for `/`.
3. If the old `robinlab.pages.dev` property exists, use Change of Address to `roveuth.com`. Keep the 301s at least a year.
4. Monitor Pages / Coverage weekly for 4-8 weeks. GA4 is optional (adds a script).

## Redirects and previews
`functions/_middleware.js` 301s `www.roveuth.com` and the exact host `robinlab.pages.dev` to `https://roveuth.com`
(path + query kept). Every other host, including `<hash>.robinlab.pages.dev` previews, passes through, so previews work.
Their pages still declare the production canonical, which is intended.

## 404
`scripts/root/404.html` (noindex) is served by Pages with a real 404 status for unknown paths.

## Tests
`node --test scripts/tests/` — `seo.test.mjs` checks canonicals, og:url, unique titles/descriptions, sitemap vs
indexable pages, robots.txt, old-domain leftovers, JSON-LD and alt text; `middleware.test.mjs` checks the redirects.

## Social previews and schema (2026-11-20)
- `python scripts/tools/make_og.py` regenerates the 1200x630 JPEGs: `assets/og/robinlab-og.jpg` (shared by all
  non-product pages), and `og-image.jpg` for CodeLens, Pywix and Contact Book. Motiva keeps its own `Assets/other/og-image.png`.
  `robinlab-logo.png` stays the square Organization logo only.
- Product `applicationCategory`: Pywix/CodeLens = DeveloperApplication, Contact Book = UtilitiesApplication, Motiva = DesktopEnhancementApplication.
- Each product's `publisher` is the full Organization node (same `@id`, name, url, logo) because `@id` references do not resolve across pages.
- No `offers`, ratings or Organization `sameAs` are published: none can be verified from the pages.
- `veins.css` side bleed is capped to `--gutter`, and `.sk-card`/`.sk-steps li` are positioned, so no page scrolls sideways.

## Google visibility pass (2026-11-22)
- Home description names the brand and the four projects; Organization `sameAs` = the GitHub profile linked on the page (only verified profile).
- `data-nosnippet` on `.fx-loader` so the boot text ("0% click or press any key") is never used as a search snippet.
- Each project page links to the other three projects and to `/projects` from its footer.
- Live check before this pass: unknown URLs returned the home page with 200 (soft 404). `404.html` fixes this once deployed.
