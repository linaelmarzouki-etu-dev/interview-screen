const TOKEN_KEY = "mcq_license_token";

function getLicenseToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function setLicenseToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearLicenseToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function licenseHeaders(extra = {}) {
  const headers = { ...extra };
  const token = getLicenseToken();
  if (token) {
    headers["X-License-Token"] = token;
  }
  return headers;
}

async function readApiError(response) {
  const text = await response.text();
  try {
    const data = JSON.parse(text);
    return data.detail || text;
  } catch (_) {
    return text || `Request failed (${response.status})`;
  }
}

async function licenseApi(path, options = {}) {
  const headers = licenseHeaders(options.headers || {});
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    clearLicenseToken();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("License required");
  }
  if (!response.ok) {
    throw new Error(await readApiError(response));
  }
  return response.json();
}

async function ensureLicensed() {
  const info = await fetch("/api/info");
  if (!info.ok) {
    throw new Error("Server unavailable");
  }
  const data = await info.json();
  if (!data.license_required) {
    return data;
  }
  const token = getLicenseToken();
  if (!token) {
    window.location.href = "/login";
    return null;
  }
  return licenseApi("/api/license/me");
}