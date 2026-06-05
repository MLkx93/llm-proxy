/**
 * API client for the LLM Proxy Web UI.
 *
 * When served from port 8080 (admin console): calls proxy's /api/* directly
 * When served from port 8000 (demo): calls webui_api gateway at /api/*
 */
import axios from 'axios';

// When on port 8080 (proxy-served admin), use same-origin (current host)
// When on port 8000 (demo gateway), use gateway's localhost:8000
const API_BASE_URL = window.location.port === '8080'
  ? window.location.origin  // same-origin: http://localhost:8080
  : process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT to every request if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('shield_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Auth ─────────────────────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post('/api/auth/login', { username, password });
export const getMe = () => api.get('/api/auth/me');

// ── Providers ──────────────────────────────────────────────────────────────
export const getProviders = () => api.get('/api/providers');
export const getProviderModels = (providerId) => api.get(`/api/providers/${providerId}/models`);
export const switchProvider = (providerId) => api.post('/api/providers/switch', { provider_id: providerId });
export const setProviderApiKey = (providerId, apiKey) =>
  api.post('/api/providers/api-key', { provider_id: providerId, api_key: apiKey });

// ── Chat (buffered) ──────────────────────────────────────────────────────────
export const sendChatCompletion = (messages, model) =>
  api.post('/v1/chat/completions', { model, messages });

// ── Chat (streaming) — returns a fetch Response with an SSE body ─────────────
export const streamChatCompletion = (messages, model) => {
  const token = localStorage.getItem('shield_token');
  return fetch(`${API_BASE_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ model, messages, stream: true }),
  });
};

// ── Audit (admin panel) ──────────────────────────────────────────────────────
// When served by the proxy itself (port 8080), use /v1/audit/* directly (same-origin).
// When served by the demo (port 8000), go through /api/audit/* (which forwards to proxy).
const isProxyServed = window.location.port === '8080';
const STATS_PATH = isProxyServed ? '/v1/audit/stats' : '/api/audit/stats';
const LOGS_PATH = isProxyServed ? '/v1/audit/logs' : '/api/audit/logs';

// Create a dedicated audit client with correct baseURL
const auditClient = isProxyServed
  ? axios.create({ baseURL: window.location.origin, timeout: 30000 })  // e.g. http://localhost:8080
  : api;  // use the normal api client pointing to port 8000

// Always attach JWT token for authorization
auditClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('shield_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const getAuditStats = (timeRange = '24h') =>
  auditClient.get(STATS_PATH, { params: { time_range: timeRange } });
export const getAuditLogs = (params) => auditClient.get(LOGS_PATH, { params });

// ── History (chat sidebar) ───────────────────────────────────────────────────
export const listConversations = () => api.get('/api/history');
export const createConversation = (title) => api.post('/api/history', { title });
export const getConversation = (id) => api.get(`/api/history/${id}`);
export const addMessage = (id, msg) => api.post(`/api/history/${id}/messages`, msg);
export const deleteConversation = (id) => api.delete(`/api/history/${id}`);

// ── Dashboard (legacy) ───────────────────────────────────────────────────────
export const getHealth = () => api.get('/api/dashboard/health');
export const getMetrics = () => api.get('/api/dashboard/metrics');
export const getFeatures = () => api.get('/api/dashboard/features');
export const getPipeline = () => api.get('/api/dashboard/pipeline');
export const getIssues = () => api.get('/api/dashboard/issues');
export const getCodebaseStats = () => api.get('/api/dashboard/codebase-stats');
export const getComponents = () => api.get('/api/dashboard/components');
export const getRoadmap = () => api.get('/api/dashboard/roadmap');
export const checkApiHealth = () => api.get('/api/health');

export default api;
