import { api } from "./client.js";

export const authApi = {
  login: (payload) => api.post("/auth/login/", payload),
  faceLogin: (formData) => api.post("/auth/face-login/", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  faceEnroll: (formData) => api.post("/auth/face-enroll/", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  register: (payload) => api.post("/auth/register/", payload, payload instanceof FormData ? { headers: { "Content-Type": "multipart/form-data" } } : undefined),
  me: () => api.get("/auth/me/"),
  updateMe: (payload) => api.patch("/auth/me/", payload)
};

export const analyticsApi = {
  dashboard: () => api.get("/analytics/dashboard/"),
  performance: (days = 7) => api.get(`/analytics/performance/?days=${days}`)
};

export const usersApi = {
  list: (params) => api.get("/users/", { params }),
  create: (payload) => api.post("/users/", payload),
  update: (id, payload) => api.patch(`/users/${id}/`, payload),
  approve: (id) => api.post(`/users/${id}/approve/`),
  reject: (id, payload) => api.post(`/users/${id}/reject/`, payload),
  suspend: (id, payload) => api.post(`/users/${id}/suspend/`, payload),
  lookupSecret: (secretId) => api.get("/users/secret-lookup/", { params: { secret_id: secretId } })
};

export const teamsApi = {
  list: (params) => api.get("/teams/", { params }),
  create: (payload) => api.post("/teams/", payload),
  update: (id, payload) => api.patch(`/teams/${id}/`, payload),
  remove: (id) => api.delete(`/teams/${id}/`)
};

export const projectsApi = {
  list: (params) => api.get("/projects/", { params }),
  get: (id) => api.get(`/projects/${id}/`),
  create: (payload) => api.post("/projects/", payload),
  update: (id, payload) => api.patch(`/projects/${id}/`, payload),
  kanban: (id) => api.get(`/projects/${id}/kanban/`),
  analytics: (id) => api.get(`/projects/${id}/analytics/`),
  projectFlow: (id, payload) => api.post(`/projects/${id}/project-flow/`, payload),
  connection: (id) => api.get(`/projects/${id}/connection/`),
  connect: (id, payload) => api.post(`/projects/${id}/connection/`, payload),
  branches: (id) => api.get(`/projects/${id}/branches/`),
  commits: (id, params) => api.get(`/projects/${id}/commits/`, { params }),
  syncGit: (id, payload) => api.post(`/projects/${id}/sync-git/`, payload),
  pushGit: (id, payload) => api.post(`/projects/${id}/push-git/`, payload),
  deployBranch: (id, payload) => api.post(`/projects/${id}/deploy-branch/`, payload),
  review: (id, payload) => api.post(`/projects/${id}/review/`, payload),
  localStatus: (id) => api.get(`/projects/${id}/local-status/`)
};

export const tasksApi = {
  list: (params) => api.get("/tasks/", { params }),
  create: (payload) => api.post("/tasks/", payload),
  update: (id, payload) => api.patch(`/tasks/${id}/`, payload),
  move: (id, payload) => api.patch(`/tasks/${id}/move/`, payload),
  approve: (id, payload) => api.post(`/tasks/${id}/approve/`, payload),
  disapprove: (id, payload) => api.post(`/tasks/${id}/disapprove/`, payload),
  my: () => api.get("/tasks/my/")
};

export const deploymentsApi = {
  list: (params) => api.get("/deployments/", { params }),
  toggle: (id, payload) => api.post(`/deployments/${id}/toggle/`, payload)
};

export const documentsApi = {
  list: (params) => api.get("/documents/", { params }),
  upload: (formData) => api.post("/documents/", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  download: (id) => api.get(`/documents/${id}/download/`, { responseType: "blob" }),
  preview: (id) => api.get(`/documents/${id}/preview/`, { responseType: "blob" }),
  review: (id, payload) => api.post(`/documents/${id}/review/`, payload),
  remove: (id) => api.delete(`/documents/${id}/`)
};

export const ticketsApi = {
  list: (params) => api.get("/tickets/", { params }),
  get: (id) => api.get(`/tickets/${id}/`),
  create: (formData) => api.post("/tickets/", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  update: (id, payload) => api.patch(`/tickets/${id}/`, payload),
  attach: (id, formData) => api.post(`/tickets/${id}/attach/`, formData, { headers: { "Content-Type": "multipart/form-data" } }),
  comment: (id, payload) => api.post(`/tickets/${id}/comment/`, payload),
  remove: (id) => api.delete(`/tickets/${id}/`)
};

export const notificationsApi = {
  list: () => api.get("/notifications/"),
  markRead: (id) => api.post(`/notifications/${id}/mark_read/`),
  broadcast: (payload) => api.post("/notifications/broadcast/", payload)
};

export const auditApi = {
  auditLogs: (params) => api.get("/audit-logs/", { params }),
  apiLogs: (params) => api.get("/api-logs/", { params })
};

export const aiApi = {
  list: (params) => api.get("/task-suggestions/", { params }),
  generate: (payload) => api.post("/task-suggestions/generate/", payload),
  approve: (id, payload) => api.post(`/task-suggestions/${id}/approve/`, payload)
};

export const enterpriseApi = {
  companies: (params) => api.get("/companies/", { params }),
  services: (params) => api.get("/company-services/", { params }),
  createService: (payload) => api.post("/company-services/", payload),
  updateService: (id, payload) => api.patch(`/company-services/${id}/`, payload),
  collaborationChannels: (params) => api.get("/collaboration-channels/", { params }),
  createCollaborationChannel: (payload) => api.post("/collaboration-channels/", payload),
  collaborationMessages: (id) => api.get(`/collaboration-channels/${id}/messages/`),
  sendCollaborationMessage: (id, payload) => api.post(`/collaboration-channels/${id}/messages/`, payload),
  collaborationTyping: (id, payload) => api.post(`/collaboration-channels/${id}/typing/`, payload),
  connectionSummary: () => api.get("/connection-engine/summary/"),
  connectors: (params) => api.get("/universal-connectors/", { params }),
  createConnector: (payload) => api.post("/universal-connectors/", payload),
  syncConnector: (id, payload) => api.post(`/universal-connectors/${id}/sync/`, payload),
  controlConnector: (id, payload) => api.post(`/universal-connectors/${id}/control/`, payload),
  connectionEvents: (params) => api.get("/connection-events/", { params }),
  featureFlags: (params) => api.get("/feature-flags/", { params }),
  updateFeatureFlag: (id, payload) => api.patch(`/feature-flags/${id}/`, payload),
  apiKeys: (params) => api.get("/api-keys/", { params }),
  createApiKey: (payload) => api.post("/api-keys/", payload),
  updateApiKey: (id, payload) => api.patch(`/api-keys/${id}/`, payload),
  grants: (params) => api.get("/api-key-grants/", { params }),
  createGrant: (payload) => api.post("/api-key-grants/", payload),
  estimates: (params) => api.get("/project-estimates/", { params }),
  createEstimate: (payload) => api.post("/project-estimates/", payload),
  sendEstimate: (id) => api.post(`/project-estimates/${id}/send/`),
  emailEvents: (params) => api.get("/email-events/", { params }),
  hosting: (params) => api.get("/hosting-connections/", { params }),
  toggleHosting: (id, payload) => api.post(`/hosting-connections/${id}/toggle/`, payload),
  serverLive: () => api.get("/server-control/live/"),
  controlServer: (id, payload) => api.post(`/server-control/${id}/control/`, payload),
  networkLive: () => api.get("/network-telemetry/live/"),
  networkTelemetry: (params) => api.get("/network-telemetry/", { params }),
  voiceIntents: (params) => api.get("/voice-intents/", { params }),
  createVoiceIntent: (payload) => api.post("/voice-intents/", payload),
  report: (kind, format = "pdf") => api.get(`/reports/${kind}/`, { params: { format }, responseType: "blob" }),
  reportUrl: (kind, format = "pdf") => `${api.defaults.baseURL}/reports/${kind}/?format=${format}`
};
