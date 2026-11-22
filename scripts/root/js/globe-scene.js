/* RobinLab globe — WebGL scene + interaction. Needs globe.js and globe-data.js first. */
(function (w, d) {
  'use strict';
  var G = w.RLGlobe;
  if (!G) return;

  G.start = function (host) {
    if (host.__rlGlobe) return; // never initialise (or bind listeners) twice
    var stats = { frames: 0, maxDt: 0, loops: 0 }; // read by tests: frames drawn, worst frame gap, live rAF chains
    host.__rlGlobe = { stats: stats };
    var ui = G.mount(host), info = new G.Info();
    var state = { hover: false, paused: false, expanded: false, visible: true, speed: G.reduce ? 0 : 1, glow: 0.6, mark: 0, drag: null, moved: false, raf: 0, goal: null, clock: 0, dead: false };
    var rad = Math.PI / 180;

    import(G.base + 'three.module.min.js').then(function (T) {
      var renderer;
      try { renderer = new T.WebGLRenderer({ canvas: ui.canvas, antialias: true, alpha: true, powerPreference: 'low-power' }); }
      catch (e) { host.classList.add('rl-globe-off'); return; }
      renderer.setPixelRatio(Math.min(w.devicePixelRatio || 1, 1.5)); // a ~150px canvas gains nothing from more
      var scene = new T.Scene(), cam = new T.PerspectiveCamera(30, 1, 0.1, 50);
      cam.position.z = 6.2;
      // "ready" (fade-in) only once every texture is in; a failed texture hides the globe instead of showing a half-lit sphere
      var lm = new T.LoadingManager(function () { prewarm(); host.classList.add('rl-globe-ready'); }, function () {}, function () { host.classList.add('rl-globe-off'); });
      var tl = new T.TextureLoader(lm), max = renderer.capabilities.getMaxAnisotropy();
      var tex = function (n, srgb) {
        var t = tl.load(G.base + n);
        if (srgb) t.colorSpace = T.SRGBColorSpace; t.anisotropy = Math.min(8, max); texes.push(t); return t;
      };
      var texes = [];
      var sun = new T.Vector3(-1, 0.35, 0.9).normalize();
      var earth = new T.Mesh(new T.SphereGeometry(1, 96, 64), new T.ShaderMaterial({
        uniforms: { day: { value: tex('earth_atmos_2048.jpg') }, night: { value: tex('earth_lights_2048.png') }, spec: { value: tex('earth_specular_2048.jpg') }, sun: { value: sun } },
        vertexShader: 'varying vec2 vUv; varying vec3 vN; varying vec3 vV; void main(){ vUv=uv; vN=normalize(normalMatrix*normal); vec4 mv=modelViewMatrix*vec4(position,1.); vV=normalize(-mv.xyz); gl_Position=projectionMatrix*mv; }',
        fragmentShader: 'uniform sampler2D day,night,spec; uniform vec3 sun; varying vec2 vUv; varying vec3 vN; varying vec3 vV;' +
          'void main(){ vec3 n=normalize(vN); float l=dot(n,normalize(sun)); float k=smoothstep(-.12,.22,l);' +
          'vec3 dc=texture2D(day,vUv).rgb; vec3 nc=texture2D(night,vUv).rgb*1.3+dc*.05; float s=texture2D(spec,vUv).r;' +
          'vec3 h=normalize(normalize(sun)+vV); float sp=pow(max(dot(n,h),0.),48.)*s*.55*k;' +
          'vec3 c=mix(nc,dc*(.28+.95*max(l,0.)),k)+sp*vec3(.7,.85,1.);' +
          'float f=pow(1.-max(dot(n,vV),0.),3.); c+=vec3(.12,.4,.9)*f*.5*(.35+k); gl_FragColor=vec4(c,1.); }'
      }));
      var cloud = new T.Mesh(new T.SphereGeometry(1.012, 64, 48), new T.MeshBasicMaterial({ map: tex('earth_clouds_1024.png', true), transparent: true, opacity: 0.38, depthWrite: false, alphaMap: null }));
      var glow = new T.ShaderMaterial({
        uniforms: { g: { value: state.glow } }, transparent: true, side: T.BackSide, depthWrite: false, blending: T.AdditiveBlending,
        vertexShader: 'varying vec3 vN; void main(){ vN=normalize(normalMatrix*normal); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }',
        fragmentShader: 'uniform float g; varying vec3 vN; void main(){ float i=pow(max(.62-dot(vN,vec3(0,0,1)),0.),2.2); gl_FragColor=vec4(.25,.62,1.,1.)*i*g*1.1; }'
      });
      var halo = new T.Mesh(new T.SphereGeometry(1.16, 64, 48), glow);
      var spin = new T.Group(); spin.add(earth, cloud);
      var tilt = new T.Group(); tilt.rotation.z = -0.2; tilt.add(spin); scene.add(tilt, halo);

      // stars (deep space) — fixed, very light
      var sp = new Float32Array(600 * 3);
      for (var i = 0; i < 600; i++) { var u = Math.random() * 6.283, v = Math.acos(2 * Math.random() - 1), r = 14; sp[i * 3] = r * Math.sin(v) * Math.cos(u); sp[i * 3 + 1] = r * Math.cos(v); sp[i * 3 + 2] = r * Math.sin(v) * Math.sin(u); }
      var sg = new T.BufferGeometry(); sg.setAttribute('position', new T.BufferAttribute(sp, 3));
      scene.add(new T.Points(sg, new T.PointsMaterial({ color: 0xaecbff, size: 0.05, sizeAttenuation: true, transparent: true, opacity: 0.55 })));

      // marker anchor on the sphere
      var anchor = new T.Object3D(); spin.add(anchor);
      function place() {
        var L = info.loc; if (!L) return;
        var la = L.lat * rad, lo = L.lon * rad;
        anchor.position.set(Math.cos(la) * Math.cos(lo), Math.sin(la), -Math.cos(la) * Math.sin(lo)).multiplyScalar(1.005);
      }
      place();
      var faceAngle = function (L) { return -(L.lon * rad) - 1.57; }; // Y-rotation that turns longitude L toward the camera
      spin.rotation.y = info.loc ? faceAngle(info.loc) : 0;

      function prewarm() { if (renderer.initTexture) texes.forEach(function (t) { try { renderer.initTexture(t); } catch (e) {} }); }
      var off = { x: 0, y: 0, w: 1, h: 1 }; // canvas box inside the host, cached so frames never force layout
      function size() {
        var r = host.getBoundingClientRect(), s = Math.max(120, Math.round(Math.min(r.width, r.height)));
        renderer.setSize(s, s, false); cam.aspect = 1; cam.updateProjectionMatrix();
        var rc = ui.canvas.getBoundingClientRect(); off = { x: rc.left - r.left, y: rc.top - r.top, w: rc.width, h: rc.height };
        run();
      }
      var ro = w.ResizeObserver ? new ResizeObserver(size) : null;
      if (ro) ro.observe(host); else w.addEventListener('resize', size);

      // exponential ease, exact for any frame time (k = rate per second); snaps once close so a settled scene stops requesting frames
      function ease(v, t, k, dt) { v += (t - v) * (1 - Math.exp(-k * dt)); return Math.abs(t - v) < 0.002 ? t : v; }
      var wp = new T.Vector3(), cd = new T.Vector3(), last = performance.now();
      var fine = w.matchMedia('(hover: hover)').matches;
      var rm = w.matchMedia('(prefers-reduced-motion: reduce)'), onRm = function () { G.reduce = rm.matches; run(); };
      if (rm.addEventListener) rm.addEventListener('change', onRm);
      function frame(now) {
        state.raf = 0;
        if (state.dead) return;
        var gap = (now - last) / 1000, dt = Math.min(0.1, Math.max(0, gap)); last = now;
        stats.frames++; if (gap < 1 && gap > stats.maxDt) stats.maxDt = gap;
        var live = !G.reduce; // reduced motion: no ambient spin or cloud drift, only user-driven movement
        var target = state.paused || !live ? 0 : (state.hover || state.drag ? 0.18 : 1);
        var gt = state.hover ? 1 : 0.6, mt = state.hover || state.expanded ? 1 : 0;
        state.speed = ease(state.speed, target, 4, dt); state.glow = ease(state.glow, gt, 4, dt); state.mark = ease(state.mark, mt, 6, dt);
        glow.uniforms.g.value = state.glow;
        if (state.goal !== null && !state.drag) { // ease toward a new location (after a precise fix)
          var df = Math.atan2(Math.sin(state.goal - spin.rotation.y), Math.cos(state.goal - spin.rotation.y));
          spin.rotation.y += df * (1 - Math.exp(-3 * dt));
          if (Math.abs(df) < 0.01) state.goal = null;
        } else if (!state.drag) spin.rotation.y += dt * 0.12 * state.speed;
        if (live && !state.paused) cloud.rotation.y += dt * 0.012;
        renderer.render(scene, cam);

        // project the marker (only while it can be seen)
        var vis = 0;
        if (info.loc && state.mark > 0.01) {
          anchor.getWorldPosition(wp);
          cd.copy(cam.position).normalize();
          vis = wp.dot(cd) > 0.12 ? state.mark : 0; // facing the camera, not on the far side
          wp.project(cam);
          ui.marker.style.transform = 'translate(' + (off.x + (wp.x * 0.5 + 0.5) * off.w).toFixed(1) + 'px,' + (off.y + (-wp.y * 0.5 + 0.5) * off.h).toFixed(1) + 'px) translate(-50%,-50%)';
        }
        ui.marker.style.opacity = vis.toFixed(2); ui.marker.style.pointerEvents = vis > 0.5 ? 'auto' : 'none';
        ui.marker.tabIndex = vis > 0.5 ? 0 : -1;

        // keep rendering only while something is moving; otherwise the GPU idles
        var busy = state.drag || state.goal !== null || (live && !state.paused) || state.speed !== target ||
          state.glow !== gt || state.mark !== mt;
        if (busy && state.visible && !d.hidden) { state.raf = requestAnimationFrame(frame); stats.loops = 1; } else stats.loops = 0;
      }
      function run() { if (!state.raf && !state.dead && state.visible && !d.hidden) { last = performance.now(); state.raf = requestAnimationFrame(frame); } }

      // ---- panel: rebuild markup only when its structure changes, so buttons survive the clock tick
      var lastKey = '', TIME = /<div class="rl-g-time">(.*?)<\/div>/;
      function refresh() {
        var h = info.html(state.expanded), key = h.replace(TIME, '');
        if (key !== lastKey) { lastKey = key; ui.panel.innerHTML = h; return; }
        var t = ui.panel.querySelector('.rl-g-time'), m = h.match(TIME); if (t && m) t.innerHTML = m[1];
      }
      function clock(on) {
        if (on && !state.clock) state.clock = setInterval(refresh, 1000);
        else if (!on && state.clock) { clearInterval(state.clock); state.clock = 0; }
      }

      // ---- interaction
      function setHover(v) {
        state.hover = v; host.classList.toggle('is-hover', v);
        if (!v) state.expanded = false;
        host.classList.toggle('is-expanded', state.expanded);
        if (v) refresh();
        clock(v && state.visible && !d.hidden); run();
      }
      if (fine) {
        host.addEventListener('pointerenter', function () { setHover(true); });
        host.addEventListener('pointerleave', function () { if (!state.drag) setHover(false); });
      }
      ui.canvas.addEventListener('pointerdown', function (e) {
        if (e.button > 0) return;
        state.drag = { x: e.clientX, y: e.clientY, r: spin.rotation.y, t: tilt.rotation.x, id: e.pointerId }; state.moved = false; state.goal = null;
        try { ui.canvas.setPointerCapture(e.pointerId); } catch (x) {}
        host.classList.add('is-drag'); run();
      });
      ui.canvas.addEventListener('pointermove', function (e) {
        var g = state.drag; if (!g || e.pointerId !== g.id) return;
        var dx = e.clientX - g.x, dy = e.clientY - g.y;
        if (Math.abs(dx) > 4 || Math.abs(dy) > 4) state.moved = true;
        spin.rotation.y = g.r + dx * 0.008;
        tilt.rotation.x = Math.max(-0.6, Math.min(0.6, g.t + dy * 0.006)); // measured from drag start, so it cannot run away
        run();
      });
      function end(e, cancelled) {
        var g = state.drag; if (!g || e.pointerId !== g.id) return;
        state.drag = null; host.classList.remove('is-drag');
        if (!cancelled && !state.moved) { // a tap/click, not a drag
          if (!fine) setHover(!state.hover); else { state.paused = !state.paused; host.classList.toggle('is-paused', state.paused); }
        } else if (fine && !host.matches(':hover')) setHover(false); // released outside the globe
        run();
      }
      ui.canvas.addEventListener('pointerup', function (e) { end(e, false); });
      ui.canvas.addEventListener('pointercancel', function (e) { end(e, true); });
      ui.marker.addEventListener('click', function (e) {
        e.stopPropagation(); state.expanded = !state.expanded; host.classList.toggle('is-expanded', state.expanded); refresh(); run();
      });
      ui.panel.addEventListener('click', function (e) {
        if (!e.target.hasAttribute('data-precise') || info.busy) return;
        info.usePrecise(function (ok) {
          if (ok) { place(); state.goal = faceAngle(info.loc); }
          refresh(); run();
        });
        refresh(); // shows the "waiting for your browser" state immediately
      });
      host.addEventListener('keydown', function (e) { if (e.key === 'Escape') setHover(false); });
      ui.marker.addEventListener('focus', function () { setHover(true); });
      // touch: tapping anywhere outside the globe closes the panel
      var outside = function (e) { if (!fine && state.hover && !host.contains(e.target)) setHover(false); };
      d.addEventListener('pointerdown', outside);
      ui.canvas.addEventListener('webglcontextlost', function (e) { e.preventDefault(); host.classList.add('rl-globe-off'); clock(false); });

      // pause when off-screen / tab hidden
      var io = new IntersectionObserver(function (en) {
        state.visible = en[0].isIntersecting; clock(state.hover && state.visible); if (state.visible) run();
      }, { rootMargin: '80px' });
      io.observe(host);
      var onVis = function () { clock(state.hover && !d.hidden); if (!d.hidden) run(); };
      d.addEventListener('visibilitychange', onVis);
      // full teardown: no rAF, timers, observers or document/media listeners survive
      host.__rlGlobe.destroy = function () {
        state.dead = true; if (state.raf) cancelAnimationFrame(state.raf); state.raf = 0; clock(false);
        io.disconnect(); if (ro) ro.disconnect(); else w.removeEventListener('resize', size);
        d.removeEventListener('pointerdown', outside); d.removeEventListener('visibilitychange', onVis);
        if (rm.removeEventListener) rm.removeEventListener('change', onRm);
        renderer.dispose(); host.__rlGlobe = null;
      };
      host.__rlGlobe.state = state;
      size();
    }).catch(function () { host.classList.add('rl-globe-off'); });
  };
})(window, document);
