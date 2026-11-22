/* RobinLab — interactive Earth that hides the visitor's local time/location.
   Idle: spinning planet + "Explore Earth". Hover: slows, marker + glass panel appear.
   Click: pause/resume. Drag: rotate. Marker click: expanded details / opt-in precise location.
   three.js + textures are self-hosted and loaded lazily when the globe nears the viewport. */
(function (w, d) {
  'use strict';
  var script = d.currentScript;
  var BASE = new URL('../assets/globe/', script ? script.src : location.href).href;
  var reduce = w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var DATA = w.RLGlobeData;
  var pad = function (n) { return String(n).padStart(2, '0'); };

  function mount(host) {
    host.classList.add('rl-globe');
    host.innerHTML =
      '<canvas class="rl-globe-canvas" aria-hidden="true"></canvas>' +
      '<div class="rl-globe-hint" aria-hidden="true">Explore Earth</div>' +
      '<button class="rl-globe-marker" type="button" aria-label="Show location details" tabindex="-1"></button>' +
      '<div class="rl-globe-panel" role="status" aria-live="off"></div>';
    host.setAttribute('role', 'img');
    host.setAttribute('aria-label', 'Interactive rotating Earth. Hover to reveal your local time and approximate location.');
    return {
      canvas: host.querySelector('canvas'), marker: host.querySelector('.rl-globe-marker'),
      panel: host.querySelector('.rl-globe-panel')
    };
  }

  /* ------------------------------------------------------------ info model */
  function Info() {
    var tz = 'UTC';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (e) {}
    this.tz = tz;
    this.tzName = { 'Asia/Calcutta': 'Asia/Kolkata', 'Europe/Kiev': 'Europe/Kyiv' }[tz] || tz;
    this.loc = DATA.fromTimezone(tz);
  }
  var WHY = {
    unsupported: 'Precise location is not available in this browser.',
    denied: 'Location permission was denied. Showing the approximate position.',
    unavailable: 'Your device could not determine a position. Showing the approximate position.',
    timeout: 'Locating took too long. Showing the approximate position.'
  };
  /* cb(ok, reason). reason: unsupported | denied | unavailable | timeout. Never throws. */
  Info.prototype.usePrecise = function (cb) {
    var self = this, done = false;
    var fin = function (ok, why) { if (done) return; done = true; self.busy = false; self.note = ok ? '' : WHY[why] || WHY.unavailable; cb(ok, why); };
    if (!navigator.geolocation) { self.note = WHY.unsupported; return cb(false, 'unsupported'); }
    self.busy = true; self.note = 'Waiting for your browser…';
    try {
      navigator.geolocation.getCurrentPosition(function (p) {
        var la = p.coords.latitude, lo = p.coords.longitude;
        if (!isFinite(la) || !isFinite(lo) || Math.abs(la) > 90 || Math.abs(lo) > 180) return fin(false, 'unavailable');
        self.loc = { city: 'Your position', region: '', country: '', lat: la, lon: lo, precise: true };
        fin(true);
      }, function (err) { fin(false, err && err.code === 1 ? 'denied' : err && err.code === 3 ? 'timeout' : 'unavailable'); },
      { maximumAge: 6e5, timeout: 8000 });
    } catch (e) { fin(false, 'unavailable'); }
  };
  Info.prototype.html = function (expanded) {
    var now = new Date(), tz = this.tz, tzName = this.tzName, loc = this.loc, o = '';
    var fmt = function (opt) { try { return new Intl.DateTimeFormat([], opt).format(now); } catch (e) { return ''; } };
    var offMin = -now.getTimezoneOffset(), sign = offMin < 0 ? '-' : '+', a = Math.abs(offMin);
    var utc = 'UTC' + sign + pad(Math.floor(a / 60)) + ':' + pad(a % 60);
    var row = function (k, v) { return '<div class="rl-g-row"><span>' + k + '</span><b>' + v + '</b></div>'; };
    o += '<div class="rl-g-time">' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + '<i>:' + pad(now.getSeconds()) + '</i></div>';
    o += '<div class="rl-g-date">' + fmt({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) + '</div>';
    if (loc) {
      var name = [loc.city, loc.region, loc.country].filter(Boolean).join(', ');
      o += '<div class="rl-g-place">' + name + (loc.precise ? '' : ' <em>approx.</em>') + '</div>';
    } else {
      o += '<div class="rl-g-place">' + tzName.replace(/_/g, ' ') + ' <em>no map position</em></div>';
    }
    o += row('Time zone', tzName.replace(/_/g, ' ')) + row('Offset', utc);
    if (loc) {
      var ns = loc.lat >= 0 ? 'N' : 'S', ew = loc.lon >= 0 ? 'E' : 'W';
      // approximate positions are shown at 2 decimals; only an opted-in precise fix uses more
      var dp = loc.precise ? 3 : 2;
      o += row('Latitude', Math.abs(loc.lat).toFixed(dp) + '° ' + ns) + row('Longitude', Math.abs(loc.lon).toFixed(dp) + '° ' + ew);
      o += row('Hemisphere', (loc.lat >= 0 ? 'Northern' : 'Southern') + ' · ' + (loc.lon >= 0 ? 'Eastern' : 'Western'));
      if (expanded) {
        var s = DATA.sun(loc.lat, loc.lon, now), t = function (x) { return fmt0(x, tz); };
        o += s ? row('Sunrise', t(s.rise)) + row('Sunset', t(s.set)) : row('Sun', 'No sunrise/sunset today');
        if (loc.precise) o += '<div class="rl-g-note">From your device GPS. Not sent anywhere.</div>';
        else o += '<button type="button" class="rl-g-btn" data-precise' + (this.busy ? ' disabled' : '') + '>Use precise location</button>' +
          '<div class="rl-g-note">' + (this.note || 'Asks your browser. Stays on this device.') + '</div>';
      } else o += '<div class="rl-g-note">' + (loc.precise ? '' : 'Approximate, from your time zone. ') + 'Click or tap the marker for more</div>';
    }
    return o;
  };
  function fmt0(date, tz) {
    try { return new Intl.DateTimeFormat([], { hour: '2-digit', minute: '2-digit', timeZoneName: 'short', timeZone: tz }).format(date); } catch (e) { return '—'; }
  }

  w.RLGlobe = { mount: mount, Info: Info, why: WHY, base: BASE, reduce: reduce, pad: pad };
})(window, document);
