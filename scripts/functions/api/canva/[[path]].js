/**
 * Cloudflare Pages Function: /api/canva/*  — "Edit in Canva" for the /logos page.
 *
 *   GET  /api/canva/login?return=/logos   start Canva OAuth (PKCE)
 *   GET  /api/canva/callback              Canva redirects here with ?code&state
 *   POST /api/canva/edit                  {path, title, w, h} -> {editUrl}
 *
 * Flow: the visitor signs in to Canva once; we upload the logo from the bucket
 * to THEIR Canva account as an asset, create a design containing it (titled
 * with the logo's name) and hand back Canva's edit URL.
 *
 * Secrets (Pages -> Settings -> Environment variables):
 *   CANVA_CLIENT_ID, CANVA_CLIENT_SECRET   from canva.dev -> your integration
 *   SHARE_SECRET                            key that encrypts the session cookie (required;
 *                                           no fallback to HF_TOKEN)
 * Register `https://<site>/api/canva/callback` as a redirect URL in the portal.
 * Scopes to enable: asset:write, design:content:write.
 *
 * Tokens live only in an AES-GCM-encrypted, HttpOnly cookie scoped to /api/canva.
 */
import { getListing, fetchBucketObject, requireToken } from "../collection/[[path]].js";

const AUTH_URL = "https://www.canva.com/api/oauth/authorize";
const API = "https://api.canva.com/rest/v1";
const SCOPES = "asset:write design:content:write";
const LOGO_FOLDER = "LOGO/";
const SESSION_COOKIE = "rl_canva";
const OAUTH_COOKIE = "rl_canva_oauth";
const MAX_UPLOAD_BYTES = 30 * 1024 * 1024;
const STATE_MAX_AGE_MS = 10 * 60 * 1000; // same as the OAuth cookie's Max-Age (600 s)
const DEFAULT_DIM = 1000;
// Canva Connect limits for custom designs / asset names.
const MIN_DIM = 40;
const MAX_DIM = 8000;
const MAX_AREA = 25_000_000;
const MAX_ASSET_NAME = 50;
const MAX_TITLE = 255;
const POLL_TRIES = 20;
const POLL_MS = 600;

const enc = new TextEncoder();
const dec = new TextDecoder();

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

/* ------------------------------ crypto helpers ----------------------------- */

const b64url = (bytes) =>
  btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64url = (s) => {
  const raw = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (s.length % 4)) % 4));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};
const randomToken = (n = 32) => b64url(crypto.getRandomValues(new Uint8Array(n)));

function secretOf(env) {
  return env.SHARE_SECRET || null;
}

async function aesKey(secret) {
  const digest = await crypto.subtle.digest("SHA-256", enc.encode(`canva-session:${secret}`));
  return crypto.subtle.importKey("raw", digest, "AES-GCM", false, ["encrypt", "decrypt"]);
}

async function seal(secret, value) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await aesKey(secret), enc.encode(JSON.stringify(value)));
  return `${b64url(iv)}.${b64url(ct)}`;
}

async function unseal(secret, token) {
  try {
    const [iv, ct] = token.split(".");
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64url(iv) }, await aesKey(secret), unb64url(ct));
    return JSON.parse(dec.decode(pt));
  } catch {
    return null;
  }
}

function readCookie(request, name) {
  const header = request.headers.get("Cookie") || "";
  for (const part of header.split(/;\s*/)) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i) === name) return part.slice(i + 1);
  }
  return null;
}

function cookie(url, name, value, maxAge) {
  const secure = url.protocol === "https:" ? "; Secure" : "";
  return `${name}=${value}; Path=/api/canva; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure}`;
}

/* --------------------------------- Canva API -------------------------------- */

function redirectUri(url) {
  return `${url.origin}/api/canva/callback`;
}

async function tokenRequest(env, params) {
  const basic = btoa(`${env.CANVA_CLIENT_ID}:${env.CANVA_CLIENT_SECRET}`);
  const res = await fetch(`${API}/oauth/token`, {
    method: "POST",
    headers: { Authorization: `Basic ${basic}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(params),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || !body.access_token) throw new Error(body.error_description || body.error || `Canva token error (HTTP ${res.status})`);
  return body;
}

const configured = (env) => env.CANVA_CLIENT_ID && env.CANVA_CLIENT_SECRET && secretOf(env);

/* ---------------------------------- routes ---------------------------------- */

async function handleLogin(env, url) {
  if (!configured(env)) return json({ error: "not_configured", message: "Canva is not set up on this deployment yet." }, 503);

  const verifier = randomToken(48);
  const challenge = b64url(await crypto.subtle.digest("SHA-256", enc.encode(verifier)));
  const state = randomToken(16);
  const ret = "/logos";

  const auth = new URL(AUTH_URL);
  auth.search = new URLSearchParams({
    code_challenge: challenge,
    code_challenge_method: "S256",
    scope: SCOPES,
    response_type: "code",
    client_id: env.CANVA_CLIENT_ID,
    state,
    redirect_uri: redirectUri(url),
  }).toString();

  const sealed = await seal(secretOf(env), { v: verifier, s: state, ret, t: Date.now() });
  return new Response(null, {
    status: 302,
    headers: { Location: auth.toString(), "Set-Cookie": cookie(url, OAUTH_COOKIE, sealed, 600), "Cache-Control": "no-store" },
  });
}

async function handleCallback(env, request, url) {
  if (!configured(env)) return json({ error: "not_configured" }, 503);

  const pending = await unseal(secretOf(env), readCookie(request, OAUTH_COOKIE) || "");
  const clear = cookie(url, OAUTH_COOKIE, "", 0);
  const back = (flag) =>
    new Response(null, {
      status: 302,
      headers: { Location: `${pending?.ret || "/logos"}?canva=${flag}`, "Cache-Control": "no-store" },
    });

  const code = url.searchParams.get("code");
  // Sealed state must carry a numeric issue time that is neither in the future nor older than 10 min.
  const age = pending ? Date.now() - pending.t : NaN;
  const fresh = Number.isFinite(age) && age >= 0 && age <= STATE_MAX_AGE_MS;
  if (url.searchParams.get("error") || !code || !pending || !fresh || url.searchParams.get("state") !== pending.s) {
    const res = back("denied");
    res.headers.append("Set-Cookie", clear);
    return res;
  }

  try {
    const t = await tokenRequest(env, {
      grant_type: "authorization_code",
      code,
      code_verifier: pending.v,
      redirect_uri: redirectUri(url),
    });
    const session = { a: t.access_token, r: t.refresh_token, e: Date.now() + (t.expires_in || 3600) * 1000 - 60_000 };
    const res = back("connected");
    res.headers.append("Set-Cookie", clear);
    res.headers.append("Set-Cookie", cookie(url, SESSION_COOKIE, await seal(secretOf(env), session), 60 * 60 * 24 * 30));
    return res;
  } catch {
    const res = back("error");
    res.headers.append("Set-Cookie", clear);
    return res;
  }
}

/**
 * Canva rotates refresh tokens (each is single-use). Two requests that find the
 * access token stale at once would both spend the same refresh token and the
 * loser would sign the visitor out, so concurrent refreshes in one isolate share
 * one in-flight call, keyed by the refresh token.
 */
const refreshing = new Map();

function refreshOnce(env, refreshToken) {
  let p = refreshing.get(refreshToken);
  if (!p) {
    p = tokenRequest(env, { grant_type: "refresh_token", refresh_token: refreshToken }).finally(() => refreshing.delete(refreshToken));
    refreshing.set(refreshToken, p);
  }
  return p;
}

const sessionCookie = async (env, url, session) => cookie(url, SESSION_COOKIE, await seal(secretOf(env), session), 60 * 60 * 24 * 30);

/** The visitor's access token, refreshed when stale. Returns {token, setCookie}, or null when signed out. */
async function getSession(env, request, url) {
  const session = await unseal(secretOf(env), readCookie(request, SESSION_COOKIE) || "");
  if (!session) return null;
  if (Date.now() < session.e) return { token: session.a, setCookie: null };
  if (!session.r) return null;
  try {
    const t = await refreshOnce(env, session.r);
    const next = { a: t.access_token, r: t.refresh_token || session.r, e: Date.now() + (t.expires_in || 3600) * 1000 - 60_000 };
    return { token: next.a, setCookie: await sessionCookie(env, url, next) };
  } catch {
    return null;
  }
}

/** Width/height -> integers inside Canva's 40..8000 px and 25 MP limits, aspect ratio kept. */
export function fitDesign(w, h) {
  const one = (n) => {
    const v = typeof n === "number" || typeof n === "string" ? Number(n) : NaN;
    if (typeof n === "string" && n.trim() === "") return DEFAULT_DIM;
    if (!Number.isFinite(v) || v <= 0) return DEFAULT_DIM;
    return Math.min(MAX_DIM, Math.max(MIN_DIM, Math.round(v)));
  };
  let W = one(w);
  let H = one(h);
  if (W * H > MAX_AREA) {
    const k = Math.sqrt(MAX_AREA / (W * H));
    W = Math.max(MIN_DIM, Math.floor(W * k));
    H = Math.max(MIN_DIM, Math.floor(H * k));
  }
  return { width: W, height: H };
}

/** Asset names are capped at 50 characters (code points, so emoji aren't split). */
export const assetName = (title) => Array.from(String(title)).slice(0, MAX_ASSET_NAME).join("");

const utf8b64 = (str) => {
  let bin = "";
  for (const b of enc.encode(str)) bin += String.fromCharCode(b);
  return btoa(bin);
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function authExpired(url) {
  const res = json({ error: "auth_required", message: "Canva sign-in expired." }, 401);
  res.headers.append("Set-Cookie", cookie(url, SESSION_COOKIE, "", 0));
  return res;
}

async function handleEdit(env, request, url) {
  if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  const origin = request.headers.get("Origin");
  if (request.headers.get("Sec-Fetch-Site") === "cross-site" || (origin && origin !== url.origin)) return json({ error: "forbidden" }, 403);
  if (!configured(env)) return json({ error: "not_configured", message: "Canva is not set up on this deployment yet." }, 503);
  const missing = requireToken(env);
  if (missing) return missing;

  const body = await request.json().catch(() => ({}));
  const path = String(body.path || "");
  if (!path.startsWith(LOGO_FOLDER) || path.includes("..") || path.includes("\\")) return json({ error: "bad_path", message: "Only logos can be opened in Canva." }, 400);

  const session = await getSession(env, request, url);
  if (!session) return authExpired(url);

  let entry;
  try {
    entry = (await getListing(env.HF_TOKEN)).files.find((f) => f.path === path);
  } catch (err) {
    return json({ error: "upstream_error", message: String(err?.message || err) }, 502);
  }
  if (!entry || !entry.previewable) return json({ error: "not_found", message: "No such logo." }, 404);

  const title = (String(body.title || "").trim() || entry.name.replace(/\.[^.]+$/, "")).slice(0, MAX_TITLE);
  const auth = { Authorization: `Bearer ${session.token}` };

  try {
    const file = await fetchBucketObject(env.HF_TOKEN, path);
    if (!file.ok) return json({ error: "upstream_error", message: `Bucket returned HTTP ${file.status}.` }, 502);
    const bytes = await file.arrayBuffer();
    if (bytes.byteLength > MAX_UPLOAD_BYTES) return json({ error: "too_large", message: "That image is too large for Canva import." }, 413);

    // 1. upload to the visitor's Canva as an asset, named after the logo
    const up = await fetch(`${API}/asset-uploads`, {
      method: "POST",
      headers: {
        ...auth,
        "Content-Type": "application/octet-stream",
        "Asset-Upload-Metadata": JSON.stringify({ name_base64: utf8b64(assetName(title)) }),
      },
      body: bytes,
    });
    if (up.status === 401 || up.status === 403) return authExpired(url);
    if (up.status === 429) return json({ error: "rate_limited", message: "Canva is rate limiting requests. Try again in a minute." }, 429);
    let job = (await up.json().catch(() => ({}))).job;
    if (!up.ok || !job) return json({ error: "upstream_error", message: "Canva refused the upload." }, 502);

    // 2. wait for the import job (bounded; transient poll failures are retried)
    for (let i = 0; i < POLL_TRIES && job.status === "in_progress"; i++) {
      await sleep(POLL_MS);
      const poll = await fetch(`${API}/asset-uploads/${encodeURIComponent(job.id)}`, { headers: auth });
      if (poll.status === 401 || poll.status === 403) return authExpired(url);
      if (poll.status === 429 || poll.status >= 500) continue;
      if (!poll.ok) return json({ error: "upstream_error", message: `Canva could not check the import (HTTP ${poll.status}).` }, 502);
      job = (await poll.json().catch(() => ({}))).job || job;
    }
    if (job.status === "in_progress") return json({ error: "timeout", message: "Canva is still importing the image. Try again shortly." }, 504);
    if (job.status !== "success" || !job.asset?.id) {
      return json({ error: "upstream_error", message: job.error?.message ? `Canva could not import the image: ${job.error.message}` : "Canva could not import the image." }, 502);
    }

    // 3. new design that contains the asset
    const { width, height } = fitDesign(body.w, body.h);
    const made = await fetch(`${API}/designs`, {
      method: "POST",
      headers: { ...auth, "Content-Type": "application/json" },
      body: JSON.stringify({
        design_type: { type: "custom", width, height },
        asset_id: job.asset.id,
        title,
      }),
    });
    if (made.status === 401 || made.status === 403) return authExpired(url);
    if (made.status === 429) return json({ error: "rate_limited", message: "Canva is rate limiting requests. Try again in a minute." }, 429);
    const design = (await made.json().catch(() => ({}))).design;
    if (!made.ok || !design?.urls?.edit_url) return json({ error: "upstream_error", message: "Canva could not create the design." }, 502);

    const res = json({ editUrl: design.urls.edit_url, title });
    if (session.setCookie) res.headers.append("Set-Cookie", session.setCookie);
    return res;
  } catch (err) {
    return json({ error: "upstream_error", message: String(err?.message || err) }, 502);
  }
}

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const route = url.pathname.replace(/\/+$/, "").toLowerCase();
  if (route.endsWith("/login")) return handleLogin(env, url);
  if (route.endsWith("/callback")) return handleCallback(env, request, url);
  if (route.endsWith("/edit")) return handleEdit(env, request, url);
  return json({ error: "not_found" }, 404);
}
