/**
 * SkillSync - Spotlight Background Interactive Client Script
 * Powers the 3-beam floating spotlight animation and responsive adjustments.
 */

(function () {
  'use strict';

  function initSpotlightBackground() {
    const wrapper = document.querySelector('.spotlight-background-wrapper');
    if (!wrapper) return;

    const hero = wrapper.closest('.hero-section') || wrapper.parentElement;
    if (!hero) return;

    const beamLeft = wrapper.querySelector('.spotlight-beam-left');
    const beamMid = wrapper.querySelector('.spotlight-beam-mid');
    const beamRight = wrapper.querySelector('.spotlight-beam-right');

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;
    let animationFrameId = null;

    // Smooth subtle pointer influence (clamped to prevent jarring jumps)
    function onPointerMove(e) {
      const rect = hero.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;

      const normX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const normY = ((e.clientY - rect.top) / rect.height) * 2 - 1;

      targetX = Math.max(-1, Math.min(1, normX)) * 24; // max 24px subtle drift
      targetY = Math.max(-1, Math.min(1, normY)) * 18; // max 18px subtle drift
    }

    function onPointerLeave() {
      targetX = 0;
      targetY = 0;
    }

    function updateParallax() {
      // Lerp for smooth spring-like motion
      currentX += (targetX - currentX) * 0.05;
      currentY += (targetY - currentY) * 0.05;

      if (wrapper) {
        wrapper.style.transform = `translate3d(${currentX.toFixed(2)}px, ${currentY.toFixed(2)}px, 0)`;
      }

      animationFrameId = requestAnimationFrame(updateParallax);
    }

    hero.addEventListener('mousemove', onPointerMove, { passive: true });
    hero.addEventListener('mouseleave', onPointerLeave, { passive: true });

    animationFrameId = requestAnimationFrame(updateParallax);

    // Clean up on page unload/navigation if required
    window.addEventListener('beforeunload', () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
      hero.removeEventListener('mousemove', onPointerMove);
      hero.removeEventListener('mouseleave', onPointerLeave);
    }, { once: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSpotlightBackground);
  } else {
    initSpotlightBackground();
  }

  // Expose global controller for testing or manual re-initialization
  window.SkillSyncSpotlight = {
    init: initSpotlightBackground
  };
})();
