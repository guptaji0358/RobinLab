// Tests for the Canva OAuth hardening in scripts/functions/api/canva/[[path]].js.
// Run:  node --test scripts/tests/canva_oauth.test.mjs
// No network: global fetch plays Canva and the bucket. All secrets are fake sentinels.
// Real Canva is NOT exercised here.
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const modulePath = path.resolve(here, "../functions/api/canva/[[path]].js");
let seq = 0;
const freshModule = () => import(`${pathToFileURL(modulePath).href}?iso=${seq++}`);

const SECRET = "SENTINEL-SHARE-SECRET";
const HF = "SENTINEL-HF-TOKEN";
const env = { CANVA_CLIENT_ID: "cid", CANVA_CLIENT_SECRET: "csec", SHARE_SECRET: SECRET, HF_TOKEN: HF };
const SITE = "https://site.test";
const TEN_MIN = 10 * 60 * 1000;

let realFetch, realNow, clockOffset, designBodies, tokenCalls;

test.beforeEach(() => {
  realFetch = globalThis.fetch;
  realNow = Date.now;
  clockOffset = 0;
  designBodies = [];
  tokenCalls = 0;
  Date.now = () => realNow() + clockOffset;
  globalThis.fetch = async (input, init = {}) => {
    const u = String(input?.url || input);
    if (u.endsWith("/oauth/token")) {
      tokenCalls++;
      return Response.json({ access_token: "AT", refresh_token: "RT", expires_in: 3600 });
    }
    if (u.includes("/api/buckets/") && u.includes("/tree")) {
      return Response.json([{ type: "file", path: "LOGO/a.png", size: 4, contentType: "image/png" }]);
    }
    if (u.includes("/buckets/") && u.includes("/resolve/")) {
      return new Response(new Uint8Array([1, 2, 3, 4]), { status: 200, headers: { "Content-Type": "image/png" } });
    }
    if (u.endsWith("/asset-uploads")) return Response.json({ job: { id: "j", status: "success", asset: { id: "A1" } } });
    if (u.endsWith("/designs")) {
      designBodies.push(JSON.parse(init.body));
      return Response.json({ design: { urls: { edit_url: "https://canva.test/edit" } } });
    }
    throw new Error(`unexpected fetch ${u}`);
  };
});

test.afterEach(() => {
  globalThis.fetch = realFetch;
  Date.now = realNow;
});

const run = (mod, e, route, init = {}) =>
  mod.onRequest({ request: new Request(`${SITE}/api/canva/${route}`, init), env: e });
const setCookies = (res) => res.headers.getSetCookie();
const cookieVal = (res, name) => {
  const line = setCookies(res).find((c) => c.startsWith(`${name}=`));
  return line ? line.split(";")[0].slice(name.length + 1) : null;
};

async function login(mod, e = env) {
  const res = await run(mod, e, "login");
  assert.equal(res.status, 302);
  const state = new URL(res.headers.get("Location")).searchParams.get("state");
  return { res, state, oauth: cookieVal(res, "rl_canva_oauth") };
}
const callback = (mod, e, { code = "CODE", state, oauth } = {}) => {
  const q = new URLSearchParams();
  if (code) q.set("code", code);
  if (state) q.set("state", state);
  return run(mod, e, `callback?${q}`, { headers: oauth ? { Cookie: `rl_canva_oauth=${oauth}` } : {} });
};
const outcome = (res) => new URL(res.headers.get("Location"), SITE).searchParams.get("canva");

// Re-implements the module's seal so we can forge payloads (e.g. state with no timestamp).
const b64url = (b) => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
async function sealLike(secret, value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`canva-session:${secret}`));
  const key = await crypto.subtle.importKey("raw", digest, "AES-GCM", false, ["encrypt"]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(JSON.stringify(value)));
  return `${b64url(iv)}.${b64url(ct)}`;
}

/* ------------------------------- OAuth state ------------------------------- */

test("valid state completes the flow and sets the session cookie", async () => {
  const mod = await freshModule();
  const { state, oauth, res } = await login(mod);
  assert.match(setCookies(res)[0], /HttpOnly/);
  assert.match(setCookies(res)[0], /Max-Age=600/);
  const cb = await callback(mod, env, { state, oauth });
  assert.equal(outcome(cb), "connected");
  assert.ok(cookieVal(cb, "rl_canva"));
  assert.equal(tokenCalls, 1);
});

test("state just inside 10 minutes is accepted", async () => {
  const mod = await freshModule();
  const { state, oauth } = await login(mod);
  clockOffset = TEN_MIN - 1000;
  assert.equal(outcome(await callback(mod, env, { state, oauth })), "connected");
});

test("expired state (>10 min) is rejected without calling Canva", async () => {
  const mod = await freshModule();
  const { state, oauth } = await login(mod);
  clockOffset = TEN_MIN + 1000;
  const cb = await callback(mod, env, { state, oauth });
  assert.equal(outcome(cb), "denied");
  assert.equal(cookieVal(cb, "rl_canva"), null);
  assert.equal(tokenCalls, 0);
});

test("future-dated state is rejected", async () => {
  const mod = await freshModule();
  const { state, oauth } = await login(mod);
  clockOffset = -60_000; // the callback runs "before" the state was issued
  const cb = await callback(mod, env, { state, oauth });
  assert.equal(outcome(cb), "denied");
  assert.equal(tokenCalls, 0);
});

test("sealed state without a timestamp is rejected", async () => {
  const mod = await freshModule();
  const oauth = await sealLike(SECRET, { v: "verifier", s: "st", ret: "/logos" });
  assert.equal(outcome(await callback(mod, env, { state: "st", oauth })), "denied");
  const bad = await sealLike(SECRET, { v: "verifier", s: "st", ret: "/logos", t: "now" });
  assert.equal(outcome(await callback(mod, env, { state: "st", oauth: bad })), "denied");
  assert.equal(tokenCalls, 0);
});

test("wrong state value is rejected", async () => {
  const mod = await freshModule();
  const { oauth } = await login(mod);
  assert.equal(outcome(await callback(mod, env, { state: "forged", oauth })), "denied");
  assert.equal(tokenCalls, 0);
});

test("missing state cookie is rejected", async () => {
  const mod = await freshModule();
  const { state } = await login(mod);
  assert.equal(outcome(await callback(mod, env, { state })), "denied");
  assert.equal(tokenCalls, 0);
});

test("cookie sealed with a different secret is rejected", async () => {
  const mod = await freshModule();
  const { state, oauth } = await login(mod);
  assert.equal(outcome(await callback(mod, { ...env, SHARE_SECRET: "other" }, { state, oauth })), "denied");
});

/* ------------------------------ SHARE_SECRET ------------------------------ */

test("missing SHARE_SECRET -> 503 not_configured, even with HF_TOKEN set", async () => {
  const mod = await freshModule();
  const noSecret = { ...env, SHARE_SECRET: undefined };
  for (const route of ["login", "callback?code=x&state=y"]) {
    const res = await run(mod, noSecret, route);
    assert.equal(res.status, 503);
    const text = await res.text();
    assert.equal(JSON.parse(text).error, "not_configured");
    assert.ok(!text.includes(HF) && !text.includes(SECRET));
  }
  const edit = await run(mod, noSecret, "edit", { method: "POST", body: "{}" });
  assert.equal(edit.status, 503);
});

test("HF_TOKEN no longer decrypts a session sealed with it", async () => {
  const mod = await freshModule();
  const session = await sealLike(HF, { a: "AT", r: "RT", e: realNow() + 3_600_000 });
  const res = await run(mod, env, "edit", {
    method: "POST",
    headers: { Cookie: `rl_canva=${session}` },
    body: JSON.stringify({ path: "LOGO/a.png" }),
  });
  assert.equal(res.status, 401);
});

/* ------------------------------- dimensions ------------------------------- */

async function editWith(dims) {
  const mod = await freshModule();
  const { state, oauth } = await login(mod);
  const session = cookieVal(await callback(mod, env, { state, oauth }), "rl_canva");
  const res = await run(mod, env, "edit", {
    method: "POST",
    headers: { Cookie: `rl_canva=${session}` },
    body: JSON.stringify({ path: "LOGO/a.png", ...dims }),
  });
  assert.equal(res.status, 200, await res.clone().text());
  return designBodies.at(-1).design_type;
}

test("valid dimensions are used", async () => {
  assert.deepEqual(await editWith({ w: 640, h: 480 }), { type: "custom", width: 640, height: 480 });
  assert.deepEqual(await editWith({ w: "800", h: "600.4" }), { type: "custom", width: 800, height: 600 });
});

test("missing dimensions default to 1000", async () => {
  assert.deepEqual(await editWith({}), { type: "custom", width: 1000, height: 1000 });
  assert.deepEqual(await editWith({ w: 300 }), { type: "custom", width: 300, height: 1000 });
});

test("invalid dimensions default to 1000", async () => {
  for (const bad of [null, "", "abc", 0, -5, NaN, "Infinity", {}, [], true]) {
    assert.deepEqual(await editWith({ w: bad, h: bad }), { type: "custom", width: 1000, height: 1000 }, `bad=${JSON.stringify(bad)}`);
  }
});

test("min/max limits are preserved", async () => {
  assert.deepEqual(await editWith({ w: 1, h: 99999 }), { type: "custom", width: 40, height: 8000 });
});
