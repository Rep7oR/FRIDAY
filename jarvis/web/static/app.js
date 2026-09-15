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

  function setCoreState(state) {
    coreStage.classList.remove("listening", "thinking", "speaking");
    if (state !== "idle") coreStage.classList.add(state);
    coreState.textContent = state.toUpperCase();
    updateWaveformForState(state);
  }

  function appendEntry(who, text) {
    const entry = document.createElement("div");
    entry.className = `chat-entry ${who === "You" ? "user" : "jarvis"}`;
    const label = document.createElement("span");
    label.className = "who";
    label.textContent = who;
    entry.appendChild(label);
    entry.appendChild(document.createTextNode(text));
    chatLog.appendChild(entry);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function speak(text) {
    if (!voiceOutputEnabled || !("speechSynthesis" in window) || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    utterance.onstart = () => setCoreState("speaking");
    utterance.onend = () => {
      setCoreState("idle");
      resumeWakeListeningIfEnabled();
    };
    utterance.onerror = () => {
      setCoreState("idle");
      resumeWakeListeningIfEnabled();
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
      if (!voiceOutputEnabled) {
        setCoreState("idle");
        resumeWakeListeningIfEnabled();
      }
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
    recognizer.onerror = () => {
      micBtn.classList.remove("active");
      voiceMode = "off";
      setCoreState("idle");
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
        captureOnce(); // wake phrase alone -- listen for the command next
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
    clockEl.textContent = new Date().toLocaleTimeString([], { hour12: false });
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
  refreshStatus();
  refreshReminders();
  setInterval(tickClock, 1000);
  setInterval(refreshStatus, 15000);
  setInterval(refreshReminders, 20000);

  appendEntry("Jarvis", "Systems online. How can I help?");
})();
