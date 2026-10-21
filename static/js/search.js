/**
 * EduSelf — Global Instant Search Controller
 * Handles Cmd/Ctrl+K shortcut, instant filtering for quizzes, pages, and AI generation commands.
 */

(function () {
  'use strict';

  const QUICK_ITEMS = [
    { title: "Boshqaruv Paneli", category: "Sahifa", icon: "/static/img/icons/settings.svg", href: "/dashboard/" },
    { title: "Yangi Viktorina Yaratish", category: "Amal", icon: "/static/img/icons/plus.svg", href: "/editor/new/" },
    { title: "Play Arena (Jonli O‘yin)", category: "Sahifa", icon: "/static/img/icons/play.svg", href: "/play/" },
    { title: "Peshqadamlar Jadvali", category: "Reyting", icon: "/static/img/icons/trophy.svg", href: "/leaderboard/" },
    { title: "Mening Profilim", category: "Sahifa", icon: "/static/img/icons/user.svg", href: "/profile/" },
    { title: "Fizika: Zichlik va Massa", category: "Viktorina", icon: "/static/img/icons/sparkles.svg", href: "/editor/new/" },
    { title: "Matematika: Oddiy Kasrlar", category: "Viktorina", icon: "/static/img/icons/sparkles.svg", href: "/editor/new/" },
    { title: "Biologiya: Hujayra Tuzilishi", category: "Viktorina", icon: "/static/img/icons/sparkles.svg", href: "/editor/new/" },
    { title: "Kimyo: Davriy Jadval Asoslari", category: "Viktorina", icon: "/static/img/icons/sparkles.svg", href: "/editor/new/" },
    { title: "Informatika: AI va Algoritmlar", category: "Viktorina", icon: "/static/img/icons/sparkles.svg", href: "/editor/new/" },
    { title: "EduPlay 3D Dizayn Tizimi", category: "Vitrina", icon: "/static/img/icons/settings.svg", href: "/design-system/" },
  ];

  document.addEventListener('DOMContentLoaded', () => {
    const searchIsland = document.getElementById('navbarSearchIsland');
    const searchInput = document.getElementById('globalSearchInput');
    const dropdown = document.getElementById('searchResultsDropdown');

    if (!searchInput || !dropdown) return;

    // Render search results based on query
    function renderResults(query) {
      const q = query.trim().toLowerCase();
      let matches = [];

      if (!q) {
        // Show recommended/quick links
        matches = QUICK_ITEMS.slice(0, 5);
      } else {
        matches = QUICK_ITEMS.filter(item => 
          item.title.toLowerCase().includes(q) || 
          item.category.toLowerCase().includes(q)
        );
      }

      let html = '';

      // AI Command Suggestion if user types a query
      if (q) {
        html += `
          <div class="search-result-item ai-command-item" data-ai-prompt="${escapeHtml(query)}">
            <div class="search-result-icon ai-icon-wrap">
              <img src="/static/img/icons/sparkles.svg" alt="AI" class="svg-icon">
            </div>
            <div class="search-result-info">
              <span class="search-result-title">“${escapeHtml(query)}” mavzusida AI bilan test yaratish</span>
              <span class="search-result-badge ai-badge">AI Buyruq</span>
            </div>
            <span class="search-arrow-hint">Enter ↵</span>
          </div>
        `;
      }

      if (matches.length > 0) {
        matches.forEach(item => {
          html += `
            <a href="${item.href}" class="search-result-item">
              <div class="search-result-icon">
                <img src="${item.icon}" alt="${escapeHtml(item.category)}" class="svg-icon">
              </div>
              <div class="search-result-info">
                <span class="search-result-title">${escapeHtml(item.title)}</span>
                <span class="search-result-category">${escapeHtml(item.category)}</span>
              </div>
              <span class="search-arrow-hint">→</span>
            </a>
          `;
        });
      } else if (!q) {
        html += `<div class="search-empty-state">Qidirish uchun mavzu yoki buyruq kiriting...</div>`;
      } else {
        html += `
          <div class="search-empty-state">
            Topilmadi. Yuqoridagi AI buyrug‘i orqali test generatsiya qilishingiz mumkin.
          </div>
        `;
      }

      dropdown.innerHTML = html;
      dropdown.style.display = 'block';

      // Attach listener to AI command item
      const aiItem = dropdown.querySelector('.ai-command-item');
      if (aiItem) {
        aiItem.addEventListener('click', () => {
          const prompt = aiItem.getAttribute('data-ai-prompt');
          closeDropdown();
          if (window.openAiModalWithPrompt) {
            window.openAiModalWithPrompt(prompt);
          } else if (window.toggleAiDrawer) {
            window.toggleAiDrawer();
          }
        });
      }
    }

    function openDropdown() {
      renderResults(searchInput.value);
      if (searchIsland) searchIsland.classList.add('is-focused');
      if (window.eduAudio) window.eduAudio.playTick();
    }

    function closeDropdown() {
      dropdown.style.display = 'none';
      if (searchIsland) searchIsland.classList.remove('is-focused');
    }

    function escapeHtml(str) {
      return String(str).replace(/[&<>"']/g, s => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      }[s]));
    }

    // Input events
    searchInput.addEventListener('focus', openDropdown);
    searchInput.addEventListener('input', (e) => {
      renderResults(e.target.value);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      // Cmd/Ctrl + K or forward slash '/' to focus search
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
        openDropdown();
        return;
      }

      if (e.key === '/' && document.activeElement !== searchInput && 
          document.activeElement.tagName !== 'INPUT' && 
          document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        searchInput.focus();
        openDropdown();
        return;
      }

      if (e.key === 'Escape') {
        if (dropdown.style.display === 'block') {
          closeDropdown();
          searchInput.blur();
        }
      }
    });

    // Click outside to close
    document.addEventListener('click', (e) => {
      if (searchIsland && !searchIsland.contains(e.target)) {
        closeDropdown();
      }
    });
  });
})();
