const statusPill = document.getElementById("status-pill");
const licensePill = document.getElementById("license-pill");
const fileInput = document.getElementById("file-input");
const fileBtn = document.querySelector(".file-btn");
const btnPaste = document.getElementById("btn-paste");
const btnScreenshot = document.getElementById("btn-screenshot");
const answerCard = document.getElementById("answer-card");
const previewPanel = document.getElementById("preview-panel");
const previewImage = document.getElementById("preview-image");
const connectionHint = document.getElementById("connection-hint");

let busy = false;
let useRemoteGrab = false;
let licenseInfo = null;

function setStatus(state, detail = "") {
  statusPill.className = `pill ${state}`;
  statusPill.textContent = detail ? `${state}: ${detail}` : state;
}

function setLicenseBadge(info) {
  if (!info || !info.license_required) {
    licensePill.classList.add("hidden");
    return;
  }
  licensePill.classList.remove("hidden");
  const remaining =
    info.questions_remaining == null ? "∞" : info.questions_remaining;
  licensePill.textContent = `${info.plan || "licensed"} · ${remaining} left`;
}

function setBusy(active) {
  busy = active;
  fileBtn.classList.toggle("disabled", active);
  btnPaste.disabled = active;
  btnScreenshot.disabled = active;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function extractAnswerLetter(answer) {
  const trimmed = (answer || "").trim();
  if (/^[A-E?]$/i.test(trimmed)) {
    return trimmed.toUpperCase();
  }
  const match = trimmed.match(/Answer:\s*([A-E])/i) || trimmed.match(/\b([A-E])\b/);
  return match ? match[1].toUpperCase() : "?";
}

function renderAnswer(question, answer, options = "", consensus = "") {
  const letter = extractAnswerLetter(answer);
  answerCard.classList.remove("empty");

  const questionHtml = question
    ? `<div class="mcq-question">${escapeHtml(question)}</div>`
    : "";

  const optionsHtml = options
    ? `<div class="mcq-options">${escapeHtml(options)
        .split("\n")
        .map((line) => `<div>${line}</div>`)
        .join("")}</div>`
    : "";

  const consensusHtml = consensus
    ? `<div class="mcq-consensus">${escapeHtml(consensus)} models agree</div>`
    : "";

  answerCard.innerHTML = `
    ${questionHtml}
    ${optionsHtml}
    <div class="mcq-answer-label">Answer</div>
    <div class="answer-letter">${letter}</div>
    ${consensusHtml}
  `;
}

function showPreview(file) {
  const url = URL.createObjectURL(file);
  previewImage.src = url;
  previewPanel.classList.remove("hidden");
}

async function uploadImage(file) {
  const form = new FormData();
  form.append("image", file, file.name || "screenshot.png");
  const response = await fetch("/api/mcq/analyze", {
    method: "POST",
    headers: licenseHeaders(),
    body: form,
  });
  if (response.status === 401) {
    clearLicenseToken();
    window.location.href = "/login";
    throw new Error("License required");
  }
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return response.json();
}

async function analyzeFile(file) {
  if (busy) return;
  setBusy(true);
  showPreview(file);
  try {
    await uploadImage(file);
    await refreshLicenseInfo();
  } catch (error) {
    setStatus("error", error.message);
    setBusy(false);
  }
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  await analyzeFile(file);
  fileInput.value = "";
});

btnPaste.addEventListener("click", async () => {
  try {
    const items = await navigator.clipboard.read();
    for (const item of items) {
      const imageType = item.types.find((type) => type.startsWith("image/"));
      if (!imageType) continue;
      const blob = await item.getType(imageType);
      const file = new File([blob], "clipboard.png", { type: imageType });
      await analyzeFile(file);
      return;
    }
    setStatus("error", "No image found in clipboard");
  } catch (error) {
    setStatus("error", "Clipboard paste failed — try Upload instead");
  }
});

btnScreenshot.addEventListener("click", async () => {
  if (busy) return;
  setBusy(true);
  const endpoint = useRemoteGrab ? "/api/mcq/request-grab" : "/api/mcq/screenshot";
  try {
    await licenseApi(endpoint, { method: "POST" });
  } catch (error) {
    setStatus("error", error.message);
    setBusy(false);
  }
});

async function refreshLicenseInfo() {
  try {
    licenseInfo = await licenseApi("/api/license/me");
    setLicenseBadge(licenseInfo);
  } catch (_) {
    const info = await fetch("/api/info").then((r) => r.json());
    licenseInfo = info;
    setLicenseBadge(info);
  }
}

function connect() {
  const token = getLicenseToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws${query}`);

  socket.onopen = async () => {
    connectionHint.textContent = "Connected. Keep this on a device that is NOT screen sharing.";
    try {
      const info = await licenseApi("/api/info");
      useRemoteGrab = info.remote_grab === true;
      setLicenseBadge(info);
      if (useRemoteGrab) {
        btnScreenshot.textContent = "Grab laptop screen";
        connectionHint.textContent = info.agent_connected
          ? "Laptop connected — tap Grab laptop screen during exam."
          : "Laptop offline — run ./start_laptop_agent.sh on laptop before exam.";
      }
    } catch (_) {
      /* ignore */
    }
  };

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "ping") return;

    if (message.type === "status") {
      setStatus(message.state, message.detail || "");
      if (message.state === "thinking") {
        setBusy(true);
      }
      if (message.state === "idle" || message.state === "error") {
        setBusy(false);
      }
    }

    if (message.type === "answer") {
      renderAnswer(
        message.question,
        message.answer,
        message.options || "",
        message.consensus || ""
      );
      setBusy(false);
      refreshLicenseInfo();
    }
  };

  socket.onclose = (event) => {
    if (event.code === 4401) {
      clearLicenseToken();
      window.location.href = "/login";
      return;
    }
    connectionHint.textContent = "Disconnected. Reconnecting...";
    setTimeout(connect, 1500);
  };
}

async function boot() {
  await ensureLicensed();
  connect();
}

boot();