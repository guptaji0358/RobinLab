/* RobinLab "kinetic layer" — additive motion system.
   Loads AFTER fx.js and never touches its elements/state. Three things fx.js
   does not do:
     1. Velocity ink  — a pointer/touch trail whose size and glow follow speed.
     2. Spring field  — chips and tags are real damped springs: they shy away
        from a fast pointer.
     3. Device tilt   — on phones the code-rain backdrop drifts with the device.
        Touch devices get ONLY this one: the full-screen canvas and per-frame work
        behind 1, 2 and 4-6 made scrolling stutter on phones.
     4. Gravity well  — hold the mouse/finger: chips and particles spiral in.
     5. Constellation — a drifting node web that links to the pointer.
     6. Liquid text   — section headings ripple under the pointer (SVG filter).
   One shared rAF loop that goes to sleep when nothing moves. No dependencies.
   Window API: RLMotion.disable() / RLMotion.enable(). Off under reduced motion. */
(function () {
  'use strict';
  if (window.RLMotion) return;

  var d = document, root = d.documentElement;
  var rmq = matchMedia('(prefers-reduced-motion: reduce)');
  if (rmq.matches) return;                      // respect the preference outright

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function safe(fn) { try { fn(); } catch (e) { if (window.console) console.warn('[motion]', e); } }

  var coarse = matchMedia('(pointer: coarse)').matches;
  var enabled = true, running = false, raf = 0;
  var off = [];                                  // teardown callbacks
  function on(t, ev, fn, opt) { t.addEventListener(ev, fn, opt); off.push(function () { t.removeEventListener(ev, fn, opt); }); }

  /* ------------------------------------------------------------ pointer state */
  var P = { x: -999, y: -999, px: -999, py: -999, vx: 0, vy: 0, speed: 0, down: false, t: 0, seen: false };
  var cv, ctx, W = 0, H = 0, dpr = 1, parts = [];
  var MAX_PARTS = coarse ? 100 : 220;

  /* ---------------------------------------------------------------- springs */
  var els = [];                                  // {el, cx, cy, x, y, vx, vy}
  var visible = new Set(), rectsDirty = true;
  var SEL = '.pf-chips li, .pf-skills span, .project-tag';

  function collect() {
    Array.prototype.slice.call(d.querySelectorAll(SEL)).forEach(function (el) {
      if (el.__rlm) return;
      el.__rlm = { el: el, cx: 0, cy: 0, x: 0, y: 0, vx: 0, vy: 0 };
      els.push(el.__rlm);
      if (io) io.observe(el);
    });
    rectsDirty = true;
  }
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { var s = e.target.__rlm; if (!s) return; if (e.isIntersecting) visible.add(s); else { visible.delete(s); rest(s); } });
    rectsDirty = true;
  }) : null;
  function rest(s) { s.x = s.y = s.vx = s.vy = 0; s.el.style.translate = ''; }

  function measure() {
    visible.forEach(function (s) {
      // measure without our own offset so the home position stays stable
      var r = s.el.getBoundingClientRect();
      s.cx = r.left + r.width / 2 - s.x; s.cy = r.top + r.height / 2 - s.y;
    });
    rectsDirty = false;
  }

  function stepSprings(dt) {
    var active = false, R = coarse ? 110 : 150, R2 = R * R;
    var push = clamp(P.speed / 14, 0, 1.6);       // faster pointer -> stronger shove
    visible.forEach(function (s) {
      var ax = 0, ay = 0;
      if (P.seen && (P.speed > 1.2 || P.down)) {
        var dx = s.cx + s.x - P.x, dy = s.cy + s.y - P.y, q = dx * dx + dy * dy;
        if (q < R2 && q > 1) {
          var dist = Math.sqrt(q), f = (1 - dist / R) * push * 3400;
          ax += dx / dist * f; ay += dy / dist * f;
        }
      }
      if (P.down && P.seen) {                        // gravity well: hold to pull chips in
        var gx = P.x - (s.cx + s.x), gy = P.y - (s.cy + s.y), gq = gx * gx + gy * gy;
        if (gq < 300 * 300 && gq > 400) { var gd = Math.sqrt(gq); ax += gx / gd * (1 - gd / 300) * 2600; ay += gy / gd * (1 - gd / 300) * 2600; }
      }
      // damped spring back to rest: a = -k x - c v
      ax += -s.x * 170; ay += -s.y * 170;
      s.vx += ax * dt; s.vy += ay * dt;
      var damp = Math.pow(0.84, dt * 60);
      s.vx *= damp; s.vy *= damp;
      s.x = clamp(s.x + s.vx * dt, -34, 34); s.y = clamp(s.y + s.vy * dt, -34, 34);
      if (Math.abs(s.x) < .04 && Math.abs(s.y) < .04 && Math.abs(s.vx) < .04 && Math.abs(s.vy) < .04) {
        if (s.x || s.y) rest(s);
      } else { s.el.style.translate = s.x.toFixed(2) + 'px ' + s.y.toFixed(2) + 'px'; active = true; }
    });
    return active;
  }

  /* -------------------------------------------------------------- ink trail */
  function size() {
    dpr = 1; W = innerWidth; H = innerHeight;         // soft glows: extra pixels cost far more than they show
    cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seedNodes();
  }
  function emit(x, y, vx, vy, n) {
    for (var i = 0; i < n && parts.length < MAX_PARTS; i++) {
      var a = Math.random() * 6.283, s = Math.random() * 0.7;
      parts.push({ x: x, y: y, vx: vx * .06 + Math.cos(a) * s, vy: vy * .06 + Math.sin(a) * s,
        life: 1, dec: .014 + Math.random() * .018, r: 1.6 + Math.random() * 3.2, h: 205 + Math.random() * 110 });
    }
  }
  function drawInk(dt) {
    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';
    var i, p;
    for (i = parts.length - 1; i >= 0; i--) {
      p = parts[i];
      p.life -= p.dec * dt * 60;
      if (p.life <= 0) { parts.splice(i, 1); continue; }
      if (P.down && P.seen) {                          // particles swirl into the well
        var qx = P.x - p.x, qy = P.y - p.y, qd = Math.sqrt(qx * qx + qy * qy) + 8, qk = dt * 12 / (1 + qd / 120);
        p.vx += (qx / qd * 40 - qy / qd * 70) * qk; p.vy += (qy / qd * 40 + qx / qd * 70) * qk;
      }
      p.vx *= .965; p.vy = p.vy * .965 + .012 * dt * 60; p.x += p.vx * dt * 60; p.y += p.vy * dt * 60;
      ctx.fillStyle = 'hsla(' + (p.h | 0) + ',95%,66%,' + (p.life * .8).toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (.4 + p.life), 0, 6.283); ctx.fill();
    }
    drawWeb(dt);
    drawWell(dt);
    ctx.globalCompositeOperation = 'source-over';
  }

  /* ------------------------------------------------- constellation web */
  var nodes = [], web = { a: 0 };
  function seedNodes() {
    var n = coarse ? 12 : 26; nodes.length = 0;
    for (var i = 0; i < n; i++) nodes.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * 14, vy: (Math.random() - .5) * 14 });
  }
  function drawWeb(dt) {
    web.a += ((P.seen && performance.now() - P.t < REST_MS ? 1 : 0) - web.a) * Math.min(1, dt * 3);
    if (web.a < .01) return;
    var i, j, a, b, dx, dy, dd, L = 140, C = 190, damp = Math.pow(.97, dt * 60);
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      dx = P.x - a.x; dy = P.y - a.y; dd = Math.sqrt(dx * dx + dy * dy) || 1;
      if (P.seen && dd < 320) { a.vx += dx / dd * 30 * dt; a.vy += dy / dd * 30 * dt; }   // drawn toward the pointer
      a.vx *= damp; a.vy *= damp;
      a.x += a.vx * dt; a.y += a.vy * dt;
      if (a.x < -20) a.x = W + 20; else if (a.x > W + 20) a.x = -20;
      if (a.y < -20) a.y = H + 20; else if (a.y > H + 20) a.y = -20;
    }
    ctx.lineWidth = 1;
    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      for (j = i + 1; j < nodes.length; j++) {
        b = nodes[j]; dx = a.x - b.x; dy = a.y - b.y; dd = Math.sqrt(dx * dx + dy * dy);
        if (dd < L) { ctx.strokeStyle = 'hsla(215,90%,68%,' + ((1 - dd / L) * .3 * web.a).toFixed(3) + ')'; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
      }
      dx = a.x - P.x; dy = a.y - P.y; dd = Math.sqrt(dx * dx + dy * dy);
      if (P.seen && dd < C) { ctx.strokeStyle = 'hsla(185,95%,70%,' + ((1 - dd / C) * .55 * web.a).toFixed(3) + ')'; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(P.x, P.y); ctx.stroke(); }
      ctx.fillStyle = 'hsla(200,95%,75%,' + (.5 * web.a).toFixed(3) + ')'; ctx.beginPath(); ctx.arc(a.x, a.y, 2, 0, 6.283); ctx.fill();
    }
  }

  /* ----------------------------------------------------- gravity well */
  var well = { a: 0, rot: 0 };
  function drawWell(dt) {
    well.a += ((P.down && P.seen ? 1 : 0) - well.a) * Math.min(1, dt * 8);
    if (well.a < .02) return;
    well.rot += dt * 4;
    var g = ctx.createRadialGradient(P.x, P.y, 2, P.x, P.y, 70);
    g.addColorStop(0, 'rgba(0,0,0,' + (.55 * well.a).toFixed(3) + ')');
    g.addColorStop(.55, 'hsla(265,90%,60%,' + (.18 * well.a).toFixed(3) + ')');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(P.x, P.y, 70, 0, 6.283); ctx.fill();
    ctx.lineWidth = 2.2; ctx.strokeStyle = 'hsla(190,95%,72%,' + (.7 * well.a).toFixed(3) + ')';
    ctx.beginPath(); ctx.arc(P.x, P.y, 26 + 4 * Math.sin(well.rot * 2), well.rot, well.rot + 4.2); ctx.stroke();
    if (Math.random() < .6 && parts.length < MAX_PARTS) {
      var a = Math.random() * 6.283, r = 70 + Math.random() * 60;
      parts.push({ x: P.x + Math.cos(a) * r, y: P.y + Math.sin(a) * r, vx: 0, vy: 0, life: 1, dec: .012, r: 1.8, h: 260 + Math.random() * 90 });
    }
  }

  /* --------------------------------------------------------- liquid text */
  var liq = { svg: null, map: null, turb: null, el: null, cur: 0, list: [] };
  function setupLiquid() {
    var ns = 'http://www.w3.org/2000/svg', svg = d.createElementNS(ns, 'svg');
    svg.setAttribute('width', '0'); svg.setAttribute('height', '0'); svg.setAttribute('aria-hidden', 'true');
    svg.style.cssText = 'position:absolute;pointer-events:none';
    svg.innerHTML = '<filter id="rlm-liquid" x="-6%" y="-40%" width="112%" height="180%"><feTurbulence type="fractalNoise" baseFrequency="0.012 0.08" numOctaves="1" seed="4" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G"/></filter>';
    d.body.appendChild(svg); liq.svg = svg; liq.list = [];
    liq.turb = svg.querySelector('feTurbulence'); liq.map = svg.querySelector('feDisplacementMap');
    off.push(function () { if (liq.el) liq.el.style.filter = ''; liq.el = null; svg.remove(); liq.svg = null; });
  }
  function stepLiquid(t, dt) {
    if (!liq.svg) return false;
    var hit = null, i, r;
    if (P.seen) {
      if (!liq.list.length) liq.list = Array.prototype.slice.call(d.querySelectorAll('.section-heading h1, .section-heading h2'));
      for (i = 0; i < liq.list.length; i++) {
        r = liq.list[i].getBoundingClientRect();
        if (P.x > r.left - 40 && P.x < r.right + 40 && P.y > r.top - 40 && P.y < r.bottom + 40) { hit = liq.list[i]; break; }
      }
    }
    if (hit && hit !== liq.el) { if (liq.el) liq.el.style.filter = ''; liq.el = hit; hit.style.filter = 'url(#rlm-liquid)'; }
    var target = hit ? clamp(7 + P.speed * 1.5, 0, 24) : 0;
    liq.cur += (target - liq.cur) * Math.min(1, dt * 7);
    if (liq.cur < .25 && !hit && liq.el) { liq.el.style.filter = ''; liq.el = null; liq.cur = 0; }
    if (liq.el) {
      liq.map.setAttribute('scale', liq.cur.toFixed(2));
      liq.turb.setAttribute('baseFrequency', '0.012 ' + (0.075 + 0.025 * Math.sin(t / 380)).toFixed(4));
    }
    return !!liq.el;
  }

  /* ------------------------------------------------------------ device tilt */
  var bg = null;
  function setupTilt() {
    if (!coarse || !('DeviceOrientationEvent' in window)) return;
    if ((navigator.deviceMemory || 8) <= 4) return;   // low-memory phones: no extra work at all
    // iOS needs a permission prompt from a gesture; we don't nag — touch effects remain.
    if (typeof DeviceOrientationEvent.requestPermission === 'function') return;
    // The sensor reports ~60 times a second: apply at most 8 times a second and let a
    // compositor transition smooth the steps. No animation frame loop is needed.
    var at = 0, lx = 0, ly = 0;
    on(window, 'deviceorientation', function (e) {
      if (e.gamma == null || e.beta == null || d.hidden) return;
      var now = performance.now(); if (now - at < 125) return;
      var x = clamp(e.gamma / 35, -1, 1) * 14, y = clamp((e.beta - 45) / 35, -1, 1) * 14;
      if (bg && Math.abs(x - lx) < .5 && Math.abs(y - ly) < .5) return;
      at = now; lx = x; ly = y;
      if (!bg) { bg = d.getElementById('fx-bg'); if (!bg) return; bg.style.scale = '1.05'; bg.style.transition = 'translate .2s linear'; }
      bg.style.translate = x.toFixed(1) + 'px ' + y.toFixed(1) + 'px';
    }, { passive: true });
  }

  /* -------------------------------------------------------------- main loop */
  var last = 0, idle = 0, REST_MS = 2000;             // a still pointer lets the loop sleep
  function wake() { if (cv && !running && enabled && !d.hidden) { running = true; idle = 0; cv.style.display = ''; last = performance.now(); raf = requestAnimationFrame(frame); } }
  function frame(t) {
    var dt = Math.min(.05, (t - last) / 1000); last = t;
    if (rectsDirty) measure();
    // decay velocity between pointer events
    if (t - P.t > 60) { P.vx *= .8; P.vy *= .8; P.speed *= .8; }
    if (P.speed > 2 && P.seen) emit(P.x, P.y, P.vx, P.vy, Math.min(6, 2 + (P.speed / 14) | 0));
    var a = stepSprings(dt);
    drawInk(dt);
    var c = stepLiquid(t, dt) && t - P.t < REST_MS;
    var busy = a || c || parts.length || P.speed > .5 || t - P.t < REST_MS || web.a > .02 || well.a > .02;
    idle = busy ? 0 : idle + 1;
    if (idle > 30 || d.hidden || !enabled) {
      running = false; ctx.clearRect(0, 0, W, H); cv.style.display = 'none';   // no blend layer while asleep
      visible.forEach(function (s) { if (s.x || s.y) rest(s); });   // never leave a chip off-grid
      return;
    }
    raf = requestAnimationFrame(frame);
  }

  /* ------------------------------------------------------------------ input */
  function onMove(e) {
    var t = performance.now(), dtm = Math.max(8, t - (P.t || t - 16));
    if (P.seen) {
      var vx = (e.clientX - P.x) / dtm * 16, vy = (e.clientY - P.y) / dtm * 16;
      P.vx += (vx - P.vx) * .35; P.vy += (vy - P.vy) * .35;
      P.speed = Math.sqrt(P.vx * P.vx + P.vy * P.vy);
    }
    P.x = e.clientX; P.y = e.clientY; P.t = t; P.seen = true;
    wake();
  }
  function onDown(e) {
    // click/tap effects (shockwave ring, particle burst, hold-to-pull well) are removed:
    // a press only updates the pointer position, P.down stays false.
    P.x = e.clientX; P.y = e.clientY; P.seen = true;
    wake();
  }
  function onUp() { P.down = false; }
  function onLeave() { P.seen = false; P.speed = 0; }
  function dirty() { rectsDirty = true; wake(); }

  /* ---------------------------------------------------------------- lifecycle */
  function init() {
    if (coarse) { setupTilt(); on(rmq, 'change', function () { if (rmq.matches) api.disable(); }); return; }
    cv = d.createElement('canvas'); cv.className = 'rlm-ink'; cv.setAttribute('aria-hidden', 'true');
    ctx = cv.getContext('2d'); if (!ctx) return;
    d.body.appendChild(cv); size(); cv.style.display = 'none';
    off.push(function () { cv.remove(); });
    collect(); setupLiquid();
    on(window, 'pointermove', onMove, { passive: true });
    on(window, 'pointerdown', onDown, { passive: true });
    on(window, 'pointerup', onUp, { passive: true });
    on(window, 'pointercancel', onUp, { passive: true });
    on(d.documentElement, 'pointerleave', onLeave);
    on(window, 'resize', function () { size(); dirty(); });
    on(window, 'scroll', function () { rectsDirty = true; }, { passive: true });
    on(d, 'visibilitychange', function () { if (!d.hidden) wake(); });
    // cards/chips that other scripts render later
    var mt = 0;
    var mo = new MutationObserver(function () { if (!mt) mt = setTimeout(function () { mt = 0; if (enabled) collect(); }, 250); });
    mo.observe(d.body, { childList: true, subtree: true });
    off.push(function () { mo.disconnect(); });
    on(rmq, 'change', function () { if (rmq.matches) api.disable(); });
  }

  var api = window.RLMotion = {
    enable: function () { if (enabled) return; enabled = true; if (!cv) safe(init); },
    disable: function () {
      enabled = false; cancelAnimationFrame(raf); running = false;
      els.forEach(function (s) { rest(s); delete s.el.__rlm; }); visible.clear();
      if (bg) { bg.style.translate = bg.style.scale = bg.style.transition = ''; bg = null; }
      off.splice(0).forEach(function (f) { f(); }); if (io) io.disconnect();
      els.length = 0; cv = null; parts.length = 0;
    },
    get active() { return enabled && (!!cv || coarse); }
  };

  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', function () { safe(init); });
  else safe(init);
})();
