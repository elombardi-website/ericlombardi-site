/* site.js — small progressive enhancements. No frameworks, no tracking. */
(function () {
  var header = document.querySelector('.site-header');
  var burger = header && header.querySelector('.burger');
  if (burger) {
    burger.addEventListener('click', function () {
      var open = header.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && header.classList.contains('open')) {
        header.classList.remove('open'); burger.setAttribute('aria-expanded', 'false'); burger.focus();
      }
    });
  }

  // Expanders: items marked data-extra are hidden; "Show more" reveals the next batch (or all).
  function tidyYearHeads(box) {
    box.querySelectorAll('[data-year-head]').forEach(function (h) {
      var list = h.nextElementSibling, any = false;
      if (list) list.querySelectorAll('li').forEach(function (li) { if (!li.hidden) any = true; });
      h.hidden = !any;
    });
  }
  function reveal(key, count) {
    var box = document.querySelector('[data-expander="' + key + '"]');
    if (!box) return;
    var hidden = Array.prototype.slice.call(box.querySelectorAll('[data-extra]')).filter(function (el) { return el.hidden && el.tagName === 'LI'; });
    (count ? hidden.slice(0, count) : hidden).forEach(function (el) { el.hidden = false; });
    tidyYearHeads(box);
    var remaining = box.querySelectorAll('li[data-extra][hidden]').length;
    var btn = box.querySelector('[data-expand-for]');
    if (btn) {
      if (remaining === 0) { box.setAttribute('data-expanded', '1'); }
      else btn.textContent = 'Show more (' + remaining + ' more)';
    }
  }
  function expandAll(key) { reveal(key, 0); }
  document.querySelectorAll('[data-expand-for]').forEach(function (btn) {
    btn.addEventListener('click', function () { reveal(btn.getAttribute('data-expand-for'), parseInt(btn.getAttribute('data-batch') || '0', 10)); });
  });

  // Filter chips refine one list; filtering reveals everything first so nothing is hidden twice.
  document.querySelectorAll('[data-filter-group]').forEach(function (group) {
    var key = group.getAttribute('data-filter-group');
    var items = document.querySelectorAll('[data-filter-item="' + key + '"]');
    group.querySelectorAll('.chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        expandAll(key);
        group.querySelectorAll('.chip').forEach(function (c) { c.setAttribute('aria-pressed', 'false'); });
        chip.setAttribute('aria-pressed', 'true');
        var want = chip.getAttribute('data-value');
        items.forEach(function (it) {
          var vals = (it.getAttribute('data-values') || '').split(' ');
          it.hidden = !(want === 'all' || vals.indexOf(want) !== -1);
        });
        var box = document.querySelector('[data-expander="' + key + '"]');
        if (box) tidyYearHeads(box);
      });
    });
  });

  // Sign-up form: with no list endpoint configured this is NOT a working subscription; it opens an
  // email draft so Eric can add the person by hand, and says so plainly.
  document.querySelectorAll('form.signup').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var hp = form.querySelector('.hp input');
      if (hp && hp.value) { e.preventDefault(); return; }
      if (form.getAttribute('data-endpoint')) return;
      e.preventDefault();
      if (!form.checkValidity()) { form.reportValidity(); return; }
      var fd = new FormData(form), lines = [], name = [];
      fd.forEach(function (v, k) { if (k !== 'website' && v) lines.push(k + ': ' + v); });
      ['first_name', 'name', 'last_name'].forEach(function (k) { if (fd.get(k)) name.push(fd.get(k)); });
      var subject = encodeURIComponent('Sign up: ' + name.join(' '));
      var body = encodeURIComponent(lines.join('\n') + '\n\n(Sent from the ericlombardi.ca sign-up form)');
      window.location.href = 'mailto:' + form.getAttribute('data-mailto') + '?subject=' + subject + '&body=' + body;
      var msg = form.querySelector('.form-msg');
      if (msg) { msg.textContent = 'The sign-up list is not connected yet. Your email app should open with your details so I can add you by hand. If it did not open, email ' + form.getAttribute('data-mailto') + '.'; msg.hidden = false; }
    });
  });

  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(btn.getAttribute('data-copy')).then(function () {
        var old = btn.textContent; btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = old; }, 1600);
      });
    });
  });
})();
