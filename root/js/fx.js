/* RobinLab "living lab" — animation engine shared by every page.
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
  /* Collection page: rotating scenes (sakura -> starfield -> aurora), crossfaded. */
  function sceneBackground(c) {
    var ctx = c.getContext('2d'), W, H, dpr, last = 0, cur = 0, sw = 0;
    var names = ['Sakura', 'Starfield', 'Aurora'], items = [];
    function size() {
      dpr = fine ? Math.min(devicePixelRatio || 1, 2) : 1;
      W = innerWidth; H = innerHeight;
      c.width = W * dpr; c.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      items = [];
      var n = W < 700 ? 40 : 80, i;
      for (i = 0; i < n; i++) items.push({ x: Math.random() * W, y: Math.random() * H, z: Math.random(), a: Math.random() * 6.28, r: Math.random() });
    }
    var scenes = [
      function (dt, t) { // sakura petals
        ctx.clearRect(0, 0, W, H);
        for (var i = 0; i < items.length; i++) {
          var p = items[i], sz = 5 + p.z * 9;
          p.y += (.5 + p.z * 1.1) * dt; p.a += .02 * dt;
          p.x += Math.sin(t / 1400 + p.r * 9) * .6 * dt + .25 * dt;
          if (p.y > H + 20) { p.y = -20; p.x = Math.random() * W; }
          if (p.x > W + 20) p.x = -20;
          ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.a); ctx.scale(1, .6 + Math.abs(Math.sin(p.a * 1.7)) * .4);
          ctx.fillStyle = 'rgba(255,' + (150 + p.r * 50 | 0) + ',' + (190 + p.r * 40 | 0) + ',' + (.35 + p.z * .45) + ')';
          ctx.beginPath(); ctx.ellipse(0, 0, sz, sz * .55, 0, 0, 6.283); ctx.fill(); ctx.restore();
        }
      },
      function (dt, t) { // starfield warp drift
        ctx.clearRect(0, 0, W, H);
        var cx = W / 2, cy = H / 2;
        for (var i = 0; i < items.length; i++) {
          var p = items[i];
          p.z += .004 * dt * (1 + p.r);
          if (p.z > 1) { p.z = .02; p.a = Math.random() * 6.28; p.r = Math.random(); }
          var rad = p.z * p.z * Math.hypot(W, H) * .6, x = cx + Math.cos(p.a) * rad, y = cy + Math.sin(p.a) * rad;
          var rad2 = Math.max(0, p.z - .04) * Math.max(0, p.z - .04) * Math.hypot(W, H) * .6;
          ctx.strokeStyle = 'hsla(' + (200 + p.r * 80 | 0) + ',90%,80%,' + Math.min(1, p.z * 1.4) + ')';
          ctx.lineWidth = .6 + p.z * 1.8;
          ctx.beginPath(); ctx.moveTo(cx + Math.cos(p.a) * rad2, cy + Math.sin(p.a) * rad2); ctx.lineTo(x, y); ctx.stroke();
        }
      },
      function (dt, t) { // aurora ribbons
        ctx.clearRect(0, 0, W, H);
        ctx.globalCompositeOperation = 'lighter';
        for (var b = 0; b < 4; b++) {
          var g = ctx.createLinearGradient(0, H * .15, 0, H * .75), hue = (t / 60 + b * 70) % 360 | 0;
          g.addColorStop(0, 'hsla(' + hue + ',90%,60%,0)'); g.addColorStop(.5, 'hsla(' + hue + ',90%,60%,.16)'); g.addColorStop(1, 'hsla(' + hue + ',90%,60%,0)');
          ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(0, H);
          for (var x = 0; x <= W; x += 24) ctx.lineTo(x, H * (.38 + b * .07) + Math.sin(x / 190 + t / 1700 + b * 1.7) * 70 + Math.sin(x / 90 - t / 2300 + b) * 28);
          ctx.lineTo(W, H); ctx.closePath(); ctx.fill();
        }
        ctx.globalCompositeOperation = 'source-over';
      }
    ];
    c.style.transition = 'opacity .9s ease'; c.style.opacity = '.85';
    var btn = d.createElement('button');
    btn.type = 'button'; btn.className = 'fx-scene-btn';
    function label() { btn.textContent = '✨ ' + names[cur] + ' →'; btn.title = 'Change background scene'; }
    function next() {
      if (sw) return; sw = 1; c.style.opacity = '0';
      setTimeout(function () { cur = (cur + 1) % scenes.length; label(); size(); c.style.opacity = '.85'; sw = 0; }, 900);
    }
    btn.addEventListener('click', function () { next(); clearInterval(timer); timer = setInterval(next, 20000); });
    label(); d.body.appendChild(btn);
    size(); addEventListener('resize', size);
    var timer = reduce ? 0 : setInterval(next, 20000);
    function loop(t) {
      var dt = Math.min(40, t - last) / 16.67; last = t;
      if (!d.hidden) { scenes[cur](dt, t); requestAnimationFrame(loop); }
    }
    function start() { requestAnimationFrame(function (t) { last = t; loop(t); }); }
    if (reduce) { scenes[0](1, 0); return; }
    start();
    d.addEventListener('visibilitychange', function () { if (!d.hidden) start(); });
  }

  function background() {
    var c = $('#fx-bg');
    if (!c || !c.getContext) return;
    if (d.body.classList.contains('col-page')) return sceneBackground(c);
    var ctx = c.getContext('2d');
    var W, H, dpr, FS = 16, cols = [], last = 0, acc = 0;
    var CH = '01', CODE = '{}[]()<>/;=+*&|!#$%0123456789abcdef';
    function glyph() { return Math.random() < .72 ? CH.charAt(Math.random() * 2 | 0) : CODE.charAt(Math.random() * CODE.length | 0); }
    function size() {
      dpr = fine ? Math.min(devicePixelRatio || 1, 2) : 1;
      W = innerWidth; H = innerHeight;
      c.width = W * dpr; c.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.ceil(W / FS);
      while (cols.length < n) cols.push({ y: Math.random() * H / FS, s: .5 + Math.random() * .9, h: Math.random() });
      cols.length = n;
      ctx.fillStyle = '#04060f'; ctx.fillRect(0, 0, W, H);
    }
    function draw(dt) {
      // fade previous frame -> trails
      ctx.fillStyle = 'rgba(4,6,15,.09)'; ctx.fillRect(0, 0, W, H);
      ctx.font = FS + 'px "JetBrains Mono", Consolas, monospace';
      var hue0 = (performance.now() / 40) % 360;
      for (var i = 0; i < cols.length; i++) {
        var col = cols[i], x = i * FS, y = col.y * FS;
        var dx = x - mouse.x, dy = y - mouse.y, near = mouse.seen && dx * dx + dy * dy < 32000;
        // head glyph bright, tint cycles through cyan/violet/green
        ctx.fillStyle = near ? '#ffffff' : 'hsla(' + ((hue0 + i * 3) % 360 | 0) + ',95%,72%,.95)';
        ctx.fillText(glyph(), x, y);
        col.y += col.s * dt * (near ? 2.2 : 1);
        if (y > H && Math.random() > .96) { col.y = Math.random() * -20; col.s = .5 + Math.random() * .9; }
      }
    }
    function loop(t) {
      var dt = Math.min(40, t - last) / 16.67; last = t;
      if (!d.hidden) { draw(dt); requestAnimationFrame(loop); }
    }
    size();
    addEventListener('resize', size);
    if (reduce) { for (var k = 0; k < 90; k++) draw(1); return; }
    function start() { requestAnimationFrame(function (t) { last = t; loop(t); }); }
    start();
    d.addEventListener('visibilitychange', function () { if (!d.hidden) start(); });
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
    var h = $('.pf-hero, .col-hero, .pr-hero');
    if (!h) return;

    // name (home: .pf-name, inner pages: the page h1)
    var name = $('.pf-name', h) || $('h1', h);
    if (name && !name.classList.contains('pf-name')) name.classList.add('fx-title');
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
  function bindTilt(el) {
    if (!fine || reduce || el.classList.contains('fx-tilt')) return;
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
  }

  function interactions() {
    if (!fine || reduce) return;

    $$('.pf-tile, .project-card:not(.project-card-placeholder), .about-block').forEach(bindTilt);

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

    // inner pages (collection / certificates / presentations)
    ['.col-hero', '.pr-hero'].forEach(function (sel) {
      var hero = $(sel); if (!hero) return;
      Array.prototype.forEach.call(hero.children, function (el, i) {
        if (el.tagName === 'H1') return;       // the title is scrambled in, not faded
        el.setAttribute('data-fx', ''); el.style.setProperty('--d', 120 + i * 110 + 'ms');
      });
    });
    tag('.col-tabs, .col-toolbar, .col-chips, .col-stats, .pr-note, .site-footer', '', 60);

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

    // Cards rendered later by collection.js / presentations.js. Only the big
    // blocks are animated - hundreds of blurred thumbnails would stutter.
    var dyn = '.col-pack, .col-packcard, .col-packgroup, .pr-card';
    function adopt(node) {
      if (node.nodeType !== 1) return;
      var list = node.matches(dyn) ? [node] : $$(dyn, node);
      list.forEach(function (el, i) {
        if (el.hasAttribute('data-fx')) return;
        el.setAttribute('data-fx', '');
        el.style.setProperty('--d', Math.min(i * 70, 560) + 'ms');
        io.observe(el);
        if (el.matches('.pr-card, .col-packcard')) bindTilt(el);
      });
    }
    ['col-packs', 'col-packlist', 'pr-grid'].forEach(function (id) {
      var host = d.getElementById(id); if (!host) return;
      adopt(host);
      new MutationObserver(function (ms) {
        ms.forEach(function (m) { Array.prototype.forEach.call(m.addedNodes, adopt); });
      }).observe(host, { childList: true, subtree: true });
    });
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
