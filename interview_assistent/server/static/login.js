const form = document.getElementById("login-form");
const keyInput = document.getElementById("license-key");
const errorBox = document.getElementById("login-error");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function normalizeKey(value) {
  return value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 8);
}

function keyFromUrl() {
  const params = new URLSearchParams(location.search);
  const fromQuery = params.get("key");
  if (fromQuery) {
    return normalizeKey(fromQuery);
  }
  const match = location.pathname.match(/^\/u\/([A-Za-z]{8})$/);
  return match ? normalizeKey(match[1]) : "";
}

async function activateKey(key) {
  const response = await fetch("/api/license/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  const data = await response.json();
  setLicenseToken(data.token);
  window.location.href = "/";
}

keyInput.addEventListener("input", () => {
  const normalized = normalizeKey(keyInput.value);
  if (keyInput.value !== normalized) {
    keyInput.value = normalized;
  }
  errorBox.classList.add("hidden");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const key = normalizeKey(keyInput.value);
  if (key.length !== 8) {
    showError("Enter exactly 8 letters (A-Z).");
    return;
  }

  const button = form.querySelector("button");
  button.disabled = true;
  try {
    await activateKey(key);
  } catch (error) {
    showError(error.message);
    button.disabled = false;
  }
});

async function boot() {
  try {
    const info = await fetch("/api/info");
    if (!info.ok) {
      return;
    }
    const data = await info.json();
    if (!data.license_required) {
      window.location.href = "/";
      return;
    }

    const urlKey = keyFromUrl();
    if (urlKey.length === 8) {
      keyInput.value = urlKey;
      try {
        await activateKey(urlKey);
        return;
      } catch (error) {
        showError(error.message);
      }
    }

    if (getLicenseToken()) {
      const me = await fetch("/api/license/me", {
        headers: licenseHeaders(),
      });
      if (me.ok) {
        window.location.href = "/";
        return;
      }
      clearLicenseToken();
    }
  } catch (_) {
    /* ignore */
  }
}

boot();