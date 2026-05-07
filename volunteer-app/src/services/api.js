/**
 * Volunteer App API service — communicates with the same backend as admin.
 */

const API_BASE = 'https://sevasetu-bnup.onrender.com/api/v1';

function getToken() { return localStorage.getItem('vol_token'); }
export function setToken(t) { localStorage.setItem('vol_token', t); }
export function clearAuth() { localStorage.removeItem('vol_token'); localStorage.removeItem('vol_user'); }
export function getStoredUser() { const d = localStorage.getItem('vol_user'); return d ? JSON.parse(d) : null; }
export function setStoredUser(u) { localStorage.setItem('vol_user', JSON.stringify(u)); }

async function apiFetch(endpoint, options = {}) {
  const token = getToken();
  const headers = { ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';

  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  if (res.status === 401) { clearAuth(); window.location.href = '/login'; throw new Error('Session expired'); }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    let msg = err.error || err.detail || `HTTP ${res.status}`;
    if (Array.isArray(err.detail) && err.detail.length > 0) {
      // Extract the first validation error message (e.g. "field is required")
      msg = err.detail[0].msg || JSON.stringify(err.detail);
    }
    throw new Error(msg);
  }
  return res.json();
}

export const auth = {
  googleLogin: (idToken) => apiFetch('/auth/google/', { method: 'POST', body: JSON.stringify({ id_token: idToken, role: 'volunteer' }) }),
  emailRegister: (email, password, name) => apiFetch('/auth/register/', { method: 'POST', body: JSON.stringify({ email, password, name, role: 'volunteer' }) }),
  emailLogin: (email, password) => apiFetch('/auth/login/', { method: 'POST', body: JSON.stringify({ email, password }) }),
  getMe: () => apiFetch('/auth/me/'),
  logout: () => apiFetch('/auth/logout/', { method: 'POST' }),
};

export const volunteer = {
  getMyProfile: () => apiFetch('/volunteers/me/'),
  setup: (data) => apiFetch('/volunteers/setup/', { method: 'POST', body: JSON.stringify(data) }),
  updateLocation: (id, data) => apiFetch(`/volunteers/${id}/location/`, { method: 'PATCH', body: JSON.stringify(data) }),
  updateAvailability: (id, data) => apiFetch(`/volunteers/${id}/availability/`, { method: 'PATCH', body: JSON.stringify(data) }),
  updateFCM: (id, data) => apiFetch(`/volunteers/${id}/fcm-token/`, { method: 'PATCH', body: JSON.stringify(data) }),
  getMyTasks: (id, params = {}) => { const q = new URLSearchParams(params).toString(); return apiFetch(`/volunteers/${id}/tasks/?${q}`); },
};

export const needs = {
  create: (data) => apiFetch('/needs/', { method: 'POST', body: JSON.stringify(data) }),
  list: (params = {}) => { const q = new URLSearchParams(params).toString(); return apiFetch(`/needs/?${q}`); },
  getForMap: (params = {}) => { const q = new URLSearchParams(params).toString(); return apiFetch(`/needs/map/?${q}`); },
  getCategories: () => apiFetch('/needs/categories/'),
};

export const assignments = {
  get: (id) => apiFetch(`/matching/assignment/${id}/`),
  updateStatus: (id, data) => apiFetch(`/matching/assignment/${id}/status/`, { method: 'PATCH', body: JSON.stringify(data) }),
};

export const broadcast = {
  list: () => apiFetch('/broadcast/'),
};

// SOS (Task 2.5)
export const sos = {
  trigger: (data) => apiFetch('/volunteers/sos/', { method: 'POST', body: JSON.stringify(data) }),
};

// Fatigue & Wellness (Task 2.2)
export const wellness = {
  getFatigue: (volId) => apiFetch(`/volunteers/${volId}/fatigue/`),
  getCertificate: (volId) => apiFetch(`/volunteers/${volId}/certificate/`),
};

// Voice → Text Structure (Task 2.7)
export const textStructure = {
  analyze: (text, language = 'en-IN') =>
    apiFetch('/ocr/structure-text/', { method: 'POST', body: JSON.stringify({ text, language }) }),
};

// Token export for WebSocket
export { getToken };
