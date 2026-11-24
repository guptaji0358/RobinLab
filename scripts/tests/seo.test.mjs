// SEO guard rails. Run: node --test scripts/tests/seo.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', 'root');
const ORIGIN = 'https://roveuth.com';
const read = (p) => readFileSync(join(ROOT, p), 'utf8');

// Every page that ships SEO metadata (verification stub and 404 are handled separately).
const pages = [
  ...readdirSync(ROOT).filter((f) => f.endsWith('.html') && !f.startsWith('google') && f !== '404.html'),
  ...readdirSync(join(ROOT, 'projects'))
    .filter((d) => existsSync(join(ROOT, 'projects', d, 'index.html')))
    .map((d) => `projects/${d}/index.html`),
];
const meta = (s, re) => (s.match(re) || [])[1];
const info = (f) => {
  const s = read(f);
  return {
    f, s,
    title: meta(s, /<title>(.*?)<\/title>/s),
    desc: meta(s, /name="description"\s+content="(.*?)"/s),
    canon: meta(s, /rel="canonical"\s+href="(.*?)"/),
    robots: meta(s, /name="robots"\s+content="(.*?)"/),
    ogUrl: meta(s, /og:url"\s+content="(.*?)"/),
    ogImg: meta(s, /og:image"\s+content="(.*?)"/),
  };
};
const all = pages.map(info);
const indexable = all.filter((p) => !/noindex/.test(p.robots || ''));

test('every page has title, description, canonical, viewport, one h1', () => {
  for (const p of all) {
    assert.ok(p.title, `${p.f} title`);
    assert.ok(p.desc && p.desc.length >= 30 && p.desc.length <= 320, `${p.f} description length`);
    assert.ok(p.canon, `${p.f} canonical`);
    assert.match(p.s, /name="viewport"/, `${p.f} viewport`);
    assert.equal((p.s.match(/<h1[\s>]/g) || []).length, 1, `${p.f} h1 count`);
  }
});

test('canonical and og:url are https on the production origin and agree', () => {
  for (const p of all) {
    assert.ok(p.canon.startsWith(ORIGIN + '/'), `${p.f} canonical origin: ${p.canon}`);
    assert.equal(p.ogUrl, p.canon, `${p.f} og:url matches canonical`);
    assert.ok(p.ogImg.startsWith(ORIGIN + '/'), `${p.f} og:image absolute`);
  }
});

test('titles and descriptions are unique across pages', () => {
  for (const key of ['title', 'desc', 'canon']) {
    const seen = new Map();
    for (const p of all) {
      assert.ok(!seen.has(p[key]), `duplicate ${key}: ${p.f} vs ${seen.get(p[key])}`);
      seen.set(p[key], p.f);
    }
  }
});

test('indexable pages are not noindex; noindex pages are the intended vault pages', () => {
  const noindex = all.filter((p) => /noindex/.test(p.robots || '')).map((p) => p.f).sort();
  assert.deepEqual(noindex, ['certificates.html', 'collection.html', 'logos.html']);
  assert.ok(indexable.length >= 9);
});

test('img tags carry alt text', () => {
  for (const p of all) {
    for (const tag of p.s.match(/<img\b[^>]*>/g) || []) assert.match(tag, /\balt=/, `${p.f}: ${tag.slice(0, 80)}`);
  }
});

test('sitemap lists exactly the indexable canonical URLs', () => {
  const xml = read('sitemap.xml');
  const locs = [...xml.matchAll(/<loc>(.*?)<\/loc>/g)].map((m) => m[1]);
  assert.equal(new Set(locs).size, locs.length, 'no duplicate <loc>');
  for (const l of locs) assert.ok(l.startsWith(ORIGIN + '/') && !/\s/.test(l), `bad loc ${l}`);
  assert.deepEqual([...locs].sort(), indexable.map((p) => p.canon).sort());
});

test('robots.txt points at the production sitemap and does not block the site', () => {
  const r = read('robots.txt');
  assert.match(r, new RegExp(`^Sitemap: ${ORIGIN}/sitemap\\.xml$`, 'm'));
  assert.doesNotMatch(r, /^Disallow:\s*\/\s*$/m);
});

test('no old production domain in public files', () => {
  const walk = (d) => readdirSync(d).flatMap((n) => {
    const p = join(d, n);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
  for (const p of walk(ROOT).filter((x) => /\.(html|xml|txt|json|webmanifest|js)$/.test(x))) {
    assert.doesNotMatch(readFileSync(p, 'utf8'), /(?<![\w-])robinlab\.pages\.dev/, p);
  }
});

test('JSON-LD parses, uses the production origin, and has no invented data', () => {
  for (const p of all) {
    for (const m of p.s.matchAll(/<script type="application\/ld\+json">(.*?)<\/script>/gs)) {
      const data = JSON.parse(m[1]);
      assert.equal(data['@context'], 'https://schema.org', p.f);
      const text = JSON.stringify({ ...data, '@context': undefined });
      for (const u of text.replace(/"(downloadUrl|installUrl|sameAs|license)":(\[[^\]]*\]|"[^"]*")/g, '').match(/https?:\/\/[^"]+/g) || []) assert.ok(u.startsWith(ORIGIN), `${p.f}: ${u}`);
      assert.doesNotMatch(text, /aggregateRating|"review"|"address"/, `${p.f} invented data`);
    }
  }
  const homeLd = JSON.parse(read('index.html').match(/<script type="application\/ld\+json">(.*?)<\/script>/s)[1]);
  const org = homeLd['@graph'].find((n) => n['@type'] === 'Organization');
  assert.deepEqual(org.sameAs, ['https://github.com/guptaji0358'], 'only the GitHub profile linked on the page');
  const home = all.find((p) => p.f === 'index.html');
  assert.match(home.s, /"@type": "WebSite"/);
  assert.match(home.s, /"@type": "Organization"/);
});

test('404 page exists and is noindex', () => {
  const s = read('404.html');
  assert.match(s, /name="robots"\s+content="noindex/);
  assert.match(s, /<h1>/);
});

test('homepage description names the brand and its four projects', () => {
  const d = all.find((p) => p.f === 'index.html').desc;
  for (const w of ['RobinLab', 'PyWix', 'CodeLens', 'Contact Book', 'Motiva']) assert.ok(d.includes(w), w);
});

test('every project page links to the other three projects and the project index', () => {
  const dirs = ['Pywix', 'CodeLens', 'Contact%20Book', 'Motiva'];
  for (const d of dirs) {
    const s = read(`projects/${decodeURIComponent(d)}/index.html`);
    for (const o of dirs.filter((x) => x !== d)) assert.ok(s.includes(`href="/projects/${o}/"`), `${d} -> ${o}`);
    assert.ok(s.includes('href="/projects"'), `${d} -> /projects`);
  }
});

test('indexable pages expose crawlable <a href> nav links to the main sections', () => {
  const home = read('index.html');
  for (const h of ['/projects', '/skills', '/presentations', '/music']) assert.ok(home.includes(`href="${h}"`), h);
});

test('the boot loader text is excluded from snippets', () => {
  assert.match(read('index.html'), /class="fx-loader"[^>]*data-nosnippet/);
});

// ---- Unknown URLs must be a real 404 (no homepage / SPA fallback) ----
// Cloudflare Pages serves /404.html with status 404 for unmatched paths ONLY when the file exists
// at the publish root and nothing rewrites to index.html. Verified manually with
// `wrangler pages dev root` (unknown path -> 404 + custom page).
test('404.html is at the publish root and no rewrite/fallback config exists', () => {
  assert.ok(existsSync(join(ROOT, '404.html')), 'scripts/root/404.html missing');
  for (const f of ['_redirects', '_routes.json']) {
    if (!existsSync(join(ROOT, f))) continue;
    assert.doesNotMatch(read(f), /\/\*\s+\/index\.html|\/\*\s+\/\s+200/, `${f} must not add a catch-all fallback`);
  }
  assert.doesNotMatch(readFileSync(join(ROOT, '..', 'wrangler.toml'), 'utf8'), /not_found_handling|single-page/i);
});

test('middleware never rewrites unknown paths to the homepage', async () => {
  const { onRequest } = await import('../functions/_middleware.js');
  const res = await onRequest({
    request: new Request('https://roveuth.com/nonexistent-xyz'),
    next: async () => new Response('nf', { status: 404 }),
  });
  assert.equal(res.status, 404);
});

// Opt-in against a running server: SEO_LIVE_URL=https://roveuth.com node --test scripts/tests/seo.test.mjs
test('live: unknown URLs return HTTP 404 with the custom page', { skip: !process.env.SEO_LIVE_URL }, async () => {
  const base = process.env.SEO_LIVE_URL.replace(/\/$/, '');
  for (const p of ['/nonexistent-xyz', '/projects/Nope', '/projects/Pywix/missing.png']) {
    const r = await fetch(base + p, { redirect: 'manual' });
    assert.equal(r.status, 404, p);
    assert.match(await r.text(), /Page not found — RobinLab/, p);
  }
  assert.equal((await fetch(base + '/', { redirect: 'manual' })).status, 200);
});

test('homepage has the visible "What is RobinLab?" section linking the four projects', () => {
  const s = read('index.html');
  const m = s.match(/<article class="about-block" id="what-is-robinlab">(.*?)<\/article>/s);
  assert.ok(m, 'section missing');
  assert.match(m[1], /<h3>What is RobinLab\?<\/h3>/);
  for (const href of ['/projects/Pywix/', '/projects/CodeLens/', '/projects/Contact%20Book/', '/projects/Motiva/', '/projects'])
    assert.ok(m[1].includes(`href="${href}"`), href);
  assert.doesNotMatch(m[1], /display:\s*none|visually-hidden|sr-only|\shidden[\s>]/);
});
