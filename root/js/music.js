/* BandLab tracks. Add an entry per track: id is the REVISION id, i.e. the id=
   value in BandLab's own embed code. The post id in bandlab.com/post/<id> is not
   the same thing and the embed answers "We can't find that track" for it.
   Look it up with https://www.bandlab.com/api/v1.3/posts/<postId> -> revision.id */
(function () {
  var PROFILE = 'https://www.bandlab.com';
  var TRACKS = [
    { id: '6647d658-b68e-4497-ac60-708d4a41e8a3', title: 'Latest track' },
  ];

  var grid = document.getElementById('music-grid');
  document.getElementById('music-profile').href = PROFILE;
  var y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

  if (!TRACKS.length) {
    grid.innerHTML = '<p class="col-state">New tracks are on the way. Meanwhile, find Robin on BandLab.</p>';
    return;
  }
  TRACKS.forEach(function (t) {
    var card = document.createElement('article');
    var h = document.createElement('h2');
    h.textContent = t.title;
    h.style.fontSize = '1rem';
    var f = document.createElement('iframe');
    f.src = 'https://www.bandlab.com/embed/?id=' + encodeURIComponent(t.id) + '&blur=false';
    f.title = t.title + ' on BandLab';
    f.loading = 'lazy';
    f.allow = 'autoplay';
    f.style.cssText = 'width:100%;height:150px;border:0;border-radius:10px';
    card.append(h, f);
    grid.appendChild(card);
  });
})();
