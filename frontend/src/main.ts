// Landing page interactions

document.addEventListener('DOMContentLoaded', () => {
  // Wire all CTAs that go to the dashboard
  const ctas = document.querySelectorAll<HTMLButtonElement | HTMLAnchorElement>(
    '[data-action="goto-dashboard"]'
  );
  ctas.forEach((el) => {
    el.addEventListener('click', () => {
      window.location.href = '/dashboard.html';
    });
  });

  // Smooth scroll for nav links
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      const target = document.querySelector((a as HTMLAnchorElement).getAttribute('href') ?? '');
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
});
