// StreamBridge PWA — Main Application
(function () {
  'use strict';

  // ============ STATE ============
  const S = {
    connected: false,
    token: localStorage.getItem('sb_token') || '',
    streamState: 'idle',
    leftDb: -100, rightDb: -100,
    silenceStatus: 'ok',
    metadata: '', codec: '', bitrate: 0, sampleRate: 0, channels: 0,
    uptime: '', uptimeS: 0,
    clientCount: 0,
    micActive: false, micMode: '',
    sources: [],
    config: null,
    log: [],
    playlist: [],
    selectedPlayer: 'A',
    selectedPlaylist: 1,
    micModeTab: 'talkback',
    logFilter: 'all',
  };

  let ws = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  let micStream = null;
  let micContext = null;
  let micProcessor = null;

  const API = (path, opts = {}) => {
    const headers = { 'Content-Type': 'application/json' };
    if (S.token) headers['Authorization'] = 'Bearer ' + S.token;
    return fetch('/api/v1' + path, { ...opts, headers }).then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  };

  // ============ WEBSOCKET ============
  function wsConnect() {
    if (ws && ws.readyState <= 1) return;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    let url = proto + '//' + location.host + '/api/v1/ws';
    if (S.token) url += '?token=' + encodeURIComponent(S.token);
    ws = new WebSocket(url);

    ws.onopen = () => {
      S.connected = true;
      reconnectDelay = 1000;
      addLog('WebSocket connected', 'info');
      render();
    };
    ws.onclose = () => {
      S.connected = false;
      render();
      scheduleReconnect();
    };
    ws.onerror = () => {};
    ws.onmessage = (e) => {
      try { handleWsMsg(JSON.parse(e.data)); } catch (_) {}
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
      wsConnect();
    }, reconnectDelay);
  }

  function handleWsMsg(m) {
    switch (m.type) {
      case 'levels':
        S.leftDb = m.left_db; S.rightDb = m.right_db;
        updateMeters();
        return; // skip full render for perf
      case 'state_changed':
        S.streamState = m.state; break;
      case 'silence_warning': S.silenceStatus = 'warning'; break;
      case 'silence_alert': S.silenceStatus = 'alert'; break;
      case 'silence_ok': case 'silence_cleared': S.silenceStatus = 'ok'; break;
      case 'metadata':
        S.codec = m.codec; S.bitrate = m.bitrate; S.sampleRate = m.sample_rate;
        S.channels = m.channels; S.metadata = m.summary || ''; break;
      case 'uptime':
        S.uptime = m.formatted; S.uptimeS = m.seconds; break;
      case 'client_count': S.clientCount = m.count; break;
      case 'log':
        addLog(m.message, m.level || 'info'); break;
      case 'auto_stop':
        addLog('AUTO-STOP (' + m.detection_type + '): ' + m.reason, 'warning'); break;
      default: return;
    }
    render();
  }

  function addLog(msg, level) {
    const now = new Date();
    const t = now.toTimeString().slice(0, 8);
    S.log.push({ t, msg, level });
    if (S.log.length > 500) S.log.splice(0, S.log.length - 500);
  }

  // ============ INIT ============
  async function init() {
    try {
      const state = await API('/state');
      S.streamState = state.stream_state;
      S.clientCount = state.client_count;
      S.silenceStatus = state.silence_status;
      if (state.metadata) S.metadata = state.metadata.summary || '';
      S.connected = true;
    } catch (_) {
      S.connected = false;
    }

    try {
      const sr = await API('/sources');
      S.sources = sr.sources || [];
    } catch (_) {}

    try {
      S.config = await API('/config');
    } catch (_) {}

    wsConnect();
    render();
    showTab('dashboard');
  }

  // ============ RENDER ============
  let currentTab = 'dashboard';

  function showTab(id) {
    currentTab = id;
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-bar button').forEach(b => b.classList.remove('active'));
    const page = document.getElementById('page-' + id);
    const btn = document.getElementById('tab-' + id);
    if (page) page.classList.add('active');
    if (btn) btn.classList.add('active');
    if (id === 'log') renderLog();
    if (id === 'settings') renderSettings();
    if (id === 'sources') renderSources();
    if (id === 'mairlist') renderMairlist();
  }

  function render() {
    renderDashboard();
    if (currentTab === 'log') renderLog();
  }

  // ============ DASHBOARD ============
  function renderDashboard() {
    const st = S.streamState;
    const ledCls = st === 'connected' ? 'connected' : st === 'connecting' || st === 'reconnecting' ? 'connecting' : st === 'error' ? 'error' : '';
    const silCls = S.silenceStatus;
    const silTxt = S.silenceStatus === 'warning' ? 'Silence' : S.silenceStatus === 'alert' ? 'ALERT' : 'Audio OK';
    const streaming = st === 'connected';

    document.getElementById('dash-led').className = 'led ' + ledCls;
    document.getElementById('dash-state').textContent = st.toUpperCase();
    document.getElementById('dash-state').style.color = ledCls === 'connected' ? 'var(--green)' : ledCls === 'connecting' ? 'var(--yellow)' : ledCls === 'error' ? 'var(--red)' : 'var(--text2)';
    document.getElementById('dash-silence').className = 'silence-badge ' + silCls;
    document.getElementById('dash-silence').textContent = silTxt;
    document.getElementById('dash-uptime').textContent = S.uptime;
    document.getElementById('dash-meta').textContent = S.metadata;
    document.getElementById('dash-clients').textContent = S.clientCount + ' clients';
    document.getElementById('btn-start').disabled = streaming;
    document.getElementById('btn-stop').disabled = !streaming;

    // Source chips
    const chips = document.getElementById('dash-chips');
    chips.innerHTML = '';
    S.sources.forEach((s, i) => {
      const c = document.createElement('button');
      c.className = 'chip';
      c.textContent = s.name;
      c.onclick = () => { document.getElementById('dash-url').value = s.url; };
      chips.appendChild(c);
    });

    // Log preview
    const preview = document.getElementById('dash-log-preview');
    preview.innerHTML = '';
    S.log.slice(-3).forEach(e => {
      const d = document.createElement('div');
      d.className = 'log-entry log-' + e.level;
      d.innerHTML = '<span class="log-time">' + e.t + '</span><span class="log-dot"></span><span class="log-msg">' + esc(e.msg) + '</span>';
      preview.appendChild(d);
    });

    updateMeters();
  }

  function updateMeters() {
    setMeter('meter-l', S.leftDb);
    setMeter('meter-r', S.rightDb);
    document.getElementById('db-l').textContent = S.leftDb > -90 ? Math.round(S.leftDb) + '' : '-inf';
    document.getElementById('db-r').textContent = S.rightDb > -90 ? Math.round(S.rightDb) + '' : '-inf';
  }

  function setMeter(id, db) {
    const min = -60, max = 0;
    const pct = Math.max(0, Math.min(100, ((db - min) / (max - min)) * 100));
    document.getElementById(id).style.width = pct + '%';
  }

  // Dashboard actions
  function dashStart() {
    const url = document.getElementById('dash-url').value.trim();
    if (!url) return;
    API('/stream/start', { method: 'POST', body: JSON.stringify({ url }) });
  }
  function dashStop() {
    API('/stream/stop', { method: 'POST', body: JSON.stringify({}) });
  }

  // ============ MAIRLIST ============
  function renderMairlist() {
    // Player tabs
    document.querySelectorAll('.player-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.player === S.selectedPlayer);
    });
    // Playlist items
    const list = document.getElementById('ml-playlist');
    list.innerHTML = '';
    S.playlist.forEach((item, i) => {
      list.innerHTML += '<div class="playlist-item"><span class="playlist-num">' + (i + 1) +
        '</span><div class="playlist-info"><div class="playlist-title">' + esc(item.title) +
        '</div><div class="playlist-artist">' + esc(item.artist) +
        '</div></div><span class="playlist-dur">' + item.duration + '</span></div>';
    });
  }

  function mlSelectPlayer(p) { S.selectedPlayer = p; renderMairlist(); }
  function mlAction(action) {
    API('/mairlist/player/' + S.selectedPlayer + '/action', {
      method: 'POST', body: JSON.stringify({ action })
    });
  }
  function mlPlaylistStart() {
    API('/mairlist/command', { method: 'POST', body: JSON.stringify({ command: 'PLAYLIST ' + S.selectedPlaylist + ' START' }) });
  }
  async function mlLoadPlaylist() {
    try {
      const r = await API('/mairlist/playlist/' + S.selectedPlaylist);
      S.playlist = r.items || [];
      renderMairlist();
    } catch (_) {}
  }

  // ============ MIC ============
  function micSelectMode(mode) {
    S.micModeTab = mode;
    document.querySelectorAll('.mic-mode-tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
    document.getElementById('mic-talkback').style.display = mode === 'talkback' ? 'block' : 'none';
    document.getElementById('mic-source').style.display = mode === 'source' ? 'block' : 'none';
  }

  async function micStartCapture() {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 44100, channelCount: 1, echoCancellation: false } });
      micContext = new AudioContext({ sampleRate: 44100 });
      const source = micContext.createMediaStreamSource(micStream);
      micProcessor = micContext.createScriptProcessor(4096, 1, 1);
      micProcessor.onaudioprocess = (e) => {
        if (ws && ws.readyState === 1) {
          const float32 = e.inputBuffer.getChannelData(0);
          const int16 = new Int16Array(float32.length);
          for (let i = 0; i < float32.length; i++) {
            int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32767));
          }
          ws.send(int16.buffer);
        }
        // Update local level
        const data = e.inputBuffer.getChannelData(0);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
        const rms = Math.sqrt(sum / data.length);
        const db = 20 * Math.log10(Math.max(rms, 1e-7));
        setMeter('mic-meter-fill', db);
        document.getElementById('mic-db').textContent = db > -90 ? Math.round(db) + ' dB' : '-inf';
      };
      source.connect(micProcessor);
      micProcessor.connect(micContext.destination);
      S.micActive = true;
    } catch (err) {
      addLog('Mic error: ' + err.message, 'error');
    }
  }

  function micStopCapture() {
    if (micProcessor) { micProcessor.disconnect(); micProcessor = null; }
    if (micContext) { micContext.close(); micContext = null; }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    S.micActive = false;
    setMeter('mic-meter-fill', -100);
    document.getElementById('mic-db').textContent = '';
  }

  // PTT
  function pttDown() {
    API('/mic/start', { method: 'POST', body: JSON.stringify({ mode: 'talkback' }) });
    micStartCapture();
    document.getElementById('ptt-btn').classList.add('active');
    document.getElementById('ptt-label').textContent = 'LIVE';
  }
  function pttUp() {
    micStopCapture();
    API('/mic/stop', { method: 'POST', body: JSON.stringify({}) });
    document.getElementById('ptt-btn').classList.remove('active');
    document.getElementById('ptt-label').textContent = 'HOLD';
  }

  function sourceToggle() {
    if (S.micActive) {
      micStopCapture();
      API('/mic/stop', { method: 'POST', body: JSON.stringify({}) });
      document.getElementById('source-mic-btn').classList.remove('active');
      document.getElementById('source-mic-label').textContent = 'Start Streaming';
      document.getElementById('source-mic-icon').textContent = '\uD83C\uDFA4';
    } else {
      API('/mic/start', { method: 'POST', body: JSON.stringify({ mode: 'source' }) });
      micStartCapture();
      document.getElementById('source-mic-btn').classList.add('active');
      document.getElementById('source-mic-label').textContent = 'Stop Streaming';
      document.getElementById('source-mic-icon').textContent = '\u23F9';
    }
  }

  // ============ SOURCES ============
  function renderSources() {
    const list = document.getElementById('sources-list');
    list.innerHTML = '';
    S.sources.forEach((s, i) => {
      list.innerHTML += '<div class="card" style="display:flex;justify-content:space-between;align-items:center">' +
        '<div><div style="font-weight:600">' + esc(s.name) + '</div><div style="font-size:11px;color:var(--text2)">' + esc(s.url) + '</div></div>' +
        '<button class="btn-sm" onclick="sbDeleteSource(' + s.index + ')">Del</button></div>';
    });
  }
  async function addSource() {
    const name = document.getElementById('src-name').value.trim();
    const url = document.getElementById('src-url').value.trim();
    if (!name || !url) return;
    await API('/sources', { method: 'POST', body: JSON.stringify({ name, url }) });
    const r = await API('/sources');
    S.sources = r.sources || [];
    document.getElementById('src-name').value = '';
    document.getElementById('src-url').value = '';
    renderSources();
  }
  async function deleteSource(idx) {
    await API('/sources/' + idx, { method: 'DELETE' });
    const r = await API('/sources');
    S.sources = r.sources || [];
    renderSources();
  }

  // ============ LOG ============
  function renderLog() {
    const container = document.getElementById('log-entries');
    if (!container) return;
    const filtered = S.logFilter === 'all' ? S.log : S.log.filter(e => e.level === S.logFilter);
    container.innerHTML = '';
    filtered.forEach(e => {
      container.innerHTML += '<div class="log-entry log-' + e.level + '">' +
        '<span class="log-time">' + e.t + '</span><span class="log-dot"></span>' +
        '<span class="log-msg">' + esc(e.msg) + '</span></div>';
    });
    container.scrollTop = container.scrollHeight;
  }
  function logSetFilter(f) {
    S.logFilter = f;
    document.querySelectorAll('.log-filter').forEach(b => b.classList.toggle('active', b.dataset.filter === f));
    renderLog();
  }

  // ============ SETTINGS ============
  function renderSettings() {
    if (!S.config) return;
    const c = S.config;
    document.getElementById('set-port').value = c.port;
    document.getElementById('set-bitrate').value = c.mp3_bitrate;
    document.getElementById('set-threshold').value = c.silence?.threshold_db ?? -50;
    document.getElementById('set-warn-delay').value = c.silence?.warning_delay_s ?? 10;
    document.getElementById('set-alert-delay').value = c.silence?.alert_delay_s ?? 30;
    document.getElementById('set-autostop').className = 'toggle' + (c.silence?.auto_stop?.enabled ? ' on' : '');
    document.getElementById('set-autostop-delay').value = c.silence?.auto_stop?.delay_s ?? 2;
    document.getElementById('set-tone').className = 'toggle' + (c.silence?.auto_stop?.tone_detection_enabled ? ' on' : '');
    document.getElementById('set-trigger-ml').className = 'toggle' + (c.silence?.auto_stop?.trigger_mairlist ? ' on' : '');
    document.getElementById('set-stop-stream').className = 'toggle' + (c.silence?.auto_stop?.stop_stream ? ' on' : '');
    document.getElementById('set-ml-enabled').className = 'toggle' + (c.mairlist?.enabled ? ' on' : '');
    document.getElementById('set-ml-url').value = c.mairlist?.api_url ?? '';
    document.getElementById('set-ml-cmd').value = c.mairlist?.command ?? '';
    document.getElementById('set-ml-silence-cmd').value = c.mairlist?.silence_command ?? '';
    document.getElementById('set-ml-tone-cmd').value = c.mairlist?.tone_command ?? '';
  }

  function toggleSetting(id, path) {
    if (!S.config) return;
    const parts = path.split('.');
    let obj = S.config;
    for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
    obj[parts[parts.length - 1]] = !obj[parts[parts.length - 1]];
    document.getElementById(id).classList.toggle('on');
  }

  async function saveSettings() {
    if (!S.config) return;
    const c = S.config;
    const body = {
      port: parseInt(document.getElementById('set-port').value) || 9000,
      mp3_bitrate: parseInt(document.getElementById('set-bitrate').value) || 128,
      silence: {
        threshold_db: parseFloat(document.getElementById('set-threshold').value) || -50,
        warning_delay_s: parseInt(document.getElementById('set-warn-delay').value) || 10,
        alert_delay_s: parseInt(document.getElementById('set-alert-delay').value) || 30,
        auto_stop: {
          enabled: c.silence?.auto_stop?.enabled ?? false,
          delay_s: parseFloat(document.getElementById('set-autostop-delay').value) || 2,
          tone_detection_enabled: c.silence?.auto_stop?.tone_detection_enabled ?? false,
          trigger_mairlist: c.silence?.auto_stop?.trigger_mairlist ?? true,
          stop_stream: c.silence?.auto_stop?.stop_stream ?? true,
        },
      },
      mairlist: {
        enabled: c.mairlist?.enabled ?? false,
        api_url: document.getElementById('set-ml-url').value,
        command: document.getElementById('set-ml-cmd').value,
        silence_command: document.getElementById('set-ml-silence-cmd').value,
        tone_command: document.getElementById('set-ml-tone-cmd').value,
      },
    };
    try {
      await API('/config', { method: 'PUT', body: JSON.stringify(body) });
      S.config = await API('/config');
      addLog('Settings saved', 'info');
    } catch (err) {
      addLog('Save failed: ' + err.message, 'error');
    }
    render();
  }

  // ============ HELPERS ============
  function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // ============ GLOBAL BINDINGS ============
  window.sbShowTab = showTab;
  window.sbDashStart = dashStart;
  window.sbDashStop = dashStop;
  window.sbMlSelectPlayer = mlSelectPlayer;
  window.sbMlAction = mlAction;
  window.sbMlPlaylistStart = mlPlaylistStart;
  window.sbMlLoadPlaylist = mlLoadPlaylist;
  window.sbMicSelectMode = micSelectMode;
  window.sbPttDown = pttDown;
  window.sbPttUp = pttUp;
  window.sbSourceToggle = sourceToggle;
  window.sbAddSource = addSource;
  window.sbDeleteSource = deleteSource;
  window.sbLogSetFilter = logSetFilter;
  window.sbToggleSetting = toggleSetting;
  window.sbSaveSettings = saveSettings;

  // ============ BOOT ============
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/app/service-worker.js').catch(() => {});
  }
  init();
})();
