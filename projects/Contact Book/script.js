  /* ---------- theme toggle: light / dark, animated ---------- */
  (function(){
    const root = document.documentElement;
    const toggle = document.getElementById('themeToggle');
    const stored = localStorage.getItem('cb-theme');
    const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
    let theme = stored || (prefersLight ? 'light' : 'dark');
    root.setAttribute('data-theme', theme);
    let switching = false;

    function apply(next, evt){
      if(switching) return;
      const doSwitch = () => {
        theme = next;
        root.setAttribute('data-theme', theme);
        localStorage.setItem('cb-theme', theme);
      };
      if(document.startViewTransition && !window.matchMedia('(prefers-reduced-motion: reduce)').matches){
        switching = true;
        const x = evt ? evt.clientX : window.innerWidth / 2;
        const y = evt ? evt.clientY : 0;
        const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
        const transition = document.startViewTransition(doSwitch);
        transition.ready.then(()=>{
          document.documentElement.animate(
            { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
            { duration: 550, easing: 'ease-in-out', pseudoElement: '::view-transition-new(root)' }
          );
        }).catch(()=>{});
        transition.finished.finally(()=>{ switching = false; });
      } else {
        doSwitch();
      }
    }

    toggle.addEventListener('click', (e)=> apply(theme === 'dark' ? 'light' : 'dark', e));
  })();

  const links = document.querySelectorAll('.rail-tabs a');
  const targets = [...links].map(a => document.querySelector(a.getAttribute('href')));
  const io = new IntersectionObserver((entries)=>{
    entries.forEach(e=>{
      if(e.isIntersecting){
        const id = '#'+e.target.id;
        links.forEach(a=> a.classList.toggle('active', a.getAttribute('href')===id));
      }
    });
  }, { rootMargin: '-40% 0px -50% 0px' });
  targets.forEach(t=> t && io.observe(t));

  /* ---------- live demo: view / add / edit / delete ---------- */
  (function(){
    const ICON_VIEW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>';
    const ICON_EDIT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>';
    const ICON_DELETE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/></svg>';

    let contacts = [
      { id: 1, name: 'Naruto Uzumaki', phone: '+81 90-1234-5678', email: 'naruto@leaf.com' },
      { id: 2, name: 'Gojo Satoru',    phone: '+81 90-1234-5679', email: 'gojo@jujutsu.com' },
      { id: 3, name: 'Itachi Uchiha',  phone: '+81 90-5555-1234', email: '' },
    ];
    let nextId = 4;
    let editingId = null;
    let lastDeleted = null; // { contact, index }
    let undoTimer = null;

    const rowsEl = document.getElementById('demoRows');
    const countEl = document.getElementById('demoCount');
    const formEl = document.getElementById('demoForm');
    const addBtn = document.getElementById('demoAddBtn');
    const cancelBtn = document.getElementById('demoCancelBtn');
    const nameField = document.getElementById('dfName');
    const phoneField = document.getElementById('dfPhone');
    const emailField = document.getElementById('dfEmail');
    const overlay = document.getElementById('demoOverlay');
    const detailCard = document.getElementById('demoDetailCard');
    const closeBtn = document.getElementById('demoCloseBtn');
    const toast = document.getElementById('demoToast');
    const toastMsg = document.getElementById('demoToastMsg');
    const undoBtn = document.getElementById('demoUndoBtn');

    function initials(name){
      const parts = name.trim().split(/\s+/);
      return ((parts[0]?.[0]||'') + (parts[1]?.[0]||'')).toUpperCase() || '?';
    }

    function render(){
      countEl.textContent = contacts.length + (contacts.length === 1 ? ' contact' : ' contacts');

      if(contacts.length === 0){
        rowsEl.innerHTML = '<li class="demo-empty">No contacts left. <a id="demoEmptyAdd">Add one</a> to bring the book back to life.</li>';
        document.getElementById('demoEmptyAdd').addEventListener('click', openAddForm);
        return;
      }

      rowsEl.innerHTML = contacts.map(c => `
        <li class="demo-row" data-id="${c.id}">
          <div class="initial">${initials(c.name)}</div>
          <div class="who">
            <div class="name">${escapeHtml(c.name)}</div>
            <div class="sub">${escapeHtml(c.phone)}${c.email ? ' · ' + escapeHtml(c.email) : ''}</div>
          </div>
          <div class="actions">
            <button class="btn-icon" data-action="view" title="View">${ICON_VIEW}</button>
            <button class="btn-icon" data-action="edit" title="Edit">${ICON_EDIT}</button>
            <button class="btn-icon danger" data-action="delete" title="Delete">${ICON_DELETE}</button>
          </div>
        </li>
      `).join('');
    }

    function escapeHtml(s){
      return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    function clearErrors(){
      [nameField, phoneField, emailField].forEach(f => {
        f.closest('.field').classList.remove('err');
        f.closest('.field').querySelector('.errmsg').textContent = '';
      });
    }

    function setError(field, msg){
      field.closest('.field').classList.add('err');
      field.closest('.field').querySelector('.errmsg').textContent = msg;
    }

    function openAddForm(){
      editingId = null;
      nameField.value = '';
      phoneField.value = '';
      emailField.value = '';
      clearErrors();
      formEl.hidden = false;
      document.getElementById('demoSaveBtn').textContent = 'Save contact';
      nameField.focus();
    }

    function openEditForm(id){
      const c = contacts.find(x => x.id === id);
      if(!c) return;
      editingId = id;
      nameField.value = c.name;
      phoneField.value = c.phone;
      emailField.value = c.email || '';
      clearErrors();
      formEl.hidden = false;
      document.getElementById('demoSaveBtn').textContent = 'Save changes';
      nameField.focus();
    }

    function closeForm(){
      formEl.hidden = true;
      editingId = null;
      clearErrors();
    }

    function openView(id){
      const c = contacts.find(x => x.id === id);
      if(!c) return;
      detailCard.innerHTML = `
        <button class="close" id="demoCloseBtn" type="button" aria-label="Close">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
        <div class="initial">${initials(c.name)}</div>
        <h4>${escapeHtml(c.name)}</h4>
        <div class="detail-row"><span class="k">Phone</span><span class="v">${escapeHtml(c.phone)}</span></div>
        <div class="detail-row"><span class="k">Email</span><span class="v">${escapeHtml(c.email || '—')}</span></div>
        <div class="detail-row"><span class="k">Book</span><span class="v">demo (session only)</span></div>
      `;
      detailCard.querySelector('.close').addEventListener('click', closeView);
      overlay.classList.add('open');
    }
    function closeView(){ overlay.classList.remove('open'); }

    function showToast(msg){
      toastMsg.textContent = msg;
      toast.classList.add('show');
      clearTimeout(undoTimer);
      undoTimer = setTimeout(()=>{ toast.classList.remove('show'); lastDeleted = null; }, 5000);
    }

    function deleteContact(id){
      const index = contacts.findIndex(x => x.id === id);
      if(index === -1) return;
      lastDeleted = { contact: contacts[index], index };
      contacts.splice(index, 1);
      render();
      showToast(`"${lastDeleted.contact.name}" deleted.`);
    }

    function undoDelete(){
      if(!lastDeleted) return;
      const { contact, index } = lastDeleted;
      contacts.splice(Math.min(index, contacts.length), 0, contact);
      lastDeleted = null;
      clearTimeout(undoTimer);
      toast.classList.remove('show');
      render();
    }

    function validatePhone(v){ return /^[0-9+\-\s()]{5,}$/.test(v); }
    function validateEmail(v){ return v === '' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); }

    formEl.addEventListener('submit', (e)=>{
      e.preventDefault();
      clearErrors();
      const name = nameField.value.trim();
      const phone = phoneField.value.trim();
      const email = emailField.value.trim();
      let ok = true;

      if(!name){ setError(nameField, 'Name cannot be empty.'); ok = false; }
      if(!phone){ setError(phoneField, 'Phone number cannot be empty.'); ok = false; }
      else if(!validatePhone(phone)){ setError(phoneField, 'Digits, spaces, + and - only.'); ok = false; }
      if(!validateEmail(email)){ setError(emailField, 'That doesn’t look like an email.'); ok = false; }

      if(!ok) return;

      if(editingId === null){
        contacts.push({ id: nextId++, name, phone, email });
      } else {
        const c = contacts.find(x => x.id === editingId);
        if(c){ c.name = name; c.phone = phone; c.email = email; }
      }
      closeForm();
      render();
    });

    addBtn.addEventListener('click', ()=> formEl.hidden ? openAddForm() : closeForm());
    cancelBtn.addEventListener('click', closeForm);
    closeBtn.addEventListener('click', closeView);
    overlay.addEventListener('click', (e)=>{ if(e.target === overlay) closeView(); });
    document.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') closeView(); });
    undoBtn.addEventListener('click', undoDelete);

    rowsEl.addEventListener('click', (e)=>{
      const btn = e.target.closest('button[data-action]');
      if(!btn) return;
      const id = Number(btn.closest('.demo-row').dataset.id);
      const action = btn.dataset.action;
      if(action === 'view') openView(id);
      else if(action === 'edit') openEditForm(id);
      else if(action === 'delete') deleteContact(id);
    });

    render();
  })();
