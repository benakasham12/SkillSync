// SkillSync Client-Side Helpers

document.addEventListener('DOMContentLoaded', () => {
  // 1. Auto-dismiss alerts after 6 seconds
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s ease';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });

  // 2. Mobile Navigation Toggle
  const navToggle = document.getElementById('navToggle');
  const navCollapse = document.getElementById('navCollapse');

  if (navToggle && navCollapse) {
    navToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = navCollapse.classList.toggle('show');
      navToggle.classList.toggle('open', isOpen);
      navToggle.setAttribute('aria-expanded', isOpen);
    });

    // Close mobile nav when clicking any nav item
    const navItems = navCollapse.querySelectorAll('.nav-item, .btn');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        navCollapse.classList.remove('show');
        navToggle.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });

    // Close mobile nav when clicking anywhere outside
    document.addEventListener('click', (e) => {
      if (!navCollapse.contains(e.target) && !navToggle.contains(e.target)) {
        navCollapse.classList.remove('show');
        navToggle.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }
});
