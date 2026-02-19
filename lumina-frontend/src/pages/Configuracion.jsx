import { useState, useRef, useEffect, useCallback } from 'react'
import { ventasService, gastosService, inventarioService, clientesService, analyticsService, mappingService } from '../services/api'
import ColumnMapper from '../components/ColumnMapper'

const TIPO_GROUP = {
  ventas:     { label: 'Ventas',     icon: '💰', color: 'green' },
  gastos:     { label: 'Gastos',     icon: '💸', color: 'rose' },
  inventario: { label: 'Inventario', icon: '📦', color: 'blue' },
}

const NIVEL_BADGE = {
  critical: 'bg-red-100 text-red-700',
  warning:  'bg-amber-100 text-amber-700',
}

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

// ── AlertasSection (configuración de reglas) ─────────────────────────────────

function AlertasSection() {
  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const debounceTimers = useRef({})

  useEffect(() => {
    async function fetch() {
      try {
        const res = await analyticsService.getAlertConfig()
        setRules(res.data)
      } catch {
        setError('No se pudo conectar con la API.')
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [])

  async function handleToggle(ruleId, currentEnabled) {
    setRules(prev => prev.map(r => r.rule_id === ruleId ? { ...r, enabled: !currentEnabled } : r))
    try {
      await analyticsService.toggleAlertRule(ruleId, !currentEnabled)
    } catch {
      setRules(prev => prev.map(r => r.rule_id === ruleId ? { ...r, enabled: currentEnabled } : r))
    }
  }

  const saveParams = useCallback((ruleId, params) => {
    clearTimeout(debounceTimers.current[ruleId])
    debounceTimers.current[ruleId] = setTimeout(() => {
      analyticsService.updateAlertParams(ruleId, params).catch(() => {})
    }, 600)
  }, [])

  function handleParamChange(ruleId, key, value, paramDef) {
    let num = parseFloat(value)
    if (isNaN(num)) return
    if (paramDef.min != null) num = Math.max(paramDef.min, num)
    if (paramDef.max != null) num = Math.min(paramDef.max, num)

    setRules(prev => prev.map(r => {
      if (r.rule_id !== ruleId) return r
      const newParams = { ...r.params, [key]: num }
      // Interpolar descripción con nuevos params
      let desc = r._descTemplate || r.description
      for (const pd of r.params_def) {
        const val = pd.key === key ? num : (newParams[pd.key] ?? pd.default)
        desc = desc.replaceAll(`{${pd.key}}`, String(val))
      }
      return { ...r, params: newParams, description: desc }
    }))

    // Obtener params completos para guardar
    const rule = rules.find(r => r.rule_id === ruleId)
    if (rule) {
      const fullParams = { ...rule.params, [key]: num }
      saveParams(ruleId, fullParams)
    }
  }

  // Guardar template de descripción al cargar (para interpolar después)
  useEffect(() => {
    if (rules.length > 0 && !rules[0]._descTemplate) {
      setRules(prev => prev.map(r => {
        // Reconstruir template desde description reemplazando valores actuales por placeholders
        let template = r.description
        for (const pd of (r.params_def || [])) {
          const val = r.params?.[pd.key] ?? pd.default
          template = template.replaceAll(String(val), `{${pd.key}}`)
        }
        return { ...r, _descTemplate: template }
      }))
    }
  }, [rules.length])

  // Agrupar por tipo
  const grouped = {}
  for (const rule of rules) {
    if (!grouped[rule.tipo]) grouped[rule.tipo] = []
    grouped[rule.tipo].push(rule)
  }

  const enabledCount = rules.filter(r => r.enabled).length
  const [detecting, setDetecting] = useState(false)
  const [detectResult, setDetectResult] = useState(null)

  async function handleDetectar() {
    setDetecting(true)
    setDetectResult(null)
    try {
      const res = await analyticsService.detectarAnomalias()
      setDetectResult({ type: 'success', message: res.data?.message || 'Detección completada' })
    } catch {
      setDetectResult({ type: 'error', message: 'Error al ejecutar la detección' })
    } finally {
      setDetecting(false)
    }
  }

  return (
    <div>
      <div className="mb-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Configuración de alertas</h3>
            <p className="text-sm text-gray-500 mt-0.5">
              Elige qué reglas de alerta quieres que se evalúen automáticamente.
              Las alertas activas se muestran en el Dashboard.
            </p>
            <p className="text-xs text-gray-400 mt-1">
              {enabledCount} de {rules.length} reglas activas
            </p>
          </div>
          <button
            onClick={handleDetectar}
            disabled={detecting}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
              detecting
                ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {detecting ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Detectando...
              </>
            ) : (
              'Detectar alertas'
            )}
          </button>
        </div>
        {detectResult && (
          <div className={`mt-3 p-3 rounded-lg text-sm ${
            detectResult.type === 'success'
              ? 'bg-green-50 border border-green-200 text-green-700'
              : 'bg-red-50 border border-red-200 text-red-700'
          }`}>
            {detectResult.message}
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([tipo, tipoRules]) => {
            const group = TIPO_GROUP[tipo] || { label: tipo, icon: '📋', color: 'gray' }
            return (
              <div key={tipo}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-lg">{group.icon}</span>
                  <h4 className="text-sm font-semibold text-gray-700">{group.label}</h4>
                </div>
                <div className="space-y-2">
                  {tipoRules.map(rule => (
                    <div
                      key={rule.rule_id}
                      className={`p-4 rounded-xl border transition-colors ${
                        rule.enabled
                          ? 'bg-white border-gray-200'
                          : 'bg-gray-50 border-gray-100 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <p className="text-sm font-medium text-gray-900">{rule.label}</p>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${NIVEL_BADGE[rule.nivel] ?? 'bg-gray-100 text-gray-600'}`}>
                              {rule.nivel === 'critical' ? 'Crítica' : 'Aviso'}
                            </span>
                          </div>
                          <p className="text-xs text-gray-500">{rule.description}</p>
                        </div>
                        <button
                          onClick={() => handleToggle(rule.rule_id, rule.enabled)}
                          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                            rule.enabled ? 'bg-blue-600' : 'bg-gray-200'
                          }`}
                          role="switch"
                          aria-checked={rule.enabled}
                        >
                          <span
                            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform duration-200 ease-in-out ${
                              rule.enabled ? 'translate-x-5' : 'translate-x-0'
                            }`}
                          />
                        </button>
                      </div>

                      {/* Parámetros configurables */}
                      {rule.enabled && rule.params_def?.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-100 flex flex-wrap gap-4">
                          {rule.params_def.map(pd => (
                            <label key={pd.key} className="flex items-center gap-2 text-xs text-gray-600">
                              <span>{pd.label}:</span>
                              <span className="flex items-center gap-1">
                                {pd.prefix && <span className="text-gray-400">{pd.prefix}</span>}
                                <input
                                  type="number"
                                  min={pd.min}
                                  max={pd.max}
                                  step={pd.key === 'multiplicador' ? 0.5 : 1}
                                  value={rule.params?.[pd.key] ?? pd.default}
                                  onChange={e => handleParamChange(rule.rule_id, pd.key, e.target.value, pd)}
                                  className="w-16 px-2 py-1 text-xs text-center border border-gray-200 rounded-lg bg-gray-50 focus:outline-none focus:ring-1 focus:ring-blue-400 focus:border-blue-400"
                                />
                                {pd.suffix && <span className="text-gray-400">{pd.suffix}</span>}
                              </span>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
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
