/**
 * Logos page — brand marks stored in the bucket's "LOGO/" folder.
 *
 * The manifest (`GET /api/collection/files`) is the same one the Collection
 * page uses; this page keeps only images whose folder is `LOGO` (or a
 * subfolder below it) and renders each one on both a dark and a light stage.
 *
 * Downloads fetch the proxied original and save it through a Blob URL, so the
 * file keeps its real format and name (SVG stays vector, transparency stays
 * transparent). Nothing is watermarked or re-encoded.
 */
(() => {
  "use strict";

  const LIST_ENDPOINT = "/api/collection/files";
  const LOGO_ROOT = "logo"; // bucket folder, matched case-insensitively
  const IMAGE_RE = /\.(svg|png|jpe?g|webp|gif|avif|bmp|ico|tiff?)$/i;

  const el = {
    grid: document.getElementById("lg-grid"),
    stats: document.getElementById("lg-stats"),
    state: document.getElementById("lg-state"),
    search: document.getElementById("lg-search"),
    year: document.getElementById("year"),
    toast: document.getElementById("toast"),
    lightbox: document.getElementById("lg-lightbox"),
    panel: document.querySelector(".lg-panel"),
    close: document.getElementById("lg-close"),
    prev: document.getElementById("lg-prev"),
    next: document.getElementById("lg-next"),
    canvas: document.getElementById("lg-canvas"),
    img: document.getElementById("lg-img"),
    name: document.getElementById("lg-v-name"),
    meta: document.getElementById("lg-v-meta"),
    dim: document.getElementById("lg-v-dim"),
    counter: document.getElementById("lg-v-counter"),
    download: document.getElementById("lg-v-download"),
    bgButtons: document.querySelectorAll("#lg-bg [data-bg]"),
  };

  if (!el.grid || !el.lightbox) return;

  if (el.year) el.year.textContent = new Date().getFullYear();

  let allLogos = [];
  let shown = [];
  let query = "";
  let openAt = -1;
  let lastFocus = null;
  let toastTimer = 0;
  let dimToken = 0;

  /* ------------------------------------------------------------------ */
  /* Helpers                                                             */
  /* ------------------------------------------------------------------ */

  function node(tag, cls, attrs) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    for (const key in attrs || {}) n.setAttribute(key, attrs[key]);
    return n;
  }

  function pretty(name) {
    return window.RGSNames ? window.RGSNames.pretty(name) : name;
  }

  function formatBytes(bytes) {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / 1024 ** i;
    return `${i === 0 || value >= 10 ? Math.round(value) : value.toFixed(1)} ${units[i]}`;
  }

  function extensionOf(file) {
    const match = /\.([a-z0-9]{1,8})$/i.exec(file.name || "");
    if (match) return match[1].toUpperCase();
    const subtype = String(file.contentType || "").split("/")[1] || "FILE";
    return subtype.split("+")[0].toUpperCase();
  }

  function inLogoFolder(file) {
    const folder = String(file.folder || "").replace(/\\/g, "/").toLowerCase();
    return folder === LOGO_ROOT || folder.startsWith(`${LOGO_ROOT}/`);
  }

  function isRenderable(file) {
    return String(file.contentType || "").startsWith("image/") || IMAGE_RE.test(file.name || "");
  }

  function subfolderOf(file) {
    const folder = String(file.folder || "");
    return folder.slice(LOGO_ROOT.length).replace(/^\/+/, "");
  }

  function metaText(file) {
    const parts = [extensionOf(file), formatBytes(file.size)];
    const w = file.w || 0;
    const h = file.h || 0;
    if (w && h) parts.push(`${w} × ${h}`);
    const sub = subfolderOf(file);
    if (sub) parts.push(sub);
    return parts.join(" · ");
  }

  function showState(kind, title, detail) {
    el.state.hidden = false;
    el.state.className = `col-state col-state-${kind}`;
    el.state.textContent = "";

    const heading = node("p", "col-state-title");
    heading.textContent = title;
    el.state.appendChild(heading);

    if (detail) {
      const text = node("p", "col-state-detail");
      text.textContent = detail;
      el.state.appendChild(text);
    }
  }

  function toast(message, kind) {
    if (!el.toast) return;
    window.clearTimeout(toastTimer);
    el.toast.textContent = message;
    el.toast.className = `toast toast-${kind}`;
    el.toast.hidden = false;
    toastTimer = window.setTimeout(() => {
      el.toast.hidden = true;
    }, 3200);
  }

  /* ------------------------------------------------------------------ */
  /* Grid                                                                */
  /* ------------------------------------------------------------------ */

  function buildStage(file, mode) {
    const stage = node("span", `lg-stage lg-stage-${mode}`);
    const img = node("img", null, { alt: "", loading: "lazy", decoding: "async", draggable: "false" });
    img.src = file.url;
    stage.appendChild(img);
    return stage;
  }

  function buildCard(file, index) {
    const name = pretty(file.name);
    const card = node("article", "lg-card");
    card.title = file.path;

    const open = node("button", "lg-open", {
      type: "button",
      "aria-label": `View ${name} at full size`,
    });
    open.append(buildStage(file, "dark"), buildStage(file, "light"));
    open.addEventListener("click", () => openViewer(index));

    const firstImg = open.querySelector("img");
    firstImg.addEventListener("error", () => card.classList.add("is-broken"));

    const info = node("div", "lg-info");
    const label = node("span", "lg-name");
    label.textContent = name;
    const meta = node("span", "lg-meta");
    meta.textContent = metaText(file);
    info.append(label, meta);

    // Fill in the real dimensions once the browser has decoded the image (SVGs
    // and files without a generated thumbnail have no size in the manifest).
    if (!file.w || !file.h) {
      firstImg.addEventListener(
        "load",
        () => {
          if (!firstImg.naturalWidth || !firstImg.naturalHeight) return;
          file.w = firstImg.naturalWidth;
          file.h = firstImg.naturalHeight;
          meta.textContent = metaText(file);
        },
        { once: true },
      );
    }

    const actions = node("div", "lg-actions");
    const download = node("button", "lg-download", {
      type: "button",
      "aria-label": `Download ${name}`,
    });
    const dlLabel = node("span", "lg-dl-label");
    dlLabel.textContent = "Download";
    download.append(node("span", "ic ic-download icon icon-sm"), dlLabel);
    download.addEventListener("click", () => downloadFile(file, download, dlLabel));
    actions.appendChild(download);

    card.append(open, info, actions);
    return card;
  }

  function render() {
    el.grid.textContent = "";

    if (!allLogos.length) {
      el.stats.textContent = "";
      showState("empty", "No logos yet.", 'Add image files to the "LOGO" folder in the bucket.');
      return;
    }

    shown = query
      ? allLogos.filter((file) => {
          const haystack = `${file.name} ${file.path} ${pretty(file.name)}`.toLowerCase();
          return haystack.includes(query);
        })
      : allLogos.slice();

    el.stats.textContent = query
      ? `${shown.length} of ${allLogos.length} logos`
      : `${allLogos.length} ${allLogos.length === 1 ? "logo" : "logos"}`;

    if (!shown.length) {
      showState("empty", `No logos match “${query}”.`, "Try a shorter search.");
      return;
    }

    el.state.hidden = true;
    const frag = document.createDocumentFragment();
    shown.forEach((file, index) => frag.appendChild(buildCard(file, index)));
    el.grid.appendChild(frag);
  }

  /* ------------------------------------------------------------------ */
  /* Viewer                                                              */
  /* ------------------------------------------------------------------ */

  function openViewer(index) {
    if (!shown[index]) return;
    openAt = index;
    lastFocus = document.activeElement;
    el.lightbox.hidden = false;
    document.body.classList.add("lg-lock");
    paintViewer();
    el.close.focus();
  }

  function paintViewer() {
    const file = shown[openAt];
    if (!file) return;

    const token = ++dimToken;
    el.canvas.classList.remove("is-broken");
    el.img.alt = `${pretty(file.name)} logo`;

    el.img.onload = () => {
      if (token !== dimToken || !el.img.naturalWidth || !el.img.naturalHeight) return;
      file.w = el.img.naturalWidth;
      file.h = el.img.naturalHeight;
      el.dim.textContent = `${file.w} × ${file.h}`;
      el.meta.textContent = metaText(file);
    };
    el.img.onerror = () => {
      if (token === dimToken) el.canvas.classList.add("is-broken");
    };
    el.img.src = file.url;

    el.name.textContent = pretty(file.name);
    el.meta.textContent = metaText(file);
    el.counter.textContent = `${openAt + 1} / ${shown.length}`;
    el.dim.textContent = file.w && file.h ? `${file.w} × ${file.h}` : "…";
    el.prev.disabled = shown.length < 2;
    el.next.disabled = shown.length < 2;
  }

  function step(delta) {
    if (shown.length < 2) return;
    openAt = (openAt + delta + shown.length) % shown.length;
    paintViewer();
  }

  function closeViewer() {
    if (el.lightbox.hidden) return;
    el.lightbox.hidden = true;
    document.body.classList.remove("lg-lock");
    el.img.onload = null;
    el.img.onerror = null;
    el.img.removeAttribute("src");
    el.img.alt = "";
    el.canvas.classList.remove("is-broken");
    dimToken += 1;
    openAt = -1;
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  }

  function setBackground(bg) {
    el.canvas.dataset.bg = bg;
    for (const button of el.bgButtons) {
      button.setAttribute("aria-pressed", String(button.dataset.bg === bg));
    }
  }

  el.close.addEventListener("click", closeViewer);
  el.prev.addEventListener("click", () => step(-1));
  el.next.addEventListener("click", () => step(1));
  el.lightbox.querySelector("[data-close]").addEventListener("click", closeViewer);

  for (const button of el.bgButtons) {
    button.addEventListener("click", () => setBackground(button.dataset.bg));
  }

  el.download.addEventListener("click", () => {
    const file = shown[openAt];
    if (file) downloadFile(file, el.download, el.download.querySelector(".lg-dl-label"));
  });

  document.addEventListener("keydown", (event) => {
    if (el.lightbox.hidden) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeViewer();
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      step(-1);
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      step(1);
      return;
    }
    if (event.key === "Tab" && el.panel) {
      const focusable = el.panel.querySelectorAll(
        'button:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  /* ------------------------------------------------------------------ */
  /* Download                                                            */
  /* ------------------------------------------------------------------ */

  async function downloadFile(file, button, labelNode) {
    if (button.dataset.busy) return;
    const label = labelNode ? labelNode.textContent : "";
    button.dataset.busy = "1";
    button.disabled = true;
    if (labelNode) labelNode.textContent = "Downloading…";

    try {
      const res = await fetch(file.url, { headers: { Accept: "image/*" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = file.name || "logo";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(href), 4000);
      toast(`Saved ${file.name}`, "ok");
    } catch (err) {
      toast(`Couldn’t download ${file.name}: ${err.message}`, "warn");
    } finally {
      delete button.dataset.busy;
      button.disabled = false;
      if (labelNode) labelNode.textContent = label;
    }
  }

  /* ------------------------------------------------------------------ */
  /* Boot                                                                */
  /* ------------------------------------------------------------------ */

  async function load() {
    showState("loading", "Loading logos…");
    try {
      const res = await fetch(LIST_ENDPOINT, { headers: { Accept: "application/json" } });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) {
        throw new Error((data && data.message) || `The logo list failed to load (HTTP ${res.status}).`);
      }

      allLogos = (Array.isArray(data.files) ? data.files : [])
        .filter(inLogoFolder)
        .filter(isRenderable)
        .filter((file) => !!file.url)
        .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }));

      render();
    } catch (err) {
      el.stats.textContent = "";
      showState("error", "Couldn’t load the logos.", err.message);
    }
  }

  if (el.search) {
    el.search.addEventListener("input", () => {
      query = el.search.value.trim().toLowerCase();
      render();
    });
  }

  load();
})();
