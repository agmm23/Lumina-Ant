import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
})

export const analyticsService = {
  // { total_ventas, cantidad_transacciones, ticket_promedio, producto_mas_vendido, categoria_principal }
  getSalesStats: () => api.get('/analytics/stats'),
  // List[Alerta]
  getAlerts: (limit = 10, soloNoLeidas = false) => api.get(`/analytics/alertas?limit=${limit}&solo_no_leidas=${soloNoLeidas}`),
  getInsights: () => api.get('/analytics/insights'),
  getTopProductos: (limit = 5) => api.get(`/analytics/top-productos?limit=${limit}`),
  marcarLeida: (id) => api.patch(`/analytics/alertas/${id}/marcar-leida`),
  detectarAnomalias: () => api.post('/analytics/detect-anomalies'),
}

function uploadCSV(endpoint, file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post(endpoint, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const ventasService = {
  getAll: (params = {}) => api.get('/ventas/', { params }),
  getCount: () => api.get('/ventas/stats/count'),
  uploadCSV: (file) => uploadCSV('/ventas/upload-csv', file),
}

export const gastosService = {
  getAll: (params = {}) => api.get('/gastos/', { params }),
  getCount: () => api.get('/gastos/stats/count'),
  getPorCategoria: () => api.get('/gastos/stats/total-por-categoria'),
  uploadCSV: (file) => uploadCSV('/gastos/upload-csv', file),
}

export const inventarioService = {
  getAll: (params = {}) => api.get('/inventarios/', { params }),
  getCount: () => api.get('/inventarios/stats/count'),
  getLowStock: () => api.get('/inventarios/stats/bajo-stock'),
  getValor: () => api.get('/inventarios/stats/valor-inventario'),
  uploadCSV: (file) => uploadCSV('/inventarios/upload-csv', file),
}

export const clientesService = {
  getAll: (params = {}) => api.get('/clientes/', { params }),
  getCount: () => api.get('/clientes/stats/count'),
  getPorTipo: () => api.get('/clientes/stats/por-tipo'),
  uploadCSV: (file) => uploadCSV('/clientes/upload-csv', file),
}

export default api
