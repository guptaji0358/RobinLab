/**
 * Presentations page — .pptx decks from the RobinLab bucket.
 *
 * Rendering is delegated to **Microsoft Office Web Viewer**
 * (`view.officeapps.live.com`), the same hosted viewer Microsoft provides for
 * PowerPoint files on the web. Microsoft's servers download the deck themselves,
 * so the file has to be reachable at a public URL — which is why decks are
 * exposed on the clean `/decks/<name>.pptx` route (see
 * `functions/decks/[[path]].js`) instead of the token-guarded bucket endpoint.
 *
 * The Hugging Face token still never reaches the browser: `/decks/*` streams the
 * bytes server-side, exactly like the Collection proxy.
 *
 * Only `.pptx` files listed in the bucket appear here; images stay on
 * `/collection`.
 */
(() => {
  "use strict";

  const LIST_ENDPOINT = "/api/collection/files";
  const PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation";
  const DECK_PREFIX = "presentations/";

  // `embed.aspx` renders inside an iframe; `view.aspx` is the full-page viewer.
  const OFFICE_EMBED = "https://view.officeapps.live.com/op/embed.aspx";
  const OFFICE_VIEW = "https://view.officeapps.live.com/op/view.aspx";

  const el = {
    grid: document.getElementById("pr-grid"),
    stats: document.getElementById("pr-stats"),
    state: document.getElementById("pr-state"),
    year: document.getElementById("year"),
    viewer: document.getElementById("deck-viewer"),
    name: document.getElementById("deck-name"),
    sub: document.getElementById("deck-sub"),
    open: document.getElementById("deck-open"),
    download: document.getElementById("deck-download"),
    share: document.getElementById("deck-share"),
    stage: document.getElementById("deck-stage"),
    loading: document.getElementById("deck-loading"),
    hint: document.getElementById("deck-nav-hint"),
    hintText: document.getElementById("deck-nav-text"),
    close: document.getElementById("deck-close"),
  };

  let decks = [];
  let lastFocused = null;
  let slowTimer = null;

  /* ------------------------------------------------------------------ */
  /* Helpers                                                             */
  /* ------------------------------------------------------------------ */

  function formatBytes(bytes) {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / 1024 ** i;
    const rounded = i === 0 || value >= 10 ? Math.round(value) : value.toFixed(1);
    return `${rounded} ${units[i]}`;
  }

  function deckTitle(file) {
    return RGSNames.pretty(file.name);
  }

  function uploadedLabel(file) {
    if (!file.uploadedAt) return "";
    const date = new Date(file.uploadedAt);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function isDeck(file) {
    return (file.contentType || "") === PPTX_TYPE || /\.pptx$/i.test(file.name || "");
  }

  /** Public path Microsoft can fetch, e.g. /decks/NumberSystem.pptx */
  function deckPath(file) {
    const relative = file.path.startsWith(DECK_PREFIX) ? file.path.slice(DECK_PREFIX.length) : file.name;
    return `/decks/${relative.split("/").map(encodeURIComponent).join("/")}`;
  }

  function absoluteDeckUrl(file) {
    return new URL(deckPath(file), window.location.href).href;
  }

  /**
   * Office Web Viewer URL. `src` must be fully percent-encoded — otherwise an
   * `&` inside it would be read as a parameter of embed.aspx itself.
   */
  function officeUrl(base, file) {
    return `${base}?src=${encodeURIComponent(absoluteDeckUrl(file))}&action=embedview&wdAllowInteractivity=False`;
  }

  function showState(kind, title, detail) {
    el.state.hidden = false;
    el.state.className = `col-state col-state-${kind}`;
    el.state.textContent = "";

    const heading = document.createElement("p");
    heading.className = "col-state-title";
    heading.textContent = title;
    el.state.appendChild(heading);

    if (detail) {
      const text = document.createElement("p");
      text.className = "col-state-detail";
      text.textContent = detail;
      el.state.appendChild(text);
    }
  }

  function hideState() {
    el.state.hidden = true;
    el.state.textContent = "";
  }

  /* ------------------------------------------------------------------ */
  /* Grid                                                                */
  /* ------------------------------------------------------------------ */

  function buildCard(file) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "pr-card";
    card.title = `Open ${deckTitle(file)}`;

    const art = document.createElement("span");
    art.className = "pr-card-art";

    const ext = document.createElement("span");
    ext.className = "pr-card-ext";
    ext.textContent = "PPTX";

    const open = document.createElement("span");
    open.className = "pr-card-open";
    open.textContent = "Open deck";

    art.append(ext, open);

    const body = document.createElement("span");
    body.className = "pr-card-body";

    const title = document.createElement("span");
    title.className = "pr-card-title";
    title.textContent = deckTitle(file);

    const meta = document.createElement("span");
    meta.className = "pr-card-meta";
    meta.textContent = [formatBytes(file.size), uploadedLabel(file)].filter(Boolean).join(" · ");

    body.append(title, meta);
    card.append(art, body);
    card.addEventListener("click", () => openDeck(file));
    return card;
  }

  function render() {
    el.grid.textContent = "";

    if (!decks.length) {
      showState(
        "empty",
        "No presentations yet.",
        "Add .pptx decks to the presentations/ folder in the bucket.",
      );
      el.stats.textContent = "";
      return;
    }

    hideState();
    const frag = document.createDocumentFragment();
    for (const file of decks) frag.appendChild(buildCard(file));
    el.grid.appendChild(frag);

    const bytes = decks.reduce((sum, file) => sum + file.size, 0);
    el.stats.textContent = `${decks.length} ${decks.length === 1 ? "deck" : "decks"} · ${formatBytes(bytes)}`;
  }

  /* ------------------------------------------------------------------ */
  /* Viewer                                                              */
  /* ------------------------------------------------------------------ */

  /* ------------------------------------------------------------------ */
  /* Navigation hint                                                     */
  /* The slides run in Microsoft's cross-origin iframe, so this page      */
  /* cannot drive it: the hint only teaches the gesture, and dismisses    */
  /* once the visitor interacts (SPACE here, or a tap/click that moves    */
  /* focus into the frame).                                               */
  /* ------------------------------------------------------------------ */

  const HINT_TEXT = { touch: "Tap to navigate slides", keyboard: "Press SPACE to navigate slides" };
  const coarseQuery = window.matchMedia("(pointer: coarse)");
  let inputMode = coarseQuery.matches ? "touch" : "keyboard";
  let hintActive = false;
  let hintTimer = null;

  function paintHint() {
    el.hint.dataset.mode = inputMode;
    el.hintText.textContent = HINT_TEXT[inputMode];
  }

  function setInputMode(mode) {
    if (mode === inputMode) return;
    inputMode = mode;
    if (hintActive) paintHint();
  }

  function showHint() {
    hintActive = true;
    paintHint();
    el.hint.classList.remove("is-leaving");
    el.hint.hidden = false;
    clearTimeout(hintTimer);
    hintTimer = setTimeout(dismissHint, 12000); // safety net: taps inside the frame can be invisible to us
  }

  function dismissHint() {
    clearTimeout(hintTimer);
    if (!hintActive) return;
    hintActive = false;
    el.hint.classList.add("is-leaving");
    setTimeout(() => {
      if (!hintActive) el.hint.hidden = true;
    }, 350);
  }

  // Hybrid devices: follow whichever input was used last.
  coarseQuery.addEventListener("change", (e) => setInputMode(e.matches ? "touch" : "keyboard"));
  document.addEventListener(
    "pointerdown",
    (e) => setInputMode(e.pointerType === "touch" || e.pointerType === "pen" ? "touch" : "keyboard"),
    { passive: true },
  );
  // A tap/click inside the cross-origin frame moves focus into it: that is the only signal we get.
  window.addEventListener("blur", () => {
    if (hintActive && document.activeElement && document.activeElement.classList.contains("deck-frame")) dismissHint();
  });

  function openDeck(file) {
    currentDeck = file;
    lastFocused = document.activeElement;

    el.viewer.hidden = false;
    document.body.classList.add("deck-open");

    el.name.textContent = deckTitle(file);
    el.name.title = file.path;
    el.sub.textContent = [formatBytes(file.size), uploadedLabel(file)].filter(Boolean).join(" · ");
    el.open.href = officeUrl(OFFICE_VIEW, file);

    // Direct .pptx download from the public deck route. `download` forces a save
    // (same origin) and names the file after the deck, even though the viewer
    // gets an inline response.
    el.download.href = deckPath(file);
    el.download.setAttribute("download", file.name);

    hintActive = false;
    clearTimeout(hintTimer);
    el.hint.hidden = true;

    // Drop any previous deck and restore the loading text.
    for (const old of el.stage.querySelectorAll("iframe")) old.remove();
    if (el.loading) {
      el.loading.hidden = false;
      const detail = el.loading.querySelector(".deck-state-detail");
      if (detail) detail.textContent = "Microsoft is fetching and rendering the deck.";
    }

    const frame = document.createElement("iframe");
    frame.className = "deck-frame";
    frame.title = `${deckTitle(file)} — Microsoft PowerPoint viewer`;
    frame.allowFullscreen = true;
    frame.src = officeUrl(OFFICE_EMBED, file);

    // The viewer runs on Microsoft's origin, so a failed file fetch cannot be
    // detected from here. Hide the overlay once the viewer shell loads, and
    // offer the full-page viewer if it is taking unusually long.
    frame.addEventListener(
      "load",
      () => {
        if (el.loading) el.loading.hidden = true;
        showHint();
        if (slowTimer) {
          clearTimeout(slowTimer);
          slowTimer = null;
        }
      },
      { once: true },
    );

    el.stage.appendChild(frame);

    if (slowTimer) clearTimeout(slowTimer);
    slowTimer = setTimeout(() => {
      if (!el.loading || el.loading.hidden) return;
      const detail = el.loading.querySelector(".deck-state-detail");
      if (detail) {
        detail.textContent =
          "Still waiting on Microsoft. If the slides never appear, use “Open full view” above — the deck itself opens fine.";
      }
    }, 15000);

    // Focus the panel, not a button: SPACE on a focused button would click it (e.g. close the deck).
    const panel = el.viewer.querySelector(".deck-panel");
    panel.tabIndex = -1;
    panel.focus({ preventScroll: true });
  }

  function closeDeck() {
    if (el.viewer.hidden) return;

    el.viewer.hidden = true;
    document.body.classList.remove("deck-open");
    hintActive = false;
    clearTimeout(hintTimer);
    el.hint.hidden = true;

    // Clearing src stops the viewer and releases its network activity.
    for (const frame of el.stage.querySelectorAll("iframe")) {
      frame.src = "about:blank";
      frame.remove();
    }

    if (slowTimer) {
      clearTimeout(slowTimer);
      slowTimer = null;
    }

    el.open.href = "#";
    el.download.href = "#";
    el.download.removeAttribute("download");
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus({ preventScroll: true });
  }

  /* ------------------------------------------------------------------ */
  /* Events                                                              */
  /* ------------------------------------------------------------------ */

  /* ------------------------------------------------------------------ */
  /* Share link (valid 90 days, signed on the server)                     */
  /* ------------------------------------------------------------------ */

  let currentDeck = null;
  let shareLabelTimer = null;

  function flashShare(text) {
    el.share.textContent = text;
    if (shareLabelTimer) clearTimeout(shareLabelTimer);
    shareLabelTimer = setTimeout(() => {
      el.share.textContent = "Share link";
    }, 4000);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      window.prompt("Copy this link:", text);
      return false;
    }
  }

  async function shareDeck() {
    if (!currentDeck) return;
    el.share.disabled = true;
    try {
      const response = await fetch("/api/collection/share", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ path: currentDeck.path }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.url) {
        flashShare("Could not create link");
        return;
      }
      const days = Math.round((payload.ttlSeconds || 0) / 86400);
      const copied = await copyText(payload.url);
      flashShare(copied ? `Link copied · valid ${days} days` : "Link ready");
    } catch {
      flashShare("Could not create link");
    } finally {
      el.share.disabled = false;
    }
  }

  /** Open the deck named by `?share=<token>`, or tell the visitor the link is dead. */
  async function openSharedDeck() {
    const token = new URLSearchParams(window.location.search).get("share");
    if (!token) return;
    try {
      const response = await fetch(`/api/collection/share?token=${encodeURIComponent(token)}`, {
        headers: { Accept: "application/json" },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        showState("error", "This shared link can't be opened.", payload.message || "The link is not valid.");
        return;
      }
      const file = decks.find((deck) => deck.path === payload.path);
      if (file) openDeck(file);
      else showState("error", "That presentation is no longer available.", "");
    } catch (err) {
      console.error(err);
    }
  }

  el.share.addEventListener("click", shareDeck);
  el.close.addEventListener("click", closeDeck);
  el.viewer.addEventListener("click", (event) => {
    if (event.target.hasAttribute("data-close")) closeDeck();
  });

  document.addEventListener("keydown", (event) => {
    if (el.viewer.hidden) return;
    if (event.key === "Escape") closeDeck();
    else if (event.key === " " || event.code === "Space") {
      setInputMode("keyboard");
      // Stop the page scrolling. Hand focus to the slides so the viewer's own
      // SPACE handling takes over from the next press (we cannot forward it).
      if (!event.target.closest("a, button, input, textarea, select")) {
        event.preventDefault();
        dismissHint();
        const frame = el.stage.querySelector("iframe");
        if (frame) frame.focus({ preventScroll: true });
      }
    }
  });

  /* ------------------------------------------------------------------ */
  /* Boot                                                                */
  /* ------------------------------------------------------------------ */

  async function load() {
    showState("loading", "Loading presentations…", "Fetching the vault index.");

    try {
      const response = await fetch(LIST_ENDPOINT, { headers: { Accept: "application/json" } });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        showState(
          "error",
          "Presentations could not be loaded.",
          payload.message || `The server responded with HTTP ${response.status}.`,
        );
        return;
      }

      decks = (Array.isArray(payload.files) ? payload.files : [])
        .filter(isDeck)
        .sort((a, b) =>
          deckTitle(a).localeCompare(deckTitle(b), undefined, { numeric: true, sensitivity: "base" }),
        );

      render();
      await openSharedDeck();
    } catch (err) {
      showState(
        "error",
        "Presentations could not be loaded.",
        "Could not reach the API. If you are previewing locally, serve the site with `python dev_server.py`.",
      );
      console.error(err);
    }
  }

  if (el.year) el.year.textContent = new Date().getFullYear();
  load();
})();
