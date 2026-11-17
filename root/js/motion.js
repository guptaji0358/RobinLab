/* RobinLab "kinetic layer" — additive motion system.
   Loads AFTER fx.js and never touches its elements/state. Three things fx.js
   does not do:
     1. Velocity ink  — a pointer/touch trail whose size and glow follow speed.
     2. Spring field  — chips and tags are real damped springs: they shy away
        from a fast pointer and a click / tap sends a shockwave through them.
     3. Device tilt   — on phones the code-rain backdrop drifts with the device.
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
  var shocks = [];                               // {x, y, r, life}
  var cv, ctx, W = 0, H = 0, dpr = 1, parts = [];
  var MAX_PARTS = coarse ? 70 : 140;

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
          var dist = Math.sqrt(q), f = (1 - dist / R) * push * 2600;
          ax += dx / dist * f; ay += dy / dist * f;
        }
      }
      for (var i = 0; i < shocks.length; i++) {
        var k = shocks[i], ex = s.cx - k.x, ey = s.cy - k.y, ed = Math.sqrt(ex * ex + ey * ey) || 1;
        var band = Math.abs(ed - k.r);              // only the wavefront pushes
        if (band < 70) { var g = (1 - band / 70) * k.life * 4200; ax += ex / ed * g; ay += ey / ed * g; }
      }
      // damped spring back to rest: a = -k x - c v
      ax += -s.x * 170; ay += -s.y * 170;
      s.vx += ax * dt; s.vy += ay * dt;
      var damp = Math.pow(0.84, dt * 60);
      s.vx *= damp; s.vy *= damp;
      s.x = clamp(s.x + s.vx * dt, -26, 26); s.y = clamp(s.y + s.vy * dt, -26, 26);
      if (Math.abs(s.x) < .04 && Math.abs(s.y) < .04 && Math.abs(s.vx) < .04 && Math.abs(s.vy) < .04) {
        if (s.x || s.y) rest(s);
      } else { s.el.style.translate = s.x.toFixed(2) + 'px ' + s.y.toFixed(2) + 'px'; active = true; }
    });
    return active;
  }

  /* -------------------------------------------------------------- ink trail */
  function size() {
    dpr = Math.min(devicePixelRatio || 1, 2); W = innerWidth; H = innerHeight;
    cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function emit(x, y, vx, vy, n) {
    for (var i = 0; i < n && parts.length < MAX_PARTS; i++) {
      var a = Math.random() * 6.283, s = Math.random() * 0.7;
      parts.push({ x: x, y: y, vx: vx * .06 + Math.cos(a) * s, vy: vy * .06 + Math.sin(a) * s,
        life: 1, dec: .016 + Math.random() * .02, r: 1 + Math.random() * 2.2, h: 205 + Math.random() * 110 });
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
      p.vx *= .965; p.vy = p.vy * .965 + .012 * dt * 60; p.x += p.vx * dt * 60; p.y += p.vy * dt * 60;
      ctx.fillStyle = 'hsla(' + (p.h | 0) + ',95%,66%,' + (p.life * .55).toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (.4 + p.life), 0, 6.283); ctx.fill();
    }
    ctx.lineWidth = 1.6;
    for (i = shocks.length - 1; i >= 0; i--) {
      var k = shocks[i];
      k.r += 520 * dt; k.life -= 1.5 * dt;
      if (k.life <= 0) { shocks.splice(i, 1); continue; }
      ctx.strokeStyle = 'hsla(190,95%,70%,' + (k.life * .5).toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(k.x, k.y, k.r, 0, 6.283); ctx.stroke();
    }
    ctx.globalCompositeOperation = 'source-over';
  }

  /* ------------------------------------------------------------ device tilt */
  var tilt = { tx: 0, ty: 0, x: 0, y: 0, on: false }, bg = null;
  function setupTilt() {
    if (!coarse || !('DeviceOrientationEvent' in window)) return;
    // iOS needs a permission prompt from a gesture; we don't nag — touch effects remain.
    if (typeof DeviceOrientationEvent.requestPermission === 'function') return;
    on(window, 'deviceorientation', function (e) {
      if (e.gamma == null || e.beta == null) return;
      tilt.tx = clamp(e.gamma / 35, -1, 1) * 14;
      tilt.ty = clamp((e.beta - 45) / 35, -1, 1) * 14;
      if (!tilt.on) { tilt.on = true; bg = d.getElementById('fx-bg'); }
      wake();
    }, { passive: true });
  }
  function stepTilt(dt) {
    if (!tilt.on || !bg) return false;
    tilt.x += (tilt.tx - tilt.x) * Math.min(1, dt * 6); tilt.y += (tilt.ty - tilt.y) * Math.min(1, dt * 6);
    bg.style.translate = tilt.x.toFixed(2) + 'px ' + tilt.y.toFixed(2) + 'px';
    bg.style.scale = '1.05';
    return Math.abs(tilt.tx - tilt.x) > .05 || Math.abs(tilt.ty - tilt.y) > .05;
  }

  /* -------------------------------------------------------------- main loop */
  var last = 0, idle = 0;
  function wake() { if (!running && enabled && !d.hidden) { running = true; idle = 0; last = performance.now(); raf = requestAnimationFrame(frame); } }
  function frame(t) {
    var dt = Math.min(.05, (t - last) / 1000); last = t;
    if (rectsDirty) measure();
    // decay velocity between pointer events
    if (t - P.t > 60) { P.vx *= .8; P.vy *= .8; P.speed *= .8; }
    if (P.speed > 2 && P.seen) emit(P.x, P.y, P.vx, P.vy, Math.min(4, 1 + (P.speed / 18) | 0));
    var a = stepSprings(dt);
    drawInk(dt);
    var b = stepTilt(dt);
    var busy = a || b || parts.length || shocks.length || P.speed > .5;
    idle = busy ? 0 : idle + 1;
    if (idle > 30 || d.hidden || !enabled) {
      running = false; ctx.clearRect(0, 0, W, H);
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
    P.down = true; P.x = e.clientX; P.y = e.clientY; P.seen = true;
    shocks.push({ x: e.clientX, y: e.clientY, r: 8, life: 1 });
    if (shocks.length > 4) shocks.shift();
    emit(e.clientX, e.clientY, 0, 0, 10);
    wake();
  }
  function onUp() { P.down = false; }
  function onLeave() { P.seen = false; P.speed = 0; }
  function dirty() { rectsDirty = true; wake(); }

  /* ---------------------------------------------------------------- lifecycle */
  function init() {
    cv = d.createElement('canvas'); cv.className = 'rlm-ink'; cv.setAttribute('aria-hidden', 'true');
    ctx = cv.getContext('2d'); if (!ctx) return;
    d.body.appendChild(cv); size();
    off.push(function () { cv.remove(); });
    collect();
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
    setupTilt();
    on(rmq, 'change', function () { if (rmq.matches) api.disable(); });
  }

  var api = window.RLMotion = {
    enable: function () { if (enabled) return; enabled = true; if (!cv) safe(init); wake(); },
    disable: function () {
      enabled = false; cancelAnimationFrame(raf); running = false;
      els.forEach(function (s) { rest(s); delete s.el.__rlm; }); visible.clear();
      if (bg) { bg.style.translate = ''; bg.style.scale = ''; }
      off.splice(0).forEach(function (f) { f(); }); if (io) io.disconnect();
      els.length = 0; cv = null; parts.length = shocks.length = 0;
    },
    get active() { return enabled && !!cv; }
  };

  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', function () { safe(init); });
  else safe(init);
})();
