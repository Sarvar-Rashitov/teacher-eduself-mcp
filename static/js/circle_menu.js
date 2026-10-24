/**
 * EduSelf — "CircleMenu" Radial Navigation Component
 * Downward fan-out distribution ensuring all items open strictly below the fixed header.
 * Replaces any unicodes with crisp SVG icons, enlarged touch targets, and Web Audio toggle integration.
 */

(function () {
  'use strict';

  const MENU_ITEMS = [
    { id: "navHome", label: "Bosh Sahifa", icon: "/static/img/icons/sparkles.svg", href: "/" },
    { id: "navDashboard", label: "Ustoz Paneli", icon: "/static/img/icons/settings.svg", href: "/dashboard/" },
    { id: "navPlay", label: "Play Arena", icon: "/static/img/icons/play.svg", href: "/play/" },
    { id: "navNewQuiz", label: "Yangi Viktorina", icon: "/static/img/icons/plus.svg", href: "/editor/new/" },
    { id: "navSound", label: "Tovush: Yoqilgan", icon: "/static/img/icons/speaker_on.svg", action: "toggleSound" },
    { id: "navAi", label: "AI Asistent", icon: "/static/img/icons/sparkles.svg", action: "toggleAi" },
    { id: "navLeaderboard", label: "Peshqadamlar", icon: "/static/img/icons/trophy.svg", href: "/leaderboard/" },
    { id: "navProfile", label: "Profilim", icon: "/static/img/icons/user.svg", href: "/profile/" },
  ];

  /**
   * Calculates strictly downward positions (y > 0) with alternating tiers
   * to avoid overlap and prevent items from flying above the viewport.
   */
  function pointOnCircleDownward(index, total) {
    // Angle range from ~48° to ~162° (spread downward-left into the open viewport)
    const minAngle = Math.PI * 0.26; // ~47 deg
    const maxAngle = Math.PI * 0.90; // ~162 deg
    const step = (maxAngle - minAngle) / (total - 1);
    const angle = minAngle + index * step;

    // Dual-tiered radius: alternate inner (95px) and outer (155px)
    const isOuter = index % 2 === 1;
    const r = isOuter ? 155 : 98;

    const x = Math.round(r * Math.cos(angle) * 1.18);
    const y = Math.round(Math.abs(r * Math.sin(angle)) + 36);

    return { x, y };
  }

  class CircleNavigationMenu {
    constructor(container) {
      this.container = container;
      this.isOpen = false;
      this.items = MENU_ITEMS;
      this.init();
    }

    init() {
      this.container.classList.add('circle-menu-wrapper');

      // Create Trigger Button
      const triggerBtn = document.createElement('button');
      triggerBtn.className = 'circle-menu-trigger';
      triggerBtn.type = 'button';
      triggerBtn.setAttribute('aria-label', 'Navigatsiya Menyusi');
      triggerBtn.title = 'Tezkor Navigatsiya Menyusi';
      triggerBtn.innerHTML = `
        <span class="circle-menu-icon-open">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </span>
        <span class="circle-menu-icon-close">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </span>
      `;
      this.triggerBtn = triggerBtn;
      this.container.appendChild(triggerBtn);

      // Create Radial Items Container
      const itemsContainer = document.createElement('div');
      itemsContainer.className = 'circle-menu-items';
      this.itemsContainer = itemsContainer;
      this.container.appendChild(itemsContainer);

      // Build each radial menu item
      const n = this.items.length;
      this.itemElements = [];

      this.items.forEach((item, index) => {
        const pos = pointOnCircleDownward(index, n);

        const a = document.createElement('a');
        a.className = 'circle-menu-item';
        a.id = item.id || `circleMenuItem_${index}`;
        if (item.href) {
          a.href = item.href;
        } else {
          a.href = 'javascript:void(0);';
        }
        a.title = item.label;
        a.style.setProperty('--target-x', `${pos.x}px`);
        a.style.setProperty('--target-y', `${pos.y}px`);
        a.style.setProperty('--stagger-index', index);

        a.innerHTML = `
          <img src="${item.icon}" alt="${item.label}" class="circle-menu-icon">
          <span class="circle-menu-label">${item.label}</span>
        `;

        a.addEventListener('click', (e) => {
          if (item.action === 'toggleSound') {
            e.preventDefault();
            this.handleToggleSound(a);
            return;
          }
          if (item.action === 'toggleAi') {
            e.preventDefault();
            this.close();
            if (window.toggleAiModal) {
              window.toggleAiModal();
            } else if (window.toggleAiDrawer) {
              window.toggleAiDrawer();
            } else {
              window.location.href = '/login/?next=/dashboard/';
            }
            return;
          }
          this.close();
        });

        itemsContainer.appendChild(a);
        this.itemElements.push(a);
      });

      // Event Listeners
      triggerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggle();
      });

      document.addEventListener('click', (e) => {
        if (this.isOpen && !this.container.contains(e.target)) {
          this.close();
        }
      });

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          this.close();
        }
      });
    }

    handleToggleSound(itemEl) {
      const isMuted = window.eduAudio ? window.eduAudio.toggleMute() : false;
      if (window.eduState) {
        window.eduState.isMuted = isMuted;
        window.eduState.soundEnabled = !isMuted;
      }

      this.updateSoundDisplay(isMuted, itemEl);

      // Also sync external soundToggleBtns on page
      const extBtns = document.querySelectorAll('.audio-toggle-btn');
      extBtns.forEach(btn => {
        const textSpan = btn.querySelector('.audio-text');
        const iconImg = btn.querySelector('.svg-icon');
        if (isMuted) {
          if (textSpan) textSpan.textContent = 'Tovush: O‘chiq';
          if (iconImg) iconImg.src = '/static/img/icons/speaker_off.svg';
          btn.style.background = '#FEE2E2';
        } else {
          if (textSpan) textSpan.textContent = 'Tovush: Yoqilgan';
          if (iconImg) iconImg.src = '/static/img/icons/speaker_on.svg';
          btn.style.background = '#FFFFFF';
        }
      });

      if (!isMuted && window.eduAudio) {
        window.eduAudio.playTick();
      }

      if (window.showToast) {
        window.showToast(isMuted ? 'Tovush o‘chirildi' : 'Tovush yoqildi', isMuted ? 'warning' : 'success');
      }
    }

    updateSoundDisplay(isMuted, itemEl) {
      if (!itemEl) itemEl = document.getElementById('navSound');
      if (!itemEl) return;
      const icon = itemEl.querySelector('.circle-menu-icon');
      const label = itemEl.querySelector('.circle-menu-label');

      if (isMuted) {
        if (icon) icon.src = '/static/img/icons/speaker_off.svg';
        if (label) label.textContent = 'Tovush: O‘chiq';
        itemEl.title = 'Tovush: O‘chiq';
      } else {
        if (icon) icon.src = '/static/img/icons/speaker_on.svg';
        if (label) label.textContent = 'Tovush: Yoqilgan';
        itemEl.title = 'Tovush: Yoqilgan';
      }
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }

    open() {
      this.isOpen = true;
      this.container.classList.add('is-open');

      // Sync sound status on open
      if (window.eduAudio) {
        this.updateSoundDisplay(window.eduAudio.isMuted());
      }

      if (window.eduAudio) window.eduAudio.playTick();
    }

    close() {
      this.isOpen = false;
      this.container.classList.remove('is-open');
    }
  }

  // Global registration
  window.CircleNavigationMenu = CircleNavigationMenu;

  document.addEventListener('DOMContentLoaded', () => {
    const containers = document.querySelectorAll('[data-circle-menu]');
    containers.forEach(container => {
      new CircleNavigationMenu(container);
    });
  });
})();
