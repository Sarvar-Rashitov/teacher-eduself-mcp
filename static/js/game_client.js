/**
 * EduSelf — Real-Time WebSocket Game Engine Client
 * Adheres strictly to REALTIME_PROTOCOL.md, EVENTS.md, and Zero-Knowledge principles.
 */

class EduGameWebSocket {
  constructor(endpoint, onMessageCallback) {
    this.endpoint = endpoint;
    this.onMessageCallback = onMessageCallback;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.pingInterval = null;
    this.isConnected = false;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}${this.endpoint}`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this._startHeartbeat();
        if (this.onOpen) this.onOpen();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'pong') {
            return; // Heartbeat response
          }
          if (this.onMessageCallback) {
            this.onMessageCallback(data);
          }
        } catch (e) {
          console.error('[EduSelf WS] JSON Parse Error:', e);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('[EduSelf WS] Connection error:', err);
      };

      this.ws.onclose = (event) => {
        this.isConnected = false;
        this._stopHeartbeat();
        if (this.onClose) this.onClose(event);
        this._tryReconnect();
      };
    } catch (e) {
      console.error('[EduSelf WS] Socket init failed:', e);
      this._tryReconnect();
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.pingInterval = setInterval(() => {
      this.send({ type: 'ping', client_ts: Date.now() });
    }, 15000);
  }

  _stopHeartbeat() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  _tryReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
      setTimeout(() => {
        this.connect();
      }, delay);
    }
  }

  disconnect() {
    this._stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

/**
 * Student WebSocket Client
 */
class EduStudentClient {
  constructor(roomCode, ticket = '', nickname = '', avatar = '🦁') {
    this.roomCode = roomCode;
    this.ticket = ticket;
    this.nickname = nickname;
    this.avatar = avatar;
    this.eventHandlers = {};

    const query = this.ticket ? `?ticket=${encodeURIComponent(this.ticket)}` : '';
    this.socket = new EduGameWebSocket(`/ws/session/${roomCode}/${query}`, (msg) => this._handleMessage(msg));
  }

  on(eventType, handler) {
    if (!this.eventHandlers[eventType]) {
      this.eventHandlers[eventType] = [];
    }
    this.eventHandlers[eventType].push(handler);
  }

  emit(eventType, data) {
    const handlers = this.eventHandlers[eventType] || [];
    handlers.forEach(fn => fn(data));
  }

  start() {
    this.socket.onOpen = () => {
      this.emit('connected', { roomCode: this.roomCode });
      if (!this.ticket && this.nickname) {
        this.socket.send({
          type: 'session.join',
          payload: { nickname: this.nickname, avatar: this.avatar }
        });
      }
    };
    this.socket.connect();
  }

  submitAnswer(questionId, selectedIndex) {
    const payload = {
      submission_id: 'sub_' + Math.random().toString(36).substr(2, 9),
      question_id: questionId,
      response_data: { selected_index: selectedIndex },
      submitted_at: Date.now()
    };
    this.socket.send({
      type: 'game.submit_answer',
      payload: payload
    });
    if (window.triggerHaptic) window.triggerHaptic('light');
  }

  _handleMessage(msg) {
    const type = msg.type;
    const payload = msg.payload || {};

    if (type === 'session.state_changed') {
      this.emit('state_changed', payload);
    } else if (type === 'question.revealed') {
      if (window.eduAudio) window.eduAudio.playTick();
      this.emit('question_revealed', payload);
    } else if (type === 'game.answer_result') {
      if (payload.is_correct) {
        if (window.eduAudio) {
          window.eduAudio.playCorrect();
          setTimeout(() => window.eduAudio.playCoin(), 300);
        }
        if (window.triggerHaptic) window.triggerHaptic('success');
      } else {
        if (window.eduAudio) window.eduAudio.playWrong();
        if (window.triggerHaptic) window.triggerHaptic('error');
      }
      this.emit('answer_result', payload);
    } else if (type === 'leaderboard.updated') {
      this.emit('leaderboard_updated', payload);
    } else if (type === 'game.finished') {
      if (window.eduAudio) window.eduAudio.playVictory();
      this.emit('game_finished', payload);
    }
  }
}

/**
 * Teacher / Host Stage WebSocket Client
 */
class EduHostClient {
  constructor(roomCode) {
    this.roomCode = roomCode;
    this.eventHandlers = {};
    this.socket = new EduGameWebSocket(`/ws/host/${roomCode}/`, (msg) => this._handleMessage(msg));
  }

  on(eventType, handler) {
    if (!this.eventHandlers[eventType]) {
      this.eventHandlers[eventType] = [];
    }
    this.eventHandlers[eventType].push(handler);
  }

  emit(eventType, data) {
    const handlers = this.eventHandlers[eventType] || [];
    handlers.forEach(fn => fn(data));
  }

  start() {
    this.socket.onOpen = () => this.emit('connected', { roomCode: this.roomCode });
    this.socket.connect();
  }

  startGame() {
    this.socket.send({ action: 'host.start_game', payload: {} });
  }

  nextQuestion() {
    this.socket.send({ action: 'host.next_question', payload: {} });
  }

  showPodium() {
    this.socket.send({ action: 'host.show_podium', payload: {} });
    if (window.eduAudio) window.eduAudio.playVictory();
  }

  endSession() {
    this.socket.send({ action: 'host.end_session', payload: {} });
  }

  _handleMessage(msg) {
    const type = msg.type || msg.action;
    const payload = msg.payload || {};

    if (type === 'session.participant_joined') {
      if (window.eduAudio) window.eduAudio.playTick();
      this.emit('participant_joined', payload);
    } else if (type === 'session.state_changed') {
      this.emit('state_changed', payload);
    } else if (type === 'leaderboard.updated') {
      this.emit('leaderboard_updated', payload);
    }
  }
}

// Global exposure
window.EduStudentClient = EduStudentClient;
window.EduHostClient = EduHostClient;
