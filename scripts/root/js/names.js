/* Display-only name formatting: "deep-research_notes.v2" -> "Deep Research Notes V2".
   Never touches the real file names or URLs. */
(function () {
  const SMALL = new Set(["a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "vs"]);

  function pretty(raw) {
    const words = String(raw || "")
      .replace(/\.[a-z0-9]{2,5}$/i, "")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
      .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
      .replace(/[-_.]+/g, " ")
      .replace(/\s+/g, " ")
      .trim()
      .split(" ");
    return words
      .map((w, i) => {
        const lower = w.toLowerCase();
        if (i > 0 && SMALL.has(lower)) return lower;
        if (w.length > 1 && w === w.toUpperCase() && /[A-Z]/.test(w)) return w; // keep acronyms (PDF, RGS)
        return lower.charAt(0).toUpperCase() + lower.slice(1);
      })
      .join(" ");
  }

  function ext(raw) {
    const m = /\.([a-z0-9]{2,5})$/i.exec(String(raw || ""));
    return m ? m[1].toUpperCase() : "";
  }

  window.RGSNames = { pretty, ext };
})();
