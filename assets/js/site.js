/* site.js — small progressive enhancements. No frameworks, no tracking.
   Hooks are data-* attributes only (data-form, data-expander, data-filter-for, data-copy), never style classes. */
(function () {
  var $ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  // ---- Menu: an overlay below the header with a scrim; the page does not move or scroll behind it.
  var header = document.querySelector('.site-header');
  var burger = header && header.querySelector('.burger');
  if (burger) {
    var inertables = [document.querySelector('main'), document.querySelector('.site-footer')].filter(Boolean);
    var setOpen = function (open, refocus) {
      header.classList.toggle('open', open);
      document.documentElement.classList.toggle('menu-open', open);
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
      inertables.forEach(function (el) { if (open) el.setAttribute('inert', ''); else el.removeAttribute('inert'); });
      if (!open && refocus) burger.focus();
    };
    burger.addEventListener('click', function () { setOpen(!header.classList.contains('open')); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && header.classList.contains('open')) setOpen(false, true); });
    document.addEventListener('click', function (e) { if (header.classList.contains('open') && !header.contains(e.target)) setOpen(false); });
    header.addEventListener('click', function (e) { if (e.target === header) setOpen(false); });
    header.addEventListener('focusout', function (e) { if (header.classList.contains('open') && e.relatedTarget && !header.contains(e.relatedTarget)) setOpen(false); });
    $('nav.mobile a').forEach(function (a) { a.addEventListener('click', function () { setOpen(false); }); });
    window.matchMedia('(min-width:66rem)').addEventListener('change', function (m) { if (m.matches) setOpen(false); });
  }

  // The email address never appears in the page source. It is stored reversed in data-m and
  // assembled here, so simple scrapers do not find it, while real people can still write.
  function addr() { return (document.body.getAttribute('data-m') || '').split('').reverse().join(''); }
  function say(status, text, state) { if (!status) return; status.textContent = text || ''; status.setAttribute('data-state', state || ''); }

  // ---- Lists: one state per list {filter, shown}. Chips filter only their own list; "All" restores the
  // short view; "Show more" adds one batch of the current matches (a remainder of three or fewer comes along).
  $('[data-expander]').forEach(function (box) {
    var key = box.id;
    var limit = parseInt(box.getAttribute('data-limit') || '3', 10);
    var batch = parseInt(box.getAttribute('data-batch') || '10', 10);
    var items = $('[data-item]', box);
    var btn = box.querySelector('[data-expand]');
    var status = box.querySelector('.status');
    var chips = $('[data-filter-for="' + key + '"] [data-filter]');
    var state = { filter: 'all', shown: limit };
    function matches() {
      return items.filter(function (it) { return state.filter === 'all' || (it.getAttribute('data-values') || '').split(' ').indexOf(state.filter) !== -1; });
    }
    function draw() {
      var m = matches();
      items.forEach(function (it) { it.hidden = true; });
      m.slice(0, state.shown).forEach(function (it) { it.hidden = false; });
      $('.year-group', box).forEach(function (g) { g.hidden = !$('[data-item]', g).some(function (it) { return !it.hidden; }); });
      var remaining = Math.max(0, m.length - state.shown);
      if (btn) {
        btn.parentElement.hidden = remaining === 0;
        btn.textContent = (btn.getAttribute('data-template') || 'Show more ({n} more)').replace('{n}', remaining);
      }
      return m;
    }
    if (btn) btn.addEventListener('click', function () {
      var before = matches().slice(0, state.shown).length;
      var total = matches().length;
      state.shown = (total - (state.shown + batch) <= 3) ? total : state.shown + batch;
      var m = draw();
      var first = m[before];
      if (first) { var link = first.querySelector('a'); if (link) link.focus(); }
      if (status) say(status, (status.getAttribute('data-template') || '').replace('{shown}', Math.min(state.shown, m.length)).replace('{total}', m.length));
    });
    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        chips.forEach(function (c) { c.setAttribute('aria-pressed', c === chip ? 'true' : 'false'); });
        state.filter = chip.getAttribute('data-filter');
        state.shown = limit;
        var m = draw();
        if (status) say(status, (status.getAttribute('data-template') || '').replace('{shown}', Math.min(state.shown, m.length)).replace('{total}', m.length));
      });
    });
    draw();
  });

  // ---- Forms: validate here (forms carry novalidate), mark fields, move focus to the first problem.
  function validate(form) {
    var bad = $('input,select,textarea', form).filter(function (el) {
      if (el.type === 'hidden' || el.closest('.hp')) return false;
      var ok = el.checkValidity();
      if (ok) el.removeAttribute('aria-invalid'); else el.setAttribute('aria-invalid', 'true');
      return !ok;
    });
    if (bad.length) { bad[0].focus(); if (bad[0].reportValidity) bad[0].reportValidity(); }
    return bad.length === 0;
  }
  function honeypot(form) { var hp = form.querySelector('.hp input'); return hp && hp.value; }
  // A service can answer 200 and still refuse (Brevo: {success: false, errors: {FIELD: message}}), so read the body too.
  function send(form, endpoint, okText, status, prepare) {
    var btn = form.querySelector('button[type=submit]'); if (btn) btn.disabled = true;
    var body = new FormData(form); body.delete('website');
    return Promise.resolve(prepare && prepare(form, body))
      .then(function () { return fetch(endpoint, { method: 'POST', headers: { 'Accept': 'application/json' }, body: body }); })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (res) {
          if (r.ok && res.success !== false) { form.reset(); say(status, okText, 'sent'); return; }
          var bad = Object.keys(res.errors || {}).map(function (k) { return form.elements[k]; }).filter(Boolean);
          bad.forEach(function (el) { el.setAttribute('aria-invalid', 'true'); });
          if (bad.length) { bad[0].focus(); say(status, form.getAttribute('data-invalid-msg'), 'error'); }
          else say(status, form.getAttribute('data-error-msg'), 'error');
        });
      })
      .catch(function () { say(status, form.getAttribute('data-error-msg'), 'error'); })
      .then(function () { if (btn) btn.disabled = false; });
  }

  // City or postal code, one optional field. A city is sent as typed. A postal code goes to the postal
  // field, and Represent supplies its city and riding; if the lookup fails, the sign-up goes on without them.
  var POSTAL_CODE = /^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d$/i;
  var POSTAL_AREA = /^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z]$/i;
  function titleCase(text) { return text.toLowerCase().replace(/(^|[\s-])\S/g, function (c) { return c.toUpperCase(); }); }
  function place(form, body) {
    var cityField = form.getAttribute('data-city-field'), postalField = form.getAttribute('data-postal-field');
    var typed = (body.get(cityField) || '').trim();
    body.delete(cityField);
    if (!typed) return;
    if (POSTAL_AREA.test(typed)) { body.set(postalField, typed.toUpperCase()); return; }
    if (!POSTAL_CODE.test(typed)) { body.set(cityField, typed); return; }
    var code = typed.toUpperCase().replace(/[ -]/, '');
    body.set(postalField, code.slice(0, 3) + ' ' + code.slice(3));
    var timer = new AbortController();
    setTimeout(function () { timer.abort(); }, 2500);
    return fetch('https://represent.opennorth.ca/postcodes/' + code + '/', { signal: timer.signal })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (found) {
        if (found.city) body.set(cityField, titleCase(found.city));
        var riding = (found.boundaries_centroid || []).concat(found.boundaries_concordance || []).filter(function (b) {
          return ((b.related || {}).boundary_set_url || '').indexOf('/' + form.getAttribute('data-riding-set') + '/') !== -1;
        })[0];
        if (riding) body.set(form.getAttribute('data-riding-field'), riding.name);
      })
      .catch(function () {});
  }

  // Sign-up: with no list endpoint configured this is NOT a working subscription; it opens an
  // email draft so Eric can add the person by hand, and says so plainly.
  $('form[data-form="signup"]').forEach(function (form) {
    var status = form.querySelector('.status');
    form.addEventListener('input', function (e) { if (e.target.getAttribute('aria-invalid') && e.target.checkValidity()) e.target.removeAttribute('aria-invalid'); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (honeypot(form)) return;
      if (!validate(form)) { say(status, form.getAttribute('data-invalid-msg'), 'error'); return; }
      var endpoint = form.getAttribute('data-endpoint');
      if (endpoint) { send(form, endpoint, form.getAttribute('data-sent-msg') || '', status, place); return; }
      var fd = new FormData(form), lines = [], name = [];
      fd.forEach(function (v, k) { if (k !== 'website' && v) lines.push(k + ': ' + v); });
      ['first_name', 'last_name'].forEach(function (k) { if (fd.get(k)) name.push(fd.get(k)); });
      var subject = encodeURIComponent('Sign up: ' + name.join(' '));
      var body = encodeURIComponent(lines.join('\n') + '\n\n(Sent from the ericlombardi.ca sign-up form)');
      window.location.href = 'mailto:' + addr() + '?subject=' + subject + '&body=' + body;
      say(status, form.getAttribute('data-fallback-msg'), 'fallback');
    });
  });

  // Contact: topic from ?topic=, POST to the configured service, or open an email draft.
  $('form[data-form="contact"]').forEach(function (form) {
    var status = form.querySelector('.status');
    var sel = form.querySelector('select[name="topic"]');
    var topic = new URLSearchParams(location.search).get('topic');
    if (topic && sel) Array.prototype.forEach.call(sel.options, function (o) { if (o.value === topic) sel.value = topic; });
    form.addEventListener('input', function (e) { if (e.target.getAttribute('aria-invalid') && e.target.checkValidity()) e.target.removeAttribute('aria-invalid'); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (honeypot(form)) return;
      if (!validate(form)) { say(status, form.getAttribute('data-invalid-msg'), 'error'); return; }
      var endpoint = form.getAttribute('data-endpoint');
      if (endpoint) { send(form, endpoint, form.getAttribute('data-sent'), status); return; }
      var fd = new FormData(form);
      var label = sel ? sel.options[sel.selectedIndex].text : '';
      var subject = encodeURIComponent((label ? label + ': ' : '') + (fd.get('name') || ''));
      var body = encodeURIComponent((fd.get('message') || '') + '\n\n' + (fd.get('name') || '') + '\n' + (fd.get('email') || '') + '\n\n(Sent from the ericlombardi.ca contact form)');
      window.location.href = 'mailto:' + addr() + '?subject=' + subject + '&body=' + body;
      say(status, form.getAttribute('data-fallback'), 'fallback');
    });
  });

  // ---- Copy the calendar address. The label never changes; the result goes to the status line.
  $('[data-copy]').forEach(function (btn) {
    var block = btn.closest('.block') || btn.parentElement;
    var status = block.querySelector('.status');
    var field = block.querySelector('.copy-field');
    function manual() { if (field) { field.hidden = false; field.focus(); field.select(); } say(status, btn.getAttribute('data-manual')); }
    btn.addEventListener('click', function () {
      if (!navigator.clipboard) { manual(); return; }
      navigator.clipboard.writeText(btn.getAttribute('data-copy')).then(function () { say(status, btn.getAttribute('data-copied')); }).catch(manual);
    });
  });
})();
