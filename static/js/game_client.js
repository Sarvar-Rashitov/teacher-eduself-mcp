/**
 * EduSelf Teacher — "EduPlay 3D" Real-Time WebSocket Game Client
 * Manages WebSocket connection to /ws/session/<room_code>/, event dispatching,
 * state synchronization, answer submission, and procedural audio feedback.
 */

class EduPlayGameClient {
  constructor(roomCode, options = {}) {
    this.roomCode = roomCode;
    this.options = Object.assign({
      isHost: false,
      nickname: "",
      reconnectToken: null,
      autoReconnect: true,
      maxReconnectAttempts: 5,
    }, options);

    this.socket = null;
    this.reconnectAttempts = 0;
    this.reconnectTimer = null;
    this.pingInterval = null;
    this.handlers = {};

    this.state = {
      connected: false,
      status: "lobby",
      currentQuestion: null,
      currentQuestionIndex: 0,
      totalQuestions: 0,
      answered: false,
      score: 0,
      streak: 0,
      participants: [],
      leaderboard: [],
    };
  }

  // Event handler registration
  on(event, handler) {
    if (!this.handlers[event]) {
      this.handlers[event] = [];
    }
    this.handlers[event].push(handler);
    return this;
  }

  emit(event, data) {
    if (this.handlers[event]) {
      this.handlers[event].forEach(fn => {
        try { fn(data); } catch (e) { console.error(`Error in handler for ${event}:`, e); }
      });
    }
    // Also dispatch to document for UI templates
    document.dispatchEvent(new CustomEvent(`eduself:${event}`, { detail: data }));
  }

  // Connect to Django Channels WebSocket endpoint
  connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/session/${this.roomCode}/`;

    console.log(`[EduPlay WS] Connecting to ${wsUrl}...`);
    this.socket = new WebSocket(wsUrl);

    this.socket.onopen = () => {
      console.log(`[EduPlay WS] Connected to room ${this.roomCode}!`);
      this.state.connected = true;
      this.reconnectAttempts = 0;
      this.emit("connected", { roomCode: this.roomCode });

      // Start ping/pong heartbeat every 20 seconds
      this.startHeartbeat();

      // If reconnect token exists, reconnect
      if (this.options.reconnectToken) {
        this.reconnect(this.options.reconnectToken);
      } else if (this.options.nickname && !this.options.isHost) {
        this.join(this.options.nickname);
      }
    };

    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleIncomingMessage(message);
      } catch (err) {
        console.error("[EduPlay WS] JSON parse error:", err);
      }
    };

    this.socket.onclose = (event) => {
      console.warn(`[EduPlay WS] Disconnected (code: ${event.code})`);
      this.state.connected = false;
      this.stopHeartbeat();
      this.emit("disconnected", { code: event.code });

      if (this.options.autoReconnect && this.reconnectAttempts < this.options.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
        console.log(`[EduPlay WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})...`);
        this.reconnectTimer = setTimeout(() => this.connect(), delay);
      }
    };

    this.socket.onerror = (err) => {
      console.error("[EduPlay WS] Socket error:", err);
      this.emit("error", err);
    };
  }

  // Send JSON message to server
  send(type, payload = {}) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn("[EduPlay WS] Cannot send message: Socket is not open.");
      return false;
    }
    const message = { type, payload, client_ts: Date.now() };
    this.socket.send(JSON.stringify(message));
    return true;
  }

  // Heartbeat ping/pong
  startHeartbeat() {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => {
      this.send("ping", { client_ts: Date.now() });
    }, 20000);
  }

  stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  // Handle incoming server messages
  handleIncomingMessage(message) {
    const type = message.type;
    const payload = message.payload || message;

    console.log(`[EduPlay WS] Received: ${type}`, payload);

    switch (type) {
      case "session.welcome":
        this.emit("welcome", payload);
        break;

      case "session.state_sync":
        this.state.status = payload.status;
        this.state.currentQuestionIndex = payload.current_question_index;
        this.emit("state_sync", payload);
        break;

      case "session.started":
        this.state.status = "active";
        this.emit("session_started", payload);
        this.emit("session.started", payload);
        break;

      case "participant.joined":
        this.state.participants.push(payload.participant || payload);
        if (window.eduAudio) window.eduAudio.playCoin();
        this.emit("participant_joined", payload);
        this.emit("participant.joined", payload);
        break;

      case "question.opened":
        this.state.status = "question_active";
        this.state.currentQuestion = payload;
        this.state.answered = false;
        this.emit("question_opened", payload);
        this.emit("question.opened", payload);
        break;

      case "answer.count_updated":
        this.emit("answer_count_updated", payload);
        this.emit("answer.count_updated", payload);
        break;

      case "question.start":
        this.state.status = "question_active";
        this.state.currentQuestion = payload.question;
        this.state.currentQuestionIndex = payload.question_index;
        this.state.totalQuestions = payload.total_questions;
        this.state.answered = false;
        if (window.eduAudio) window.eduAudio.playTick();
        this.emit("question_start", payload);
        break;

      case "question.reveal":
        this.state.status = "question_reveal";
        if (payload.is_user_correct === true) {
          if (window.eduAudio) window.eduAudio.playCorrect();
        } else if (payload.is_user_correct === false) {
          if (window.eduAudio) window.eduAudio.playWrong();
        }
        this.emit("question_reveal", payload);
        break;

      case "leaderboard.update":
        this.state.leaderboard = payload.leaderboard || [];
        this.emit("leaderboard_update", payload);
        break;

      case "session.ended":
        this.state.status = "completed";
        if (window.eduAudio) window.eduAudio.playVictory();
        this.emit("session_ended", payload);
        break;

      case "error":
        this.emit("server_error", payload);
        break;

      default:
        this.emit(type, payload);
        break;
    }
  }

  // Actions
  join(nickname) {
    this.options.nickname = nickname;
    this.send("participant.join", { nickname });
  }

  reconnect(token) {
    this.options.reconnectToken = token;
    this.send("participant.reconnect", { token });
  }

  submitAnswer(submissionId, answer, timeTakenMs = 0) {
    if (this.state.answered) return false;
    this.state.answered = true;

    if (window.eduAudio) window.eduAudio.playTick();

    return this.send("participant.answer", {
      submission_id: submissionId || `sub_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      user_answer: answer,
      time_taken_ms: timeTakenMs,
    });
  }

  // Host Controls
  hostStartGame() {
    return this.send("host.start_game", {});
  }

  hostNextQuestion() {
    return this.send("host.next_question", {});
  }

  hostRevealAnswer() {
    return this.send("host.reveal_answer", {});
  }

  hostEndGame() {
    return this.send("host.end_game", {});
  }

  disconnect() {
    this.options.autoReconnect = false;
    this.stopHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.socket) this.socket.close();
  }
}

// Global factory
window.EduPlayGameClient = EduPlayGameClient;
