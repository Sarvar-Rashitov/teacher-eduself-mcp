/**
 * EduSelf Teacher — "EduPlay 3D" Interactive Component Controller
 * Orchestrates simulator tabs, procedural audio triggers, quiz simulator,
 * dynamic leaderboard, and victory celebration modals.
 */

document.addEventListener('DOMContentLoaded', () => {
  // State
  const state = {
    coins: 1420,
    streak: 3,
    activeTab: 'home',
    soundEnabled: true,
    quizAnswered: false,
    timerSeconds: 15,
    timerInterval: null
  };

  // DOM Elements
  const coinCounterEl = document.getElementById('globalCoinCount');
  const modalEl = document.getElementById('victoryModal');
  const muteBtn = document.getElementById('muteToggleBtn');
  const simTabs = document.querySelectorAll('.sim-tab-btn');
  const simScreens = document.querySelectorAll('.sim-screen-view');

  // Audio Init on First User Interaction (to satisfy browser autoplay policies)
  const initAudioOnFirstGesture = () => {
    if (window.eduAudio) {
      window.eduAudio.init();
    }
    document.removeEventListener('click', initAudioOnFirstGesture);
    document.removeEventListener('keydown', initAudioOnFirstGesture);
  };
  document.addEventListener('click', initAudioOnFirstGesture);
  document.addEventListener('keydown', initAudioOnFirstGesture);

  // Mute / Unmute Control
  if (muteBtn) {
    muteBtn.addEventListener('click', () => {
      const isMuted = window.eduAudio ? window.eduAudio.toggleMute() : false;
      state.soundEnabled = !isMuted;
      const icon = isMuted ? 'icons/speaker_off.svg' : 'icons/speaker_on.svg';
      const text = isMuted ? 'Tovush: O‘chiq' : 'Tovush: Yoqilgan';
      muteBtn.innerHTML = `<img src="${icon}" alt="Ovoz" class="svg-icon svg-icon-sm"> <span>${text}</span>`;
      muteBtn.style.background = isMuted ? '#FEE2E2' : '#FFFFFF';
    });
  }

  // Update Coin Display
  function updateCoinDisplay(amountAdded = 0) {
    state.coins += amountAdded;
    if (coinCounterEl) {
      coinCounterEl.textContent = state.coins.toLocaleString();
    }
    const modalCoinEl = document.getElementById('modalCoinReward');
    if (modalCoinEl && amountAdded > 0) {
      modalCoinEl.classList.add('pulse-pop');
      setTimeout(() => modalCoinEl.classList.remove('pulse-pop'), 400);
    }
  }

  // Simulator Screen Switching
  function switchTab(tabId) {
    state.activeTab = tabId;
    simTabs.forEach(btn => {
      if (btn.dataset.tab === tabId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    simScreens.forEach(screen => {
      if (screen.id === `screen-${tabId}`) {
        screen.style.display = 'block';
        screen.classList.add('fade-in');
      } else {
        screen.style.display = 'none';
        screen.classList.remove('fade-in');
      }
    });

    if (window.eduAudio) {
      window.eduAudio.playTick();
    }

    if (tabId === 'quiz') {
      startQuizTimer();
    } else {
      stopQuizTimer();
    }
  }

  simTabs.forEach(btn => {
    btn.addEventListener('click', () => {
      switchTab(btn.dataset.tab);
    });
  });

  // Expose switchTab globally for external buttons
  window.switchSimulatorTab = switchTab;

  // Victory Modal Actions
  window.openVictoryModal = function(coinsWon = 100) {
    if (!modalEl) return;
    modalEl.classList.add('active');
    if (window.eduAudio) {
      window.eduAudio.playVictory();
    }
  };

  window.closeVictoryModal = function(claim = false) {
    if (!modalEl) return;
    if (claim) {
      if (window.eduAudio) {
        window.eduAudio.playCoin();
      }
      updateCoinDisplay(100);
    }
    modalEl.classList.remove('active');
  };

  // Sound Board Buttons (Explorer Column)
  const soundBtns = document.querySelectorAll('[data-sound]');
  soundBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const soundType = btn.dataset.sound;
      btn.classList.add('btn-bounce');
      setTimeout(() => btn.classList.remove('btn-bounce'), 250);

      if (!window.eduAudio) return;

      switch (soundType) {
        case 'coin':
          window.eduAudio.playCoin();
          updateCoinDisplay(10);
          break;
        case 'correct':
          window.eduAudio.playCorrect();
          break;
        case 'wrong':
          window.eduAudio.playWrong();
          break;
        case 'tick':
          window.eduAudio.playTick();
          break;
        case 'streak':
          window.eduAudio.playStreak();
          break;
        case 'victory':
          window.eduAudio.playVictory();
          break;
      }
    });
  });

  // Quiz Simulator Logic
  const quizOptions = document.querySelectorAll('.quiz-option-btn');
  const timerBar = document.getElementById('quizTimerBar');
  const timerText = document.getElementById('quizTimerText');

  function startQuizTimer() {
    stopQuizTimer();
    state.timerSeconds = 15;
    if (timerText) timerText.textContent = `${state.timerSeconds}s`;
    if (timerBar) timerBar.style.width = '100%';

    state.timerInterval = setInterval(() => {
      state.timerSeconds--;
      if (timerText) timerText.textContent = `${state.timerSeconds}s`;
      if (timerBar) {
        const pct = (state.timerSeconds / 15) * 100;
        timerBar.style.width = `${pct}%`;
        if (state.timerSeconds <= 5) {
          timerBar.style.background = '#EF4444';
          if (window.eduAudio) window.eduAudio.playTick();
        } else {
          timerBar.style.background = '#FF7527';
        }
      }

      if (state.timerSeconds <= 0) {
        stopQuizTimer();
        if (window.eduAudio) window.eduAudio.playWrong();
      }
    }, 1000);
  }

  function stopQuizTimer() {
    if (state.timerInterval) {
      clearInterval(state.timerInterval);
      state.timerInterval = null;
    }
  }

  quizOptions.forEach(opt => {
    opt.addEventListener('click', () => {
      if (state.quizAnswered) return;
      const isCorrect = opt.dataset.correct === 'true';

      if (isCorrect) {
        opt.classList.add('correct-glow');
        if (window.eduAudio) {
          window.eduAudio.playCorrect();
          setTimeout(() => window.eduAudio.playCoin(), 300);
        }
        updateCoinDisplay(50);
        stopQuizTimer();
        state.quizAnswered = true;

        setTimeout(() => {
          window.openVictoryModal(50);
        }, 1000);
      } else {
        opt.classList.add('wrong-shake');
        if (window.eduAudio) {
          window.eduAudio.playWrong();
        }
        setTimeout(() => opt.classList.remove('wrong-shake'), 600);
      }
    });
  });

  // Handle Mythological Options in Simulator
  window.handleSimAnswer = function(btnEl, isCorrect) {
    if (state.quizAnswered) return;

    if (isCorrect) {
      btnEl.classList.add('correct-glow');
      if (window.eduAudio) {
        window.eduAudio.playCorrect();
        setTimeout(() => window.eduAudio.playCoin(), 300);
      }
      updateCoinDisplay(2185);
      stopQuizTimer();
      state.quizAnswered = true;

      setTimeout(() => {
        window.openVictoryModal(2185);
      }, 900);
    } else {
      btnEl.classList.add('wrong-shake');
      if (window.eduAudio) {
        window.eduAudio.playWrong();
      }
      setTimeout(() => btnEl.classList.remove('wrong-shake'), 600);
    }
  };

  // Reset Quiz State
  window.resetQuizSimulator = function() {
    state.quizAnswered = false;
    document.querySelectorAll('.answer-card, .quiz-option-btn').forEach(opt => {
      opt.classList.remove('correct-glow', 'wrong-shake');
    });
    startQuizTimer();
  };

  // Podium Click Fun Interactions
  const podiumCols = document.querySelectorAll('.podium-column');
  podiumCols.forEach(col => {
    col.addEventListener('click', () => {
      col.classList.add('btn-bounce');
      setTimeout(() => col.classList.remove('btn-bounce'), 300);
      if (window.eduAudio) {
        window.eduAudio.playStreak();
      }
    });
  });
});

