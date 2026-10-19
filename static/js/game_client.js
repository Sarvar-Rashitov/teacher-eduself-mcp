/**
 * EduSelf Teacher — Real-Time WebSocket Game Client
 * Manages WebSocket connectivity for both Students and Hosts with
 * automatic reconnection, state dispatching, and sound effects.
 */

class EduGameClient {
  constructor(options = {}) {
    this.roomCode = options.roomCode || '';
    this.isHost = options.isHost || false;
    this.token = options.token || localStorage.getItem('eduself_reconnect_token') || '';
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.listeners = {};
    this.isConnected = false;
  }

  // Event listener registration
  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
    return this;
  }

  emit(event, data) {
    const handlers = this.listeners[event] || [];
    handlers.forEach(fn => fn(data));
  }

  connect() {
    if (!this.roomCode) {
      console.error("[EduGameClient] roomCode is required to connect");
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    let url = '';

    if (this.isHost) {
      url = `${protocol}//${host}/ws/host/${this.roomCode}/`;
    } else {
      url = `${protocol}//${host}/ws/session/${this.roomCode}/`;
      if (this.token) {
        url += `?token=${encodeURIComponent(this.token)}`;
      }
    }

    console.log(`[EduGameClient] Connecting to ${url}`);
    this.socket = new WebSocket(url);

    this.socket.onopen = (e) => {
      console.log("[EduGameClient] Connected successfully!");
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.emit('connected', e);
    };

    this.socket.onmessage = (event) => {
      try {
        const packet = JSON.parse(event.data);
        this.handleMessage(packet);
      } catch (err) {
        console.error("[EduGameClient] Failed to parse message:", err, event.data);
      }
    };

    this.socket.onclose = (event) => {
      this.isConnected = false;
      this.emit('disconnected', event);
      if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
        const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts);
        this.reconnectAttempts++;
        console.warn(`[EduGameClient] Connection lost. Reconnecting in ${delay}ms... (Attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
      }
    };

    this.socket.onerror = (error) => {
      console.error("[EduGameClient] WebSocket error:", error);
      this.emit('error', error);
    };
  }

  send(action, payload = {}) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ action, ...payload }));
    } else {
      console.warn("[EduGameClient] Cannot send message, socket is not open");
    }
  }

  // Incoming WebSocket protocol message dispatch
  handleMessage(packet) {
    const type = packet.type || packet.action;
    console.log("[EduGameClient] Received:", type, packet);

    // Save reconnection token if returned
    if (packet.token) {
      this.token = packet.token;
      localStorage.setItem('eduself_reconnect_token', packet.token);
    }

    switch (type) {
      case 'join_ack':
      case 'joined':
        this.emit('joined', packet);
        break;

      case 'question_start':
      case 'new_question':
        if (window.eduAudio) window.eduAudio.playTick();
        this.emit('question_start', packet);
        break;

      case 'answer_result':
        if (packet.is_correct) {
          if (window.eduAudio) window.eduAudio.playCorrect();
        } else {
          if (window.eduAudio) window.eduAudio.playWrong();
        }
        this.emit('answer_result', packet);
        break;

      case 'reveal_answers':
        this.emit('reveal_answers', packet);
        break;

      case 'leaderboard_update':
        this.emit('leaderboard_update', packet);
        break;

      case 'game_over':
      case 'podium':
        if (window.eduAudio) window.eduAudio.playVictory();
        this.emit('game_over', packet);
        break;

      default:
        this.emit(type, packet);
        break;
    }
  }

  // Student Actions
  joinGame(nickname) {
    this.send('join', { nickname });
  }

  submitAnswer(questionId, answerPayload, responseTimeMs = 0) {
    if (navigator.vibrate) {
      navigator.vibrate(15);
    }
    this.send('submit_answer', {
      question_id: questionId,
      answer: answerPayload,
      response_time_ms: responseTimeMs,
    });
  }

  // Host Actions
  hostStartGame() {
    this.send('start_session');
  }

  hostNextQuestion() {
    this.send('next_question');
  }

  hostRevealAnswers() {
    this.send('reveal_answers');
  }

  hostEndGame() {
    this.send('end_session');
  }
}

window.EduGameClient = EduGameClient;
