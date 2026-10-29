document.getElementById("year").textContent = new Date().getFullYear();

/* Project cards: spotlight follows the pointer */
(function () {
  document.querySelectorAll('.project-card').forEach(function (card) {
    card.addEventListener('pointermove', function (e) {
      var r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      card.style.setProperty('--my', (e.clientY - r.top) + 'px');
    });
  });
})();
