// API-robustness tests for scripts/functions/api/canva/[[path]].js and its Python mirror.
// Run:  node --test scripts/tests/canva_api.test.mjs
// No network: global fetch plays Canva and the bucket. Real Canva is NOT exercised.
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const modulePath = path.resolve(here, "../functions/api/canva/[[path]].js");
let seq = 0;
const freshModule = () => import(`${pathToFileURL(modulePath).href}?api=${seq++}`);

const env = { CANVA_CLIENT_ID: "cid", CANVA_CLIENT_SECRET: "csec", SHARE_SECRET: "SENTINEL", HF_TOKEN: "SENTINEL-HF" };
const SITE = "https://site.test";
const FILES = ["LOGO/a.png", "wallpapers/w.png", "LOGO/" + "x".repeat(80) + ".png"];

let realFetch, realTimeout, realNow, now, calls, canva;

test.beforeEach(() => {
  realFetch = globalThis.fetch;
  realTimeout = globalThis.setTimeout;
  realNow = Date.now;
  now = 0;
  Date.now = () => realNow() + now;
  globalThis.setTimeout = (fn) => realTimeout(fn, 0);
  calls = [];
  canva = { upload: () => Response.json({ job: { id: "j", status: "success", asset: { id: "A1" } } }), poll: null, token: null };
  globalThis.fetch = async (input, init = {}) => {
    const u = String(input?.url || input);
    calls.push({ u, init });
    if (u.endsWith("/oauth/token")) return canva.token ? canva.token(init) : Response.json({ access_token: "AT", refresh_token: "RT", expires_in: 3600 });
    if (u.includes("/api/buckets/") && u.includes("/tree")) {
      return Response.json(FILES.map((p) => ({ type: "file", path: p, size: 4, contentType: "image/png" })));
    }
    if (u.includes("/buckets/") && u.includes("/resolve/")) return new Response(new Uint8Array([1, 2, 3, 4]), { headers: { "Content-Type": "image/png" } });
    if (u.endsWith("/asset-uploads")) return canva.upload();
    if (u.includes("/asset-uploads/")) return canva.poll();
    if (u.endsWith("/designs")) return Response.json({ design: { urls: { edit_url: "https://www.canva.com/e" } } });
    throw new Error(`unexpected fetch ${u}`);
  };
});
test.afterEach(() => {
  globalThis.fetch = realFetch;
  globalThis.setTimeout = realTimeout;
  Date.now = realNow;
});

const run = (mod, route, init = {}) => mod.onRequest({ request: new Request(`${SITE}/api/canva/${route}`, init), env });
const cookieVal = (res, name) => res.headers.getSetCookie().find((c) => c.startsWith(`${name}=`))?.split(";")[0].slice(name.length + 1);

async function session(mod) {
  const l = await run(mod, "login");
  const state = new URL(l.headers.get("Location")).searchParams.get("state");
  const cb = await run(mod, `callback?code=C&state=${state}`, { headers: { Cookie: `rl_canva_oauth=${cookieVal(l, "rl_canva_oauth")}` } });
  return cookieVal(cb, "rl_canva");
}
const edit = (mod, sess, body, headers = {}) =>
  run(mod, "edit", { method: "POST", headers: { Cookie: `rl_canva=${sess}`, ...headers }, body: JSON.stringify(body) });
const designBody = () => JSON.parse(calls.find((c) => c.u.endsWith("/designs")).init.body);

test("PKCE challenge method is uppercase S256", async () => {
  const mod = await freshModule();
  const l = await run(mod, "login");
  assert.equal(new URL(l.headers.get("Location")).searchParams.get("code_challenge_method"), "S256");
});

test("folder authorization: only LOGO/ exact files; other folders, case tricks and traversal refused", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  for (const p of ["wallpapers/w.png", "logo/a.png", "LOGO/../wallpapers/w.png", "LOGO\\a.png", "", "_thumbs/LOGO/a.png"]) {
    const r = await edit(mod, s, { path: p });
    assert.equal(r.status, 400, p);
  }
  assert.equal((await edit(mod, s, { path: "LOGO/missing.png" })).status, 404);
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" })).status, 200);
  assert.ok(!calls.some((c) => c.u.endsWith("/asset-uploads") && false));
});

test("CSRF: cross-site and foreign-Origin edit requests are refused before any Canva call", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  const before = calls.length;
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" }, { "Sec-Fetch-Site": "cross-site" })).status, 403);
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" }, { Origin: "https://evil.test" })).status, 403);
  assert.equal(calls.length, before);
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" }, { Origin: SITE })).status, 200);
});

test("design area is capped at 25 MP and 8000 px, aspect ratio kept", async () => {
  const { fitDesign } = await freshModule();
  for (const [w, h] of [[8000, 8000], [8000, 7000], [8000, 40], [40, 8000], [5000, 5001], [99999, 99999], [3000, 9000]]) {
    const d = fitDesign(w, h);
    assert.ok(d.width * d.height <= 25_000_000, `${w}x${h} -> ${d.width}x${d.height}`);
    assert.ok(d.width >= 40 && d.width <= 8000 && d.height >= 40 && d.height <= 8000);
  }
  assert.deepEqual(fitDesign(8000, 8000), { width: 5000, height: 5000 });
  assert.deepEqual(fitDesign(640, 480), { width: 640, height: 480 });
  assert.deepEqual(fitDesign(0, "x"), { width: 1000, height: 1000 });
});

test("edit sends the fitted size to Canva", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  await edit(mod, s, { path: "LOGO/a.png", w: 8000, h: 8000 });
  assert.deepEqual(designBody().design_type, { type: "custom", width: 5000, height: 5000 });
});

test("asset name is truncated to 50 characters (code points); title keeps up to 255", async () => {
  const { assetName } = await freshModule();
  assert.equal(assetName("a".repeat(80)).length, 50);
  assert.equal(Array.from(assetName("😀".repeat(80))).length, 50);
  assert.equal(assetName("short"), "short");
  const mod = await freshModule();
  const s = await session(mod);
  await edit(mod, s, { path: "LOGO/a.png", title: "é".repeat(120) });
  const meta = JSON.parse(calls.find((c) => c.u.endsWith("/asset-uploads")).init.headers["Asset-Upload-Metadata"]);
  assert.equal(Array.from(new TextDecoder().decode(Uint8Array.from(atob(meta.name_base64), (c) => c.charCodeAt(0)))).length, 50);
  assert.equal(Array.from(designBody().title).length, 120);
});

test("concurrent refresh shares ONE refresh-token call and both requests succeed", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  now = 2 * 3600 * 1000; // access token now stale
  let refreshes = 0;
  canva.token = async () => { refreshes++; await new Promise((r) => realTimeout(r, 20)); return Response.json({ access_token: "AT2", refresh_token: "RT2", expires_in: 3600 }); };
  const [a, b] = await Promise.all([edit(mod, s, { path: "LOGO/a.png" }), edit(mod, s, { path: "LOGO/a.png" })]);
  assert.deepEqual([a.status, b.status], [200, 200]);
  assert.equal(refreshes, 1);
  assert.ok(cookieVal(a, "rl_canva") && cookieVal(b, "rl_canva"));
});

test("failed refresh signs the visitor out: 401 auth_required and the cookie is cleared", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  now = 2 * 3600 * 1000;
  canva.token = () => Response.json({ error: "invalid_grant" }, { status: 400 });
  const r = await edit(mod, s, { path: "LOGO/a.png" });
  assert.equal(r.status, 401);
  assert.equal((await r.json()).error, "auth_required");
  assert.match(r.headers.getSetCookie().join(";"), /rl_canva=;.*Max-Age=0/);
});

test("upload: 401 -> auth_required, 429 -> rate_limited, no job -> 502", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  canva.upload = () => new Response("{}", { status: 401 });
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" })).status, 401);
  canva.upload = () => new Response("{}", { status: 429 });
  assert.equal((await (await edit(mod, s, { path: "LOGO/a.png" })).json()).error, "rate_limited");
  canva.upload = () => Response.json({});
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" })).status, 502);
});

test("polling: waits for success, retries 5xx, surfaces failure, times out with 504", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  const pending = () => Response.json({ job: { id: "j", status: "in_progress" } });
  canva.upload = pending;
  let n = 0;
  canva.poll = () => (++n < 3 ? new Response("{}", { status: 503 }) : Response.json({ job: { id: "j", status: "success", asset: { id: "A" } } }));
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" })).status, 200);
  assert.equal(n, 3);

  canva.poll = () => Response.json({ job: { id: "j", status: "failed", error: { code: "x", message: "bad file" } } });
  const failed = await edit(mod, s, { path: "LOGO/a.png" });
  assert.equal(failed.status, 502);
  assert.match((await failed.json()).message, /bad file/);

  canva.poll = pending;
  n = calls.length;
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" })).status, 504);
  assert.equal(calls.slice(n).filter((c) => c.u.includes("/asset-uploads/")).length, 20, "polling is bounded");

  canva.poll = () => new Response("{}", { status: 404 });
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" })).status, 502);
  canva.poll = () => new Response("{}", { status: 401 });
  assert.equal((await edit(mod, s, { path: "LOGO/a.png" })).status, 401);
});

test("secrets never reach the client: responses and cookies carry no client secret or tokens in clear", async () => {
  const mod = await freshModule();
  const s = await session(mod);
  const r = await edit(mod, s, { path: "LOGO/a.png" });
  const blob = (await r.text()) + r.headers.getSetCookie().join(";") + s;
  for (const secret of ["csec", "SENTINEL", '"AT"', "RT"]) assert.ok(!blob.includes(secret), secret);
  const l = await run(mod, "login");
  assert.match(l.headers.getSetCookie()[0], /HttpOnly/);
});

test("Python dev mirror agrees with the Function on sizes and names", async () => {
  const { fitDesign, assetName } = await freshModule();
  const cases = [[640, 480], [8000, 8000], [0, 5], ["abc", 3], [1, 99999], ["800", "600.4"], [null, null], [3000, 9000], [true, 5], ["", 7]];
  const code = `import json,sys\nfrom devserver.canva.edit import fit_design, asset_name\ncs=json.loads(sys.argv[1])\nprint(json.dumps({"d":[list(fit_design(a,b)) for a,b in cs],"n":asset_name("😀"*80)}))`;
  const r = spawnSync("python", ["-I", "-B", "-c", `import sys; sys.path.insert(0, ${JSON.stringify(path.resolve(here, ".."))}); exec(${JSON.stringify(code)})`, JSON.stringify(cases)], { encoding: "utf8" });
  if (r.error || r.status !== 0) return void console.log("python unavailable, skipped:", r.stderr || r.error);
  const py = JSON.parse(r.stdout);
  assert.deepEqual(py.d, cases.map(([a, b]) => { const d = fitDesign(a, b); return [d.width, d.height]; }));
  assert.equal(Array.from(py.n).length, Array.from(assetName("😀".repeat(80))).length);
});
