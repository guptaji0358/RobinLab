/* site.js — builds the header nav, contact list and every [data-link] /
   [data-mail] href from js/links.js. Runs before first paint of the body
   content below the header (loaded at the end of <body>, before fx.js). */
(function () {
  var L = window.RL_LINKS;
  if (!L) return;

  function dig(path) {
    return path.split('.').reduce(function (o, k) { return o == null ? o : o[k]; }, L);
  }
  /* "pages.about" -> "/#about"; "social.x" -> object url; literal URLs pass through. */
  function resolve(ref) {
    var v = /^[a-z]+\.[a-zA-Z]+$/.test(ref) ? dig(ref) : null;
    if (v == null) return ref;
    return typeof v === 'string' ? v : v.url;
  }
  var path = location.pathname.replace(/\/index\.html$/, '/').replace(/\.html$/, '');
  function local(url) {                       // on the home page "/#x" -> "#x" (smooth in-page jump)
    return path === '/' && url.indexOf('/#') === 0 ? url.slice(1) : url;
  }
  function el(tag, cls, attrs) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    for (var k in attrs || {}) n.setAttribute(k, attrs[k]);
    return n;
  }
  function icon(cls, extra) { return el('span', 'ic icon ' + cls + (extra ? ' ' + extra : ''), { 'aria-hidden': 'true' }); }

  /* Header nav */
  var nav = document.querySelector('.site-nav');
  if (nav) {
    nav.textContent = '';
    L.nav.forEach(function (item) {
      var url = resolve(item.url);
      var a = el('a', 'nav-link', { href: local(url) });
      if (item.icon) a.appendChild(icon(item.icon, 'nav-ic'));
      a.appendChild(document.createTextNode(item.label));
      if (url.split('#')[0] === path && url.indexOf('#') < 0 && path !== '/') a.setAttribute('aria-current', 'page');
      nav.appendChild(a);
    });
    var soc = el('span', 'nav-social');
    Object.keys(L.social).forEach(function (k) {
      var s = L.social[k];
      var a = el('a', 'icon-link', { href: s.url, target: '_blank', rel: 'noopener', 'aria-label': s.label, title: s.label });
      a.appendChild(icon(s.icon));
      soc.appendChild(a);
    });
    nav.appendChild(soc);
  }

  /* Contact section */
  var box = document.querySelector('.contact-links');
  if (box) {
    box.textContent = '';
    L.contact.forEach(function (c) {
      var url = resolve(c.url);
      var ext = /^https?:/.test(url);
      var a = el('a', 'contact-link', { href: url, title: c.title || c.label });
      if (ext) { a.target = '_blank'; a.rel = 'noopener'; }
      if (c.img) a.appendChild(el('img', 'icon brand-icon', { src: c.img, alt: c.label }));
      else a.appendChild(icon(c.icon));
      a.appendChild(document.createTextNode('\n        ' + c.label + '\n      '));
      box.appendChild(a);
    });
  }

  /* [data-link="pages.collection"] and [data-link="projects.pywix"] */
  document.querySelectorAll('[data-link]').forEach(function (n) {
    var v = dig(n.getAttribute('data-link'));
    if (v == null) return;
    n.setAttribute('href', local(typeof v === 'string' ? v : v.url));
  });

  /* [data-mail="presentation"] */
  document.querySelectorAll('[data-mail]').forEach(function (n) {
    var m = L.mailRequests && L.mailRequests[n.getAttribute('data-mail')];
    if (m) n.setAttribute('href', 'mailto:' + m.to + '?subject=' + encodeURIComponent(m.subject));
  });
})();
