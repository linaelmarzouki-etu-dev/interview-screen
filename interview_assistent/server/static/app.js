const statusPill = document.getElementById("status-pill");
const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");
const btnAnswer = document.getElementById("btn-answer");
const answerCard = document.getElementById("answer-card");
const transcriptList = document.getElementById("transcript-list");
const connectionHint = document.getElementById("connection-hint");

let listening = false;

function setStatus(state, detail = "") {
  statusPill.className = `pill ${state}`;
  statusPill.textContent = detail ? `${state}: ${detail}` : state;
}

function setListening(active) {
  listening = active;
  btnStart.disabled = active;
  btnStop.disabled = !active;
  btnAnswer.disabled = !active;
}

function renderAnswer(question, answer) {
  answerCard.classList.remove("empty");
  answerCard.innerHTML = `
    <div class="question">Q: ${escapeHtml(question)}</div>
    <div class="answer">${escapeHtml(answer)}</div>
  `;
}

function appendTranscript(text, isQuestion) {
  const item = document.createElement("li");
  if (isQuestion) item.classList.add("question");
  item.textContent = text;
  transcriptList.appendChild(item);
  transcriptList.scrollTop = transcriptList.scrollHeight;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

btnStart.addEventListener("click", async () => {
  try {
    await api("/api/start", { method: "POST" });
    setListening(true);
  } catch (error) {
    setStatus("error", error.message);
  }
});

btnStop.addEventListener("click", async () => {
  try {
    await api("/api/stop", { method: "POST" });
    setListening(false);
  } catch (error) {
    setStatus("error", error.message);
  }
});

btnAnswer.addEventListener("click", async () => {
  try {
    await api("/api/answer", { method: "POST", body: "{}" });
  } catch (error) {
    setStatus("error", error.message);
  }
});

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws`);

  socket.onopen = async () => {
    connectionHint.textContent = "Connected. Keep this on a device that is NOT screen sharing.";
    try {
      const info = await api("/api/info");
      connectionHint.textContent += ` Open on phone: ${info.companion_url}`;
    } catch (_) {
      /* ignore */
    }
  };

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "ping") return;

    if (message.type === "status") {
      setStatus(message.state, message.detail || "");
      if (message.state === "listening") setListening(true);
      if (message.state === "idle" || message.state === "error") setListening(false);
    }

    if (message.type === "transcript") {
      appendTranscript(message.text, message.is_question);
    }

    if (message.type === "answer") {
      renderAnswer(message.question, message.answer);
    }
  };

  socket.onclose = () => {
    connectionHint.textContent = "Disconnected. Reconnecting...";
    setTimeout(connect, 1500);
  };
}

connect();