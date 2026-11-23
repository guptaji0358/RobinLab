// Tests for the "Edit in Canva" new-tab flow (scripts/root/js/canva-edit.js).
// Run:  node --test scripts/tests/canva_client.test.mjs
// No browser, no network: `deps` are fakes.
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const { startEdit, isCanvaUrl, LOGIN_URL } = createRequire(import.meta.url)(path.resolve(here, "../root/js/canva-edit.js"));

const EDIT = "https://www.canva.com/design/DAF/edit";

function fakeTab() {
  return { closed: false, opener: "set", navigated: null, close() { this.closed = true; }, location: { replace(u) { this.owner.navigated = u; } } };
}
function harness({ tab = fakeTab(), response, openThrows = false } = {}) {
  if (tab) tab.location.owner = tab;
  const log = { opens: 0, fetches: [], assigns: [], pending: [], notes: [] };
  const deps = {
    open: () => { log.opens++; if (openThrows) throw new Error("blocked"); return tab; },
    fetch: async (url, init) => { log.fetches.push({ url, body: JSON.parse(init.body) }); return response(); },
    assign: (u) => log.assigns.push(u),
    setPending: (p) => log.pending.push(p),
    notify: (m, k) => log.notes.push([m, k]),
    title: (n) => n.replace(/\.[^.]+$/, ""),
  };
  return { deps, log, tab };
}
const ok = (data, status = 200) => () => ({ ok: status < 400, status, json: async () => data });
const file = { path: "LOGO/a.png", name: "a.png", w: 640, h: 480 };

test("success: blank tab opened first, then navigated to the Canva edit URL; original untouched", async () => {
  const h = harness({ response: ok({ editUrl: EDIT }) });
  assert.equal(await startEdit(file, h.deps), "opened");
  assert.equal(h.log.opens, 1);
  assert.equal(h.tab.navigated, EDIT);
  assert.equal(h.tab.closed, false);
  assert.equal(h.tab.opener, null, "new tab must not keep a handle on this page");
  assert.deepEqual(h.log.assigns, [], "original tab is never navigated");
});

test("popup blocked: no API call, clear message, nothing to clean up", async () => {
  for (const blocked of [{ tab: null }, { openThrows: true }]) {
    const h = harness({ ...blocked, response: ok({ editUrl: EDIT }) });
    assert.equal(await startEdit(file, h.deps), "popup_blocked");
    assert.equal(h.log.fetches.length, 0);
    assert.match(h.log.notes[0][0], /pop-ups/i);
  }
});

test("tab is opened synchronously, before any await", async () => {
  const h = harness({ response: ok({ editUrl: EDIT }) });
  const p = startEdit(file, h.deps);
  assert.equal(h.log.opens, 1, "open() must have run before startEdit yields");
  await p;
});

test("API error: tab is closed, error reported, original tab unchanged", async () => {
  const h = harness({ response: ok({ error: "upstream_error", message: "Canva refused the upload." }, 502) });
  assert.equal(await startEdit(file, h.deps), "error");
  assert.equal(h.tab.closed, true);
  assert.match(h.log.notes[0][0], /Canva refused the upload/);
  assert.deepEqual(h.log.assigns, []);
});

test("network failure closes the tab", async () => {
  const h = harness({ response: () => { throw new Error("offline"); } });
  assert.equal(await startEdit(file, h.deps), "error");
  assert.equal(h.tab.closed, true);
});

test("auth required: tab closed, pending logo remembered, this tab goes to sign-in", async () => {
  const h = harness({ response: ok({ error: "auth_required" }, 401) });
  assert.equal(await startEdit(file, h.deps), "auth_required");
  assert.equal(h.tab.closed, true);
  assert.deepEqual(h.log.pending, ["LOGO/a.png"]);
  assert.deepEqual(h.log.assigns, [LOGIN_URL]);
});

test("a non-Canva edit URL is refused and the tab closed", async () => {
  for (const bad of ["javascript:alert(1)", "https://evil.example/x", "https://canva.com.evil.example/x", "http://www.canva.com/x", ""]) {
    const h = harness({ response: ok({ editUrl: bad }) });
    assert.equal(await startEdit(file, h.deps), "error", bad);
    assert.equal(h.tab.navigated, null);
    assert.equal(h.tab.closed, true);
  }
  assert.ok(isCanvaUrl("https://canva.com/x") && isCanvaUrl(EDIT));
});

test("user closed the new tab meanwhile: reported, no navigation", async () => {
  const tab = fakeTab();
  const h = harness({ tab, response: () => { tab.closed = true; return { ok: true, status: 200, json: async () => ({ editUrl: EDIT }) }; } });
  assert.equal(await startEdit(file, h.deps), "closed");
  assert.equal(h.tab.navigated, null);
});

test("image selection: the request carries the file clicked, even if the object changes mid-flight", async () => {
  const mutable = { path: "LOGO/a.png", name: "a.png", w: 640, h: 480 };
  let release;
  const gate = new Promise((r) => (release = r));
  const h = harness({ response: async () => { await gate; return { ok: true, status: 200, json: async () => ({ editUrl: EDIT }) }; } });
  const p = startEdit(mutable, h.deps);
  // the viewer moves on to another logo while the first request is in flight
  Object.assign(mutable, { path: "LOGO/b.png", name: "b.png", w: 1, h: 1 });
  release();
  await p;
  assert.deepEqual(h.log.fetches[0].body, { path: "LOGO/a.png", title: "a", w: 640, h: 480 });
});
