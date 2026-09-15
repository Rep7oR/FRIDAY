(() => {
  "use strict";

  const chatLog = document.getElementById("chat-log");
  const textInput = document.getElementById("text-input");
  const sendBtn = document.getElementById("send-btn");
  const micBtn = document.getElementById("mic-btn");
  const voiceToggle = document.getElementById("voice-toggle");
  const coreStage = document.querySelector(".core-stage");
  const coreState = document.getElementById("core-state");
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const clockEl = document.getElementById("clock");
  const remindersList = document.getElementById("reminders-list");

  let voiceOutputEnabled = true;
  let recognizing = false;

  function setCoreState(state) {
    coreStage.classList.remove("listening", "thinking", "speaking");
    if (state !== "idle") coreStage.classList.add(state);
    coreState.textContent = state.toUpperCase();
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
    utterance.onend = () => setCoreState("idle");
    utterance.onerror = () => setCoreState("idle");
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
      if (!voiceOutputEnabled) setCoreState("idle");
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
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;
  if (SpeechRecognition) {
    recognizer = new SpeechRecognition();
    recognizer.continuous = false;
    recognizer.interimResults = false;
    recognizer.lang = "en-US";

    recognizer.onstart = () => {
      recognizing = true;
      micBtn.classList.add("active");
      setCoreState("listening");
    };
    recognizer.onend = () => {
      recognizing = false;
      micBtn.classList.remove("active");
      if (coreState.textContent === "LISTENING") setCoreState("idle");
    };
    recognizer.onerror = () => {
      recognizing = false;
      micBtn.classList.remove("active");
      setCoreState("idle");
    };
    recognizer.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      sendMessage(transcript);
    };

    micBtn.addEventListener("click", () => {
      if (recognizing) {
        recognizer.stop();
      } else {
        recognizer.start();
      }
    });
  } else {
    micBtn.title = "Voice input not supported in this browser (try Chrome or Edge)";
    micBtn.style.opacity = "0.35";
    micBtn.style.cursor = "not-allowed";
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

  setCoreState("idle");
  tickClock();
  refreshStatus();
  refreshReminders();
  setInterval(tickClock, 1000);
  setInterval(refreshStatus, 15000);
  setInterval(refreshReminders, 20000);

  appendEntry("Jarvis", "Systems online. How can I help?");
})();
