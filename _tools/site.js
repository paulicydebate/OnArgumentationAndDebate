// Mobile contents toggle
(function () {
  var btn = document.querySelector('.navtoggle');
  if (btn) {
    btn.addEventListener('click', function () {
      var open = document.body.classList.toggle('nav-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  document.addEventListener('click', function (e) {
    if (document.body.classList.contains('nav-open') && !e.target.closest('.sidebar') && !e.target.closest('.navtoggle')) {
      document.body.classList.remove('nav-open');
      if (btn) btn.setAttribute('aria-expanded', 'false');
    }
  });
})();

// Check questions: instant feedback, nothing stored
document.querySelectorAll('.q').forEach(function (q) {
  var correct = q.getAttribute('data-correct');
  var fb = q.querySelector('.fb');
  q.querySelectorAll('.opt').forEach(function (opt) {
    opt.addEventListener('click', function () {
      q.querySelectorAll('.opt').forEach(function (o) { o.classList.remove('right', 'wrong'); });
      var letter = opt.getAttribute('data-letter');
      var ok = letter === correct;
      opt.classList.add(ok ? 'right' : 'wrong');
      fb.className = 'fb ' + (ok ? 'ok' : 'no');
      fb.innerHTML = '<span class="verdict">' + (ok ? 'Correct.' : 'Not quite.') + '</span>' + (opt.getAttribute('data-fb') || '') +
        (ok ? '' : ' <em>Try another answer.</em>');
    });
  });
});

// Glossary filter
(function () {
  var f = document.getElementById('gfilter');
  if (!f) return;
  f.addEventListener('input', function () {
    var q = f.value.trim().toLowerCase();
    document.querySelectorAll('.gentry').forEach(function (e) {
      var hit = !q || e.textContent.toLowerCase().indexOf(q) !== -1;
      e.hidden = !hit;
    });
    document.querySelectorAll('.gletter').forEach(function (s) {
      s.hidden = !s.querySelector('.gentry:not([hidden])');
    });
  });
})();

// Site search: loads a small index on first use, nothing is sent anywhere
(function () {
  var input = document.getElementById('q'), box = document.getElementById('results');
  if (!input) return;
  var index = null, loading = false, active = -1, pending = null;
  function load(cb) {
    if (index) return cb();
    pending = cb;
    if (loading) return;
    loading = true;
    fetch('search-index.json').then(function (r) { return r.json(); }).then(function (d) {
      index = d.map(function (r) { r.lx = r.x.toLowerCase(); r.ls = (r.s + ' ' + r.t).toLowerCase(); return r; });
      if (pending) pending();
    }).catch(function () { box.hidden = false; box.innerHTML = '<div class="none">Search needs the site to be online.</div>'; });
  }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function snippet(r, words) {
    var i = r.lx.indexOf(words[0]);
    var start = Math.max(0, i - 60);
    if (start > 0) { var sp = r.x.indexOf(' ', start); if (sp !== -1 && sp < i) start = sp + 1; }
    var end = Math.min(r.x.length, start + 180), sp2 = r.x.lastIndexOf(' ', end);
    if (end < r.x.length && sp2 > start + 100) end = sp2;
    var s = r.x.slice(start, end);
    var out = esc((start > 0 ? '… ' : '') + s + (end < r.x.length ? ' …' : ''));
    words.forEach(function (w) {
      if (w.length < 2) return;
      out = out.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>');
    });
    return out;
  }
  function run() {
    var q = input.value.trim().toLowerCase();
    active = -1;
    if (q.length < 2) { box.hidden = true; return; }
    var words = q.split(/\s+/).filter(Boolean);
    var scored = [];
    index.forEach(function (r) {
      var score = 0;
      for (var i = 0; i < words.length; i++) {
        var w = words[i], inT = r.ls.indexOf(w) !== -1, inX = r.lx.indexOf(w) !== -1;
        if (!inT && !inX) return;
        score += (inT ? 5 : 0) + (inX ? 1 : 0);
      }
      if (r.lx.indexOf(q) !== -1) score += 3;
      if (r.ls.indexOf(q) !== -1) score += 6;
      if (r.c === 0 && r.s.toLowerCase() === q) score += 20;
      scored.push([score, r]);
    });
    scored.sort(function (a, b) { return b[0] - a[0]; });
    var top = scored.slice(0, 12);
    box.hidden = false;
    if (!top.length) { box.innerHTML = '<div class="none">No matches for “' + esc(input.value) + '”.</div>'; return; }
    box.innerHTML = top.map(function (p) {
      var r = p[1];
      var where = r.c ? 'Chapter ' + r.c + ' · ' + esc(r.t) + (r.s && r.s !== 'Introduction' ? ' › ' + esc(r.s) : '') : 'Glossary · ' + esc(r.s);
      return '<a href="' + r.u + '"><span class="where">' + where + '</span><span class="snip">' + snippet(r, words) + '</span></a>';
    }).join('');
  }
  input.addEventListener('focus', function () { load(function () {}); });
  input.addEventListener('input', function () { load(run); });
  input.addEventListener('keydown', function (e) {
    var links = box.querySelectorAll('a');
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      if (!links.length) return;
      e.preventDefault();
      active = (active + (e.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
      links.forEach(function (a, i) { a.classList.toggle('active', i === active); });
      links[active].scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      var t = links[active >= 0 ? active : 0];
      if (t) window.location.href = t.getAttribute('href');
    } else if (e.key === 'Escape') {
      box.hidden = true; input.blur();
    }
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('.search')) box.hidden = true; });
})();
