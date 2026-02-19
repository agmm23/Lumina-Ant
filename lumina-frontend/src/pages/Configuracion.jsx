import { useState, useRef, useEffect, useCallback } from 'react'
import { ventasService, gastosService, inventarioService, clientesService, analyticsService, mappingService } from '../services/api'
import ColumnMapper from '../components/ColumnMapper'

// ── Datos de fuentes CSV ───────────────────────────────────────────────────────

const DATASOURCES = [
  {
    id: 'ventas',
    label: 'Ventas',
    icon: '💰',
    color: 'green',
    service: ventasService,
    description: 'Historial de transacciones de venta por producto y cliente.',
  },
  {
    id: 'gastos',
    label: 'Gastos',
    icon: '💸',
    color: 'red',
    service: gastosService,
    description: 'Registro de gastos operativos por categoría y proveedor.',
  },
  {
    id: 'inventario',
    label: 'Inventario',
    icon: '📦',
    color: 'blue',
    service: inventarioService,
    description: 'Productos en stock con niveles mínimos y precios.',
  },
  {
    id: 'clientes',
    label: 'Clientes',
    icon: '👥',
    color: 'purple',
    service: clientesService,
    description: 'Base de clientes con datos de contacto y tipo.',
  },
]

const colorMap = {
  green:  { border: 'border-green-200',  bg: 'bg-green-50',  icon: 'bg-green-100',  badge: 'bg-green-100 text-green-700',  hover: 'hover:border-green-400 hover:bg-green-50'  },
  red:    { border: 'border-red-200',    bg: 'bg-red-50',    icon: 'bg-red-100',    badge: 'bg-red-100 text-red-700',    hover: 'hover:border-red-400 hover:bg-red-50'    },
  blue:   { border: 'border-blue-200',   bg: 'bg-blue-50',   icon: 'bg-blue-100',   badge: 'bg-blue-100 text-blue-700',   hover: 'hover:border-blue-400 hover:bg-blue-50'   },
  purple: { border: 'border-purple-200', bg: 'bg-purple-50', icon: 'bg-purple-100', badge: 'bg-purple-100 text-purple-700', hover: 'hover:border-purple-400 hover:bg-purple-50' },
}

const STORAGE_KEY = (id) => `lumina_uploaded_${id}`

/** Lee los headers (primera línea) de un CSV sin cargar todo el archivo */
function parseCSVHeaders(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      let text = e.target.result
      // Quitar BOM si existe
      if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1)
      const firstLine = text.split(/\r?\n/)[0]
      const headers = firstLine.split(',').map(h => h.trim().replace(/^"|"$/g, ''))
      resolve(headers)
    }
    reader.onerror = reject
    reader.readAsText(file.slice(0, 4096))
  })
}

// ── UploadCard ─────────────────────────────────────────────────────────────────

function UploadCard({ datasource }) {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY(datasource.id))
    return saved ? JSON.parse(saved) : null
  })

  // Mapping state
  const [step, setStep] = useState('idle') // 'idle' | 'analyzing' | 'mapping' | 'uploading'
  const [mapResponse, setMapResponse] = useState(null) // auto-map API response
  const [confirmedMapping, setConfirmedMapping] = useState(null)

  const inputRef = useRef()
  const c = colorMap[datasource.color]

  async function handleFile(f) {
    if (!f) return
    if (!f.name.endsWith('.csv')) {
      setResult({ type: 'error', message: 'Solo se aceptan archivos .csv' })
      return
    }
    setFile(f)
    setResult(null)
    setConfirmedMapping(null)

    // Parse headers y llamar auto-map
    setStep('analyzing')
    try {
      const headers = await parseCSVHeaders(f)
      const res = await mappingService.autoMap(headers, datasource.id)
      const data = res.data
      setMapResponse(data)

      // Si hay mappings guardados, la estructura no cambió, y todo está mapeado:
      // auto-confirmar (no es primera vez)
      if (data.has_saved_mappings && !data.structure_changed && data.all_mapped) {
        // Construir mapping desde sugerencias
        const autoMapping = {}
        for (const s of data.mappings) {
          if (s.target_column && s.csv_column !== s.target_column) {
            autoMapping[s.csv_column] = s.target_column
          }
        }
        setConfirmedMapping(autoMapping)
        setStep('idle')
      } else {
        // Primera vez o estructura cambió → mostrar UI de mapeo siempre
        setStep('mapping')
      }
    } catch (err) {
      console.error('Error en auto-map:', err)
      // Fallback: dejar subir sin mapping (como antes)
      setStep('idle')
      setMapResponse(null)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  function handleMappingConfirm(mapping) {
    setConfirmedMapping(mapping)
    setStep('idle')

    // Guardar mapping en backend para futuras sesiones
    const fullMapping = {}
    if (mapResponse) {
      for (const s of mapResponse.mappings) {
        const target = mapping[s.csv_column] !== undefined
          ? (mapping[s.csv_column] || s.csv_column) // manual override
          : s.target_column // from suggestion
        if (target) fullMapping[s.csv_column] = target
      }
    }
    mappingService.save(datasource.id, fullMapping).catch(() => {})
  }

  function handleMappingCancel() {
    setStep('idle')
    setFile(null)
    setMapResponse(null)
    setConfirmedMapping(null)
  }

  async function handleUpload() {
    if (!file) return
    setStep('uploading')
    setUploading(true)
    setResult(null)
    const fileName = file.name
    try {
      const res = await datasource.service.uploadCSV(file, confirmedMapping)
      const data = res.data
      const successResult = { type: 'success', message: data.message, fileName, detail: data.data }
      setResult(successResult)
      localStorage.setItem(STORAGE_KEY(datasource.id), JSON.stringify(successResult))
      setFile(null)
      setConfirmedMapping(null)
      setMapResponse(null)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Error al subir el archivo'
      setResult({ type: 'error', message: msg })
      localStorage.removeItem(STORAGE_KEY(datasource.id))
    } finally {
      setUploading(false)
      setStep('idle')
    }
  }

  const isMapping = step === 'mapping'
  const isAnalyzing = step === 'analyzing'
  const hasConfirmedMapping = confirmedMapping !== null

  return (
    <div className={`bg-white rounded-xl border ${c.border} p-5`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${c.icon} text-xl`}>{datasource.icon}</div>
        <div>
          <h3 className="font-semibold text-gray-900">{datasource.label}</h3>
          <p className="text-xs text-gray-500">{datasource.description}</p>
        </div>
      </div>

      {/* Mapping UI or Drop zone */}
      {isMapping && mapResponse ? (
        <ColumnMapper
          suggestions={mapResponse.mappings}
          targetColumns={mapResponse.target_columns}
          structureChanged={mapResponse.structure_changed}
          hasSavedMappings={mapResponse.has_saved_mappings}
          onConfirm={handleMappingConfirm}
          onCancel={handleMappingCancel}
          color={datasource.color}
        />
      ) : (
        <>
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => !isAnalyzing && inputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
              isAnalyzing
                ? 'border-blue-300 bg-blue-50 cursor-wait'
                : dragging
                ? 'border-blue-400 bg-blue-50 cursor-pointer'
                : file
                ? 'border-gray-300 bg-gray-50 cursor-pointer'
                : `border-gray-200 bg-white ${c.hover} cursor-pointer`
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => { handleFile(e.target.files[0]); e.target.value = '' }}
            />
            {isAnalyzing ? (
              <div className="flex items-center justify-center gap-2 text-sm text-blue-600">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Analizando columnas...
              </div>
            ) : file ? (
              <div className="flex items-center justify-center gap-2 text-sm text-gray-700">
                <span className="text-lg">📄</span>
                <span className="font-medium truncate max-w-48">{file.name}</span>
                {hasConfirmedMapping && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Mapeo listo</span>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); setFile(null); setConfirmedMapping(null); setMapResponse(null) }}
                  className="text-gray-400 hover:text-red-500 ml-1 cursor-pointer"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div className="text-sm text-gray-400">
                <p>Arrastra tu CSV aquí o <span className="text-blue-500 underline">selecciona archivo</span></p>
              </div>
            )}
          </div>

          {/* Editar mapeo / Subir */}
          {file && !isAnalyzing && (
            <div className="mt-3 space-y-2">
              {hasConfirmedMapping && (
                <button
                  onClick={() => setStep('mapping')}
                  className="text-xs text-blue-600 hover:text-blue-800 underline cursor-pointer"
                >
                  Editar mapeo de columnas
                </button>
              )}
              <button
                onClick={handleUpload}
                disabled={!hasConfirmedMapping || uploading}
                className={`w-full py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                  !hasConfirmedMapping || uploading
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {uploading ? 'Cargando...' : 'Subir CSV'}
              </button>
            </div>
          )}
        </>
      )}

      {/* Resultado */}
      {result && (
        <div className={`mt-3 p-3 rounded-lg text-sm ${
          result.type === 'success'
            ? 'bg-green-50 border border-green-200 text-green-800'
            : 'bg-red-50 border border-red-200 text-red-800'
        }`}>
          <p className="font-medium">{result.type === 'success' ? '✓' : '✗'} {result.message}</p>
          {result.type === 'success' && result.fileName && (
            <p className="text-xs mt-0.5 opacity-70 font-mono">{result.fileName}</p>
          )}
          {result.detail?.errores?.length > 0 && (
            <details className="mt-1">
              <summary className="text-xs cursor-pointer opacity-70">
                Ver {result.detail.errores.length} error(es)
              </summary>
              <ul className="mt-1 text-xs space-y-0.5 font-mono">
                {result.detail.errores.map((e, i) => (
                  <li key={i} className="opacity-80">{e}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

    </div>
  )
}

// ── AlertasSection ─────────────────────────────────────────────────────────────

const NIVEL_CONFIG = {
  critical: { label: 'Crítica',   bg: 'bg-red-50',    border: 'border-red-200',   text: 'text-red-700',   badge: 'bg-red-100 text-red-700',   dot: 'bg-red-500'   },
  warning:  { label: 'Aviso',     bg: 'bg-amber-50',  border: 'border-amber-200', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-700', dot: 'bg-amber-400' },
  info:     { label: 'Info',      bg: 'bg-blue-50',   border: 'border-blue-200',  text: 'text-blue-700',  badge: 'bg-blue-100 text-blue-700',  dot: 'bg-blue-400'  },
}

const TIPO_BADGE = {
  ventas:     'bg-green-100 text-green-700',
  gastos:     'bg-rose-100 text-rose-700',
  inventario: 'bg-blue-100 text-blue-700',
  clientes:   'bg-purple-100 text-purple-700',
}

const FILTROS = [
  { id: 'todas',    label: 'Todas' },
  { id: 'no_leidas', label: 'No leídas' },
  { id: 'critical', label: '🔴 Críticas' },
  { id: 'warning',  label: '🟡 Avisos' },
  { id: 'info',     label: '🔵 Info' },
]

function fmtDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (isNaN(d)) return value
  return d.toLocaleString('es-MX', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function AlertCard({ alerta, onMarcarLeida }) {
  const [marking, setMarking] = useState(false)
  const n = NIVEL_CONFIG[alerta.nivel] ?? NIVEL_CONFIG.info

  async function handleMarcar() {
    setMarking(true)
    try {
      await onMarcarLeida(alerta.id)
    } finally {
      setMarking(false)
    }
  }

  return (
    <div className={`rounded-xl border p-4 transition-opacity ${n.bg} ${n.border} ${alerta.leida ? 'opacity-50' : ''}`}>
      <div className="flex items-start gap-3">
        {/* Dot indicador */}
        <div className="mt-1 flex-shrink-0">
          <span className={`inline-block w-2 h-2 rounded-full ${alerta.leida ? 'bg-gray-300' : n.dot}`} />
        </div>

        {/* Contenido */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            {/* Nivel */}
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${n.badge}`}>
              {n.label}
            </span>
            {/* Tipo */}
            <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${TIPO_BADGE[alerta.tipo] ?? 'bg-gray-100 text-gray-600'}`}>
              {alerta.tipo}
            </span>
            {alerta.leida && (
              <span className="text-xs text-gray-400">Leída</span>
            )}
          </div>

          <p className={`text-sm font-medium ${n.text}`}>{alerta.mensaje}</p>

          <p className="text-xs text-gray-400 mt-1">{fmtDateTime(alerta.fecha_creacion)}</p>
        </div>

        {/* Acción */}
        {!alerta.leida && (
          <button
            onClick={handleMarcar}
            disabled={marking}
            className="flex-shrink-0 text-xs text-gray-400 hover:text-gray-700 border border-gray-200 hover:border-gray-300 bg-white rounded-lg px-2.5 py-1.5 transition-colors cursor-pointer disabled:opacity-50"
          >
            {marking ? '...' : 'Marcar leída'}
          </button>
        )}
      </div>
    </div>
  )
}

function AlertasSection() {
  const [alertas, setAlertas] = useState([])
  const [loading, setLoading] = useState(true)
  const [detecting, setDetecting] = useState(false)
  const [detectResult, setDetectResult] = useState(null)
  const [filtro, setFiltro] = useState('todas')
  const [error, setError] = useState(null)

  const fetchAlertas = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await analyticsService.getAlerts(100)
      setAlertas(res.data)
    } catch {
      setError('No se pudo conectar con la API.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAlertas() }, [fetchAlertas])

  async function handleDetectar() {
    setDetecting(true)
    setDetectResult(null)
    try {
      const res = await analyticsService.detectarAnomalias()
      setDetectResult({ type: 'success', message: res.data.message })
      await fetchAlertas()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al detectar anomalías'
      setDetectResult({ type: 'error', message: msg })
    } finally {
      setDetecting(false)
    }
  }

  async function handleMarcarLeida(id) {
    try {
      await analyticsService.marcarLeida(id)
      setAlertas(prev => prev.map(a => a.id === id ? { ...a, leida: true } : a))
    } catch {
      // silencioso
    }
  }

  async function handleMarcarTodasLeidas() {
    const noLeidas = alertas.filter(a => !a.leida)
    await Promise.allSettled(noLeidas.map(a => analyticsService.marcarLeida(a.id)))
    setAlertas(prev => prev.map(a => ({ ...a, leida: true })))
  }

  const alertasFiltradas = alertas.filter(a => {
    if (filtro === 'no_leidas') return !a.leida
    if (filtro === 'critical') return a.nivel === 'critical'
    if (filtro === 'warning')  return a.nivel === 'warning'
    if (filtro === 'info')     return a.nivel === 'info'
    return true
  })

  const noLeidasCount = alertas.filter(a => !a.leida).length

  return (
    <div>
      {/* Header de sección */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h3 className="text-base font-semibold text-gray-900">Gestión de alertas</h3>
          <p className="text-sm text-gray-500 mt-0.5">
            {noLeidasCount > 0
              ? `${noLeidasCount} alerta${noLeidasCount > 1 ? 's' : ''} sin leer`
              : 'Todas las alertas han sido revisadas'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {noLeidasCount > 0 && (
            <button
              onClick={handleMarcarTodasLeidas}
              className="text-sm text-gray-500 hover:text-gray-800 border border-gray-200 bg-white rounded-lg px-3 py-2 transition-colors cursor-pointer"
            >
              Marcar todas leídas
            </button>
          )}
          <button
            onClick={handleDetectar}
            disabled={detecting}
            className={`text-sm font-medium px-4 py-2 rounded-lg transition-colors cursor-pointer ${
              detecting
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-amber-500 hover:bg-amber-600 text-white'
            }`}
          >
            {detecting ? 'Analizando...' : '🔍 Detectar anomalías'}
          </button>
        </div>
      </div>

      {/* Resultado de detección */}
      {detectResult && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          detectResult.type === 'success'
            ? 'bg-green-50 border border-green-200 text-green-800'
            : 'bg-red-50 border border-red-200 text-red-800'
        }`}>
          {detectResult.type === 'success' ? '✓' : '✗'} {detectResult.message}
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-2 mb-4">
        {FILTROS.map(f => (
          <button
            key={f.id}
            onClick={() => setFiltro(f.id)}
            className={`text-sm px-3 py-1.5 rounded-lg border transition-colors cursor-pointer ${
              filtro === f.id
                ? 'bg-gray-800 text-white border-gray-800'
                : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
            }`}
          >
            {f.label}
            {f.id === 'no_leidas' && noLeidasCount > 0 && (
              <span className="ml-1.5 text-xs bg-red-500 text-white rounded-full px-1.5 py-0.5">
                {noLeidasCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : alertasFiltradas.length === 0 ? (
        <div className="p-8 bg-gray-50 border border-dashed border-gray-200 rounded-xl text-center text-gray-400">
          <p className="text-3xl mb-2">🔔</p>
          <p className="font-medium text-sm">
            {filtro === 'todas' ? 'No hay alertas registradas' : 'No hay alertas en este filtro'}
          </p>
          {filtro === 'todas' && (
            <p className="text-xs mt-1">Usa "Detectar anomalías" para analizar los datos cargados.</p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {alertasFiltradas.map(a => (
            <AlertCard key={a.id} alerta={a} onMarcarLeida={handleMarcarLeida} />
          ))}
          {alertasFiltradas.length >= 100 && (
            <p className="text-xs text-gray-400 text-center pt-1">Mostrando las últimas 100 alertas.</p>
          )}
        </div>
      )}
    </div>
  )
}

// ── Tabs de navegación interna ────────────────────────────────────────────────

const TABS = [
  { id: 'fuentes', label: 'Fuentes de datos', icon: '📂' },
  { id: 'alertas', label: 'Alertas',           icon: '🔔' },
]

// ── Main Page ─────────────────────────────────────────────────────────────────

function Configuracion() {
  const [activeTab, setActiveTab] = useState('fuentes')

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Configuración</h2>
        <p className="text-sm text-gray-500 mt-0.5">Gestiona fuentes de datos y alertas del sistema</p>
      </div>

      {/* Tabs internos */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              activeTab === tab.id
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Contenido según tab */}
      {activeTab === 'fuentes' && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {DATASOURCES.map((ds) => (
            <UploadCard key={ds.id} datasource={ds} />
          ))}
        </div>
      )}

      {activeTab === 'alertas' && <AlertasSection />}
    </div>
  )
}

export default Configuracion
