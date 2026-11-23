/**
 * "Edit in Canva" client flow for /logos (loaded before logos.js).
 *
 * Opens a blank tab synchronously inside the click handler (the only moment
 * browsers allow it), asks /api/canva/edit to build the design, then points that
 * tab at Canva's edit URL. The original tab is never navigated, except for the
 * one-time OAuth sign-in redirect, which has to be a full-page flow.
 *
 * Pure of DOM globals: everything it touches arrives through `deps`, so
 * scripts/tests/canva_client.test.mjs can drive it without a browser.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.RLCanva = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const EDIT_ENDPOINT = "/api/canva/edit";
  const LOGIN_URL = "/api/canva/login?return=/logos";

  /** Only ever navigate a tab to a Canva-owned https URL (never trust the response blindly). */
  function isCanvaUrl(value) {
    try {
      const u = new URL(String(value));
      return u.protocol === "https:" && (u.hostname === "canva.com" || u.hostname.endsWith(".canva.com"));
    } catch (e) {
      return false;
    }
  }

  /** Freeze what the visitor clicked NOW; later viewer navigation can't change it. */
  function snapshot(file) {
    return { path: String(file.path), name: String(file.name), w: file.w, h: file.h };
  }

  function discard(tab) {
    try { if (tab && !tab.closed) tab.close(); } catch (e) { /* already gone */ }
  }

  /**
   * deps: { open(), fetch, assign(url), setPending(path), notify(msg, kind), title(name) }
   * Returns "opened" | "popup_blocked" | "auth_required" | "closed" | "error".
   * Must be called synchronously from the click handler.
   */
  async function startEdit(file, deps) {
    const pick = snapshot(file);

    let tab = null;
    try { tab = deps.open(); } catch (e) { tab = null; }
    if (!tab) {
      deps.notify("Your browser blocked the new tab. Allow pop-ups for this site, then click Edit in Canva again.", "warn");
      return "popup_blocked";
    }
    try { tab.opener = null; } catch (e) { /* cross-origin guard */ }

    try {
      const res = await deps.fetch(EDIT_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: pick.path, title: deps.title(pick.name), w: pick.w, h: pick.h }),
      });
      const data = await res.json().catch(() => ({}));

      if (res.status === 401 && data.error === "auth_required") {
        discard(tab);
        deps.setPending(pick.path);
        deps.notify("Sign in to Canva to continue…", "ok");
        deps.assign(LOGIN_URL);
        return "auth_required";
      }
      if (!res.ok || !data.editUrl) throw new Error(data.message || `HTTP ${res.status}`);
      if (!isCanvaUrl(data.editUrl)) throw new Error("Canva returned an unexpected address.");
      if (tab.closed) {
        deps.notify("The Canva tab was closed before the design was ready.", "warn");
        return "closed";
      }
      tab.location.replace(data.editUrl);
      return "opened";
    } catch (err) {
      discard(tab);
      deps.notify(`Couldn’t open ${pick.name} in Canva: ${err && err.message ? err.message : err}`, "warn");
      return "error";
    }
  }

  return { startEdit, isCanvaUrl, snapshot, EDIT_ENDPOINT, LOGIN_URL };
});
