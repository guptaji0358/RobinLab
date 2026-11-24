// Tests for the watermark-service 429 handling in the collection Pages Function.
// Run:  node --test scripts/tests/watermark_resilience.test.mjs
// No network: global fetch is replaced by a stub that plays the bucket and the
// watermark service. Secrets used here are fake sentinel strings.
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const modulePath = path.resolve(here, "../functions/api/collection/[[path]].js");
let seq = 0;
/** A fresh module instance = a fresh isolate (own listing cache and cooldown). */
const freshModule = () => import(`${pathToFileURL(modulePath).href}?iso=${seq++}`);

const SECRET_KEY = "SENTINEL-WATERMARK-KEY";
const SECRET_TOKEN = "SENTINEL-HF-TOKEN";
const env = { HF_TOKEN: SECRET_TOKEN, WATERMARK_URL: "https://wm.test/", WATERMARK_KEY: SECRET_KEY };
const PNG = new Uint8Array([137, 80, 78, 71]);

let calls, serviceHandler, logs, realFetch, realNow, clockOffset, realConsole;

test.beforeEach(() => {
  calls = { service: [], bucket: 0 };
  logs = [];
  clockOffset = 0;
  realFetch = globalThis.fetch;
  realNow = Date.now;
  realConsole = { log: console.log, warn: console.warn, error: console.error };
  for (const k of ["log", "warn", "error"]) console[k] = (...a) => logs.push(a.join(" "));
  Date.now = () => realNow() + clockOffset;
  serviceHandler = () => new Response(PNG, { status: 200, headers: { "Content-Type": "image/png" } });
  globalThis.fetch = async (input, init = {}) => {
    const u = String(input?.url || input);
    if (u.startsWith("https://wm.test/")) {
      calls.service.push(u);
      return serviceHandler(u, init);
    }
    if (u.includes("/api/buckets/") && u.includes("/tree")) {
      return Response.json([{ type: "file", path: "a.png", size: 4, contentType: "image/png" }]);
    }
    if (u.includes("/buckets/") && u.includes("/resolve/")) {
      calls.bucket++;
      return new Response("ORIGINAL", { status: 200, headers: { "Content-Type": "image/png" } });
    }
    throw new Error(`unexpected fetch ${u}`);
  };
});

test.afterEach(() => {
  globalThis.fetch = realFetch;
  Date.now = realNow;
  Object.assign(console, realConsole);
  delete globalThis.caches;
});

const ctx = () => ({ waitUntil() {}, request: null });
const call = async (mod, route, headers = {}) =>
  mod.onRequest({
    request: new Request(`https://site.test/api/collection/${route}?path=a.png`, { headers }),
    env,
    waitUntil() {},
  });
const noSecrets = async (res) => {
  const text = await res.clone().text();
  const hdrs = JSON.stringify([...res.headers]);
  for (const s of [SECRET_KEY, SECRET_TOKEN]) {
    assert.ok(!text.includes(s) && !hdrs.includes(s) && !logs.join("\n").includes(s), "secret leaked");
  }
};

test("download: success passes the watermarked file through", async () => {
  const mod = await freshModule();
  serviceHandler = () =>
    new Response(PNG, { status: 200, headers: { "Content-Type": "image/png", "Content-Disposition": "attachment; filename=a-RGS.png" } });
  const res = await call(mod, "download");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("Content-Disposition"), /a-RGS\.png/);
  assert.equal(calls.service.length, 1);
  await noSecrets(res);
});

test("download: upstream 429 -> 503 with forwarded Retry-After, no retry", async () => {
  const mod = await freshModule();
  serviceHandler = () => new Response("secret upstream detail", { status: 429, headers: { "Retry-After": "42", "X-Internal": "x" } });
  const res = await call(mod, "download");
  assert.equal(res.status, 503);
  assert.equal(res.headers.get("Retry-After"), "42");
  assert.equal(res.headers.get("X-Internal"), null);
  const body = await res.clone().json();
  assert.equal(body.error, "service_busy");
  assert.ok(!JSON.stringify(body).includes("upstream detail"));
  assert.equal(calls.service.length, 1, "must not retry automatically");
  await noSecrets(res);
});

test("download: 429 without / with invalid Retry-After uses the 30s fallback; huge values are clamped", async () => {
  const mod = await freshModule();
  for (const [header, expected] of [[null, "30"], ["soon", "30"], ["0", "30"], ["99999", "300"]]) {
    serviceHandler = () => new Response("", { status: 429, headers: header ? { "Retry-After": header } : {} });
    const res = await call(mod, "download");
    assert.equal(res.status, 503);
    assert.equal(res.headers.get("Retry-After"), expected, `header=${header}`);
  }
});

test("download: other upstream failures keep the existing 502 handling", async () => {
  const mod = await freshModule();
  serviceHandler = () => Response.json({ error: "Bucket fetch failed (HTTP 500)." }, { status: 502 });
  let res = await call(mod, "download");
  assert.equal(res.status, 502);
  assert.equal((await res.json()).message, "Bucket fetch failed (HTTP 500).");

  serviceHandler = () => new Response("<html>", { status: 500 });
  res = await call(mod, "download");
  assert.equal(res.status, 502);
  assert.equal((await res.json()).message, "Watermark service failed (HTTP 500).");
  assert.equal(res.headers.get("Retry-After"), null);

  serviceHandler = () => {
    throw new Error("network down");
  };
  res = await call(mod, "download");
  assert.equal(res.status, 502);
  await noSecrets(res);
});

test("preview: success returns the resized WebP", async () => {
  const mod = await freshModule();
  serviceHandler = () => new Response("WEBP", { status: 200, headers: { "Content-Type": "image/webp" } });
  const res = await call(mod, "preview");
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Content-Type"), "image/webp");
  assert.equal(await res.text(), "WEBP");
  assert.equal(calls.bucket, 0);
});

test("preview: 429 falls back to the original; cooldown skips the service; it resumes afterwards", async () => {
  const mod = await freshModule();
  serviceHandler = () => new Response("", { status: 429, headers: { "Retry-After": "10" } });

  let res = await call(mod, "preview");
  assert.equal(res.status, 200);
  assert.equal(await res.text(), "ORIGINAL");
  assert.notEqual(res.headers.get("Content-Type"), "image/webp", "failure must not look like a thumbnail");
  assert.equal(calls.service.length, 1);

  // During cooldown: no further service calls, still the original.
  for (let i = 0; i < 3; i++) {
    res = await call(mod, "preview");
    assert.equal(await res.text(), "ORIGINAL");
  }
  assert.equal(calls.service.length, 1, "service must not be called during cooldown");

  // After cooldown: service is used again.
  clockOffset = 11_000;
  serviceHandler = () => new Response("WEBP", { status: 200, headers: { "Content-Type": "image/webp" } });
  res = await call(mod, "preview");
  await noSecrets(res);
  assert.equal(await res.text(), "WEBP");
  assert.equal(calls.service.length, 2);
});

test("preview: cooldown is shared with other isolates through the Cache API; 429 is never cached as a thumbnail", async () => {
  const store = new Map();
  const fakeCache = {
    async match(req) {
      const hit = store.get(req.url);
      return hit ? hit.clone() : undefined;
    },
    async put(req, res) {
      store.set(req.url, res);
    },
  };
  globalThis.caches = { default: fakeCache };

  const isolateA = await freshModule();
  serviceHandler = () => new Response("", { status: 429 });
  const pending = [];
  await isolateA.onRequest({
    request: new Request("https://site.test/api/collection/preview?path=a.png"),
    env,
    waitUntil: (p) => pending.push(p),
  });
  await Promise.all(pending);
  assert.ok(![...store.keys()].some((k) => k.includes("/api/collection/preview")), "429 result must not be cached as a preview");

  const isolateB = await freshModule(); // different isolate: empty memory
  const before = calls.service.length;
  const res = await call(isolateB, "preview");
  assert.equal(await res.text(), "ORIGINAL");
  assert.equal(calls.service.length, before, "isolate B must honour the shared cooldown");
});

test("no secrets in logs across failure paths", async () => {
  const mod = await freshModule();
  serviceHandler = () => new Response("", { status: 429 });
  await call(mod, "download");
  await call(mod, "preview");
  assert.ok(!logs.join("\n").includes(SECRET_KEY));
  assert.ok(!logs.join("\n").includes(SECRET_TOKEN));
});
