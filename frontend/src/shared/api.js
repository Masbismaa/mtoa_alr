// panggil API Flask. Semua balasan API ALR bentuknya { is_success, message, data, error_list }
// (app/utils/response_formatter.py). Error dilempar sebagai ApiError biar komponen tinggal nampilin pesannya.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    // 401 = sesi login habis (app/security/role_guard.py:api_login_required)
    this.isSessionExpired = status === 401;
  }
}

const NETWORK_ERROR_MESSAGE = "Koneksi ke server gagal, cek jaringan lalu coba lagi";
const INVALID_RESPONSE_MESSAGE = "Respon server tidak valid, coba muat ulang halaman";
// samain dgn SESSION_EXPIRED_MESSAGE di app/security/role_guard.py
const SESSION_EXPIRED_MESSAGE = "Sesi login habis, muat ulang halaman lalu login lagi";

// token CSRF dari <meta name="csrf-token"> (layouts/base.html), wajib buat request POST
export function readCsrfToken() {
  const metaEl = document.querySelector('meta[name="csrf-token"]');
  return metaEl ? metaEl.content : "";
}

async function sendRequest(url, options) {
  let response;
  try {
    response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
  } catch (error) {
    // request dibatalin karena udah ada request yg lebih baru: biarin yg manggil yg mutusin
    if (error.name === "AbortError") throw error;
    throw new ApiError(NETWORK_ERROR_MESSAGE, 0);
  }
  // API ALR ga pernah redirect. Kena redirect = endpoint lama yg masih pake @login_required -> pasti ke halaman login
  if (response.redirected) throw new ApiError(SESSION_EXPIRED_MESSAGE, 401);

  let body = null;
  try {
    body = await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(INVALID_RESPONSE_MESSAGE, response.status);
  }
  if (!response.ok || !body || body.is_success !== true) {
    throw new ApiError((body && body.message) || INVALID_RESPONSE_MESSAGE, response.status);
  }
  return body.data;
}

// GET JSON. signal = AbortController.signal buat batalin request lama
export function getJson(url, signal) {
  return sendRequest(url, { method: "GET", signal });
}

// POST JSON + token CSRF. isKeepalive = tetep dikirim walau halamannya lagi ditutup
export function postJson(url, payload, isKeepalive = false) {
  return sendRequest(url, {
    method: "POST",
    keepalive: isKeepalive,
    headers: { "Content-Type": "application/json", "X-CSRFToken": readCsrfToken() },
    body: JSON.stringify(payload),
  });
}
