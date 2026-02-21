const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const isCoarsePointer = window.matchMedia('(pointer: coarse)').matches;
const lowCoreDevice = typeof navigator.hardwareConcurrency === 'number' && navigator.hardwareConcurrency <= 4;
const performanceMode = prefersReducedMotion || isCoarsePointer || lowCoreDevice;

if (performanceMode) {
  document.body.classList.add('performance-mode');
}

const nav = document.getElementById('main-nav') || document.getElementById('nav');

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

/* ── Unified scroll pipeline (nav + progress + parallax) ────────────────── */
const pgBar = document.createElement('div');
pgBar.style.cssText = [
  'position:fixed', 'top:0', 'left:0', 'height:2px', 'z-index:9999',
  'background:var(--accent)', 'width:0%', 'pointer-events:none'
].join(';');
document.body.appendChild(pgBar);

const parallaxItems = !performanceMode
  ? Array.from(document.querySelectorAll('[data-scroll-speed]')).map(el => ({
      el,
      speed: parseFloat(el.getAttribute('data-scroll-speed')) || 0.08,
      centerY: 0,
    }))
  : [];

const scrollState = {
  ticking: false,
  vh: window.innerHeight,
  maxScroll: Math.max(document.documentElement.scrollHeight - window.innerHeight, 1),
};

function recalcScrollMetrics() {
  scrollState.vh = window.innerHeight;
  scrollState.maxScroll = Math.max(document.documentElement.scrollHeight - scrollState.vh, 1);
  if (!parallaxItems.length) return;
  const y = window.scrollY;
  parallaxItems.forEach(item => {
    const rect = item.el.getBoundingClientRect();
    item.centerY = rect.top + y + rect.height / 2;
  });
}

function updateScrollEffects() {
  const y = window.scrollY;

  if (nav) {
    nav.classList.toggle('scrolled', y > 60);
  }

  const pct = Math.min(100, Math.max(0, (y / scrollState.maxScroll) * 100));
  pgBar.style.width = `${pct}%`;

  if (parallaxItems.length) {
    const viewCenter = y + scrollState.vh * 0.5;
    parallaxItems.forEach(item => {
      const shift = (viewCenter - item.centerY) * item.speed;
      item.el.style.setProperty('--scroll-shift', `${shift.toFixed(2)}px`);
    });
  }

  scrollState.ticking = false;
}

function scheduleScrollEffects() {
  if (scrollState.ticking) return;
  scrollState.ticking = true;
  requestAnimationFrame(updateScrollEffects);
}

window.addEventListener('scroll', scheduleScrollEffects, { passive: true });
window.addEventListener('resize', () => {
  recalcScrollMetrics();
  scheduleScrollEffects();
});
window.addEventListener('orientationchange', () => {
  recalcScrollMetrics();
  scheduleScrollEffects();
});

recalcScrollMetrics();
scheduleScrollEffects();

/* ── Scroll reveal ───────────────────────────────────────────────────────── */
const revealEls = document.querySelectorAll('.reveal, .reveal-stagger');
if (performanceMode) {
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
  if (performanceMode) {
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
