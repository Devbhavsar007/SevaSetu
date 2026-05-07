/**
 * WebSocket Manager for Volunteer App — real-time event subscriptions.
 */

const WS_BASE = 'wss://sevasetu-bnup.onrender.com';

function getWsUrl(room, token) {
  const isLocal = window.location.hostname === 'localhost';
  const base = isLocal ? 'ws://localhost:8000' : WS_BASE;
  return `${base}/ws/${room}/${token}`;
}

class WSManager {
  constructor() {
    this.ws = null;
    this.room = null;
    this.token = null;
    this.onMessage = null;
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 30000;
    this.reconnectTimer = null;
    this.pingTimer = null;
    this._listeners = [];
  }

  connect(room, token, onMessage) {
    this.room = room;
    this.token = token;
    this.onMessage = onMessage;
    this.reconnectAttempts = 0;
    this._doConnect();
  }

  _doConnect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) return;
    const url = getWsUrl(this.room, this.token);
    try { this.ws = new WebSocket(url); } catch (e) { this._scheduleReconnect(); return; }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this._notifyListeners({ type: '_connection', connected: true });
      this._startPing();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return;
        if (this.onMessage) this.onMessage(data);
        this._notifyListeners(data);
      } catch (e) { /* ignore */ }
    };

    this.ws.onclose = (event) => {
      this._stopPing();
      this._notifyListeners({ type: '_connection', connected: false });
      if (event.code !== 1000 && event.code < 4000) this._scheduleReconnect();
    };

    this.ws.onerror = () => {};
  }

  disconnect() {
    clearTimeout(this.reconnectTimer);
    this._stopPing();
    if (this.ws) { this.ws.close(1000); this.ws = null; }
    this._notifyListeners({ type: '_connection', connected: false });
  }

  isConnected() { return this.ws && this.ws.readyState === WebSocket.OPEN; }

  addListener(fn) {
    this._listeners.push(fn);
    return () => { this._listeners = this._listeners.filter(l => l !== fn); };
  }

  _notifyListeners(event) {
    this._listeners.forEach(fn => { try { fn(event); } catch (e) {} });
  }

  _scheduleReconnect() {
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => this._doConnect(), delay);
  }

  _startPing() {
    this._stopPing();
    this.pingTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send('ping');
    }, 25000);
  }

  _stopPing() { clearInterval(this.pingTimer); this.pingTimer = null; }
}

export const wsManager = new WSManager();
