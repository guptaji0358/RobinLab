/* Tracks. id is the BandLab REVISION id (the id= value in BandLab's embed code,
   not the post id in bandlab.com/post/<id>).
   src (optional) is a direct audio URL (mp3/m4a). With src the custom player is
   used: play/pause, prev/next, seek bar. Without it the BandLab embed is loaded
   on Play instead, because a cross-origin iframe can't be controlled from here. */
(function () {
  var PROFILE = 'https://www.bandlab.com';
  var TRACKS = [
    { id: '6647d658-b68e-4497-ac60-708d4a41e8a3', title: 'Latest track', src: '' },
  ];

  var grid = document.getElementById('music-grid');
  document.getElementById('music-profile').href = PROFILE;
  var y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

  if (!TRACKS.length) {
    grid.innerHTML = '<p class="col-state">New tracks are on the way. Meanwhile, find Robin on BandLab.</p>';
    return;
  }

  function fmt(s) {
    if (!isFinite(s)) return '0:00';
    return Math.floor(s / 60) + ':' + ('0' + Math.floor(s % 60)).slice(-2);
  }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  var audio = new Audio();
  audio.preload = 'none';
  var current = -1;
  var cards = [];

  function hideControls(c) {
    c.root.classList.remove('is-active', 'is-playing');
    c.play.textContent = '▶';
    c.play.setAttribute('aria-label', 'Play');
    c.seek.value = 0;
    c.cur.textContent = '0:00';
    if (c.frame) { c.frame.remove(); c.frame = null; }
  }
  function stopAll() {
    audio.pause();
    cards.forEach(hideControls);
    current = -1;
  }

  function load(i, autoplay) {
    cards.forEach(function (c, j) { if (j !== i) hideControls(c); });
    var c = cards[i];
    current = i;
    c.root.classList.add('is-active');
    if (!c.track.src) {
      audio.pause();
      c.frame = el('iframe');
      c.frame.src = 'https://www.bandlab.com/embed/?id=' + encodeURIComponent(c.track.id) + '&blur=false';
      c.frame.title = c.track.title + ' on BandLab';
      c.frame.allow = 'autoplay';
      c.embed.appendChild(c.frame);
      return;
    }
    audio.src = c.track.src;
    c.total.textContent = '0:00';
    if (autoplay) audio.play().catch(function () {});
  }

  function step(dir) {
    var next = current + dir;
    if (next < 0 || next >= cards.length) return;
    load(next, true);
  }

  audio.addEventListener('play', function () {
    if (current < 0) return;
    cards[current].root.classList.add('is-playing');
    cards[current].play.textContent = '❚❚';
    cards[current].play.setAttribute('aria-label', 'Pause');
  });
  audio.addEventListener('pause', function () {
    if (current < 0) return;
    cards[current].root.classList.remove('is-playing');
    cards[current].play.textContent = '▶';
    cards[current].play.setAttribute('aria-label', 'Play');
  });
  audio.addEventListener('loadedmetadata', function () {
    if (current >= 0) {
      cards[current].total.textContent = fmt(audio.duration);
      cards[current].seek.max = audio.duration;
    }
  });
  audio.addEventListener('timeupdate', function () {
    if (current < 0 || cards[current].dragging) return;
    cards[current].seek.value = audio.currentTime;
    cards[current].cur.textContent = fmt(audio.currentTime);
  });
  audio.addEventListener('ended', function () {
    /* Song finished: controls go away. */
    if (current >= 0) hideControls(cards[current]);
    current = -1;
  });
  /* Switching browser tabs pauses the song and removes the controls. */
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stopAll();
  });
  window.addEventListener('pagehide', stopAll);

  TRACKS.forEach(function (t, i) {
    var root = el('article', 'pr-card mu-card');
    var title = el('h2', 'mu-title', t.title);
    var btn = el('button', 'mu-big', '▶ Play');
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Play ' + t.title);

    var controls = el('div', 'mu-controls');
    var prev = el('button', 'mu-btn', '⏮'); prev.type = 'button'; prev.setAttribute('aria-label', 'Previous');
    var play = el('button', 'mu-btn mu-btn-main', '▶'); play.type = 'button'; play.setAttribute('aria-label', 'Play');
    var next = el('button', 'mu-btn', '⏭'); next.type = 'button'; next.setAttribute('aria-label', 'Next');
    var cur = el('span', 'mu-time', '0:00');
    var seek = el('input', 'mu-seek');
    seek.type = 'range'; seek.min = 0; seek.max = 0; seek.step = 'any'; seek.value = 0;
    seek.setAttribute('aria-label', 'Seek');
    var total = el('span', 'mu-time', '0:00');
    controls.append(prev, play, next, cur, seek, total);

    var embed = el('div', 'mu-embed');
    root.append(title, btn, embed, controls);
    grid.appendChild(root);

    var c = { root: root, track: t, play: play, seek: seek, cur: cur, total: total, embed: embed, frame: null, dragging: false };
    cards.push(c);

    btn.addEventListener('click', function () { load(i, true); });
    play.addEventListener('click', function () {
      if (audio.paused) audio.play().catch(function () {}); else audio.pause();
    });
    prev.addEventListener('click', function () {
      if (audio.currentTime > 3 || i === 0) audio.currentTime = 0; else step(-1);
    });
    next.addEventListener('click', function () {
      if (i + 1 < cards.length) step(1); else audio.currentTime = audio.duration || 0;
    });
    seek.addEventListener('input', function () {
      c.dragging = true;
      cur.textContent = fmt(+seek.value);
    });
    seek.addEventListener('change', function () {
      audio.currentTime = +seek.value;
      c.dragging = false;
    });
  });
})();
