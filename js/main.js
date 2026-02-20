const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ── Nav scroll (works on index + resume/cover pages) ───────────────────── */
const nav = document.getElementById('main-nav') || document.getElementById('nav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 60);
  }, { passive: true });
}

/* ── Mobile nav (supports both nav variants) ─────────────────────────────── */
const burger = document.getElementById('navBurger') || document.getElementById('navHamburger');
const mobileNav = document.getElementById('navMobile');
if (burger && mobileNav) {
  burger.addEventListener('click', () => {
    burger.classList.toggle('open');
    mobileNav.classList.toggle('open');
  });
  document.querySelectorAll('.nav__mobile-link, .nav-mobile-link').forEach(link => {
    link.addEventListener('click', () => {
      burger.classList.remove('open');
      mobileNav.classList.remove('open');
    });
  });
}

/* ── Smooth scroll (ignore placeholder '#') ──────────────────────────────── */
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  const href = anchor.getAttribute('href');
  if (!href || href === '#') return;
  const target = document.querySelector(href);
  if (!target) return;
  anchor.addEventListener('click', event => {
    event.preventDefault();
    target.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
  });
});

/* ── Scroll progress bar ─────────────────────────────────────────────────── */
const pgBar = document.createElement('div');
pgBar.style.cssText = [
  'position:fixed', 'top:0', 'left:0', 'height:2px', 'z-index:9999',
  'background:var(--accent)', 'width:0%',
  'transition:width .1s linear', 'pointer-events:none'
].join(';');
document.body.appendChild(pgBar);
window.addEventListener('scroll', () => {
  const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
  const pct = maxScroll > 0 ? (window.scrollY / maxScroll) * 100 : 0;
  pgBar.style.width = `${pct}%`;
}, { passive: true });

/* ── Scroll reveal ───────────────────────────────────────────────────────── */
const revealEls = document.querySelectorAll('.reveal, .reveal-stagger');
if (prefersReducedMotion) {
  revealEls.forEach(el => el.classList.add('visible'));
} else {
  const revealObs = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('visible');
      revealObs.unobserve(entry.target);
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -40px 0px'
  });
  revealEls.forEach(el => revealObs.observe(el));
}

/* ── Scroll-linked parallax (new) ───────────────────────────────────────── */
const parallaxEls = document.querySelectorAll('[data-scroll-speed]');
if (!prefersReducedMotion && parallaxEls.length) {
  let ticking = false;
  const updateParallax = () => {
    const vh = window.innerHeight;
    parallaxEls.forEach(el => {
      const speed = parseFloat(el.getAttribute('data-scroll-speed')) || 0.08;
      const rect = el.getBoundingClientRect();
      const centerDelta = (vh / 2) - (rect.top + rect.height / 2);
      const shift = centerDelta * speed;
      el.style.setProperty('--scroll-shift', `${shift.toFixed(2)}px`);
    });
    ticking = false;
  };
  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(updateParallax);
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  updateParallax();
}

/* ── Hero stat counters ──────────────────────────────────────────────────── */
function setCounterValue(el, rawValue, suffix) {
  const formatted = rawValue >= 1000 ? rawValue.toLocaleString() : String(rawValue);
  el.textContent = `${formatted}${suffix || ''}`;
}

function animateCounter(el) {
  const target = parseFloat(el.dataset.target);
  const suffix = el.dataset.suffix || '';
  const durationMs = 1600;
  const startTime = performance.now();

  (function frame(now) {
    const progress = Math.min((now - startTime) / durationMs, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const value = Math.round(target * eased);
    setCounterValue(el, value, suffix);
    if (progress < 1) requestAnimationFrame(frame);
  })(startTime);
}

const statEls = document.querySelectorAll('.hero__stat-number[data-target]');
if (statEls.length) {
  if (prefersReducedMotion) {
    statEls.forEach(el => {
      const target = parseFloat(el.dataset.target);
      const suffix = el.dataset.suffix || '';
      setCounterValue(el, target, suffix);
    });
  } else {
    const statObs = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        animateCounter(entry.target);
        statObs.unobserve(entry.target);
      });
    }, { threshold: 0.5 });
    statEls.forEach(el => statObs.observe(el));
  }
}
