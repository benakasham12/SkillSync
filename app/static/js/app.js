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

  // 2. GitHub-Style Slide-Out Sidebar Navigation
  const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
  const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');
  const githubSidebar = document.getElementById('githubSidebar');

  const openSidebar = () => {
    if (!githubSidebar) return;
    githubSidebar.classList.add('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('is-visible');
    document.body.classList.add('sidebar-lock-scroll');
    if (sidebarToggleBtn) sidebarToggleBtn.setAttribute('aria-expanded', 'true');
    githubSidebar.setAttribute('aria-hidden', 'false');
    // Focus close button for accessibility
    if (sidebarCloseBtn) sidebarCloseBtn.focus();
  };

  const closeSidebar = () => {
    if (!githubSidebar) return;
    githubSidebar.classList.remove('is-open');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('is-visible');
    document.body.classList.remove('sidebar-lock-scroll');
    if (sidebarToggleBtn) {
      sidebarToggleBtn.setAttribute('aria-expanded', 'false');
      sidebarToggleBtn.focus();
    }
    githubSidebar.setAttribute('aria-hidden', 'true');
  };

  if (sidebarToggleBtn) {
    sidebarToggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openSidebar();
    });
  }

  if (sidebarCloseBtn) {
    sidebarCloseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      closeSidebar();
    });
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', () => {
      closeSidebar();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && githubSidebar && githubSidebar.classList.contains('is-open')) {
      closeSidebar();
    }
  });

  // Close sidebar when clicking any navigation link inside it
  if (githubSidebar) {
    const sidebarLinks = githubSidebar.querySelectorAll('.sidebar-link');
    sidebarLinks.forEach(link => {
      link.addEventListener('click', () => {
        closeSidebar();
      });
    });
  }

  // 3. Show/Hide Password Toggle
  const toggleButtons = document.querySelectorAll('.btn-toggle-password');
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-target');
      let input;
      if (targetId) {
        input = document.getElementById(targetId);
      } else {
        input = btn.closest('.input-icon-wrapper').querySelector('input');
      }

      if (input) {
        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';

        const eyeIcon = btn.querySelector('.icon-eye');
        const eyeOffIcon = btn.querySelector('.icon-eye-off');
        if (eyeIcon && eyeOffIcon) {
          eyeIcon.style.display = isPassword ? 'none' : 'block';
          eyeOffIcon.style.display = isPassword ? 'block' : 'none';
        }
      }
    });
  });

  // 4. Student Login Form Validation & Loading State
  const loginForm = document.getElementById('studentLoginForm');
  if (loginForm) {
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const submitBtn = document.getElementById('loginSubmitBtn');
    const textContent = submitBtn ? submitBtn.querySelector('.btn-text-content') : null;
    const spinnerContent = document.getElementById('loginSpinner');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');

    const validateEmail = (val) => {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      return emailRegex.test(val);
    };

    loginForm.addEventListener('submit', (e) => {
      let isValid = true;
      if (emailError) emailError.textContent = '';
      if (passwordError) passwordError.textContent = '';

      const emailVal = emailInput ? emailInput.value.trim() : '';
      const passwordVal = passwordInput ? passwordInput.value : '';

      if (!emailVal) {
        isValid = false;
        if (emailError) emailError.textContent = 'Please enter your student email address.';
        if (emailInput) emailInput.classList.add('input-invalid');
      } else if (!validateEmail(emailVal)) {
        isValid = false;
        if (emailError) emailError.textContent = 'Please enter a valid email format (e.g. name@bmsit.in).';
        if (emailInput) emailInput.classList.add('input-invalid');
      } else if (emailInput) {
        emailInput.classList.remove('input-invalid');
      }

      if (!passwordVal) {
        isValid = false;
        if (passwordError) passwordError.textContent = 'Please enter your password.';
        if (passwordInput) passwordInput.classList.add('input-invalid');
      } else if (passwordInput) {
        passwordInput.classList.remove('input-invalid');
      }

      if (!isValid) {
        e.preventDefault();
        return false;
      }

      // Enter loading state and prevent duplicate submissions
      if (submitBtn && !submitBtn.disabled) {
        submitBtn.disabled = true;
        if (textContent) textContent.style.display = 'none';
        if (spinnerContent) spinnerContent.style.display = 'inline-flex';
      }
    });

    if (emailInput) {
      emailInput.addEventListener('input', () => {
        emailInput.classList.remove('input-invalid');
        if (emailError) emailError.textContent = '';
      });
    }
    if (passwordInput) {
      passwordInput.addEventListener('input', () => {
        passwordInput.classList.remove('input-invalid');
        if (passwordError) passwordError.textContent = '';
      });
    }
  }

  // 5. Demo Personas Accordion Toggle (For College Reviews)
  const demoToggle = document.getElementById('demoAccordionToggle');
  const demoContent = document.getElementById('demoAccordionContent');
  if (demoToggle && demoContent) {
    demoToggle.addEventListener('click', () => {
      const isVisible = demoContent.style.display !== 'none';
      demoContent.style.display = isVisible ? 'none' : 'block';
      demoToggle.classList.toggle('active', !isVisible);
      demoToggle.setAttribute('aria-expanded', !isVisible);
    });
  }

  // 6. Generic Loading State for Other Auth Forms (Forgot & Reset Password)
  const otherAuthForms = document.querySelectorAll('#forgotPwForm, #resetPwForm');
  otherAuthForms.forEach(form => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"]');
      if (btn && !btn.disabled) {
        btn.disabled = true;
        btn.style.opacity = '0.75';
        btn.innerText = 'Processing...';
      }
    });
  });

  // 7. Live Notification Badge Sync for Topbar and Sidebar
  const navBadge = document.getElementById('navUnreadMessagesBadge');
  const sidebarBadge = document.getElementById('sidebarUnreadBadge');
  if (navBadge || sidebarBadge) {
    const updateUnreadBadges = async () => {
      try {
        const res = await fetch('/api/messages/unread');
        if (!res.ok) return;
        const data = await res.json();
        const count = data.total_unread || 0;
        [navBadge, sidebarBadge].forEach(b => {
          if (!b) return;
          if (count > 0) {
            b.textContent = count > 99 ? '99+' : count;
            b.style.display = 'inline-flex';
          } else {
            b.textContent = '';
            b.style.display = 'none';
          }
        });
      } catch (e) {
        // Silent catch for background polling
      }
    };
    // Initial quick sync and periodic update every 10 seconds
    setInterval(updateUnreadBadges, 10000);
  }

  // 8. Dark Mode / Light Mode Theme Toggle
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const sidebarThemeToggleBtn = document.getElementById('sidebarThemeToggleBtn');

  const getCurrentTheme = () => {
    return document.documentElement.getAttribute('data-theme') ||
      localStorage.getItem('skillsync_theme') ||
      (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  };

  const updateThemeUI = (theme) => {
    const isDark = theme === 'dark';
    const label = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';

    if (themeToggleBtn) {
      themeToggleBtn.setAttribute('aria-label', label);
      themeToggleBtn.setAttribute('title', label);
    }

    if (sidebarThemeToggleBtn) {
      sidebarThemeToggleBtn.setAttribute('aria-label', label);
      sidebarThemeToggleBtn.setAttribute('title', label);
      const textSpan = sidebarThemeToggleBtn.querySelector('.sidebar-theme-text');
      if (textSpan) {
        textSpan.textContent = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
      }
    }
  };

  const applyTheme = (theme, persist = true) => {
    document.documentElement.setAttribute('data-theme', theme);
    if (persist) {
      try {
        localStorage.setItem('skillsync_theme', theme);
      } catch (e) {
        // Safe fallback if local storage is restricted
      }
    }
    updateThemeUI(theme);
    window.dispatchEvent(new CustomEvent('skillsync:themechange', { detail: { theme } }));
  };

  const toggleTheme = () => {
    const currentTheme = getCurrentTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme, true);
  };

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      toggleTheme();
    });
  }

  if (sidebarThemeToggleBtn) {
    sidebarThemeToggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      toggleTheme();
    });
  }

  // Initialize UI state with current theme
  updateThemeUI(getCurrentTheme());

  // Listen to OS / System color scheme changes if user hasn't explicitly set a preference
  if (window.matchMedia) {
    try {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('skillsync_theme')) {
          applyTheme(e.matches ? 'dark' : 'light', false);
        }
      });
    } catch (e) {
      // Support older browsers
    }
  }
});
