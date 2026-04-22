import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  timeout: 10000,
})

// Adjunta el token JWT a todas las peticiones
api.interceptors.request.use(config => {
  const token = localStorage.getItem('lumina_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// Si el servidor devuelve 401 (token expirado), limpiar sesión y recargar
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401 && localStorage.getItem('lumina_token')) {
      localStorage.removeItem('lumina_token')
      delete api.defaults.headers.common['Authorization']
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authService = {
  register: (email, password, displayName) =>
    api.post('/auth/register', { email, password, display_name: displayName }),
  login: (email, password) =>
    api.post('/auth/login', { email, password }),
  loginWithGoogle: (credential) =>
    api.post('/auth/google', { credential }),
  getMe: () => api.get('/auth/me'),
  updateConfig: (patch) => api.patch('/auth/config', patch),
}

export const analyticsService = {
  getSalesStats: () => api.get('/analytics/stats'),
  getAlerts: (limit = 10, soloNoLeidas = false, tipo = null) => {
    let url = `/analytics/alertas?limit=${limit}&solo_no_leidas=${soloNoLeidas}`
    if (tipo) url += `&tipo=${tipo}`
    return api.get(url)
  },
  getInsights: () => api.get('/analytics/insights'),
  getTopProductos: (limit = 5) => api.get(`/analytics/top-productos?limit=${limit}`),
  marcarLeida: (id) => api.patch(`/analytics/alertas/${id}/marcar-leida`),
  detectarAnomalias: () => api.post('/analytics/detect-anomalies'),
  getAlertConfig: () => api.get('/analytics/alert-config'),
  toggleAlertRule: (ruleId, enabled) => api.patch(`/analytics/alert-config/${ruleId}`, { enabled }),
  updateAlertParams: (ruleId, params) => api.patch(`/analytics/alert-config/${ruleId}`, { params }),
}

export const mappingService = {
  autoMap: (headers, datasourceType) =>
    api.post('/mappings/auto-map', { headers, datasource_type: datasourceType }),
  save: (datasourceType, mappings) =>
    api.post(`/mappings/${datasourceType}`, { mappings }),
}

// Upload genérico: acepta CSV y Excel, con mapping y sheet_name opcionales
function uploadFile(endpoint, file, columnMapping = null, sheetName = null) {
  const formData = new FormData()
  formData.append('file', file)
  if (columnMapping) {
    formData.append('column_mapping', JSON.stringify(columnMapping))
  }
  if (sheetName) {
    formData.append('sheet_name', sheetName)
  }
  return api.post(endpoint, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
}

export const ventasService = {
  getAll: (params = {}) => api.get('/ventas/', { params }),
  getAnalytics: (params = {}) => api.get('/ventas/analytics/resumen', { params }),
  getCount: () => api.get('/ventas/stats/count'),
  uploadCSV: (file, mapping, sheet) => uploadFile('/ventas/upload-csv', file, mapping, sheet),
}

export const gastosService = {
  getAll: (params = {}) => api.get('/gastos/', { params }),
  getAnalytics: (params = {}) => api.get('/gastos/analytics/resumen', { params }),
  getCount: () => api.get('/gastos/stats/count'),
  getPorCategoria: () => api.get('/gastos/stats/total-por-categoria'),
  uploadCSV: (file, mapping, sheet) => uploadFile('/gastos/upload-csv', file, mapping, sheet),
}

export const inventarioService = {
  getAll: (params = {}) => api.get('/inventarios/', { params }),
  getAnalytics: () => api.get('/inventarios/analytics/resumen'),
  getCount: () => api.get('/inventarios/stats/count'),
  getLowStock: () => api.get('/inventarios/stats/bajo-stock'),
  getValor: () => api.get('/inventarios/stats/valor-inventario'),
  uploadCSV: (file, mapping, sheet) => uploadFile('/inventarios/upload-csv', file, mapping, sheet),
}

export const clientesService = {
  getAll: (params = {}) => api.get('/clientes/', { params }),
  getAnalytics: () => api.get('/clientes/analytics/resumen'),
  getCount: () => api.get('/clientes/stats/count'),
  getPorTipo: () => api.get('/clientes/stats/por-tipo'),
  uploadCSV: (file, mapping, sheet) => uploadFile('/clientes/upload-csv', file, mapping, sheet),
}

// Servicio de importación: listado de hojas y conexión a Google Sheets
export const importService = {
  // Excel: obtener lista de hojas antes del upload
  getExcelSheets: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/import/excel/sheets', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 15000,
    })
  },
  // Google Sheets: obtener hojas por URL o ID
  getSheetsInfo: (urlOrId) =>
    api.post('/import/sheets/info', { url_or_id: urlOrId }, { timeout: 15000 }),
  // Google Sheets: obtener headers de una hoja específica (para auto-map)
  getSheetsHeaders: (spreadsheetId, sheet = null) =>
    api.post('/import/sheets/headers', { spreadsheet_id: spreadsheetId, sheet }),
  // Google Sheets: importar datos directamente desde una hoja
  importFromSheets: (datasourceType, spreadsheetId, sheet, columnMapping = null) => {
    const body = {
      spreadsheet_id: spreadsheetId,
      sheet,
      datasource_type: datasourceType,
      column_mapping: columnMapping || {},
    }
    return api.post(`/import/sheets/import`, body, { timeout: 30000 })
  },
}

export const chatService = {
  send: (message, history = []) => api.post('/chat/', { message, history }),
  getSuggestedPrompts: () => api.get('/chat/suggested-prompts'),
}

export const watcherService = {
  getStatus: () => api.get('/watcher/status'),
  list: () => api.get('/watcher/'),
  // body: { file_path, source_type?, source_config?, reset_cursor? }
  upsert: (datasourceType, body) => api.put(`/watcher/${datasourceType}`, body),
  patch: (datasourceType, body) => api.patch(`/watcher/${datasourceType}`, body),
  remove: (datasourceType) => api.delete(`/watcher/${datasourceType}`),
}

export default api
