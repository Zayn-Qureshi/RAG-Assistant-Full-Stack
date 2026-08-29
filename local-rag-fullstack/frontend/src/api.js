/**
 * API client for the FastAPI backend — JWT-based auth.
 * Token is stored in localStorage under 'rag_token'.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function getToken() {
  return localStorage.getItem('rag_token') || ''
}

export function setToken(token) {
  localStorage.setItem('rag_token', token)
}

export function clearToken() {
  localStorage.removeItem('rag_token')
}

export function isLoggedIn() {
  return !!getToken()
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...options.headers,
    },
  })

  if (response.status === 401) {
    // Token is invalid, expired, or revoked — clear it so isLoggedIn()
    // correctly reflects reality instead of trusting a stale token's
    // mere presence in localStorage.
    clearToken()
    localStorage.removeItem('rag_username')
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    const error = new Error(errorBody.detail || `Request failed: ${response.status}`)
    error.status = response.status
    throw error
  }

  return response.json()
}

// --- Auth ---
export async function signup(username, password) {
  const result = await apiRequest('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setToken(result.access_token)
  localStorage.setItem('rag_username', result.username)
  return result
}

export async function login(username, password) {
  const result = await apiRequest('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setToken(result.access_token)
  localStorage.setItem('rag_username', result.username)
  return result
}

export async function logout() {
  try {
    await apiRequest('/auth/logout', { method: 'POST' })
  } finally {
    clearToken()
    localStorage.removeItem('rag_username')
  }
}

// --- Conversations ---
export async function listConversations() {
  return apiRequest('/conversations')
}

export async function createConversation(title = 'New conversation') {
  return apiRequest('/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export async function getConversationMessages(conversationId) {
  return apiRequest(`/conversations/${conversationId}`)
}

export async function deleteConversation(conversationId) {
  return apiRequest(`/conversations/${conversationId}`, { method: 'DELETE' })
}

// --- Query ---
export async function sendQuery(query, conversationId, topK = 3) {
  return apiRequest('/query', {
    method: 'POST',
    body: JSON.stringify({ query, conversation_id: conversationId, top_k: topK }),
  })
}

// --- Documents ---
export async function listDocuments() {
  return apiRequest('/documents')
}

export async function deleteDocument(filename) {
  return apiRequest(`/documents/${encodeURIComponent(filename)}`, { method: 'DELETE' })
}

export async function uploadDocument(file) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/ingest`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${getToken()}` },
    body: formData,
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || `Upload failed: ${response.status}`)
  }

  return response.json()
}

// --- Misc ---
export async function checkHealth() {
  const response = await fetch(`${API_BASE_URL}/health`)
  if (!response.ok) throw new Error('Backend offline')
  return response.json()
}
