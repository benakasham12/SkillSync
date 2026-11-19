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

    const navItems = navCollapse.querySelectorAll('.nav-item, .btn');
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        navCollapse.classList.remove('show');
        navToggle.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      });
    });

    document.addEventListener('click', (e) => {
      if (!navCollapse.contains(e.target) && !navToggle.contains(e.target)) {
        navCollapse.classList.remove('show');
        navToggle.classList.remove('open');
        navToggle.setAttribute('aria-expanded', 'false');
      }
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
});
