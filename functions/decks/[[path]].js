/**
 * Public deck endpoint for the Office Web Viewer — Cloudflare Pages Function.
 *
 *   GET /decks/<name>.pptx  -> streams presentations/<name>.pptx
 *
 * Microsoft's viewer downloads the file itself from a public URL, so this route
 * exists to hand it a clean path that ends in `.pptx` (the viewer is unreliable
 * with long, query-string-heavy URLs). Only PowerPoint files are exposed here;
 * images and everything else stay on `/api/collection/file`.
 *
 * The bytes still come from the private Hugging Face bucket through the shared
 * `streamBucketFile` helper, so the token remains server-side.
 */

import { PPTX_TYPE, streamBucketFile } from "../api/collection/[[path]].js";

const DECK_FOLDER = "presentations/";

/** `params.path` is the wildcard tail; Cloudflare may hand it over as a string or string[]. */
function wildcardPath(params) {
  const raw = params && params.path;
  const parts = Array.isArray(raw) ? raw : raw ? [raw] : [];
  const text = parts.filter(Boolean).join("/");
  if (!text) return "";
  // Cloudflare leaves the wildcard percent-encoded (`Studies%20of…`). Decode it
  // so it lines up with bucket paths; `+` is a literal plus, not a space.
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

export async function onRequest({ request, env, params }) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method not allowed", {
      status: 405,
      headers: { Allow: "GET, HEAD" },
    });
  }

  const name = wildcardPath(params);
  if (!name) return new Response("Not found", { status: 404 });

  const path = `${DECK_FOLDER}${name}`;

  return streamBucketFile(env, request, path, {
    // Belt and braces: the file must live in presentations/ and be a real deck.
    allow: (entry) => entry.path === path && entry.contentType === PPTX_TYPE,
  });
}
