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
