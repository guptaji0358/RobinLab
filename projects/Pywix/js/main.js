// ---------- Feature grid ----------
const FEATURES = [
  ["package", "One-File / One-Dir builds", "Convert any .py file into a single .exe or a folder distribution."],
  ["palette", "Custom branding", "Set a custom app icon, name, version, and description."],
  ["image", "Bundle extra assets", "Images, fonts, audio, and other files get packed alongside the output .exe."],
  ["monitor", "Console / windowed toggle", "Choose whether the built app shows a console window."],
  ["chart", "Live build progress", "Real-time output with cancel support mid-build."],
  ["search", "Command preview", "Inspect (and edit) the generated PyInstaller command before it runs."],
  ["link", "Start Menu shortcuts", "Optionally create a shortcut for the built app, with a customizable install path."],
  ["idcard", "Editable version metadata", "Company, Author, Copyright, and Trademark saved once and reused for every build."],
  ["keyboard", "Editable keyboard shortcuts", "Rebind shortcuts from Settings, including quick-jump between input fields."],
  ["theming", "Light / Dark / System / Developer", "Switch appearance with an animated crossfade — auto-follows Windows when set to System."],
  ["archive", "Build history", "Every successful build is logged to a local SQLite database."],
  ["wizard", "Custom installer", "A branded, step-by-step Windows installer with live progress and shortcut creation."],
];

const grid = document.getElementById("features-grid");
FEATURES.forEach(([icon, title, desc], i) => {
  const card = document.createElement("div");
  card.className = "feature-card reveal";
  card.style.transitionDelay = `${(i % 3) * 0.06}s`;
  card.innerHTML = `
    <div class="feature-icon"><img src="assets/${icon}.svg" alt=""></div>
    <h3>${title}</h3>
    <p>${desc}</p>
  `;
  grid.appendChild(card);
});

// ---------- Reveal on scroll ----------
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("in-view");
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.15 });

document.querySelectorAll(".reveal").forEach((el) => revealObserver.observe(el));

// ---------- Theme switcher demo ----------
const THEMES = {
  Light:     { bg: "#f4f6fb", border: "#dfe3ee", bar: "linear-gradient(90deg,#2b5c8a,#3f7bb0)", line: "#c9ceda", swatch: "#f4f6fb" },
  Dark:      { bg: "#171b28", border: "#262a3a", bar: "linear-gradient(90deg,#00aaff,#7c5cff)", line: "#3a3f52", swatch: "#171b28" },
  System:    { bg: "#1b2030", border: "#2a3040", bar: "linear-gradient(90deg,#00aaff,#7c5cff)", line: "#3a4055", swatch: "#1b2030" },
  Developer: { bg: "#141414", border: "#2e2e2e", bar: "linear-gradient(90deg,#00aaff,#00e0c6)", line: "#333333", swatch: "#0d0d0d" },
};

const switchEl = document.getElementById("theme-switch");
const previewEl = document.getElementById("theme-preview");

function applyTheme(name) {
  const t = THEMES[name];
  previewEl.style.background = t.bg;
  previewEl.style.borderColor = t.border;
  previewEl.querySelector(".mock-bar").style.background = t.bar;
  previewEl.querySelectorAll(".mock-line").forEach((l) => (l.style.background = t.line));
  previewEl.querySelector(".mock-btn.primary").style.background = t.bar;
  previewEl.querySelector(".mock-btn.secondary").style.background = "transparent";
  previewEl.querySelector(".mock-btn.secondary").style.border = `1px solid ${t.border}`;
  [...switchEl.children].forEach((btn) => btn.classList.toggle("active", btn.dataset.theme === name));
}

Object.keys(THEMES).forEach((name) => {
  const btn = document.createElement("button");
  btn.className = "theme-option";
  btn.dataset.theme = name;
  btn.innerHTML = `<span class="theme-swatch-dot" style="background:${THEMES[name].swatch};border:1px solid ${THEMES[name].border}"></span>${name}`;
  btn.addEventListener("click", () => applyTheme(name));
  switchEl.appendChild(btn);
});
applyTheme("Dark");

// ---------- Installer demo (auto-advancing) ----------
const STEPS = ["Welcome", "Location", "Options", "Install", "Finish"];
const STEP_CONTENT = {
  Welcome: `<div class="installer-badge">SETUP WIZARD</div><div class="installer-title">Welcome to Pywix</div><p style="color:var(--subtext)">This wizard installs everything you need — no PyInstaller command line required.</p>`,
  Location: `<div class="installer-badge">STEP 2 OF 4</div><div class="installer-title">Choose Install Location</div><p style="color:var(--subtext)">C:\\Program Files\\Pywix</p>`,
  Options: `<div class="installer-badge">STEP 3 OF 4</div><div class="installer-title">Additional Options</div><p style="color:var(--subtext)">☑ Create a Start Menu shortcut</p>`,
  Install: `<div class="installer-badge">STEP 4 OF 4</div><div class="installer-title">Installing</div>
    <div class="installer-percent" id="demo-percent">0%</div>
    <div class="installer-progress-wrap"><div class="installer-progress-bar"><div class="installer-progress-fill" id="demo-fill"></div></div></div>
    <div class="installer-status" id="demo-status">Copying files…</div>`,
  Finish: `<div class="installer-badge">ALL DONE</div><div class="installer-title">Pywix is ready</div><p style="color:var(--subtext)">☑ Launch Pywix</p>`,
};

const stepsEl = document.getElementById("installer-steps");
const contentEl = document.getElementById("installer-content");
let stepIndex = 0;
let installTimer = null;

function renderSteps() {
  stepsEl.innerHTML = STEPS.map((s, i) => {
    const cls = i < stepIndex ? "done" : i === stepIndex ? "active" : "";
    const mark = i < stepIndex ? "✓ " : i === stepIndex ? "▸ " : "";
    return `<div class="installer-step ${cls}">${mark}${s}</div>`;
  }).join("");
}

function renderInstallerContent() {
  contentEl.innerHTML = STEP_CONTENT[STEPS[stepIndex]];
  if (STEPS[stepIndex] === "Install") {
    clearInterval(installTimer);
    let pct = 0;
    const fill = document.getElementById("demo-fill");
    const pctLabel = document.getElementById("demo-percent");
    const status = document.getElementById("demo-status");
    installTimer = setInterval(() => {
      pct = Math.min(100, pct + 8);
      if (fill) fill.style.width = pct + "%";
      if (pctLabel) pctLabel.textContent = pct + "%";
      if (status && pct >= 100) status.textContent = "Installation complete.";
      if (pct >= 100) clearInterval(installTimer);
    }, 140);
  }
}

function advanceInstaller() {
  renderSteps();
  renderInstallerContent();
  stepIndex = (stepIndex + 1) % STEPS.length;
}

const installerSection = document.getElementById("installer");
let installerStarted = false;
const installerObserver = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting && !installerStarted) {
      installerStarted = true;
      advanceInstaller();
      setInterval(advanceInstaller, 2400);
    }
  });
}, { threshold: 0.3 });
installerObserver.observe(installerSection);

// ---------- Fireworks demo ----------
const canvas = document.getElementById("fireworks-canvas");
const ctx = canvas.getContext("2d");
const demoBox = document.getElementById("fireworks-demo");
const caption = document.getElementById("fireworks-caption");
const playBtn = document.getElementById("fireworks-play");

function resizeCanvas() {
  canvas.width = demoBox.clientWidth;
  canvas.height = demoBox.clientHeight;
}
resizeCanvas();
window.addEventListener("resize", resizeCanvas);

const COLORS = ["#ff5a5a", "#ffc83c", "#5ac8ff", "#8cff8c", "#e682ff", "#ffffff"];

class Particle {
  constructor(x, y, angle, speed, color) {
    this.x = x; this.y = y;
    this.vx = Math.cos(angle) * speed;
    this.vy = Math.sin(angle) * speed;
    this.color = color;
    this.life = 1;
  }
  step(dt) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
    this.vy += 70 * dt;
    this.life -= dt * 0.7;
  }
}

let fireworks = [];
let fireworksRunning = false;
let spawnInterval = null;
let tickInterval = null;
let lastTime = null;

function spawnFirework() {
  const x = canvas.width * (0.2 + Math.random() * 0.6);
  const y = canvas.height * (0.15 + Math.random() * 0.35);
  const color = COLORS[Math.floor(Math.random() * COLORS.length)];
  const count = 35 + Math.floor(Math.random() * 20);
  const particles = [];
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 60 + Math.random() * 140;
    particles.push(new Particle(x, y, angle, speed, color));
  }
  fireworks.push(particles);
}

function tick() {
  const now = Date.now();
  if (lastTime === null) lastTime = now;
  const dt = Math.min(0.05, (now - lastTime) / 1000);
  lastTime = now;

  ctx.fillStyle = "rgba(8,9,15,0.25)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  fireworks.forEach((particles) => {
    particles.forEach((p) => {
      p.step(dt);
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 2.5 + 2 * Math.max(0, p.life), 0, Math.PI * 2);
      ctx.fill();
    });
  });
  ctx.globalAlpha = 1;
  fireworks = fireworks.map((particles) => particles.filter((p) => p.life > 0)).filter((p) => p.length);
}

function playFireworks() {
  if (fireworksRunning) return;
  fireworksRunning = true;
  lastTime = null;
  fireworks = [];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  caption.style.transition = "opacity 0.3s ease";
  caption.style.opacity = "0.15";
  spawnFirework();
  spawnInterval = setInterval(spawnFirework, 380);
  tickInterval = setInterval(tick, 16);

  setTimeout(() => {
    clearInterval(spawnInterval);
  }, 5500);
  setTimeout(() => {
    fireworksRunning = false;
    clearInterval(tickInterval);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    caption.style.opacity = "1";
  }, 6500);
}

playBtn.addEventListener("click", playFireworks);
