/**
 * EduSelf — Floating AI Assistant & Platform Command Center
 * Located in the bottom-right corner. Controls quizzes, live sessions, analytics, and Web Audio.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const widget = document.getElementById('floatingAiWidget');
    const trigger = document.getElementById('floatingAiTrigger');
    const modal = document.getElementById('aiCommandModal');
    const closeBtn = document.getElementById('aiModalCloseBtn');
    const chatBody = document.getElementById('aiChatBody');
    const input = document.getElementById('aiModalInput');
    const sendBtn = document.getElementById('aiModalSendBtn');

    if (!widget || !trigger || !modal) return;

    let isOpen = false;

    function openModal() {
      isOpen = true;
      modal.style.display = 'flex';
      widget.classList.add('is-open');
      if (input) input.focus();
      if (window.eduAudio) window.eduAudio.playTick();
    }

    function closeModal() {
      isOpen = false;
      modal.style.display = 'none';
      widget.classList.remove('is-open');
    }

    function toggleModal() {
      if (isOpen) {
        closeModal();
      } else {
        openModal();
      }
    }

    // Global hooks
    window.toggleAiModal = toggleModal;
    window.openAiModalWithPrompt = function (promptText) {
      openModal();
      if (input) {
        input.value = promptText;
        handleSend();
      }
    };

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleModal();
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        closeModal();
      });
    }

    // Click outside to close
    document.addEventListener('click', (e) => {
      if (isOpen && !widget.contains(e.target)) {
        closeModal();
      }
    });

    // Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && isOpen) {
        closeModal();
      }
    });

    // Command Chips Handlers
    const commandChips = modal.querySelectorAll('[data-ai-action]');
    commandChips.forEach(chip => {
      chip.addEventListener('click', (e) => {
        e.preventDefault();
        const action = chip.getAttribute('data-ai-action');
        executePlatformAction(action);
      });
    });

    function executePlatformAction(action) {
      if (window.eduAudio) window.eduAudio.playTick();

      switch (action) {
        case 'new-quiz':
          appendUserMessage("Yangi viktorina yaratish");
          showAiTyping();
          setTimeout(() => {
            removeAiTyping();
            appendAiMessage("Ajoyib! Viktorina yaratish muharriri ochilmoqda. Qaysi fan va mavzudan test tuzmoqchisiz?");
            if (window.eduAudio) window.eduAudio.playCoin();
            setTimeout(() => {
              window.location.href = '/editor/new/';
            }, 900);
          }, 600);
          break;

        case 'live-game':
          appendUserMessage("Jonli dars o‘yinini boshlash");
          showAiTyping();
          setTimeout(() => {
            removeAiTyping();
            appendAiMessage("Eng so‘nggi chop etilgan test bo‘yicha jonli sinf arenasi faollashtirilmoqda! PIN kod: 489201");
            if (window.eduAudio) window.eduAudio.playCoin();
            setTimeout(() => {
              window.location.href = '/live/489201/';
            }, 1000);
          }, 600);
          break;

        case 'analytics':
          appendUserMessage("Sinf o‘zlashtirish statistikasi");
          showAiTyping();
          setTimeout(() => {
            removeAiTyping();
            appendAiMessage(`
              <strong>📊 7-8 sinflar bo‘yicha tahlil:</strong><br>
              • Jami faol o‘quvchilar: <strong>156 nafar</strong><br>
              • O‘rtacha aniqlik: <span style="color:#10B981;font-weight:700;">82% (A’lo)</span><br>
              • Eng faol fan: <em>Fizika (Zichlik mavzusi)</em><br>
              • AI token byudjeti: <strong>864,200 / 1,000,000</strong>
            `);
            if (window.eduAudio) window.eduAudio.playCoin();
          }, 700);
          break;

        case 'sound-toggle':
          const isMuted = window.eduAudio ? window.eduAudio.toggleMute() : false;
          if (window.eduState) {
            window.eduState.isMuted = isMuted;
            window.eduState.soundEnabled = !isMuted;
          }
          const soundChip = modal.querySelector('[data-ai-action="sound-toggle"]');
          if (soundChip) {
            soundChip.innerHTML = isMuted ? '🔇 Tovush: O‘chiq' : '🔊 Tovush: Yoqilgan';
          }
          appendAiMessage(isMuted ? "Tizim tovushlari o‘chirildi 🔇" : "Tizim tovushlari muvaffaqiyatli yoqildi 🔊");
          if (!isMuted && window.eduAudio) window.eduAudio.playTick();
          break;

        case 'leaderboard':
          appendUserMessage("Peshqadamlar jadvalini ko‘rish");
          setTimeout(() => {
            window.location.href = '/leaderboard/';
          }, 400);
          break;
      }
    }

    // Chat Message Rendering
    function appendUserMessage(text) {
      if (!chatBody) return;
      const msg = document.createElement('div');
      msg.className = 'ai-chat-bubble user-bubble';
      msg.textContent = text;
      chatBody.appendChild(msg);
      chatBody.scrollTop = chatBody.scrollHeight;
    }

    function appendAiMessage(htmlContent) {
      if (!chatBody) return;
      const msg = document.createElement('div');
      msg.className = 'ai-chat-bubble ai-bubble';
      msg.innerHTML = htmlContent;
      chatBody.appendChild(msg);
      chatBody.scrollTop = chatBody.scrollHeight;
    }

    function showAiTyping() {
      if (!chatBody) return;
      const typing = document.createElement('div');
      typing.id = 'aiTypingIndicator';
      typing.className = 'ai-chat-bubble ai-bubble typing-bubble';
      typing.innerHTML = `
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      `;
      chatBody.appendChild(typing);
      chatBody.scrollTop = chatBody.scrollHeight;
    }

    function removeAiTyping() {
      const el = document.getElementById('aiTypingIndicator');
      if (el) el.remove();
    }

    // Send Button and Enter Key
    function handleSend() {
      if (!input) return;
      const val = input.value.trim();
      if (!val) return;

      input.value = '';
      appendUserMessage(val);
      showAiTyping();
      if (window.eduAudio) window.eduAudio.playTick();

      // Simulate AI intelligent reasoning & question generation
      setTimeout(() => {
        removeAiTyping();
        generateQuizPreview(val);
        if (window.eduAudio) window.eduAudio.playCoin();
      }, 1000);
    }

    function generateQuizPreview(prompt) {
      const cardHtml = `
        <div class="ai-generated-card">
          <div class="ai-generated-header">
            <span class="ai-tag">AI GENERATSIYA</span>
            <span class="ai-grade-tag">7-Sinf Standarti</span>
          </div>
          <div class="ai-question-title">
            <strong>Savol:</strong> ${escapeHtml(prompt)} bo‘yicha qaysi qonuniyat to‘g‘ri ifodalangan?
          </div>
          <div class="ai-options-list">
            <div class="ai-option correct"><span class="opt-key">A</span> Zichlik massa va hajm nisbatiga teng (ρ = m / V) ✓</div>
            <div class="ai-option"><span class="opt-key">B</span> Zichlik faqat jism shakliga bog‘liq</div>
            <div class="ai-option"><span class="opt-key">C</span> Hajm o‘zgarmaganda massa har doim kamayadi</div>
            <div class="ai-option"><span class="opt-key">D</span> Zichlik birligi Nyutonda o‘lchanadi</div>
          </div>
          <div class="ai-card-actions">
            <a href="/editor/new/?topic=${encodeURIComponent(prompt)}" class="ai-save-btn">
              Viktorinaga Saqlash va Tahrirlash →
            </a>
          </div>
        </div>
      `;
      appendAiMessage(`Mavzu bo‘yicha standartlarga mos savol tayyorlandi:<br>` + cardHtml);
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

    if (sendBtn) {
      sendBtn.addEventListener('click', handleSend);
    }

    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          handleSend();
        }
      });
    }
  });
})();
