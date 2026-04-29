/** * API client for communicating with the LLM Proxy Web UI API server. * All requests go through the API server (port 8000) which then * proxies to the LLM Security Proxy (port 8080). */ import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Provider APIs ────────────────────────────────────────────────────────────

export const getProviders = () => api.get('/api/providers');

export const getProviderModels = (providerId) =>
  api.get(`/api/providers/${providerId}/models`);

export const switchProvider = (providerId) =>
  api.post('/api/providers/switch', { provider_id: providerId });

export const setProviderApiKey = (providerId, apiKey) =>
  api.post('/api/providers/api-key', { provider_id: providerId, api_key: apiKey });

// ── Chat API ─────────────────────────────────────────────────────────────────

export const sendChatCompletion = (messages, model, apiKey) =>
  api.post('/v1/chat/completions', {
    model,
    messages,
  }, {
    headers: {
      'Authorization': `Bearer ${apiKey}`,
    },
  });

// ── Dashboard APIs ───────────────────────────────────────────────────────────

export const getHealth = () => api.get('/api/dashboard/health');

export const getMetrics = () => api.get('/api/dashboard/metrics');

export const getFeatures = () => api.get('/api/dashboard/features');

export const getPipeline = () => api.get('/api/dashboard/pipeline');

export const getIssues = () => api.get('/api/dashboard/issues');

export const getCodebaseStats = () => api.get('/api/dashboard/codebase-stats');

export const getComponents = () => api.get('/api/dashboard/components');

export const getRoadmap = () => api.get('/api/dashboard/roadmap');

// ── API Health ───────────────────────────────────────────────────────────────

export const checkApiHealth = () => api.get('/api/health');

export default api;