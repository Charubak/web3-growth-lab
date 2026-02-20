/* ── Nav scroll ─────────────────────────────────────────────────────────── */
const nav = document.getElementById('main-nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 60);
}, { passive: true });

/* ── Mobile nav ─────────────────────────────────────────────────────────── */
const burger   = document.getElementById('navBurger');
const mobileNav = document.getElementById('navMobile');
burger.addEventListener('click', () => {
  burger.classList.toggle('open');
  mobileNav.classList.toggle('open');
});
document.querySelectorAll('.nav__mobile-link').forEach(l =>
  l.addEventListener('click', () => {
    burger.classList.remove('open');
    mobileNav.classList.remove('open');
  })
);

/* ── Smooth scroll ───────────────────────────────────────────────────────── */
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

/* ── Scroll progress bar ─────────────────────────────────────────────────── */
const pgBar = document.createElement('div');
pgBar.style.cssText = [
  'position:fixed','top:0','left:0','height:2px','z-index:9999',
  'background:var(--accent)','width:0%',
  'transition:width .1s linear','pointer-events:none'
].join(';');
document.body.appendChild(pgBar);
window.addEventListener('scroll', () => {
  const pct = (window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100 || 0;
  pgBar.style.width = pct + '%';
}, { passive: true });

/* ═══════════════════════════════════════════════════════════════════════════
   SCROLL REVEAL
   Elements with class .reveal start hidden via CSS.
   IntersectionObserver adds .visible → CSS transition plays.
   This is the most reliable approach: the browser sees the class change
   as a distinct mutation and always fires the transition.
   ═══════════════════════════════════════════════════════════════════════════ */
const revealObs = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    entry.target.classList.add('visible');
    revealObs.unobserve(entry.target);
  });
}, {
  threshold:   0.1,
  rootMargin: '0px 0px -40px 0px'
});

document.querySelectorAll('.reveal, .reveal-stagger').forEach(el => revealObs.observe(el));

/* ═══════════════════════════════════════════════════════════════════════════
   HERO STAT COUNTERS
   ═══════════════════════════════════════════════════════════════════════════ */
function animateCounter(el) {
  const target   = parseFloat(el.dataset.target);
  const suffix   = el.dataset.suffix || '';
  const dur      = 1600;
  const t0       = performance.now();

  (function frame(now) {
    const p     = Math.min((now - t0) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    const v     = Math.round(target * eased);

    /* Format: 2500 → "2,500" ; else plain */
    const formatted = v >= 1000 ? v.toLocaleString() : String(v);
    el.innerHTML = formatted + (suffix ? `<span>${suffix}</span>` : '');

    if (p < 1) requestAnimationFrame(frame);
  })(t0);
}

const statObs = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      animateCounter(e.target);
      statObs.unobserve(e.target);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('.hero__stat-number[data-target]').forEach(el => statObs.observe(el));
