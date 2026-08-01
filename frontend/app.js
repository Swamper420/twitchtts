// TwitchTTS Client Application Logic & Web Audio Queue Sequencer

class TwitchTTSApp {
  constructor() {
    this.ws = null;
    this.audioCtx = null;
    this.isOverlay = window.location.search.includes('overlay=true') || window.location.hash === '#overlay';
    this.voices = [];
    this.queueState = { current: null, queue: [], history: [], count: 0 };
    this.isPlayingAudio = false;

    this.init();
  }

  async init() {
    if (this.isOverlay) {
      document.body.classList.add('overlay-body');
      document.getElementById('dashboardView').classList.remove('active');
      document.getElementById('overlayView').classList.add('active');
      document.querySelector('.app-header')?.remove();
    }

    this.setupEventListeners();
    await this.fetchSettings();
    await this.fetchVoices();
    this.connectWebSocket();
  }

  setupEventListeners() {
    if (!this.isOverlay) {
      document.getElementById('sendTtsBtn')?.addEventListener('click', () => this.sendTtsMessage());
      document.getElementById('directSynthesizeBtn')?.addEventListener('click', () => this.directSynthesize());
      document.getElementById('clearQueueBtn')?.addEventListener('click', () => this.clearQueue());
      document.getElementById('skipQueueBtn')?.addEventListener('click', () => this.skipQueue());
      document.getElementById('saveSettingsBtn')?.addEventListener('click', () => this.saveSettings());
      document.getElementById('openOverlayBtn')?.addEventListener('click', () => {
        window.open(window.location.origin + '/?overlay=true', '_blank', 'width=600,height=300');
      });
    }

    // Initialize Web Audio API on first user click
    window.addEventListener('click', () => {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
    }, { once: true });
  }

  connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.updateWsStatus('connecting', 'Connecting...');
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.updateWsStatus('online', 'Connected');
    };

    this.ws.onmessage = async (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'QUEUE_UPDATE') {
          this.handleQueueUpdate(message.data);
        }
      } catch (err) {
        console.error("WS message parse error:", err);
      }
    };

    this.ws.onclose = () => {
      this.updateWsStatus('offline', 'Disconnected');
      setTimeout(() => this.connectWebSocket(), 3000);
    };

    this.ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };
  }

  updateWsStatus(state, label) {
    const statusDot = document.querySelector('#wsStatus .status-dot');
    const statusLabel = document.querySelector('#wsStatus .status-label');
    if (statusDot && statusLabel) {
      statusDot.className = `status-dot ${state}`;
      statusLabel.textContent = label;
    }
  }

  async fetchSettings() {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      if (data.twitch_channel) {
        const channelName = document.getElementById('channelName');
        const channelInput = document.getElementById('twitchChannelInput');
        if (channelName) channelName.textContent = `#${data.twitch_channel}`;
        if (channelInput) channelInput.value = data.twitch_channel;
      }
    } catch (err) {
      console.error("Error fetching settings:", err);
    }
  }

  async fetchVoices() {
    try {
      const res = await fetch('/api/voices');
      const data = await res.json();
      this.voices = data.voices || [];
      this.renderVoiceSelectors();
    } catch (err) {
      console.error("Error fetching voices:", err);
    }
  }

  renderVoiceSelectors() {
    const select = document.getElementById('defaultVoiceSelect');
    const pills = document.getElementById('quickVoicePills');
    const grid = document.getElementById('voicesGrid');

    if (select) {
      select.innerHTML = this.voices.map(v => `<option value="${v.name}">${v.name}</option>`).join('');
    }

    if (pills) {
      pills.innerHTML = this.voices.map(v => 
        `<span class="voice-pill" onclick="app.insertVoiceTag('${v.name}')">[${v.name}]</span>`
      ).join('');
    }

    if (grid) {
      grid.innerHTML = this.voices.map(v => `
        <div class="voice-card" onclick="app.insertVoiceTag('${v.name}')">
          <div class="voice-card-name">${v.name}</div>
        </div>
      `).join('');
    }
  }

  insertVoiceTag(voiceName) {
    const input = document.getElementById('multiVoiceInput');
    if (input) {
      input.value += ` [${voiceName}] `;
      input.focus();
    }
  }

  async handleQueueUpdate(newState) {
    this.queueState = newState;
    this.renderQueueUI();

    // Check if there is an item ready to play and we're not currently playing audio
    if (newState.current && newState.current.status === 'playing' && !this.isPlayingAudio) {
      this.playQueueItem(newState.current);
    } else if (!newState.current && newState.queue.length > 0 && !this.isPlayingAudio) {
      // Fetch next item via pop/poll API if needed
      this.pollNextQueueItem();
    }
  }

  renderQueueUI() {
    if (this.isOverlay) {
      const current = this.queueState.current;
      const obsUser = document.getElementById('obsUser');
      const obsText = document.getElementById('obsText');
      const obsVoice = document.getElementById('obsVoice');

      if (current) {
        if (obsUser) obsUser.textContent = current.user;
        if (obsText) obsText.textContent = current.raw_text;
        if (obsVoice) obsVoice.textContent = current.segments.map(s => s.voice).join(', ');
      }
      return;
    }

    const currentCard = document.getElementById('nowPlayingCard');
    const currentContent = document.getElementById('nowPlayingContent');
    const queueList = document.getElementById('queueList');

    if (this.queueState.current && currentContent) {
      const cur = this.queueState.current;
      currentContent.innerHTML = `
        <div class="queue-item playing">
          <div>
            <div class="queue-user"><i class="fa-solid fa-microphone"></i> ${cur.user}</div>
            <div class="queue-text">${cur.raw_text}</div>
            <div class="voice-pills" style="margin-top: 6px;">
              ${cur.segments.map(s => `<span class="voice-pill">[${s.voice}] "${s.text}"</span>`).join('')}
            </div>
          </div>
        </div>
      `;
    } else if (currentContent) {
      currentContent.innerHTML = `<p class="idle-msg">No active speech playing. Messages in Twitch chat will automatically read back here!</p>`;
    }

    if (queueList) {
      if (this.queueState.queue.length === 0) {
        queueList.innerHTML = `<p class="idle-msg" style="text-align: center; padding: 1rem;">Queue is empty.</p>`;
      } else {
        queueList.innerHTML = this.queueState.queue.map((item, idx) => `
          <div class="queue-item">
            <div>
              <span class="queue-user">#${idx + 1} ${item.user}</span>
              <div class="queue-text">${item.raw_text}</div>
            </div>
            <span class="status-badge">${item.status}</span>
          </div>
        `).join('');
      }
    }
  }

  async pollNextQueueItem() {
    try {
      const res = await fetch('/api/queue');
      const state = await res.json();
      if (state.queue.length > 0 && !this.isPlayingAudio) {
        // Trigger next item playback
      }
    } catch (err) {
      console.error("Queue poll error:", err);
    }
  }

  async playQueueItem(item) {
    if (this.isPlayingAudio) return;
    this.isPlayingAudio = true;

    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }

      for (let i = 0; i < item.segments.length; i++) {
        const audioUrl = `/api/queue/audio/${item.id}/${i}`;
        await this.playAudioSegment(audioUrl);
      }

      // Mark item finished on backend
      await fetch('/api/queue/skip', { method: 'POST' });
    } catch (err) {
      console.error("Audio playback error:", err);
    } finally {
      this.isPlayingAudio = false;
    }
  }

  playAudioSegment(url) {
    return new Promise(async (resolve, reject) => {
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const arrayBuffer = await response.arrayBuffer();
        const audioBuffer = await this.audioCtx.decodeAudioData(arrayBuffer);

        const source = this.audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioCtx.destination);

        source.onended = () => resolve();
        source.start(0);
      } catch (err) {
        console.error("Failed to decode audio segment:", err);
        resolve(); // Continue playback sequence even if segment fails
      }
    });
  }

  async sendTtsMessage() {
    const user = document.getElementById('speakerUser')?.value || 'Streamer';
    const text = document.getElementById('multiVoiceInput')?.value || '';

    if (!text.trim()) return;

    try {
      await fetch('/api/queue/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user, text })
      });
      document.getElementById('multiVoiceInput').value = '';
    } catch (err) {
      console.error("Error adding message:", err);
    }
  }

  async directSynthesize() {
    const text = document.getElementById('multiVoiceInput')?.value || 'Tervehdys kaikille';
    if (!text.trim()) return;

    try {
      const response = await fetch(`/api/tts?text=${encodeURIComponent(text)}`);
      const blob = await response.blob();
      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      audio.play();
    } catch (err) {
      console.error("Direct synthesis error:", err);
    }
  }

  async skipQueue() {
    await fetch('/api/queue/skip', { method: 'POST' });
  }

  async clearQueue() {
    await fetch('/api/queue/clear', { method: 'POST' });
  }

  async saveSettings() {
    const twitchChannel = document.getElementById('twitchChannelInput')?.value;
    const defaultVoice = document.getElementById('defaultVoiceSelect')?.value;

    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          twitch_channel: twitchChannel,
          chatterbox_default_voice: defaultVoice
        })
      });
      alert("Settings saved successfully!");
      this.fetchSettings();
    } catch (err) {
      alert("Failed to save settings: " + err.message);
    }
  }
}

// Global App Instance
const app = new TwitchTTSApp();
