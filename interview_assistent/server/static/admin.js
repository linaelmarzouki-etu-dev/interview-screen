const ADMIN_TOKEN_KEY = "mcq_admin_token";

const loginPanel = document.getElementById("login-panel");
const adminPanel = document.getElementById("admin-panel");
const loginForm = document.getElementById("admin-login-form");
const loginError = document.getElementById("admin-login-error");
const generateForm = document.getElementById("generate-form");
const generatedKeys = document.getElementById("generated-keys");
const licenseTable = document.getElementById("license-table");
const btnRefresh = document.getElementById("btn-refresh");
const btnLogout = document.getElementById("btn-logout");

function getAdminToken() {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY) || "";
}

function setAdminToken(token) {
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

function clearAdminToken() {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

function showLoginError(message) {
  loginError.textContent = message;
  loginError.classList.remove("hidden");
}

function showAdmin() {
  loginPanel.classList.add("hidden");
  adminPanel.classList.remove("hidden");
  btnLogout.classList.remove("hidden");
}

function showLogin() {
  loginPanel.classList.remove("hidden");
  adminPanel.classList.add("hidden");
  btnLogout.classList.add("hidden");
}

async function adminApi(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Admin-Token": getAdminToken(),
    ...(options.headers || {}),
  };
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    clearAdminToken();
    showLogin();
    throw new Error("Admin session expired");
  }
  if (!response.ok) {
    const text = await response.text();
    try {
      const data = JSON.parse(text);
      throw new Error(data.detail || text);
    } catch (_) {
      throw new Error(text || `Request failed (${response.status})`);
    }
  }
  return response.json();
}

function renderLicenses(licenses) {
  if (!licenses.length) {
    licenseTable.innerHTML = "<p class='muted'>No licenses yet.</p>";
    return;
  }
  const rows = licenses
    .map(
      (item) => `
      <div class="license-row">
        <div><strong>${item.prefix}******</strong></div>
        <div>${item.plan}</div>
        <div>${item.status}</div>
        <div>${item.questions_used}/${item.questions_limit ?? "∞"}</div>
        <div>${item.customer_email || "—"}</div>
        <button class="ghost revoke-btn" data-prefix="${item.prefix}">Revoke</button>
      </div>`
    )
    .join("");
  licenseTable.innerHTML = `
    <div class="license-row license-head">
      <div>Key</div><div>Plan</div><div>Status</div><div>Used</div><div>Email</div><div></div>
    </div>
    ${rows}
  `;
  licenseTable.querySelectorAll(".revoke-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      const prefix = button.dataset.prefix;
      if (!confirm(`Revoke all keys with prefix ${prefix}?`)) return;
      await adminApi("/api/admin/keys/revoke", {
        method: "POST",
        body: JSON.stringify({ prefix }),
      });
      await refreshLicenses();
    });
  });
}

async function refreshLicenses() {
  const data = await adminApi("/api/admin/keys?active_only=true");
  renderLicenses(data.licenses);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const password = document.getElementById("admin-password").value;
  try {
    const response = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const data = await response.json();
    setAdminToken(data.token);
    showAdmin();
    await refreshLicenses();
  } catch (error) {
    showLoginError(error.message);
  }
});

generateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {
    plan: document.getElementById("plan").value,
    count: Number(document.getElementById("count").value || 1),
    email: document.getElementById("email").value.trim(),
    notes: document.getElementById("notes").value.trim(),
  };
  const data = await adminApi("/api/admin/keys/generate", {
    method: "POST",
    body: JSON.stringify(body),
  });
  generatedKeys.textContent = data.keys
    .map(
      (item) =>
        `Key: ${item.key}\n` +
        `Share URL (send to customer): ${item.share_url}\n` +
        `plan=${item.plan}  expires=${item.expires_at}  limit=${item.questions_limit}`
    )
    .join("\n\n");
  await refreshLicenses();
});

btnRefresh.addEventListener("click", refreshLicenses);
btnLogout.addEventListener("click", () => {
  clearAdminToken();
  showLogin();
});

if (getAdminToken()) {
  showAdmin();
  refreshLicenses().catch(() => {
    clearAdminToken();
    showLogin();
  });
}