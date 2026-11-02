/**
 * Skills page — Claude skills stored in the bucket's "Claude Skills/" folder.
 *
 * `/api/collection/skills` returns each skill's title, description and section
 * outline. The full text is fetched from `/api/collection/skill?id=…` only when
 * a visitor presses Copy or drags a card out.
 */
(() => {
  "use strict";

  const ENDPOINT = "/api/collection/skills";
  const SKILL_ENDPOINT = "/api/collection/skill";

  const el = {
    grid: document.getElementById("sk-grid"),
    stats: document.getElementById("sk-stats"),
    state: document.getElementById("sk-state"),
    year: document.getElementById("year"),
  };

  if (el.year) el.year.textContent = new Date().getFullYear();

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

  function updatedLabel(skill) {
    if (!skill.uploadedAt) return "";
    const date = new Date(skill.uploadedAt);
    if (Number.isNaN(date.getTime())) return "";
    return `Updated ${date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}`;
  }

  function buildCard(skill) {
    const card = document.createElement("article");
    card.className = "sk-card";

    const name = document.createElement("span");
    name.className = "sk-name";
    name.textContent = skill.skillName;

    const title = document.createElement("h3");
    title.className = "sk-title";
    title.textContent = skill.title;

    const desc = document.createElement("p");
    desc.className = "sk-desc";
    desc.textContent = skill.description;

    card.append(name, title, desc);

    if (skill.sections.length) {
      const label = document.createElement("span");
      label.className = "sk-label";
      label.textContent = "What it covers";
      const list = document.createElement("ul");
      list.className = "sk-chips";
      for (const section of skill.sections) {
        const chip = document.createElement("li");
        chip.textContent = section;
        list.appendChild(chip);
      }
      card.append(label, list);
    }

    const meta = document.createElement("span");
    meta.className = "sk-meta";
    meta.textContent = updatedLabel(skill);

    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "sk-copy";
    copy.textContent = "Copy skill";
    copy.addEventListener("click", () => copySkill(skill, copy));

    const hint = document.createElement("span");
    hint.className = "sk-drag-hint";
    hint.textContent = "or drag this card into Claude";

    const actions = document.createElement("div");
    actions.className = "sk-actions";
    actions.append(copy, hint);
    card.append(meta, actions);

    // Drag out as a .md file. Only the file payload is set (no text/plain or
    // URL), so text boxes and other pages get nothing; a browser cannot stop a
    // file drop elsewhere, but Claude's upload areas accept it.
    card.draggable = true;
    card.addEventListener("dragstart", (event) => {
      const url = new URL(`${SKILL_ENDPOINT}?id=${encodeURIComponent(skill.id)}&download=1`, location.href).href;
      event.dataTransfer.effectAllowed = "copy";
      event.dataTransfer.setData("DownloadURL", `text/markdown:${skill.id}.md:${url}`);
    });
    return card;
  }

  async function copySkill(skill, button) {
    const label = button.textContent;
    button.disabled = true;
    try {
      const res = await fetch(`${SKILL_ENDPOINT}?id=${encodeURIComponent(skill.id)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await navigator.clipboard.writeText(await res.text());
      button.textContent = "Copied";
      button.classList.add("is-done");
    } catch {
      button.textContent = "Copy failed";
    }
    setTimeout(() => {
      button.textContent = label;
      button.classList.remove("is-done");
      button.disabled = false;
    }, 1800);
  }

  async function load() {
    showState("loading", "Loading skills…");
    try {
      const res = await fetch(ENDPOINT, { headers: { Accept: "application/json" } });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) {
        throw new Error((data && data.message) || `The skills list failed to load (HTTP ${res.status}).`);
      }

      const skills = data.skills || [];
      el.grid.textContent = "";
      if (!skills.length) {
        el.stats.textContent = "";
        showState("empty", "No skills yet.", 'Add .md skill files to the "Claude Skills" folder in the bucket.');
        return;
      }

      el.state.hidden = true;
      const frag = document.createDocumentFragment();
      for (const skill of skills) frag.appendChild(buildCard(skill));
      el.grid.appendChild(frag);
      el.stats.textContent = `${skills.length} ${skills.length === 1 ? "skill" : "skills"}`;
    } catch (err) {
      showState("error", "Couldn’t load the skills.", err.message);
    }
  }

  load();
})();
