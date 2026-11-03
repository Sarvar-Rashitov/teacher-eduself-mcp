/**
 * EduSelf — "EduPlay 3D" Interactive Component Controller
 * Orchestrates modals, sound triggers, AI drawer, haptics, and toast notifications.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global State
  window.eduState = {
    coins: 1420,
    streak: 3,
    soundEnabled: true,
    isMuted: false
  };

  // 1. Audio Toggle Controls
  const audioToggleBtns = document.querySelectorAll('.audio-toggle-btn');
  audioToggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const isMuted = window.eduAudio ? window.eduAudio.toggleMute() : false;
      window.eduState.isMuted = isMuted;
      window.eduState.soundEnabled = !isMuted;

      const iconImg = btn.querySelector('.svg-icon');
      const textSpan = btn.querySelector('.audio-text');

      if (isMuted) {
        if (textSpan) textSpan.textContent = 'Tovush: O‘chiq';
        if (iconImg) iconImg.src = '/static/img/icons/speaker_off.svg';
        btn.style.background = '#FEE2E2';
      } else {
        if (textSpan) textSpan.textContent = 'Tovush: Yoqilgan';
        if (iconImg) iconImg.src = '/static/img/icons/speaker_on.svg';
        btn.style.background = '#FFFFFF';
        if (window.eduAudio) window.eduAudio.playTick();
      }
    });
  });

  // 2. Global Toast Notification System
  window.showToast = function(message, type = 'info', duration = 3000) {
    let container = document.getElementById('globalToastContainer');
    if (!container) {
      container = document.createElement('div');
      container.id = 'globalToastContainer';
      container.style.cssText = `
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 10px;
        pointer-events: none;
      `;
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    const bgColors = {
      success: '#10B981',
      error: '#EF4444',
      warning: '#F59E0B',
      info: '#FF7527'
    };

    toast.style.cssText = `
      background: ${bgColors[type] || '#1E1E24'};
      color: #FFFFFF;
      padding: 12px 20px;
      border-radius: 9999px;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-weight: 700;
      font-size: 14px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
      opacity: 0;
      transform: translateY(16px);
      transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
      pointer-events: auto;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(() => {
      toast.style.opacity = '1';
      toast.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  };

  // 3. Victory & Reward Modal Controller (victory_reward.jpg)
  const victoryModalEl = document.getElementById('victoryModal');
  window.openVictoryModal = function(coinsWon = 100) {
    if (!victoryModalEl) return;
    const modalCoinsEl = document.getElementById('modalCoinRewardText');
    if (modalCoinsEl) {
      modalCoinsEl.textContent = `+${coinsWon} Tangalar`;
    }
    victoryModalEl.classList.add('active');
    if (window.eduAudio) {
      window.eduAudio.playVictory();
    }
    if (navigator.vibrate) {
      navigator.vibrate([100, 50, 100]);
    }
  };

  window.closeVictoryModal = function(claim = false) {
    if (!victoryModalEl) return;
    if (claim) {
      if (window.eduAudio) {
        window.eduAudio.playCoin();
      }
      window.updateGlobalCoins(100);
      window.showToast('100 oltin tanga hisobingizga qo‘shildi! 🎉', 'success');
    }
    victoryModalEl.classList.remove('active');
  };

  // 4. Global Coin Counter Update
  window.updateGlobalCoins = function(amount = 0) {
    window.eduState.coins += amount;
    const coinCounters = document.querySelectorAll('.global-coin-count');
    coinCounters.forEach(el => {
      el.textContent = window.eduState.coins.toLocaleString();
      el.classList.add('pulse-pop');
      setTimeout(() => el.classList.remove('pulse-pop'), 400);
    });
  };

  // 5. AI Assistant Drawer Toggle
  window.toggleAiDrawer = function() {
    const drawer = document.getElementById('aiAssistantDrawer');
    if (drawer) {
      drawer.classList.toggle('active');
      if (window.eduAudio) window.eduAudio.playTick();
    }
  };

  // 6. Generic Modal Helpers
  window.openModal = function(id) {
    const m = document.getElementById(id);
    if (m) {
      m.classList.add('active');
      if (window.eduAudio) window.eduAudio.playTick();
    }
  };

  window.closeModal = function(id) {
    const m = document.getElementById(id);
    if (m) {
      m.classList.remove('active');
    }
  };

  // 7. Haptic Vibration Helper
  window.triggerHaptic = function(type = 'light') {
    if (!navigator.vibrate) return;
    if (type === 'light') navigator.vibrate(15);
    else if (type === 'success') navigator.vibrate([20, 30, 20]);
    else if (type === 'error') navigator.vibrate([40, 40, 40]);
  };
});
