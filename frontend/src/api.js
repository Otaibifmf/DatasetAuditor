import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const getDatasets = (params) => api.get('/datasets', { params })
export const getDatasetDetail = (id) => api.get(`/datasets/${id}`)
export const getDatasetHistory = (id) => api.get(`/datasets/${id}/history`)
export const getLeaderboard = () => api.get('/leaderboard')
export const getStats = () => api.get('/stats')
export const getTrends = (days = 90) => api.get('/trends', { params: { days } })
export const auditDataset = (id) => api.post(`/audit/${id}`)
export const auditByUrl = (url) => api.post('/audit/by-url', null, { params: { url } })
export const auditBulk = (limit = 50) => api.post('/audit/bulk', null, { params: { limit } })
export const auditSeed = (urls) => api.post('/audit/seed', { urls })
export const getPdfUrl = (id) => `/api/datasets/${id}/report.pdf`
