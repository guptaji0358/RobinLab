// Google Search Console ownership file. Served by a Function so the URL answers 200
// at the exact .html path (Pages' static handler would 308 it to the extensionless URL).
const BODY = "google-site-verification: google94352492b05c9384.html";
const HEADERS = { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300" };

export const onRequestGet = () => new Response(BODY, { headers: HEADERS });
// HEAD must also answer 200 here, otherwise it falls through to the static 308 redirect.
export const onRequestHead = () =>
  new Response(null, { headers: { ...HEADERS, "content-length": String(BODY.length) } });
