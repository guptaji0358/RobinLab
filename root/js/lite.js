/* RobinLab "lite mode" — a plain, static look for machines that can't render the
   animated background / custom cursor properly (GPU acceleration off, software
   rendering, old or low-power hardware).

   Loaded in <head> on every page, before first paint. It only decides and sets
   <html class="fx-lite">; css/fx.css restyles the page and js/fx.js stops the
   canvas, cursor and motion. Everything fails soft.

   Decision order:
     1. ?lite=1 / ?lite=0 in the URL (also saved)
     2. the visitor's saved choice (toggle button)  — localStorage "fx-mode": "lite" | "full"
     3. auto: reduced-motion, data-saver, software/no WebGL renderer, very low CPU/RAM
     4. auto: a short frame-rate probe after load; if the page can't hold ~24 fps it
        switches itself to lite and remembers ("auto-lite")                          */
(function () {
  'use strict';
  var d = document, root = d.documentElement, KEY = 'fx-mode';

  function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function set(v) { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (e) {} }

  function softwareRenderer() {
    try {
      var c = d.createElement('canvas');
      var gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (!gl) return true;                                   // no GPU context at all
      var ext = gl.getExtension('WEBGL_debug_renderer_info');
      var name = ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : '';
      var lose = gl.getExtension('WEBGL_lose_context'); if (lose) lose.loseContext();
      return /swiftshader|llvmpipe|softpipe|software|basic render|microsoft basic|mesa offscreen/i.test(name);
    } catch (e) { return false; }
  }

  function autoReason() {
    var conn = navigator.connection || {};
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return 'reduced-motion';
    if (conn.saveData) return 'save-data';
    if ((navigator.hardwareConcurrency || 8) <= 2) return 'low-cpu';
    if ((navigator.deviceMemory || 8) <= 2) return 'low-memory';
    if (softwareRenderer()) return 'software-render';
    return '';
  }

  var q = /[?&]lite=([01])/.exec(location.search);
  if (q) set(q[1] === '1' ? 'lite' : 'full');

  var mode = get();
  var lite = mode === 'lite' || mode === 'auto-lite' || (mode !== 'full' && !!autoReason());

  function apply(on) {
    root.classList.toggle('fx-lite', on);
    if (on) root.classList.remove('fx-booting');
    try { d.dispatchEvent(new CustomEvent('fx-lite', { detail: on })); } catch (e) {}
    paintButton();
  }

  var btn;
  function paintButton() {
    if (!btn) return;
    var on = root.classList.contains('fx-lite');
    btn.textContent = on ? 'Full effects' : 'Lite mode';
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.title = on ? 'Switch the animated background and cursor back on'
                   : 'Plain, fast look — use this if the page looks broken or runs slowly';
  }
  function addButton() {
    btn = d.createElement('button');
    btn.type = 'button'; btn.className = 'fx-lite-toggle';
    btn.addEventListener('click', function () {
      var on = !root.classList.contains('fx-lite');
      set(on ? 'lite' : 'full');
      apply(on);
      if (!on) location.reload();   // let the animation engine start cleanly
    });
    d.body.appendChild(btn);
    paintButton();
  }

  /* frame-rate probe: only when we are still in full mode and nothing is saved */
  function probe() {
    if (root.classList.contains('fx-lite') || mode === 'full') return;
    var times = [], t0;
    function tick(t) {
      if (d.hidden) { times = []; return setTimeout(function () { requestAnimationFrame(tick); }, 500); }
      times.push(t);
      if (t - times[0] < 1800) return requestAnimationFrame(tick);
      var gaps = [];
      for (var i = 1; i < times.length; i++) gaps.push(times[i] - times[i - 1]);
      gaps.sort(function (a, b) { return a - b; });
      var median = gaps[Math.floor(gaps.length / 2)] || 16;
      if (median > 42) { set('auto-lite'); apply(true); }   // ~<24 fps
    }
    setTimeout(function () { requestAnimationFrame(tick); }, 2500);   // after the boot curtain
  }

  if (lite) apply(true);
  window.fxLite = { on: function () { return root.classList.contains('fx-lite'); } };

  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', function () { addButton(); probe(); });
  else { addButton(); probe(); }
})();
