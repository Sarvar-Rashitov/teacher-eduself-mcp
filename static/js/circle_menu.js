/**
 * EduSelf — "CircleMenu" Radial Navigation Component
 * Pure Vanilla JS + CSS Spring Physics implementation of the circular menu.
 * Trigonometric circular fan-out distribution: pointOnCircle(i, n, r)
 */

(function () {
  'use strict';

  const MENU_ITEMS = [
    { label: "Bosh Sahifa", icon: "/static/img/icons/sparkles.svg", href: "/" },
    { label: "Ustoz Paneli", icon: "/static/img/icons/settings.svg", href: "/dashboard/" },
    { label: "Play Arena", icon: "/static/img/icons/play.svg", href: "/play/" },
    { label: "Yangi Viktorina", icon: "/static/img/icons/plus.svg", href: "/editor/new/" },
    { label: "AI Yordamchi", icon: "/static/img/icons/sparkles.svg", href: "javascript:window.toggleAiDrawer();" },
    { label: "3D Vitrina", icon: "/static/img/icons/trophy.svg", href: "/design-system/" },
    { label: "Profilim", icon: "/static/img/icons/user.svg", href: "/profile/" },
  ];

  const RADIUS = 110; // Distance of radial items from center (px)

  function pointOnCircle(i, n, r) {
    const theta = (2 * Math.PI * i) / n - Math.PI / 2;
    const x = r * Math.cos(theta);
    const y = r * Math.sin(theta);
    return { x: Math.round(x), y: Math.round(y) };
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
      triggerBtn.title = 'Tezkor Radial Menyu';
      triggerBtn.innerHTML = `
        <span class="circle-menu-icon-open">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </span>
        <span class="circle-menu-icon-close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
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
        const pos = pointOnCircle(index, n, RADIUS);

        const a = document.createElement('a');
        a.className = 'circle-menu-item';
        a.href = item.href;
        a.title = item.label;
        a.style.setProperty('--target-x', `${pos.x}px`);
        a.style.setProperty('--target-y', `${pos.y}px`);
        a.style.setProperty('--stagger-index', index);

        a.innerHTML = `
          <img src="${item.icon}" alt="${item.label}" class="svg-icon svg-icon-sm">
          <span class="circle-menu-label">${item.label}</span>
        `;

        a.addEventListener('click', () => {
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
