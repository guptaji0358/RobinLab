/**
 * Logos page — brand marks stored in the bucket's "LOGO/" folder.
 *
 * The manifest (`GET /api/collection/files`) is the same one the Collection
 * page uses; this page keeps only images whose folder is `LOGO` (or a
 * subfolder below it). The bucket folders drive the layout: each folder directly
 * under `LOGO/` is a category section, deeper folders are subcategories inside
 * it, and files sitting in `LOGO/` itself are listed last under "General".
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
  const LOOSE_LABEL = "General"; // files directly inside LOGO/
  // Folder names whose Title Case form would be wrong. Display only.
  const FOLDER_LABELS = { ai: "AI", pytorch: "PyTorch" };

  const el = {
    grid: document.getElementById("lg-grid"),
    cats: document.getElementById("lg-cats"),
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
    art: document.getElementById("lg-art"),
    name: document.getElementById("lg-v-name"),
    meta: document.getElementById("lg-v-meta"),
    counter: document.getElementById("lg-v-counter"),
    download: document.getElementById("lg-v-download"),
    copy: document.getElementById("lg-v-copy"),
  };

  if (!el.grid || !el.lightbox) return;

  if (el.year) el.year.textContent = new Date().getFullYear();

  // Preview background switch: transparent (checkerboard) or white.
  (function initBgSwitch() {
    const box = document.getElementById("lg-bgsw");
    if (!box) return;
    const apply = (bg) => {
      el.grid.dataset.bg = bg;
      box.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.bg === bg)));
    };
    let saved = "transparent";
    try { saved = localStorage.getItem("lg-bg") === "white" ? "white" : "transparent"; } catch (e) {}
    apply(saved);
    box.addEventListener("click", (ev) => {
      const b = ev.target.closest("button[data-bg]");
      if (!b) return;
      apply(b.dataset.bg);
      try { localStorage.setItem("lg-bg", b.dataset.bg); } catch (e) {}
    });
  })();

  let allLogos = [];
  let shown = [];
  let query = "";
  let category = null; // selected top-level folder; null = all, "" = loose files
  let openAt = -1;
  let lastFocus = null;
  let toastTimer = 0;
  let artImg = null;
  let artToken = 0;

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
    const folder = String(file.folder || "").replace(/\\/g, "/");
    return folder.slice(LOGO_ROOT.length).replace(/^\/+|\/+$/g, "");
  }

  function folderLabel(segment) {
    return FOLDER_LABELS[segment.toLowerCase()] || pretty(segment);
  }

  function categoryOf(file) {
    return subfolderOf(file).split("/")[0];
  }

  function categoryLabel(key) {
    return key ? folderLabel(key) : LOOSE_LABEL;
  }

  // "" when the file sits directly in its category folder.
  function subcategoryLabel(file) {
    return subfolderOf(file).split("/").slice(1).map(folderLabel).join(" / ");
  }

  function folderTrail(file) {
    const top = categoryLabel(categoryOf(file));
    const sub = subcategoryLabel(file);
    return sub ? `${top} / ${sub}` : top;
  }

  function compareText(a, b) {
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
  }

  // Category (loose files last), then subcategory (direct files first), then
  // name. The viewer steps through this same order.
  function compareLogos(a, b) {
    const ca = categoryOf(a);
    const cb = categoryOf(b);
    if (!ca !== !cb) return ca ? -1 : 1;
    return (
      compareText(categoryLabel(ca), categoryLabel(cb)) ||
      ca.localeCompare(cb) ||
      compareText(subcategoryLabel(a), subcategoryLabel(b)) ||
      compareText(a.name, b.name)
    );
  }

  function metaText(file, withFolder) {
    const parts = [extensionOf(file), formatBytes(file.size)];
    const w = file.w || 0;
    const h = file.h || 0;
    if (w && h) parts.push(`${w} × ${h}`);
    if (withFolder) parts.push(folderTrail(file));
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

  function buildStage(file) {
    const stage = node("span", "lg-stage");
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
    open.append(buildStage(file));
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
      title: "Download",
    });
    const dlLabel = node("span", "lg-dl-label");
    dlLabel.textContent = "Download";
    download.append(node("span", "ic ic-download icon icon-sm"), dlLabel);
    download.addEventListener("click", () => downloadFile(file, download, dlLabel));
    const editBtn = node("button", "lg-download lg-edit", {
      type: "button",
      "aria-label": `Edit ${name} in Canva`,
      title: "Edit in Canva",
    });
    const editLabel = node("span", "lg-edit-label");
    editLabel.textContent = "Edit in Canva";
    editBtn.append(node("img", "lg-canva-ic", { src: "assets/canva-icon.png", alt: "", width: "20", height: "20" }), editLabel);
    editBtn.addEventListener("click", () => editInCanva(file, editBtn));
    const copyBtn = node("button", "lg-download lg-copy", {
      type: "button",
      "aria-label": `Copy ${name}`,
      title: "Copy image",
    });
    const copyLabel = node("span", "lg-dl-label");
    copyLabel.textContent = "Copy";
    copyBtn.append(node("span", "ic ic-copy icon icon-sm"), copyLabel);
    copyBtn.addEventListener("click", () => copyImage(file, copyBtn, copyLabel));
    actions.append(editBtn, copyBtn, download);

    card.append(open, info, actions);
    return card;
  }

  function plural(count) {
    return `${count} ${count === 1 ? "logo" : "logos"}`;
  }

  // Category buttons, one per folder. Counts follow the search box.
  function renderChips(matches) {
    if (!el.cats) return;
    const keys = [...new Set(allLogos.map(categoryOf))]; // allLogos is already ordered
    el.cats.textContent = "";
    el.cats.hidden = keys.length < 2;

    [null, ...keys].forEach((key) => {
      const count = key === null ? matches.length : matches.filter((f) => categoryOf(f) === key).length;
      const chip = node("button", "col-chip", { type: "button", "aria-pressed": String(key === category) });
      chip.textContent = key === null ? "All" : categoryLabel(key);
      const badge = node("span", "col-chip-count");
      badge.textContent = count;
      chip.appendChild(badge);
      chip.addEventListener("click", () => {
        category = key;
        render();
        const pressed = el.cats.querySelector('[aria-pressed="true"]');
        if (pressed) pressed.focus({ preventScroll: true });
      });
      el.cats.appendChild(chip);
    });
  }

  // `shown` is sorted by category then subcategory, so a new heading starts
  // exactly where either value changes.
  function buildSections() {
    const frag = document.createDocumentFragment();
    let section = null;
    let grid = null;
    let currentCat = null;
    let currentSub = null;

    shown.forEach((file, index) => {
      const cat = categoryOf(file);
      const sub = subcategoryLabel(file);

      if (cat !== currentCat) {
        currentCat = cat;
        currentSub = null;
        const id = `lg-cat-${frag.childElementCount}`;
        section = node("section", "lg-pack", { "aria-labelledby": id });
        const head = node("div", "col-pack-head");
        const title = node("h3", "col-pack-title", { id });
        title.textContent = categoryLabel(cat);
        const meta = node("span", "col-pack-meta");
        meta.textContent = plural(shown.filter((f) => categoryOf(f) === cat).length);
        head.append(title, meta);
        section.appendChild(head);
        frag.appendChild(section);
      }

      if (sub !== currentSub) {
        currentSub = sub;
        if (sub) {
          const subTitle = node("h4", "lg-sub-title");
          subTitle.textContent = sub;
          section.appendChild(subTitle);
        }
        grid = node("div", "lg-grid");
        section.appendChild(grid);
      }

      grid.appendChild(buildCard(file, index));
    });

    return frag;
  }

  function render() {
    el.grid.textContent = "";

    if (!allLogos.length) {
      el.stats.textContent = "";
      if (el.cats) el.cats.hidden = true;
      showState("empty", "No logos yet.", 'Add image files to the "LOGO" folder in the bucket.');
      return;
    }

    const matches = query
      ? allLogos.filter((file) => {
          const haystack = `${file.name} ${file.path} ${pretty(file.name)} ${folderTrail(file)}`.toLowerCase();
          return haystack.includes(query);
        })
      : allLogos;
    shown = category === null ? matches.slice() : matches.filter((file) => categoryOf(file) === category);

    renderChips(matches);

    el.stats.textContent =
      shown.length === allLogos.length ? plural(allLogos.length) : `${shown.length} of ${plural(allLogos.length)}`;

    if (!shown.length) {
      const where = category === null ? "" : ` in ${categoryLabel(category)}`;
      showState(
        "empty",
        `No logos match “${query}”${where}.`,
        category !== null && matches.length ? "Choose All to see matches in other categories." : "Try a shorter search.",
      );
      return;
    }

    el.state.hidden = true;
    el.grid.appendChild(buildSections());
  }

  /* ------------------------------------------------------------------ */
  /* Viewer                                                              */
  /* ------------------------------------------------------------------ */

  function draw() {
    const img = artImg;
    if (!img || !img.naturalWidth) return;
    const cv = el.art;
    cv.width = img.naturalWidth;
    cv.height = img.naturalHeight;
    const ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.drawImage(img, 0, 0);
  }


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

    const token = ++artToken;
    el.lightbox.classList.remove("is-broken");
    const img = new Image();
    img.onload = () => {
      if (token !== artToken) return;
      artImg = img;
      file.w = img.naturalWidth;
      file.h = img.naturalHeight;
      el.meta.textContent = metaText(file, true);
      draw();
    };
    img.onerror = () => {
      if (token === artToken) el.lightbox.classList.add("is-broken");
    };
    img.src = file.url;

    el.name.textContent = pretty(file.name);
    el.meta.textContent = metaText(file, true);
    el.counter.textContent = `${openAt + 1} / ${shown.length}`;
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
    artToken += 1;
    artImg = null;
    openAt = -1;
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  }

  el.close.addEventListener("click", closeViewer);
  el.prev.addEventListener("click", () => step(-1));
  el.next.addEventListener("click", () => step(1));
  el.lightbox.querySelector("[data-close]").addEventListener("click", closeViewer);

  el.download.addEventListener("click", () => {
    const file = shown[openAt];
    if (file) downloadFile(file, el.download, el.download.querySelector(".lg-dl-label"));
  });

  if (el.copy) {
    el.copy.addEventListener("click", () => {
      const file = shown[openAt];
      if (file) copyImage(file, el.copy, el.copy.querySelector(".lg-dl-label"));
    });
  }

  const viewerEdit = el.lightbox.querySelector(".lg-link");
  if (viewerEdit) {
    viewerEdit.addEventListener("click", (event) => {
      event.preventDefault(); // href stays as the no-JS fallback
      const file = shown[openAt];
      if (file) editInCanva(file, viewerEdit);
    });
  }

  document.addEventListener("keydown", (event) => {
    if (el.lightbox.hidden) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeViewer();
      return;
    }
    const inField = /^(INPUT|SELECT|TEXTAREA)$/.test(event.target.tagName);
    if (event.key === "ArrowLeft" && !inField) {
      event.preventDefault();
      step(-1);
      return;
    }
    if (event.key === "ArrowRight" && !inField) {
      event.preventDefault();
      step(1);
      return;
    }
    if (event.key === "Tab" && el.panel) {
      const focusable = el.panel.querySelectorAll(
        'button:not(:disabled), input, a[href], [tabindex]:not([tabindex="-1"])',
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
  /* Copy image to clipboard                                             */
  /* ------------------------------------------------------------------ */

  // Clipboards reliably accept PNG only, so the original is re-drawn to a
  // canvas at its natural size (transparency kept). Download stays untouched.
  async function copyImage(file, button, labelNode) {
    if (button.dataset.busy) return;
    const target = labelNode || button;
    const label = target.textContent;
    button.dataset.busy = "1";
    button.disabled = true;
    target.textContent = "Copying…";

    try {
      if (!navigator.clipboard || !window.ClipboardItem) {
        throw new Error("clipboard not supported in this browser");
      }
      const pngPromise = (async () => {
        const res = await fetch(file.url, { headers: { Accept: "image/*" } });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (blob.type === "image/png") return blob;
        const bmp = await createImageBitmap(blob);
        const canvas = document.createElement("canvas");
        canvas.width = bmp.width;
        canvas.height = bmp.height;
        canvas.getContext("2d").drawImage(bmp, 0, 0);
        return await new Promise((resolve, reject) =>
          canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), "image/png"),
        );
      })();
      // Passing the promise keeps the user-gesture valid (needed by Safari).
      await navigator.clipboard.write([new ClipboardItem({ "image/png": pngPromise })]);
      toast(`Copied ${file.name}`, "ok");
    } catch (err) {
      toast(`Couldn’t copy ${file.name}: ${err.message}`, "warn");
    } finally {
      delete button.dataset.busy;
      button.disabled = false;
      target.textContent = label;
    }
  }

  /* ------------------------------------------------------------------ */
  /* Edit in Canva                                                    */
  /* ------------------------------------------------------------------ */

  const CANVA_PENDING = "rl-canva-pending";

  // Opens a blank tab inside the click (the only time browsers allow it), builds
  // the design in the visitor's Canva, then points that tab at it. First use sends
  // this tab through Canva sign-in; we then ask the visitor to click again, since
  // a tab can't be opened without a fresh click.
  async function editInCanva(file, button) {
    if (button.dataset.busy) return;
    const target = button.querySelector(".lg-edit-label") || button; // keep the icon
    const label = target.textContent;
    button.dataset.busy = "1";
    button.disabled = true;
    target.textContent = "Opening Canva…";
    try {
      await window.RLCanva.startEdit(file, {
        open: () => window.open("about:blank", "_blank"),
        fetch: (url, init) => window.fetch(url, init),
        assign: (url) => window.location.assign(url),
        setPending: (path) => {
          try { sessionStorage.setItem(CANVA_PENDING, path); } catch (e) { /* private mode */ }
        },
        notify: toast,
        title: pretty,
      });
    } finally {
      button.disabled = false;
      target.textContent = label;
      delete button.dataset.busy;
    }
  }

  // Back from Canva sign-in: tell the visitor to click the same logo again.
  function resumeCanva() {
    const flag = new URLSearchParams(window.location.search).get("canva");
    if (!flag) return;
    window.history.replaceState(null, "", window.location.pathname);
    let path = null;
    try { path = sessionStorage.getItem(CANVA_PENDING); sessionStorage.removeItem(CANVA_PENDING); } catch (e) { /* ignore */ }
    if (flag !== "connected") {
      toast("Canva sign-in didn’t complete. Try Edit in Canva again.", "warn");
      return;
    }
    const file = allLogos.find((f) => f.path === path);
    toast(file ? `Canva connected. Click Edit in Canva on ${pretty(file.name)} to continue.` : "Canva connected. Click Edit in Canva to continue.", "ok");
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
        .sort(compareLogos);

      render();
      resumeCanva();
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
