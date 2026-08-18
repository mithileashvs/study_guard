// Thin client for the Study Guard API (see ../../../desktop-agent/api_server.py,
// also deployable standalone via ../../backend/app.py).
//
// API_BASE is resolved in priority order:
//   1. VITE_API_BASE, if set (see .env.example) -- this is what a
//      Vercel-hosted build uses to reach either (a) a locally-running
//      desktop agent at http://127.0.0.1:8000, since live camera/
//      posture/session data only ever exists on the machine running
//      it, or (b) a standalone cloud backend deployment, for the
//      roadmap/settings/history features that don't need local
//      hardware.
//   2. If unset and this is a dev build (`npm run dev`, Vite on
//      :5173), default to the desktop agent's local API so frontend
//      development works out of the box against `python launcher.py`.
//   3. If unset in a production build, default to '' (relative
//      '/api/...' paths) -- correct when the desktop agent is serving
//      this built frontend itself (see api_server.py's static-file
//      route), same origin as the API.
const API_BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error || `Request failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  getStatus: () => request('/api/status'),
  getStatusFrameUrl: () => `${API_BASE}/api/status/frame?t=${Date.now()}`,
  getSessionScore: () => request('/api/session/score'),
  getSessionsHistory: () => request('/api/sessions/history'),
  getWeeklyAnalytics: () => request('/api/analytics/weekly'),

  getSessionStatus: () => request('/api/session/status'),
  getSessionReadiness: () => request('/api/session/readiness'),
  startSession: (durationMinutes, opts = {}) =>
    request('/api/session/start', {
      method: 'POST',
      body: JSON.stringify({ duration_minutes: durationMinutes, ...opts }),
    }),
  pauseSession: () => request('/api/session/pause', { method: 'POST' }),
  resumeSession: () => request('/api/session/resume', { method: 'POST' }),
  endSession: () => request('/api/session/end', { method: 'POST' }),
  acknowledgeSession: () => request('/api/session/acknowledge', { method: 'POST' }),

  getSettings: () => request('/api/settings'),
  setAllowedApps: (allowed_apps) =>
    request('/api/settings/allowed-apps', {
      method: 'POST',
      body: JSON.stringify({ allowed_apps }),
    }),
  setStudyKeywords: (study_keywords) =>
    request('/api/settings/keywords', {
      method: 'POST',
      body: JSON.stringify({ study_keywords }),
    }),

  coachGreeting: () => request('/api/coach/greeting'),
  coachMessage: (text, action_key) =>
    request('/api/coach/message', {
      method: 'POST',
      body: JSON.stringify({ text, action_key }),
    }),

  getActiveRoadmap: () => request('/api/roadmap/active'),
  listRoadmaps: () => request('/api/roadmap/list'),
  createRoadmap: (payload) =>
    request('/api/roadmap/create', { method: 'POST', body: JSON.stringify(payload) }),
  startTopic: (roadmapId, topicId) =>
    request(`/api/roadmap/${roadmapId}/topic/${topicId}/start`, { method: 'POST' }),
  endTopic: (roadmapId, topicId, progressDeltaPct = 0) =>
    request(`/api/roadmap/${roadmapId}/topic/${topicId}/end`, {
      method: 'POST',
      body: JSON.stringify({ progress_delta_pct: progressDeltaPct }),
    }),
  setTopicProgress: (roadmapId, topicId, progressPct) =>
    request(`/api/roadmap/${roadmapId}/topic/${topicId}/progress`, {
      method: 'POST',
      body: JSON.stringify({ progress_pct: progressPct }),
    }),
  getTopicResources: (roadmapId, topicId, force = false) =>
    request(`/api/roadmap/${roadmapId}/topic/${topicId}/resources${force ? '?force=1' : ''}`),
  setActiveRoadmap: (roadmapId) =>
    request(`/api/roadmap/${roadmapId}/set-active`, { method: 'POST' }),
  deleteRoadmap: (roadmapId) => request(`/api/roadmap/${roadmapId}`, { method: 'DELETE' }),
}

export default api
