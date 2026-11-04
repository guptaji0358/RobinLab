/* ------------------------------------------------------------------
   links.js — every URL on the site lives here. Edit this file only.

   Nav item   : { label, url, icon }   icon = class name from css/style.css
                (ic-*), e.g. 'ic-image-thin'. Add new SVGs under
                assets/icons/ and register them at the bottom of style.css.
   Social     : { label, url, icon }   shown as icon-only buttons in the nav.
   Contact    : { label, url, icon | img, title }  the Contact section.
   Page links : referenced in HTML as  data-link="pages.collection"
                (dot path into this object). Anything with data-link gets
                its href filled in by js/site.js.
   Hash URLs ("/#about") work from every page.
------------------------------------------------------------------- */
window.RL_LINKS = {
  site: { url: 'https://robinlab.pages.dev' },

  pages: {
    home:          '/',
    projects:      '/#projects',
    collection:    '/collection',
    certificates:  '/certificates',
    presentations: '/presentations',
    music:         '/music',
    skills:        '/skills',
    about:         '/#about',
    contact:       '/#contact'
  },

  /* Header navigation, in order. `url` is a pages.* key or a literal URL. */
  nav: [
    { label: 'Projects',      url: 'pages.projects',      icon: 'ic-grid' },
    { label: 'Collection',    url: 'pages.collection',    icon: 'ic-image-thin' },
    { label: 'Certificates',  url: 'pages.certificates',  icon: 'ic-award' },
    { label: 'Presentations', url: 'pages.presentations', icon: 'ic-presentation' },
    { label: 'Music',         url: 'pages.music',         icon: 'ic-music' },
    { label: 'Claude Skills', url: 'pages.skills',        icon: 'ic-sparkles-thin' },
    { label: 'About',         url: 'pages.about',         icon: 'ic-user' },
    { label: 'Contact',       url: 'pages.contact',       icon: 'ic-mail' }
  ],

  social: {
    github:   { label: 'GitHub',      url: 'https://github.com/guptaji0358',                     icon: 'ic-github' },
    x:        { label: 'X (Twitter)', url: 'https://x.com/RobinGupta0358',                       icon: 'ic-x' },
    linkedin: { label: 'LinkedIn',    url: 'https://www.linkedin.com/in/robin-gupta-25849b36a/', icon: 'ic-linkedin' }
  },

  email: {
    outlook: 'hema82471@outlook.com',
    gmail:   'guptaji0358@gmail.com'
  },

  /* Contact section on the home page, in order. */
  contact: [
    { label: 'Outlook',  url: 'mailto:hema82471@outlook.com',  title: 'hema82471@outlook.com',          img: 'assets/icons/brands/outlook.svg' },
    { label: 'Gmail',    url: 'mailto:guptaji0358@gmail.com',  title: 'guptaji0358@gmail.com',          img: 'assets/icons/brands/gmail.svg' },
    { label: 'GitHub',   url: 'social.github',                 title: 'github.com/guptaji0358',         icon: 'ic-github' },
    { label: 'X',        url: 'social.x',                      title: 'x.com/RobinGupta0358',           img: 'assets/icons/brands/x-brand.svg' },
    { label: 'LinkedIn', url: 'social.linkedin',               title: 'linkedin.com/in/robin-gupta',    img: 'assets/icons/brands/linkedin-brand.svg' }
  ],

  /* Project pages (relative to the site root; spaces URL-encoded). */
  projects: {
    pywix:       'projects/Pywix/index.html',
    codelens:    'projects/CodeLens/index.html',
    contactbook: 'projects/Contact%20Book/index.html',
    motiva:      'projects/Motiva/index.html'
  },

  /* "Email Robin" links; HTML uses data-mail="presentation" etc. */
  mailRequests: {
    presentation: { to: 'hema82471@outlook.com', subject: 'Presentation request' },
    skill:        { to: 'hema82471@outlook.com', subject: 'Claude skill request' }
  }
};
