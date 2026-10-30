/* RobinLab "living lab" — animation engine for the home page.
   No dependencies. Every module is independent and fails soft: if one throws,
   the rest still run and the page stays readable. */
(function () {
  'use strict';

  var d = document, root = d.documentElement;
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var fine = matchMedia('(hover: hover) and (pointer: fine)').matches;

  function $(s, c) { return (c || d).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || d).querySelectorAll(s)); }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function safe(fn) { try { fn(); } catch (e) { if (window.console) console.warn('[fx]', e); } }

  var mouse = { x: innerWidth / 2, y: innerHeight / 2, seen: false };
  var scroll = { y: scrollY, vel: 0 };

  /* ------------------------------------------------------------------ boot */
  function boot(done) {
    var el = $('.fx-loader');
    if (!el || !root.classList.contains('fx-booting')) {
      if (el) el.remove();
      root.classList.remove('fx-booting');
      return done();
    }
    var log = $('.fx-boot-log', el), bar = $('.fx-boot-bar i', el), pct = $('.fx-boot-pct', el);
    var lines = [
      '> <b>RobinLab</b> OS  v' + new Date().getFullYear() + '.1',
      '> mounting projects ........ ok',
      '> loading imagination ...... ok',
      '> compiling personality .... ok',
      '> hello, visitor. welcome.'
    ];
    var i = 0, finished = false;

    function finish() {
      if (finished) return;
      finished = true;
      try { sessionStorage.setItem('fx-boot', '1'); } catch (e) {}
      bar.style.width = '100%'; pct.textContent = '100%';
      el.classList.add('open');
      setTimeout(done, 380);
      setTimeout(function () { el.remove(); root.classList.remove('fx-booting'); }, 1000);
    }
    function step() {
      if (finished) return;
      if (i >= lines.length) return setTimeout(finish, 280);
      log.innerHTML += (i ? '\n' : '') + lines[i];
      i++;
      var p = Math.round((i / lines.length) * 100);
      bar.style.transition = 'width .22s ease';
      bar.style.width = p + '%';
      pct.textContent = p + '%';
      setTimeout(step, 230 + Math.random() * 120);
    }
    el.addEventListener('click', finish);
    addEventListener('keydown', finish, { once: true });
    setTimeout(finish, 5000);
    step();
  }

  /* --------------------------------------------------- background canvas */
  function background() {
    var c = $('#fx-bg');
    if (!c || !c.getContext) return;
    var ctx = c.getContext('2d');
    var W, H, dpr, pts = [], bursts = [];
    var stops = [[118, 168, 255], [180, 140, 255], [79, 227, 193]];

    function color(h, a) {
      var t = h * 2, i = Math.min(1, Math.floor(t)), f = t - i;
      var s = stops[i], e = stops[i + 1];
      return 'rgba(' + Math.round(s[0] + (e[0] - s[0]) * f) + ',' + Math.round(s[1] + (e[1] - s[1]) * f) + ',' +
        Math.round(s[2] + (e[2] - s[2]) * f) + ',' + a + ')';
    }
    function spawn() {
      return {
        x: Math.random() * W, y: Math.random() * H,
        vx: (Math.random() - .5) * .35, vy: (Math.random() - .5) * .35,
        r: Math.random() * 1.6 + .6, h: Math.random(), z: Math.random() * .8 + .2
      };
    }
    function size() {
      dpr = Math.min(devicePixelRatio || 1, 2);
      W = innerWidth; H = innerHeight;
      c.width = W * dpr; c.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.round(clamp(W * H / 9500, 45, 170));
      if (W < 700) n = Math.min(n, 60);
      while (pts.length < n) pts.push(spawn());
      pts.length = n;
      if (reduce) draw(0);
    }

    var LINK = 125, MOUSE_R = 190, last = 0;
    function draw(dt) {
      ctx.clearRect(0, 0, W, H);
      var sv = scroll.vel * .08;
      var i, j, p, q, dx, dy, dist;
      for (i = 0; i < pts.length; i++) {
        p = pts[i];
        if (!reduce) {
          p.x += p.vx * dt; p.y += p.vy * dt - sv * p.z;
          // gentle push away from the pointer
          dx = p.x - mouse.x; dy = p.y - mouse.y; dist = Math.sqrt(dx * dx + dy * dy);
          if (mouse.seen && dist < MOUSE_R && dist > 1) {
            var f = (1 - dist / MOUSE_R) * .9;
            p.x += dx / dist * f * dt * .5; p.y += dy / dist * f * dt * .5;
          }
        }
        if (p.x < -20) p.x = W + 20; else if (p.x > W + 20) p.x = -20;
        if (p.y < -20) p.y = H + 20; else if (p.y > H + 20) p.y = -20;
      }
      ctx.lineWidth = 1;
      for (i = 0; i < pts.length; i++) {
        p = pts[i];
        for (j = i + 1; j < pts.length; j++) {
          q = pts[j]; dx = p.x - q.x;
          if (dx > LINK || dx < -LINK) continue;
          dy = p.y - q.y; dist = dx * dx + dy * dy;
          if (dist < LINK * LINK) {
            ctx.strokeStyle = color((p.h + q.h) / 2, (1 - Math.sqrt(dist) / LINK) * .28);
            ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
          }
        }
        // pointer web
        if (mouse.seen && !reduce) {
          dx = p.x - mouse.x; dy = p.y - mouse.y; dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < MOUSE_R + 40) {
            ctx.strokeStyle = color(p.h, (1 - dist / (MOUSE_R + 40)) * .55);
            ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
          }
        }
        ctx.fillStyle = color(p.h, .35 + p.z * .5);
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (1 + p.z * .4), 0, 6.2832); ctx.fill();
      }
      // click bursts
      for (i = bursts.length - 1; i >= 0; i--) {
        var b = bursts[i];
        b.x += b.vx * dt; b.y += b.vy * dt; b.vx *= .96; b.vy *= .96; b.life -= dt * .0016;
        if (b.life <= 0) { bursts.splice(i, 1); continue; }
        ctx.fillStyle = color(b.h, b.life);
        ctx.beginPath(); ctx.arc(b.x, b.y, 2.2 * b.life + .4, 0, 6.2832); ctx.fill();
      }
    }
    function loop(t) {
      var dt = Math.min(40, t - last) / 16.67; last = t;
      draw(dt);
      requestAnimationFrame(loop);
    }

    size();
    addEventListener('resize', size);
    if (!reduce) requestAnimationFrame(function (t) { last = t; loop(t); });

    // click anywhere → burst of particles
    addEventListener('pointerdown', function (e) {
      if (reduce) return;
      for (var k = 0; k < 22; k++) {
        var a = Math.random() * 6.2832, s = Math.random() * 5 + 1.5;
        bursts.push({ x: e.clientX, y: e.clientY, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: 1, h: Math.random() });
      }
    });
  }

  /* --------------------------------------------------------- split words */
  function splitWords(el, startAt) {
    var n = startAt || 0;
    (function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (ch) {
        if (ch.nodeType === 3) {
          var parts = ch.nodeValue.split(/(\s+)/), frag = d.createDocumentFragment();
          parts.forEach(function (w) {
            if (!w) return;
            if (/^\s+$/.test(w)) { frag.appendChild(d.createTextNode(' ')); return; }
            var s = d.createElement('span');
            s.className = 'w'; s.style.setProperty('--i', n++); s.textContent = w;
            frag.appendChild(s);
          });
          ch.parentNode.replaceChild(frag, ch);
        } else if (ch.nodeType === 1) walk(ch);
      });
    })(el);
    return n;
  }

  /* ---------------------------------------------------------- name scramble */
  var GLYPHS = '!<>-_\\/[]{}=+*^?#0123456789ABCDEFGHJKLMNPQRSTUVWXYZ';
  function scramble(el, text, dur, then) {
    var start = performance.now(), len = text.length;
    el.classList.add('scrambling');
    (function frame(now) {
      var p = (now - start) / dur, out = '';
      for (var i = 0; i < len; i++) {
        var ch = text.charAt(i);
        if (ch === ' ') { out += ' '; continue; }
        // each letter locks in at a staggered moment
        out += p >= (i / len) * .75 + .22 ? ch : GLYPHS.charAt(Math.floor(Math.random() * GLYPHS.length));
      }
      el.textContent = out;
      if (p < 1) requestAnimationFrame(frame);
      else { el.textContent = text; el.classList.remove('scrambling'); if (then) then(); }
    })(start);
  }

  function hero() {
    var h = $('.pf-hero');
    if (!h) return;

    // name
    var name = $('.pf-name', h);
    if (name) {
      var text = name.textContent.trim();
      name.setAttribute('data-text', text);
      name.setAttribute('aria-label', text);
      if (!reduce) {
        scramble(name, text, 1100, function () { name.classList.add('glitch'); setTimeout(function () { name.classList.remove('glitch'); }, 450); });
        var busy = false;
        name.addEventListener('pointerenter', function () {
          if (busy) return; busy = true;
          scramble(name, text, 650, function () { busy = false; });
        });
        // occasional glitch twitch
        setInterval(function () {
          if (d.hidden) return;
          name.classList.add('glitch');
          setTimeout(function () { name.classList.remove('glitch'); }, 450);
        }, 6500);
      }
    }

    // role line types out and cycles
    var role = $('.pf-role', h);
    if (role) {
      var first = role.textContent.trim();
      role.setAttribute('aria-label', first);
      var phrases = [first, 'I turn frustrations into software', 'Python · C++ · Qt', 'Anime wallpaper curator', 'Always learning, always building'];
      role.innerHTML = '<span class="fx-prefix" aria-hidden="true">&gt; </span><span class="fx-typed" aria-hidden="true"></span><span class="fx-caret" aria-hidden="true"></span>';
      var typed = $('.fx-typed', role);
      if (reduce) typed.textContent = first;
      else {
        var pi = 0, ci = 0, del = false;
        (function tick() {
          var cur = phrases[pi];
          if (!del) { ci++; typed.textContent = cur.slice(0, ci); if (ci === cur.length) { del = true; return setTimeout(tick, 2000); } return setTimeout(tick, 45 + Math.random() * 40); }
          ci -= 2; if (ci <= 0) { ci = 0; del = false; pi = (pi + 1) % phrases.length; typed.textContent = ''; return setTimeout(tick, 320); }
          typed.textContent = cur.slice(0, ci); setTimeout(tick, 22);
        })();
      }
    }

    // orbit rings
    var av = $('.pf-avatar', h);
    if (av) {
      ['o1', 'o2', 'o3'].forEach(function (k) {
        var o = d.createElement('span'); o.className = 'fx-orbit ' + k; o.innerHTML = '<i></i>'; av.appendChild(o);
      });
    }

    // little live HUD (local time + pointer coordinates)
    var hud = d.createElement('div');
    hud.className = 'fx-hud'; hud.setAttribute('aria-hidden', 'true');
    h.appendChild(hud);
    function hudTick() {
      var t = new Date();
      hud.innerHTML = 'LOCAL <b>' + t.toLocaleTimeString([], { hour12: false }) + '</b><br>' +
        'X <b>' + String(Math.round(mouse.x)).padStart(4, '0') + '</b> Y <b>' + String(Math.round(mouse.y)).padStart(4, '0') + '</b>';
    }
    hudTick(); setInterval(hudTick, 250);

    // avatar follows the pointer a little
    if (fine && !reduce && av) {
      h.addEventListener('pointermove', function (e) {
        var r = h.getBoundingClientRect();
        av.style.setProperty('--ax', ((e.clientX - r.left) / r.width - .35) * 26 + 'px');
        av.style.setProperty('--ay', ((e.clientY - r.top) / r.height - .5) * 26 + 'px');
      });
      h.addEventListener('pointerleave', function () { av.style.setProperty('--ax', '0px'); av.style.setProperty('--ay', '0px'); });
    }
  }

  /* ------------------------------------------------------------------ marquee */
  var marquees = [];
  function marquee() {
    var host = $('.fx-marquee');
    if (!host) return;
    $$('.fx-row', host).forEach(function (row, idx) {
      row.innerHTML += row.innerHTML;         // duplicate for a seamless loop
      marquees.push({ el: row, x: 0, w: 0, dir: idx % 2 ? 1 : -1, speed: 0.55 + idx * 0.15 });
    });
    function measure() {
      marquees.forEach(function (m) { m.w = m.el.scrollWidth / 2; if (m.dir > 0 && m.x === 0) m.x = -m.w; });
    }
    measure(); addEventListener('resize', measure); addEventListener('load', measure);
  }

  /* ------------------------------------------------------ cursor + main loop */
  var cur = { x: mouse.x, y: mouse.y, rx: mouse.x, ry: mouse.y };
  var dot, ring;
  function cursor() {
    if (!fine || reduce) return;
    dot = d.createElement('div'); dot.className = 'fx-cur-dot';
    ring = d.createElement('div'); ring.className = 'fx-cur-ring';
    d.body.appendChild(ring); d.body.appendChild(dot);
    root.classList.add('fx-cursor', 'cur-out');
    var hot = 'a, button, .btn, input, textarea, select, [role="button"], .pf-skills span, .pf-chips li';
    d.addEventListener('pointerover', function (e) {
      root.classList.toggle('cur-link', !!(e.target.closest && e.target.closest(hot)));
    });
    d.addEventListener('pointerdown', function () { root.classList.add('cur-down'); });
    d.addEventListener('pointerup', function () { root.classList.remove('cur-down'); });
    d.documentElement.addEventListener('pointerleave', function () { root.classList.add('cur-out'); });
    d.documentElement.addEventListener('pointerenter', function () { root.classList.remove('cur-out'); });
  }

  function mainLoop() {
    function frame() {
      // cursor
      if (dot) {
        cur.x = mouse.x; cur.y = mouse.y;
        cur.rx += (cur.x - cur.rx) * .16; cur.ry += (cur.y - cur.ry) * .16;
        dot.style.transform = 'translate3d(' + cur.x + 'px,' + cur.y + 'px,0)';
        ring.style.transform = 'translate3d(' + cur.rx + 'px,' + cur.ry + 'px,0)';
      }
      // marquee — speeds up with scroll velocity
      for (var i = 0; i < marquees.length; i++) {
        var m = marquees[i];
        if (!m.w) continue;
        m.x += m.dir * (m.speed + Math.abs(scroll.vel) * .12);
        if (m.dir < 0 && m.x <= -m.w) m.x += m.w;
        if (m.dir > 0 && m.x >= 0) m.x -= m.w;
        m.el.style.transform = 'translate3d(' + m.x + 'px,0,0)';
      }
      scroll.vel *= .9;
      requestAnimationFrame(frame);
    }
    if (reduce) return;
    requestAnimationFrame(frame);
  }

  /* ----------------------------------------------- tilt + magnetic + spotlight */
  function interactions() {
    if (!fine || reduce) return;

    $$('.pf-tile, .project-card:not(.project-card-placeholder), .about-block').forEach(function (el) {
      el.classList.add('fx-tilt');
      el.addEventListener('pointermove', function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
        el.style.setProperty('--ry', ((px - .5) * 9).toFixed(2) + 'deg');
        el.style.setProperty('--rx', ((.5 - py) * 7).toFixed(2) + 'deg');
        el.style.setProperty('--mx', (e.clientX - r.left) + 'px');
        el.style.setProperty('--my', (e.clientY - r.top) + 'px');
      });
      el.addEventListener('pointerleave', function () {
        el.style.setProperty('--rx', '0deg'); el.style.setProperty('--ry', '0deg');
      });
    });

    $$('.btn, .contact-link, .icon-link, .brand').forEach(function (el) {
      el.classList.add('fx-mag');
      el.addEventListener('pointermove', function (e) {
        var r = el.getBoundingClientRect();
        var x = (e.clientX - (r.left + r.width / 2)) * .28, y = (e.clientY - (r.top + r.height / 2)) * .38;
        el.style.translate = x.toFixed(1) + 'px ' + y.toFixed(1) + 'px';
      });
      el.addEventListener('pointerleave', function () { el.style.translate = ''; });
    });
  }

  /* --------------------------------------------------------- reveal on scroll */
  function counters(el) {
    var m = /^(\D*)(\d+)(.*)$/.exec(el.textContent.trim());
    if (!m || reduce) return;
    var to = +m[2], t0 = performance.now();
    (function f(now) {
      var p = clamp((now - t0) / 1400, 0, 1), e = 1 - Math.pow(1 - p, 4);
      el.textContent = m[1] + Math.round(to * e) + m[3];
      if (p < 1) requestAnimationFrame(f);
    })(t0);
  }

  function reveal() {
    function tag(sel, mode, stepMs, ctx) {
      $$(sel, ctx).forEach(function (el, i) {
        el.setAttribute('data-fx', mode || '');
        el.style.setProperty('--d', Math.min(i * (stepMs == null ? 70 : stepMs), 700) + 'ms');
      });
    }
    // hero: staggered entrance
    ['.pf-avatar', '.pf-status', '.pf-name', '.pf-role', '.pf-chips', '.pf-actions'].forEach(function (s, i) {
      var el = $(s, $('.pf-hero')); if (!el) return;
      el.setAttribute('data-fx', s === '.pf-avatar' ? 'pop' : ''); el.style.setProperty('--d', 120 + i * 110 + 'ms');
    });
    var bio = $('.pf-bio');
    if (bio) { splitWords(bio); bio.setAttribute('data-fx', 'words'); }

    tag('.fx-marquee', '', 0);
    tag('.pf-bento > .pf-tile', '', 80);
    tag('.section-heading', '', 0);
    tag('.project-grid > .project-card', '', 90);
    tag('.about-block', '', 0);
    tag('.about-intro', '', 0);
    tag('.about-signoff', '', 0);
    tag('.contact-links', '', 0);
    tag('.contact .about-text', '', 0);

    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        el.classList.add('in');
        io.unobserve(el);
        if (el.classList.contains('pf-tile')) { var s = $('.pf-stat', el); if (s) counters(s); }
        // once revealed, drop the stagger delay so hovers stay snappy
        setTimeout(function () { el.style.removeProperty('--d'); }, 1800);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    $$('[data-fx]').forEach(function (el) { io.observe(el); });
  }

  /* ------------------------------------------ scroll-scrubbed "read me" text */
  var scrubs = [];
  function scrubText() {
    if (reduce) return;
    $$('.about-intro p').forEach(function (p) {
      splitWords(p);
      p.classList.add('fx-scrub');
      scrubs.push({ el: p, words: $$('.w', p), lit: 0 });
    });
  }
  function updateScrub() {
    var vh = innerHeight;
    scrubs.forEach(function (s) {
      var r = s.el.getBoundingClientRect();
      var p = clamp((vh * .82 - r.top) / (r.height + vh * .3), 0, 1);
      var n = Math.round(p * s.words.length);
      if (n === s.lit) return;
      for (var i = Math.min(n, s.lit); i < Math.max(n, s.lit); i++) s.words[i].classList.toggle('on', i < n);
      s.lit = n;
    });
  }

  /* ---------------------------------------------- horizontal project showcase */
  var hs = null;
  function hscroll() {
    var sec = $('#projects'), grid = sec && $('.project-grid', sec);
    if (!grid || reduce) return;
    var mq = matchMedia('(min-width: 1000px) and (min-height: 600px)');
    var pin, bar, maxX = 0, headH = 64, on = false;

    function layout() {
      grid.style.transform = 'none';
      maxX = Math.max(0, grid.scrollWidth - innerWidth);
      var pinH = innerHeight - headH;
      pin.style.height = pinH + 'px';
      sec.style.height = (pinH + maxX) + 'px';
      update();
    }
    function update() {
      if (!on) return;
      var r = sec.getBoundingClientRect();
      var p = maxX ? clamp((headH - r.top) / maxX, 0, 1) : 0;
      grid.style.transform = 'translate3d(' + (-p * maxX).toFixed(1) + 'px,0,0)';
      bar.firstElementChild.style.transform = 'scaleX(' + p.toFixed(3) + ')';
      bar.lastElementChild.textContent = String(Math.round(p * 100)).padStart(3, '0') + '%';
    }
    function enable() {
      if (on) return;
      pin = d.createElement('div'); pin.className = 'fx-h-pin';
      while (sec.firstChild) pin.appendChild(sec.firstChild);
      bar = d.createElement('div'); bar.className = 'fx-h-bar'; bar.setAttribute('aria-hidden', 'true');
      bar.innerHTML = '<span>Scroll</span><div class="track"><i></i></div><span>000%</span>';
      pin.appendChild(bar);
      sec.appendChild(pin); sec.classList.add('fx-h');
      on = true; layout();
      // reveal every card at once; they travel in from the side anyway
      $$('.project-card', sec).forEach(function (c) { c.classList.add('in'); });
    }
    function disable() {
      if (!on) return;
      on = false;
      bar.remove();
      while (pin.firstChild) sec.insertBefore(pin.firstChild, pin);
      pin.remove();
      sec.classList.remove('fx-h'); sec.style.height = ''; grid.style.transform = '';
    }
    function check() { mq.matches ? enable() : disable(); if (on) layout(); }
    check();
    mq.addEventListener('change', check);
    addEventListener('resize', function () { if (on) layout(); });
    addEventListener('load', function () { if (on) layout(); });
    hs = { update: update };
  }

  /* ------------------------------------------------------- scroll-linked bits */
  function scrollFx() {
    var prog = d.createElement('div'); prog.className = 'fx-progress'; d.body.appendChild(prog);
    var header = $('.site-header');
    var orbs = $$('.fx-orbs i');
    var links = $$('.site-nav > a[href^="#"]');
    var targets = links.map(function (a) { return $(a.getAttribute('href')); });
    var lastY = scrollY, ticking = false;

    function onScroll() {
      var y = scrollY;
      scroll.vel = clamp(scroll.vel + (y - lastY) * .5, -60, 60);
      // header hides on scroll down, returns on scroll up
      if (header) header.classList.toggle('fx-hide', y > 160 && y > lastY && y - lastY > 2 && !(hs && $('#projects.fx-h') && inPinned()));
      lastY = y;
      if (!ticking) { ticking = true; requestAnimationFrame(apply); }
    }
    function inPinned() {
      var r = $('#projects').getBoundingClientRect();
      return r.top <= 70 && r.bottom > innerHeight * .5;
    }
    function apply() {
      ticking = false;
      var y = scrollY, max = d.documentElement.scrollHeight - innerHeight;
      prog.style.transform = 'scaleX(' + (max > 0 ? y / max : 0).toFixed(4) + ')';
      orbs.forEach(function (o, i) { o.style.transform = 'translate3d(0,' + (-y * (.05 + i * .035)).toFixed(1) + 'px,0)'; });
      var cut = innerHeight * .4, active = -1;
      targets.forEach(function (t, i) { if (t && t.getBoundingClientRect().top <= cut) active = i; });
      links.forEach(function (a, i) { a.classList.toggle('is-active', i === active); });
      if (hs) hs.update();
      updateScrub();
    }
    addEventListener('scroll', onScroll, { passive: true });
    addEventListener('resize', apply);
    apply();
  }

  /* ---------------------------------------------------------------- start */
  function injectDom() {
    var b = d.body, frag = d.createDocumentFragment();
    var cv = d.createElement('canvas'); cv.id = 'fx-bg'; cv.setAttribute('aria-hidden', 'true'); frag.appendChild(cv);
    var orbs = d.createElement('div'); orbs.className = 'fx-orbs'; orbs.setAttribute('aria-hidden', 'true'); orbs.innerHTML = '<i></i><i></i><i></i>'; frag.appendChild(orbs);
    if (!reduce) { var g = d.createElement('div'); g.className = 'fx-grain'; g.setAttribute('aria-hidden', 'true'); frag.appendChild(g); }
    b.insertBefore(frag, b.firstChild);
  }

  addEventListener('pointermove', function (e) {
    mouse.x = e.clientX; mouse.y = e.clientY; mouse.seen = true;
    if (e.pointerType === 'mouse') root.classList.remove('cur-out');
  }, { passive: true });

  safe(injectDom);
  safe(background);
  safe(marquee);
  safe(cursor);
  safe(mainLoop);
  safe(scrubText);
  safe(hscroll);
  safe(scrollFx);
  safe(interactions);
  // Hero + reveals wait for the boot curtain.
  boot(function () { safe(hero); safe(reveal); });
})();
