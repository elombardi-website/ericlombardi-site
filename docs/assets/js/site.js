/* site.js — small progressive enhancements. No frameworks, no tracking. */
(function () {
  // Mobile navigation
  var header = document.querySelector('.site-header');
  var burger = header && header.querySelector('.burger');
  if (burger) {
    burger.addEventListener('click', function () {
      var open = header.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  // Expanders: [data-expander] hides items marked data-extra until "Show all" is clicked
  function expand(key) {
    var box = document.querySelector('[data-expander="' + key + '"]');
    if (!box) return;
    box.querySelectorAll('[data-extra]').forEach(function (el) { el.hidden = false; });
    box.setAttribute('data-expanded', '1');
  }
  document.querySelectorAll('[data-expand-for]').forEach(function (btn) {
    btn.addEventListener('click', function () { expand(btn.getAttribute('data-expand-for')); });
  });

  // Filter chips: [data-filter-group] buttons toggle [data-filter-item] visibility
  document.querySelectorAll('[data-filter-group]').forEach(function (group) {
    var key = group.getAttribute('data-filter-group');
    var items = document.querySelectorAll('[data-filter-item="' + key + '"]');
    group.querySelectorAll('.chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        expand(key);
        group.querySelectorAll('.chip').forEach(function (c) { c.setAttribute('aria-pressed', 'false'); });
        chip.setAttribute('aria-pressed', 'true');
        var want = chip.getAttribute('data-value');
        items.forEach(function (it) {
          var vals = (it.getAttribute('data-values') || '').split(' ');
          it.hidden = !(want === 'all' || vals.indexOf(want) !== -1);
        });
        document.querySelectorAll('[data-year-head="' + key + '"]').forEach(function (h) {
          var sib = h.nextElementSibling, any = false;
          if (sib) sib.querySelectorAll('[data-filter-item]').forEach(function (it) { if (!it.hidden) any = true; });
          h.hidden = !any;
        });
      });
    });
  });

  // Sign-up form: until a list endpoint is configured, fall back to an email to Eric
  document.querySelectorAll('form.signup').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var hp = form.querySelector('.hp input');
      if (hp && hp.value) { e.preventDefault(); return; }
      if (form.getAttribute('data-endpoint')) return;            // native POST to the list tool
      e.preventDefault();
      var fd = new FormData(form), lines = [], name = [];
      fd.forEach(function (v, k) { if (k !== 'website' && v) lines.push(k + ': ' + v); });
      ['first_name', 'name', 'last_name'].forEach(function (k) { if (fd.get(k)) name.push(fd.get(k)); });
      var subject = encodeURIComponent('Sign up: ' + name.join(' '));
      var body = encodeURIComponent(lines.join('\n') + '\n\n(Sent from the ericlombardi.ca sign-up form)');
      window.location.href = 'mailto:' + form.getAttribute('data-mailto') + '?subject=' + subject + '&body=' + body;
      var msg = form.querySelector('.form-msg');
      if (msg) { msg.textContent = 'Thanks. Your email app should open with your details ready to send.'; msg.hidden = false; }
    });
  });

  // Copy-to-clipboard (calendar feed URL)
  document.querySelectorAll('[data-copy]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(btn.getAttribute('data-copy')).then(function () {
        var old = btn.textContent; btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = old; }, 1600);
      });
    });
  });
})();
