import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
})

export const analyticsService = {
  getSalesStats: () => api.get('/analytics/stats'),
  getAlerts: (limit = 10, soloNoLeidas = false) => api.get(`/analytics/alertas?limit=${limit}&solo_no_leidas=${soloNoLeidas}`),
  getInsights: () => api.get('/analytics/insights'),
  getTopProductos: (limit = 5) => api.get(`/analytics/top-productos?limit=${limit}`),
  marcarLeida: (id) => api.patch(`/analytics/alertas/${id}/marcar-leida`),
  detectarAnomalias: () => api.post('/analytics/detect-anomalies'),
}

export const mappingService = {
  autoMap: (headers, datasourceType, userId = 'default') =>
    api.post('/mappings/auto-map', { headers, datasource_type: datasourceType, user_id: userId }),
  save: (datasourceType, mappings, userId = 'default') =>
    api.post(`/mappings/${datasourceType}`, { mappings, user_id: userId }),
}

function uploadCSV(endpoint, file, columnMapping = null) {
  const formData = new FormData()
  formData.append('file', file)
  if (columnMapping) {
    formData.append('column_mapping', JSON.stringify(columnMapping))
  }
  return api.post(endpoint, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const ventasService = {
  getAll: (params = {}) => api.get('/ventas/', { params }),
  getAnalytics: (params = {}) => api.get('/ventas/analytics/resumen', { params }),
  getCount: () => api.get('/ventas/stats/count'),
  uploadCSV: (file, mapping) => uploadCSV('/ventas/upload-csv', file, mapping),
}

export const gastosService = {
  getAll: (params = {}) => api.get('/gastos/', { params }),
  getAnalytics: (params = {}) => api.get('/gastos/analytics/resumen', { params }),
  getCount: () => api.get('/gastos/stats/count'),
  getPorCategoria: () => api.get('/gastos/stats/total-por-categoria'),
  uploadCSV: (file, mapping) => uploadCSV('/gastos/upload-csv', file, mapping),
}

export const inventarioService = {
  getAll: (params = {}) => api.get('/inventarios/', { params }),
  getAnalytics: () => api.get('/inventarios/analytics/resumen'),
  getCount: () => api.get('/inventarios/stats/count'),
  getLowStock: () => api.get('/inventarios/stats/bajo-stock'),
  getValor: () => api.get('/inventarios/stats/valor-inventario'),
  uploadCSV: (file, mapping) => uploadCSV('/inventarios/upload-csv', file, mapping),
}

export const clientesService = {
  getAll: (params = {}) => api.get('/clientes/', { params }),
  getAnalytics: () => api.get('/clientes/analytics/resumen'),
  getCount: () => api.get('/clientes/stats/count'),
  getPorTipo: () => api.get('/clientes/stats/por-tipo'),
  uploadCSV: (file, mapping) => uploadCSV('/clientes/upload-csv', file, mapping),
}

export const watcherService = {
  getStatus: () => api.get('/watcher/status'),
  list: () => api.get('/watcher/'),
  upsert: (datasourceType, filePath) => api.put(`/watcher/${datasourceType}`, { file_path: filePath }),
  patch: (datasourceType, body) => api.patch(`/watcher/${datasourceType}`, body),
  remove: (datasourceType) => api.delete(`/watcher/${datasourceType}`),
}

export default api
