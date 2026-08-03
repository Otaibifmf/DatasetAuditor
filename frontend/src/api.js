import axios from 'axios'

// Where the backend lives. Default '/api' means "same origin" — the dev server
// proxy, the nginx container, or any reverse proxy sitting in front of both
// halves. Set VITE_API_BASE_URL at build time to point at another origin.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

// Reads are quick. Audits fan out into several upstream requests, so they get
// their own longer budget below. Both are bounded: axios defaults to no timeout
// at all, which turns a hung backend into a spinner that never resolves.
const READ_TIMEOUT = Number(import.meta.env.VITE_API_TIMEOUT_MS) || 30000
const AUDIT_TIMEOUT = Number(import.meta.env.VITE_AUDIT_TIMEOUT_MS) || 120000

const api = axios.create({ baseURL: BASE_URL, timeout: READ_TIMEOUT })

// Attach a human-readable reason to every failure so components never have to
// guess. Network errors and timeouts carry no `response` — exactly the case
// that previously surfaced as a generic fallback message, or as no message at
// all because the promise never settled.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT') {
      err.userMessage = 'The server took too long to respond. It may be starting up — try again in a moment.'
    } else if (!err.response) {
      err.userMessage = 'Could not reach the server. It may be offline.'
    } else if (err.response.status === 503) {
      err.userMessage = err.response.data?.detail || 'The server is up but its database is unavailable.'
    } else {
      err.userMessage = err.response.data?.detail || `Request failed (${err.response.status}).`
    }
    return Promise.reject(err)
  },
)

/** Best-effort human-readable message for any error thrown by this module. */
export const errorMessage = (err, fallback = 'Something went wrong') =>
  err?.userMessage || err?.response?.data?.detail || fallback

export const getDatasets = (params) => api.get('/datasets', { params })
export const getDatasetDetail = (id) => api.get(`/datasets/${id}`)
export const getDatasetHistory = (id) => api.get(`/datasets/${id}/history`)
export const getLeaderboard = () => api.get('/leaderboard')
export const getStats = () => api.get('/stats')
export const getTrends = (days = 90) => api.get('/trends', { params: { days } })

export const auditDataset = (id) => api.post(`/audit/${id}`, null, { timeout: AUDIT_TIMEOUT })
export const auditByUrl = (url) =>
  api.post('/audit/by-url', null, { params: { url }, timeout: AUDIT_TIMEOUT })
export const auditBulk = (limit = 50) =>
  api.post('/audit/bulk', null, { params: { limit }, timeout: AUDIT_TIMEOUT })
export const auditSeed = (urls) => api.post('/audit/seed', { urls }, { timeout: AUDIT_TIMEOUT })

export const getPdfUrl = (id) => `${BASE_URL}/datasets/${id}/report.pdf`
