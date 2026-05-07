/**
 * API service layer — all backend communication goes through here.
 */

const API_BASE = 'https://sevasetu-bnup.onrender.com/api/v1';

// Get stored JWT token
export function getToken() {
  return localStorage.getItem('smartalloc_token');
}

// Set JWT token
export function setToken(token) {
  localStorage.setItem('smartalloc_token', token);
}

// Clear auth data
export function clearAuth() {
  localStorage.removeItem('smartalloc_token');
  localStorage.removeItem('smartalloc_user');
}

// Get stored user
export function getStoredUser() {
  const data = localStorage.getItem('smartalloc_user');
  return data ? JSON.parse(data) : null;
}

// Store user
export function setStoredUser(user) {
  localStorage.setItem('smartalloc_user', JSON.stringify(user));
}

/**
 * Core fetch wrapper with auth headers and error handling.
 */
async function apiFetch(endpoint, options = {}) {
  const token = getToken();
  const headers = {
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser auto-sets with boundary)
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearAuth();
    window.location.href = '/login';
    throw new Error('Session expired');
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    let msg = error.error || error.detail || `HTTP ${res.status}`;
    if (Array.isArray(error.detail) && error.detail.length > 0) {
      msg = error.detail[0].msg || JSON.stringify(error.detail);
    }
    throw new Error(msg);
  }

  return res.json();
}

// ============================================================
// AUTH
// ============================================================
export const auth = {
  googleLogin: (idToken, role = 'admin') =>
    apiFetch('/auth/google/', {
      method: 'POST',
      body: JSON.stringify({ id_token: idToken, role }),
    }),

  emailRegister: (email, password, name, role = 'admin') =>
    apiFetch('/auth/register/', {
      method: 'POST',
      body: JSON.stringify({ email, password, name, role }),
    }),

  emailLogin: (email, password) =>
    apiFetch('/auth/login/', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  getMe: () => apiFetch('/auth/me/'),

  logout: () => apiFetch('/auth/logout/', { method: 'POST' }),
};

// ============================================================
// NEEDS
// ============================================================
export const needs = {
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/needs/?${query}`);
  },

  getForMap: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/needs/map/?${query}`);
  },

  get: (id) => apiFetch(`/needs/${id}/`),

  create: (data) =>
    apiFetch('/needs/', { method: 'POST', body: JSON.stringify(data) }),

  update: (id, data) =>
    apiFetch(`/needs/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id) =>
    apiFetch(`/needs/${id}/`, { method: 'DELETE' }),

  getCategories: () => apiFetch('/needs/categories/'),
};

// ============================================================
// VOLUNTEERS
// ============================================================
export const volunteers = {
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/volunteers/?${query}`);
  },

  getForMap: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/volunteers/map/?${query}`);
  },

  get: (id) => apiFetch(`/volunteers/${id}/`),

  getTasks: (id, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/volunteers/${id}/tasks/?${query}`);
  },
};

// ============================================================
// MATCHING
// ============================================================
export const matching = {
  getSuggestions: (needId, limit = 5) =>
    apiFetch(`/matching/suggest/${needId}/?limit=${limit}`),

  assign: (data) =>
    apiFetch('/matching/assign/', { method: 'POST', body: JSON.stringify(data) }),

  updateStatus: (assignmentId, data) =>
    apiFetch(`/matching/assignment/${assignmentId}/status/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  getAssignment: (id) => apiFetch(`/matching/assignment/${id}/`),

  listAssignments: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/matching/assignments/?${query}`);
  },
};

// ============================================================
// ANALYTICS
// ============================================================
export const analytics = {
  getSummary: () => apiFetch('/analytics/summary/'),
  getCategories: () => apiFetch('/analytics/categories/'),
  getHeatmap: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/analytics/heatmap/?${query}`);
  },
  getTimeline: (days = 30) => apiFetch(`/analytics/timeline/?days=${days}`),
  getResponseTimes: () => apiFetch('/analytics/response-times/'),
  getAISummary: () => apiFetch('/analytics/ai-summary/'),
  getImpact: (days = 7) => apiFetch(`/analytics/impact/?days=${days}`),
};

// ============================================================
// OCR
// ============================================================
export const ocr = {
  extract: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch('/ocr/extract/', { method: 'POST', body: formData });
  },

  extractAndCreate: (file, lat = 0, lon = 0) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiFetch(`/ocr/extract-and-create/?latitude=${lat}&longitude=${lon}`, {
      method: 'POST',
      body: formData,
    });
  },
};

// ============================================================
// BROADCAST
// ============================================================
export const broadcast = {
  send: (data) =>
    apiFetch('/broadcast/', { method: 'POST', body: JSON.stringify(data) }),

  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/broadcast/?${query}`);
  },

  get: (id) => apiFetch(`/broadcast/${id}/`),
};

// ============================================================
// PREDICTIONS (Task 2.1)
// ============================================================
export const predictions = {
  generate: (data) =>
    apiFetch('/predictions/generate/', { method: 'POST', body: JSON.stringify(data) }),

  list: () => apiFetch('/predictions/'),

  confirm: (needId) =>
    apiFetch(`/predictions/${needId}/confirm/`, { method: 'PATCH' }),

  dismiss: (needId) =>
    apiFetch(`/predictions/${needId}/dismiss/`, { method: 'PATCH' }),
};

// ============================================================
// INVENTORY (Task 2.3)
// ============================================================
export const inventory = {
  list: () => apiFetch('/inventory/'),

  create: (data) =>
    apiFetch('/inventory/', { method: 'POST', body: JSON.stringify(data) }),

  addItem: (inventoryId, data) =>
    apiFetch(`/inventory/${inventoryId}/items/`, { method: 'POST', body: JSON.stringify(data) }),

  adjustItem: (itemId, data) =>
    apiFetch(`/inventory/items/${itemId}/`, { method: 'PATCH', body: JSON.stringify(data) }),

  findNearby: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/inventory/nearby/?${query}`);
  },

  getAlerts: () => apiFetch('/inventory/alerts/'),
};

// ============================================================
// AUDIT (Task 3.2)
// ============================================================
export const audit = {
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiFetch(`/analytics/audit/?${query}`);
  },

  summary: () => apiFetch('/analytics/audit/summary/'),
};

// ============================================================
// VOLUNTEER EXTRAS (Tasks 2.2, 2.5, 2.6, 3.3)
// ============================================================
export const volunteerExtras = {
  getFatigue: (volId) => apiFetch(`/volunteers/${volId}/fatigue/`),
  getCertificate: (volId) => apiFetch(`/volunteers/${volId}/certificate/`),
  verifySkill: (volId, data) =>
    apiFetch(`/volunteers/${volId}/verify-skill/`, { method: 'POST', body: JSON.stringify(data) }),
  getSkillVerifications: (volId) => apiFetch(`/volunteers/${volId}/skill-verifications/`),
};

// ============================================================
// TEXT STRUCTURE (Task 2.7)
// ============================================================
export const textStructure = {
  analyze: (text, language = 'en-IN') =>
    apiFetch('/ocr/structure-text/', { method: 'POST', body: JSON.stringify({ text, language }) }),
};
