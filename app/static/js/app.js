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

  // 9. BeamsBackground Animation (Opening Hero Section ONLY)
  const heroCanvas = document.getElementById('beamsBackgroundCanvas');
  if (heroCanvas) {
    const ctx = heroCanvas.getContext('2d');
    if (ctx) {
      const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      let animationFrameId = null;
      let beams = [];
      const TOTAL_BEAMS = 22;

      const isDarkMode = () => document.documentElement.getAttribute('data-theme') === 'dark';

      const createBeam = (w, h, dark) => {
        const angle = -35 + Math.random() * 10;
        // Flowing blue and purple palette (hue ~215 to ~270)
        const hueBase = dark ? 215 : 220;
        const hueRange = dark ? 55 : 45;
        return {
          x: Math.random() * w * 1.5 - w * 0.25,
          y: Math.random() * h * 1.5 - h * 0.25,
          width: 32 + Math.random() * 58,
          length: h * 2.2,
          angle,
          speed: 0.5 + Math.random() * 0.9,
          opacity: dark ? (0.14 + Math.random() * 0.16) : (0.09 + Math.random() * 0.12),
          hue: hueBase + Math.random() * hueRange,
          pulse: Math.random() * Math.PI * 2,
          pulseSpeed: 0.02 + Math.random() * 0.025,
        };
      };

      const resetBeam = (beam, index, w, h, dark) => {
        const column = index % 3;
        const spacing = w / 3;
        const hueBase = dark ? 215 : 220;
        const hueRange = dark ? 55 : 45;

        beam.y = h + 100;
        beam.x = column * spacing + spacing / 2 + (Math.random() - 0.5) * spacing * 0.6;
        beam.width = 35 + Math.random() * 65;
        beam.speed = 0.5 + Math.random() * 0.8;
        beam.hue = hueBase + (index * hueRange) / TOTAL_BEAMS;
        beam.opacity = dark ? (0.14 + Math.random() * 0.14) : (0.09 + Math.random() * 0.10);
        return beam;
      };

      let currentW = 0;
      let currentH = 0;

      const resizeCanvas = () => {
        const rect = heroCanvas.getBoundingClientRect();
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        currentW = rect.width || window.innerWidth;
        currentH = rect.height || 600;

        heroCanvas.width = currentW * dpr;
        heroCanvas.height = currentH * dpr;
        if (ctx.resetTransform) {
          ctx.resetTransform();
        } else {
          ctx.setTransform(1, 0, 0, 1, 0, 0);
        }
        ctx.scale(dpr, dpr);

        const dark = isDarkMode();
        beams = Array.from({ length: TOTAL_BEAMS }, () => createBeam(currentW, currentH, dark));

        if (prefersReducedMotion) {
          drawStaticFrame();
        }
      };

      const drawBeam = (beam, dark) => {
        ctx.save();
        ctx.translate(beam.x, beam.y);
        ctx.rotate((beam.angle * Math.PI) / 180);

        const pulsingOpacity = beam.opacity * (0.8 + Math.sin(beam.pulse) * 0.2);
        const gradient = ctx.createLinearGradient(0, 0, 0, beam.length);
        const saturation = dark ? '88%' : '76%';
        const lightness = dark ? '62%' : '48%';

        gradient.addColorStop(0, `hsla(${beam.hue}, ${saturation}, ${lightness}, 0)`);
        gradient.addColorStop(0.1, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity * 0.4})`);
        gradient.addColorStop(0.4, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity})`);
        gradient.addColorStop(0.6, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity})`);
        gradient.addColorStop(0.9, `hsla(${beam.hue}, ${saturation}, ${lightness}, ${pulsingOpacity * 0.4})`);
        gradient.addColorStop(1, `hsla(${beam.hue}, ${saturation}, ${lightness}, 0)`);

        ctx.fillStyle = gradient;
        ctx.fillRect(-beam.width / 2, 0, beam.width, beam.length);
        ctx.restore();
      };

      const drawStaticFrame = () => {
        ctx.clearRect(0, 0, currentW, currentH);
        ctx.filter = 'blur(28px)';
        const dark = isDarkMode();
        beams.forEach(b => drawBeam(b, dark));
      };

      const animate = () => {
        ctx.clearRect(0, 0, currentW, currentH);
        ctx.filter = 'blur(28px)';
        const dark = isDarkMode();

        beams.forEach((beam, index) => {
          beam.y -= beam.speed;
          beam.pulse += beam.pulseSpeed;

          if (beam.y + beam.length < -100) {
            resetBeam(beam, index, currentW, currentH, dark);
          }

          drawBeam(beam, dark);
        });

        animationFrameId = requestAnimationFrame(animate);
      };

      resizeCanvas();
      window.addEventListener('resize', resizeCanvas);

      if (!prefersReducedMotion) {
        animate();
      }

      window.addEventListener('skillsync:themechange', () => {
        const dark = isDarkMode();
        beams.forEach(b => {
          const hueBase = dark ? 215 : 220;
          const hueRange = dark ? 55 : 45;
          b.hue = hueBase + Math.random() * hueRange;
          b.opacity = dark ? (0.14 + Math.random() * 0.16) : (0.09 + Math.random() * 0.12);
        });
        if (prefersReducedMotion) {
          drawStaticFrame();
        }
      });
    }
  }

  // 10. Hero Discovery Search Tabs (Quick Search vs Trending Searches)
  const tabQuick = document.getElementById('tabQuickSearch');
  const tabTrending = document.getElementById('tabTrendingSearch');
  const quickList = document.getElementById('quickSuggestionsList');
  const trendingList = document.getElementById('trendingSuggestionsList');

  if (tabQuick && tabTrending && quickList && trendingList) {
    tabQuick.addEventListener('click', () => {
      tabQuick.classList.add('active');
      tabTrending.classList.remove('active');
      quickList.style.display = 'flex';
      trendingList.style.display = 'none';
    });

    tabTrending.addEventListener('click', () => {
      tabTrending.classList.add('active');
      tabQuick.classList.remove('active');
      trendingList.style.display = 'flex';
      quickList.style.display = 'none';
    });
  }
});
