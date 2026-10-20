/**
 * Presentations page — .pptx decks from the RobinLab bucket, rendered in the
 * browser by the vendored `pptx-preview` bundle (`vendor/pptx-preview.umd.js`).
 *
 * The bundle is ~1.3 MB, so it is loaded lazily the first time a deck is opened
 * instead of on page load. Decks are fetched through the same server-side proxy
 * as the Collection (`/api/collection/file?path=…`); the Hugging Face token never
 * reaches the browser.
 *
 * Only files the proxy can serve — images and .pptx — appear here. Everything
 * else in the bucket is ignored.
 */
(() => {
  "use strict";

  const LIST_ENDPOINT = "/api/collection/files";
  const LIB_URL = "vendor/pptx-preview.umd.js";
  const PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation";

  // Logical slide surface. The whole deck is scaled to fit the viewport with a
  // CSS transform, so slides stay vector-crisp at every screen size. A deck can
  // be 16:9, 4:3 or anything else — the real slide box is measured after render
  // (see `measureSlides`) and these are only the fallback/initial values.
  const SLIDE_W = 1280;
  const SLIDE_H = 720;

  const el = {
    grid: document.getElementById("pr-grid"),
    stats: document.getElementById("pr-stats"),
    state: document.getElementById("pr-state"),
    year: document.getElementById("year"),
    viewer: document.getElementById("deck-viewer"),
    name: document.getElementById("deck-name"),
    sub: document.getElementById("deck-sub"),
    counter: document.getElementById("deck-counter"),
    status: document.getElementById("deck-status"),
    stage: document.getElementById("deck-stage"),
    close: document.getElementById("deck-close"),
    prev: document.getElementById("deck-prev"),
    next: document.getElementById("deck-next"),
  };

  const deckCache = new Map();
  let decks = [];
  let libPromise = null;
  let scroller = null;
  let slides = [];
  let slideW = SLIDE_W;
  let slideH = SLIDE_H;
  let slideIndex = 0;
  let lastFocused = null;
  let rafPending = false;

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
    return file.name.replace(/\.[a-z0-9]+$/i, "").replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
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
    const parts = [formatBytes(file.size), uploadedLabel(file)].filter(Boolean);
    meta.textContent = parts.join(" · ");

    body.append(title, meta);
    card.append(art, body);
    card.addEventListener("click", () => openDeck(file));
    return card;
  }

  function render() {
    el.grid.textContent = "";

    if (!decks.length) {
      showState("empty", "No presentations yet.", "Add .pptx decks to the presentations/ folder in the bucket.");
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
  /* Renderer loading                                                    */
  /* ------------------------------------------------------------------ */

  function loadLibrary() {
    if (window.pptxPreview) return Promise.resolve(window.pptxPreview);
    if (libPromise) return libPromise;

    libPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = LIB_URL;
      script.async = true;
      script.onload = () => {
        if (window.pptxPreview) resolve(window.pptxPreview);
        else reject(new Error("Renderer loaded but did not register."));
      };
      script.onerror = () => reject(new Error("Could not load the presentation renderer."));
      document.head.appendChild(script);
    });

    return libPromise;
  }

  function getDeckBytes(file) {
    if (deckCache.has(file.path)) return Promise.resolve(deckCache.get(file.path));

    return fetch(file.url, { headers: { Accept: "*/*" } }).then(async (response) => {
      if (!response.ok) {
        if (response.status === 415) {
          throw new Error("The API refused this file type. Redeploy so the proxy allows .pptx (HTTP 415).");
        }
        throw new Error(`Could not fetch the deck (HTTP ${response.status}).`);
      }
      const buffer = await response.arrayBuffer();
      deckCache.set(file.path, buffer);
      return buffer;
    });
  }

  /* ------------------------------------------------------------------ */
  /* Viewer                                                              */
  /* ------------------------------------------------------------------ */

  function showDeckState(title, detail) {
    const box = document.createElement("div");
    box.className = "deck-state";
    const heading = document.createElement("p");
    heading.className = "deck-state-title";
    heading.textContent = title;
    box.appendChild(heading);
    if (detail) {
      const text = document.createElement("p");
      text.className = "deck-state-detail";
      text.textContent = detail;
      box.appendChild(text);
    }
    el.stage.appendChild(box);
    return box;
  }

  function clearDeckState() {
    for (const box of el.stage.querySelectorAll(".deck-state")) box.remove();
  }

  function setNavEnabled() {
    const many = slides.length > 1;
    el.prev.disabled = !many || slideIndex <= 0;
    el.next.disabled = !many || slideIndex >= slides.length - 1;
  }

  function goTo(index) {
    if (!slides.length) return;
    slideIndex = Math.max(0, Math.min(slides.length - 1, index));
    if (scroller) scroller.scrollTop = slides[slideIndex].offsetTop;
    el.counter.textContent = `${slideIndex + 1} / ${slides.length}`;
    el.status.textContent = `Slide ${slideIndex + 1} of ${slides.length}`;
    setNavEnabled();
  }

  // The renderer sizes each slide from the deck's own aspect ratio, so measure
  // the first rendered slide rather than trusting the requested 16:9 box. The
  // scroll viewport is then pinned to exactly one slide, which keeps
  // "one slide per view" true for 4:3 decks too.
  function measureSlides() {
    const first = slides[0];
    if (!first) return;
    slideW = first.offsetWidth || SLIDE_W;
    slideH = first.offsetHeight || SLIDE_H;
    if (scroller) {
      scroller.style.height = `${slideH}px`;
      scroller.style.width = `${slideW}px`;
    }
  }

  // Fit the fixed-size deck into the stage with a transform. Scaling (rather than
  // re-rendering at a new size) keeps text sharp and slide navigation stable.
  function fit() {
    if (!scroller) return;
    const { width, height } = el.stage.getBoundingClientRect();
    if (!width || !height) return;
    const scale = Math.min(width / slideW, height / slideH);

    scroller.style.position = "absolute";
    scroller.style.margin = "0";
    scroller.style.transformOrigin = "top left";
    scroller.style.transform = `scale(${scale})`;
    scroller.style.left = `${Math.max(0, (width - slideW * scale) / 2)}px`;
    scroller.style.top = `${Math.max(0, (height - slideH * scale) / 2)}px`;
  }

  function syncIndexFromScroll() {
    if (rafPending || !scroller || !slides.length) return;
    rafPending = true;
    requestAnimationFrame(() => {
      rafPending = false;
      const top = scroller.scrollTop;
      let nearest = 0;
      let best = Infinity;
      slides.forEach((slide, index) => {
        const distance = Math.abs(slide.offsetTop - top);
        if (distance < best) {
          best = distance;
          nearest = index;
        }
      });
      if (nearest !== slideIndex) {
        slideIndex = nearest;
        el.counter.textContent = `${slideIndex + 1} / ${slides.length}`;
        el.status.textContent = `Slide ${slideIndex + 1} of ${slides.length}`;
        setNavEnabled();
      }
    });
  }

  async function openDeck(file) {
    lastFocused = document.activeElement;
    el.viewer.hidden = false;
    document.body.classList.add("deck-open");
    el.name.textContent = deckTitle(file);
    el.name.title = file.path;
    el.sub.textContent = [formatBytes(file.size), uploadedLabel(file)].filter(Boolean).join(" · ");
    el.counter.textContent = "";
    el.status.textContent = "Rendering…";
    el.prev.disabled = true;
    el.next.disabled = true;

    scroller = null;
    slides = [];
    slideW = SLIDE_W;
    slideH = SLIDE_H;
    slideIndex = 0;
    el.stage.querySelectorAll(".pptx-preview-wrapper, .pptx-preview-slide-wrapper, .deck-mount").forEach((node) => node.remove());
    clearDeckState();

    const loading = showDeckState("Rendering presentation…", "Fetching the deck and building slides.");
    el.close.focus({ preventScroll: true });

    try {
      const [pptxPreview, buffer] = await Promise.all([loadLibrary(), getDeckBytes(file)]);

      const mount = document.createElement("div");
      mount.className = "deck-mount";
      el.stage.appendChild(mount);

      const preview = pptxPreview.init(mount, { width: SLIDE_W, height: SLIDE_H });
      await preview.preview(buffer);

      scroller = mount.querySelector(".pptx-preview-wrapper");
      slides = Array.from(mount.querySelectorAll(".pptx-preview-slide-wrapper"));
      if (!scroller || !slides.length) throw new Error("The deck contained no renderable slides.");

      loading.remove();
      scroller.addEventListener("scroll", syncIndexFromScroll, { passive: true });

      measureSlides();
      fit();
      goTo(0);
    } catch (err) {
      loading.remove();
      showDeckState("This deck could not be displayed.", err && err.message ? err.message : String(err));
      el.status.textContent = "Failed to render";
      console.error(err);
    }
  }

  function closeDeck() {
    if (el.viewer.hidden) return;
    el.viewer.hidden = true;
    document.body.classList.remove("deck-open");
    el.stage
      .querySelectorAll(".pptx-preview-wrapper, .pptx-preview-slide-wrapper, .deck-mount, .deck-state")
      .forEach((node) => node.remove());
    scroller = null;
    slides = [];
    slideW = SLIDE_W;
    slideH = SLIDE_H;
    slideIndex = 0;
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus({ preventScroll: true });
  }

  /* ------------------------------------------------------------------ */
  /* Events                                                              */
  /* ------------------------------------------------------------------ */

  el.close.addEventListener("click", closeDeck);
  el.prev.addEventListener("click", () => goTo(slideIndex - 1));
  el.next.addEventListener("click", () => goTo(slideIndex + 1));
  el.viewer.addEventListener("click", (event) => {
    if (event.target.hasAttribute("data-close")) closeDeck();
  });

  document.addEventListener("keydown", (event) => {
    if (el.viewer.hidden) return;
    if (event.key === "Escape") closeDeck();
    else if (event.key === "ArrowLeft") goTo(slideIndex - 1);
    else if (event.key === "ArrowRight" || event.key === " ") {
      if (event.key === " ") event.preventDefault();
      goTo(slideIndex + 1);
    }
  });

  document.addEventListener("fullscreenchange", fit);
  window.addEventListener("resize", () => {
    if (!el.viewer.hidden) fit();
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
        .sort((a, b) => deckTitle(a).localeCompare(deckTitle(b), undefined, { numeric: true, sensitivity: "base" }));

      render();
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
