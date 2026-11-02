/* BandLab tracks. Add an entry per track: id is the post id from the BandLab
   share link (bandlab.com/post/<id>) or the id= value in its embed code. */
(function () {
  var PROFILE = 'https://www.bandlab.com';
  var TRACKS = [
    { id: '0ba28048-e18b-4dc6-b198-87a91aa31990', title: 'Latest track' },
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
    f.src = 'https://www.bandlab.com/embed/?id=' + encodeURIComponent(t.id);
    f.title = t.title + ' on BandLab';
    f.loading = 'lazy';
    f.allow = 'autoplay';
    f.style.cssText = 'width:100%;height:150px;border:0;border-radius:10px';
    card.append(h, f);
    grid.appendChild(card);
  });
})();
