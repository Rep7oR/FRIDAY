(() => {
  "use strict";

  const chatLog = document.getElementById("chat-log");
  const textInput = document.getElementById("text-input");
  const sendBtn = document.getElementById("send-btn");
  const micBtn = document.getElementById("mic-btn");
  const wakeBtn = document.getElementById("wake-btn");
  const voiceToggle = document.getElementById("voice-toggle");
  const coreStage = document.querySelector(".core-stage");
  const coreState = document.getElementById("core-state");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const clockEl = document.getElementById("clock");
  const remindersList = document.getElementById("reminders-list");

  const WAKE_PHRASE = "hey jarvis";
  let voiceOutputEnabled = true;
  let honorific = "sir"; // refined once /api/status reports the configured JARVIS_HONORIFIC

  function timeBasedGreeting() {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  }

  function randomAckPhrase() {
    const phrases = [
      `Yes, ${honorific}?`,
      `Go ahead, ${honorific}.`,
      `I'm listening, ${honorific}.`,
      `At your service, ${honorific}.`,
    ];
    return phrases[Math.floor(Math.random() * phrases.length)];
  }

  function setCoreState(state) {
    coreStage.classList.remove("listening", "thinking", "speaking");
    if (state !== "idle") coreStage.classList.add(state);
    coreState.textContent = state.toUpperCase();
    updateWaveformForState(state);
  }

  function appendEntry(who, text) {
    const entry = document.createElement("div");
    const cls = who === "You" ? "user" : who === "System" ? "system" : "jarvis";
    entry.className = `chat-entry ${cls}`;
    const label = document.createElement("span");
    label.className = "who";
    label.textContent = who;
    entry.appendChild(label);
    entry.appendChild(document.createTextNode(text));
    chatLog.appendChild(entry);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  // Human-readable explanations for SpeechRecognition's error codes, since Chrome gives no
  // on-screen feedback of its own when recognition fails.
  const VOICE_ERROR_MESSAGES = {
    network:
      "Network error talking to the browser's speech-recognition service (it needs internet " +
      "access to Google's servers, even though everything else here runs locally). Check your " +
      "connection or firewall.",
    "not-allowed": "Microphone access was blocked. Allow it for this site and try again.",
    "service-not-allowed": "Microphone access was blocked. Allow it for this site and try again.",
    "audio-capture": "No microphone was found. Check it's connected and not in use by another app.",
    "language-not-supported": "The recognition language isn't supported by this browser.",
  };
  let lastVoiceErrorLoggedAt = 0;
  function logVoiceError(errorCode) {
    if (errorCode === "no-speech" || errorCode === "aborted") return; // routine, not a failure
    const now = Date.now();
    if (now - lastVoiceErrorLoggedAt < 4000) return; // don't spam on rapid auto-restarts
    lastVoiceErrorLoggedAt = now;
    const message = VOICE_ERROR_MESSAGES[errorCode] || `Speech recognition error: ${errorCode}`;
    appendEntry("System", message);
  }

  function speak(text, onDone) {
    const done = onDone || resumeWakeListeningIfEnabled;
    if (!voiceOutputEnabled || !("speechSynthesis" in window) || !text) {
      done();
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    utterance.onstart = () => setCoreState("speaking");
    utterance.onend = () => {
      setCoreState("idle");
      done();
    };
    utterance.onerror = () => {
      setCoreState("idle");
      done();
    };
    window.speechSynthesis.speak(utterance);
  }

  async function sendMessage(text) {
    text = text.trim();
    if (!text) return;
    appendEntry("You", text);
    textInput.value = "";
    setCoreState("thinking");
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await response.json();
      const reply = data.reply || "(no response)";
      appendEntry("Jarvis", reply);
      speak(reply);
      refreshReminders();
    } catch (err) {
      appendEntry("Jarvis", `Connection error: ${err}`);
      setCoreState("idle");
    }
  }

  sendBtn.addEventListener("click", () => sendMessage(textInput.value));
  textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage(textInput.value);
  });

  voiceToggle.addEventListener("click", () => {
    voiceOutputEnabled = !voiceOutputEnabled;
    voiceToggle.classList.toggle("toggle-on", voiceOutputEnabled);
    voiceToggle.classList.toggle("toggle-off", !voiceOutputEnabled);
    if (!voiceOutputEnabled) window.speechSynthesis?.cancel();
  });

  // --- Voice input (Web Speech API; Chrome/Edge only) ---
  // Two modes share one underlying recognizer, since only one can use the mic at a time:
  //   - "capturing": one-shot, triggered by the mic button (or after a wake phrase fires).
  //   - "wake-armed": continuous, listening for WAKE_PHRASE ("hey jarvis") in the background.
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  let voiceMode = "off"; // "off" | "capturing" | "wake-armed"
  let wakeEnabled = false;

  function stopRecognizer() {
    if (recognizer) {
      recognizer.onend = null;
      recognizer.onresult = null;
      recognizer.onerror = null;
      try {
        recognizer.stop();
      } catch {
        /* already stopped */
      }
      recognizer = null;
    }
  }

  function captureOnce() {
    stopRecognizer();
    voiceMode = "capturing";
    micBtn.classList.add("active");
    recognizer = new SpeechRecognition();
    recognizer.continuous = false;
    recognizer.interimResults = false;
    recognizer.lang = "en-US";
    recognizer.onstart = () => setCoreState("listening");
    recognizer.onresult = (event) => sendMessage(event.results[0][0].transcript);
    recognizer.onend = () => {
      micBtn.classList.remove("active");
      voiceMode = "off";
      if (coreState.textContent === "LISTENING") setCoreState("idle");
      resumeWakeListeningIfEnabled();
    };
    recognizer.onerror = (event) => {
      micBtn.classList.remove("active");
      voiceMode = "off";
      setCoreState("idle");
      logVoiceError(event.error);
      resumeWakeListeningIfEnabled();
    };
    recognizer.start();
  }

  function startWakeListening() {
    stopRecognizer();
    voiceMode = "wake-armed";
    recognizer = new SpeechRecognition();
    recognizer.continuous = true;
    recognizer.interimResults = true;
    recognizer.lang = "en-US";
    recognizer.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcript = result[0].transcript.trim().toLowerCase();
      const idx = transcript.indexOf(WAKE_PHRASE);
      if (idx === -1) return;
      if (!result.isFinal) {
        setCoreState("listening"); // heard the wake phrase building up
        return;
      }
      const after = transcript.slice(idx + WAKE_PHRASE.length).replace(/^[,.\s]+/, "");
      if (after.length > 2) {
        sendMessage(after); // wake phrase + command said in one breath
      } else {
        // Wake phrase alone -- acknowledge it out loud, then listen for the actual command.
        const ack = randomAckPhrase();
        appendEntry("Jarvis", ack);
        stopRecognizer();
        speak(ack, () => captureOnce());
      }
    };
    recognizer.onend = () => {
      // Browsers auto-stop continuous recognition after periods of silence; restart it
      // as long as wake mode is still armed and nothing else has taken over the mic.
      if (wakeEnabled && voiceMode === "wake-armed") {
        recognizer.start();
      }
    };
    recognizer.onerror = (event) => {
      logVoiceError(event.error);
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        wakeEnabled = false;
        voiceMode = "off";
        wakeBtn.classList.remove("armed");
      }
    };
    recognizer.start();
  }

  function resumeWakeListeningIfEnabled() {
    if (wakeEnabled && voiceMode !== "wake-armed" && voiceMode !== "capturing") {
      startWakeListening();
    }
  }

  if (SpeechRecognition) {
    micBtn.addEventListener("click", () => {
      if (voiceMode === "capturing") {
        stopRecognizer();
        voiceMode = "off";
        micBtn.classList.remove("active");
        setCoreState("idle");
      } else {
        captureOnce();
      }
    });

    wakeBtn.addEventListener("click", () => {
      wakeEnabled = !wakeEnabled;
      wakeBtn.classList.toggle("armed", wakeEnabled);
      wakeBtn.title = wakeEnabled
        ? `Listening for "${WAKE_PHRASE}" -- click to disable`
        : "Toggle 'Hey Jarvis' always-listening mode";
      if (wakeEnabled) {
        startWakeListening();
      } else if (voiceMode === "wake-armed") {
        stopRecognizer();
        voiceMode = "off";
      }
    });
  } else {
    micBtn.title = "Voice input not supported in this browser (try Chrome or Edge)";
    micBtn.style.opacity = "0.35";
    micBtn.style.cursor = "not-allowed";
    wakeBtn.title = "Voice input not supported in this browser (try Chrome or Edge)";
    wakeBtn.style.opacity = "0.35";
    wakeBtn.style.cursor = "not-allowed";
  }

  // --- Status polling ---
  async function refreshStatus() {
    try {
      const response = await fetch("/api/status");
      const data = await response.json();
      if (data.honorific) honorific = data.honorific;
      if (data.ollama_reachable && data.model_available) {
        statusDot.className = "status-dot online";
        statusText.textContent = `online · ${data.model}`;
      } else if (data.ollama_reachable) {
        statusDot.className = "status-dot offline";
        statusText.textContent = `model '${data.model}' not pulled`;
      } else {
        statusDot.className = "status-dot offline";
        statusText.textContent = "ollama unreachable";
      }
    } catch {
      statusDot.className = "status-dot offline";
      statusText.textContent = "backend unreachable";
    }
  }

  async function refreshReminders() {
    try {
      const response = await fetch("/api/reminders");
      const data = await response.json();
      const text = (data.reminders || "").trim();
      remindersList.innerHTML = "";
      if (!text || text === "No reminders.") {
        remindersList.innerHTML = '<li class="muted">none yet</li>';
        return;
      }
      text.split("\n").forEach((line) => {
        const li = document.createElement("li");
        li.textContent = line;
        remindersList.appendChild(li);
      });
    } catch {
      /* leave list as-is on transient failure */
    }
  }

  function tickClock() {
    const now = new Date();
    const timeText = now.toLocaleTimeString([], { hour12: false });
    clockEl.textContent = timeText;
    const bigClock = document.getElementById("big-clock");
    const bigDate = document.getElementById("big-date");
    if (bigClock) bigClock.textContent = timeText;
    if (bigDate) {
      bigDate.textContent = now.toLocaleDateString([], {
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    }
  }

  // --- System stats (real CPU/RAM/disk/network from the machine running the server) ---
  const cpuValue = document.getElementById("cpu-value");
  const cpuSpark = document.getElementById("cpu-spark");
  const memValue = document.getElementById("mem-value");
  const memSub = document.getElementById("mem-sub");
  const memSpark = document.getElementById("mem-spark");
  const diskValue = document.getElementById("disk-value");
  const diskSub = document.getElementById("disk-sub");
  const diskGauge = document.getElementById("disk-gauge");
  const netSub = document.getElementById("net-sub");
  const netSpark = document.getElementById("net-spark");
  const uptimeValue = document.getElementById("uptime-value");
  const operatorEl = document.getElementById("operator");

  const HISTORY_LEN = 40;
  const cpuHistory = [];
  const memHistory = [];
  const netHistory = [];

  function pushHistory(arr, value) {
    arr.push(value);
    if (arr.length > HISTORY_LEN) arr.shift();
  }

  function drawSparkline(canvas, values, maxHint) {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (values.length < 2) return;
    const max = Math.max(maxHint || 0, ...values, 1);
    const step = w / (values.length - 1);
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = i * step;
      const y = h - (v / max) * (h - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#34e2ff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = "rgba(52, 226, 255, 0.12)";
    ctx.fill();
  }

  function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  async function refreshSystemStats() {
    try {
      const response = await fetch("/api/system");
      const data = await response.json();

      cpuValue.textContent = `${Math.round(data.cpu_percent)}%`;
      pushHistory(cpuHistory, data.cpu_percent);
      drawSparkline(cpuSpark, cpuHistory, 100);

      memValue.textContent = `${Math.round(data.mem_percent)}%`;
      memSub.textContent = `${data.mem_used_gb} / ${data.mem_total_gb} GB`;
      pushHistory(memHistory, data.mem_percent);
      drawSparkline(memSpark, memHistory, 100);

      diskValue.textContent = `${Math.round(data.disk_percent)}%`;
      diskSub.textContent = `${data.disk_used_gb} / ${data.disk_total_gb} GB`;
      diskGauge.style.width = `${data.disk_percent}%`;

      netSub.innerHTML = `&uarr; ${data.net_sent_kbps} KB/s &nbsp; &darr; ${data.net_recv_kbps} KB/s`;
      pushHistory(netHistory, data.net_recv_kbps);
      drawSparkline(netSpark, netHistory);

      uptimeValue.textContent = formatUptime(data.uptime_seconds);
      operatorEl.textContent = `operator: ${data.username}@${data.hostname}`;
    } catch {
      /* leave widgets showing last-known values on a transient failure */
    }
  }

  // --- Weather (real current conditions for your location via Open-Meteo; browser supplies
  // the coordinates through the Geolocation API, nothing is hardcoded or faked) ---
  function requestWeather() {
    const weatherBody = document.getElementById("weather-body");
    if (!navigator.geolocation) {
      weatherBody.textContent = "Geolocation not supported by this browser.";
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const { latitude, longitude } = pos.coords;
          const response = await fetch(`/api/weather?lat=${latitude}&lon=${longitude}`);
          const data = await response.json();
          if (!data.ok) {
            weatherBody.textContent = `Weather unavailable: ${data.error}`;
            return;
          }
          weatherBody.innerHTML = `
            <div class="weather-temp">${Math.round(data.temperature_c)}&deg;C</div>
            <div class="weather-condition">${data.condition}</div>
            <div>Humidity: ${data.humidity_percent}%</div>
            <div>Wind: ${data.wind_kmh} km/h</div>
          `;
        } catch {
          weatherBody.textContent = "Weather request failed.";
        }
      },
      () => {
        weatherBody.textContent = "Location permission denied -- enable it to show local weather.";
      },
      { timeout: 8000 }
    );
  }

  // --- Tick-ring: radial tick marks drawn once around the core (purely decorative HUD chrome) ---
  function drawTickRing() {
    const svg = document.querySelector(".tick-ring");
    if (!svg) return;
    const ns = "http://www.w3.org/2000/svg";
    const cx = 150;
    const cy = 150;
    const rOuter = 148;
    for (let i = 0; i < 60; i++) {
      const angle = (i / 60) * Math.PI * 2;
      const isLong = i % 5 === 0;
      const rInner = isLong ? 128 : 138;
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", cx + rOuter * Math.cos(angle));
      line.setAttribute("y1", cy + rOuter * Math.sin(angle));
      line.setAttribute("x2", cx + rInner * Math.cos(angle));
      line.setAttribute("y2", cy + rInner * Math.sin(angle));
      svg.appendChild(line);
    }
  }

  // --- Waveform: idle/speaking are decorative animation; listening is driven by real mic
  // input via an AnalyserNode, so it visibly reacts to your voice. ---
  const waveformEl = document.getElementById("waveform");
  const BAR_COUNT = 32;
  const bars = [];
  for (let i = 0; i < BAR_COUNT; i++) {
    const bar = document.createElement("div");
    bar.className = "bar";
    waveformEl.appendChild(bar);
    bars.push(bar);
  }

  let waveformRAF = null;
  let micStream = null;
  let audioCtx = null;

  function setBarHeights(getHeight) {
    bars.forEach((bar, i) => {
      bar.style.height = `${getHeight(i)}px`;
    });
  }

  function idleWaveformLoop(t) {
    const time = t / 600;
    setBarHeights((i) => 3 + 5 * Math.abs(Math.sin(time + i * 0.35)));
    waveformRAF = requestAnimationFrame(idleWaveformLoop);
  }

  function speakingWaveformLoop() {
    setBarHeights(() => 4 + Math.random() * 28);
    waveformRAF = requestAnimationFrame(speakingWaveformLoop);
  }

  async function startMicWaveform() {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      idleWaveformLoop(0); // mic unavailable/denied -- fall back to decorative animation
      return;
    }
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(micStream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);

    function loop() {
      analyser.getByteFrequencyData(data);
      setBarHeights((i) => 3 + (data[i % data.length] / 255) * 32);
      waveformRAF = requestAnimationFrame(loop);
    }
    loop();
  }

  function stopWaveformLoop() {
    if (waveformRAF) cancelAnimationFrame(waveformRAF);
    waveformRAF = null;
    if (micStream) {
      micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
    }
    if (audioCtx) {
      audioCtx.close();
      audioCtx = null;
    }
  }

  function updateWaveformForState(state) {
    stopWaveformLoop();
    if (state === "listening" && navigator.mediaDevices?.getUserMedia) {
      startMicWaveform();
    } else if (state === "speaking") {
      speakingWaveformLoop();
    } else {
      idleWaveformLoop(0);
    }
  }

  setCoreState("idle");
  tickClock();
  drawTickRing();
  refreshReminders();
  refreshSystemStats();
  requestWeather();
  setInterval(tickClock, 1000);
  setInterval(refreshReminders, 20000);
  setInterval(refreshSystemStats, 2000);
  setInterval(requestWeather, 900000);

  refreshStatus().then(() => {
    appendEntry("Jarvis", `${timeBasedGreeting()}, ${honorific}. All systems are online and standing by.`);
  });
  setInterval(refreshStatus, 15000);
})();
