import { useState, useRef, useEffect, useCallback } from 'react'
import { ventasService, gastosService, inventarioService, clientesService, analyticsService, mappingService, importService, watcherService } from '../services/api'
import ColumnMapper from '../components/ColumnMapper'
import { useLanguage } from '../contexts/LanguageContext'
import { useDataSync } from '../contexts/DataSyncContext'
import useWatcherRefresh from '../hooks/useWatcherRefresh'

const TIPO_GROUP = {
  ventas:     { icon: '💰', color: 'green' },
  gastos:     { icon: '💸', color: 'rose' },
  inventario: { icon: '📦', color: 'blue' },
}

const NIVEL_BADGE = {
  critical: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-400',
  warning:  'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-400',
}

// ── Datos de fuentes CSV ───────────────────────────────────────────────────────

const DATASOURCES = [
  { id: 'ventas', icon: '💰', color: 'green', service: ventasService },
  { id: 'gastos', icon: '💸', color: 'red', service: gastosService },
  { id: 'inventario', icon: '📦', color: 'blue', service: inventarioService },
  { id: 'clientes', icon: '👥', color: 'purple', service: clientesService },
]

const colorMap = {
  green:  { border: 'border-green-200 dark:border-green-800',  bg: 'bg-green-50 dark:bg-green-950',  icon: 'bg-green-100 dark:bg-green-900',  badge: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-400',  hover: 'hover:border-green-400 hover:bg-green-50 dark:hover:border-green-700 dark:hover:bg-green-950'  },
  red:    { border: 'border-red-200 dark:border-red-800',    bg: 'bg-red-50 dark:bg-red-950',    icon: 'bg-red-100 dark:bg-red-900',    badge: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-400',    hover: 'hover:border-red-400 hover:bg-red-50 dark:hover:border-red-700 dark:hover:bg-red-950'    },
  blue:   { border: 'border-blue-200 dark:border-blue-800',   bg: 'bg-blue-50 dark:bg-blue-950',   icon: 'bg-blue-100 dark:bg-blue-900',   badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-400',   hover: 'hover:border-blue-400 hover:bg-blue-50 dark:hover:border-blue-700 dark:hover:bg-blue-950'   },
  purple: { border: 'border-purple-200 dark:border-purple-800', bg: 'bg-purple-50 dark:bg-purple-950', icon: 'bg-purple-100 dark:bg-purple-900', badge: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-400', hover: 'hover:border-purple-400 hover:bg-purple-50 dark:hover:border-purple-700 dark:hover:bg-purple-950' },
}

const STORAGE_KEY = (id) => `lumina_uploaded_${id}`
const SOURCE_TYPES = ['csv', 'excel', 'google_sheets']

/** Lee los headers de un CSV sin cargar todo el archivo */
function parseCSVHeaders(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      let text = e.target.result
      if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1)
      const firstLine = text.split(/\r?\n/)[0]
      try {
        const headers = firstLine.split(',').map(h => h.trim().replace(/^"|"$/g, ''))
        resolve(headers)
      } catch { resolve([]) }
    }
    reader.onerror = reject
    reader.readAsText(file.slice(0, 4096))
  })
}

function relativeTime(isoString) {
  if (!isoString) return null
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'hace un momento'
  if (mins < 60) return `hace ${mins} min`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `hace ${hrs} h`
  return `hace ${Math.floor(hrs / 24)} d`
}

function sourceTypeIcon(st) {
  return st === 'excel' ? '📊' : st === 'google_sheets' ? '🌐' : '📄'
}

// ── UploadCard ─────────────────────────────────────────────────────────────────

function UploadCard({ datasource }) {
  const { t } = useLanguage()
  const c = colorMap[datasource.color]
  const dsLabel = t(`config.datasources.${datasource.id}.label`)
  const dsDesc = t(`config.datasources.${datasource.id}.description`)

  // Source type selector
  const [sourceType, setSourceType] = useState('csv')

  // Shared state
  const [step, setStep] = useState('idle')  // idle | analyzing | mapping | uploading
  const [mapResponse, setMapResponse] = useState(null)
  const [confirmedMapping, setConfirmedMapping] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY(datasource.id))
    return saved ? JSON.parse(saved) : null
  })

  // CSV / Excel state
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [sheets, setSheets] = useState([])       // hojas del Excel
  const [selectedSheet, setSelectedSheet] = useState('')
  const inputRef = useRef()

  // File handle for auto-sync via File System Access API
  const [fileHandle, setFileHandle] = useState(null)
  const { registerWatch, unregisterWatch, syncStatus, pendingHandles, grantPermission } = useDataSync()
  const isSyncing    = syncStatus[datasource.id] === 'syncing'
  const isWatching   = syncStatus[datasource.id] !== undefined          // activo (fresh o restored)
  const hasPending   = !!pendingHandles[datasource.id]                  // necesita permiso
  const pendingName  = pendingHandles[datasource.id]?.fileName

  // Connected source state (persisted in DB)
  const [connectedSource, setConnectedSource] = useState(null)
  const [loadingSource,   setLoadingSource]   = useState(true)
  const [changingSource,  setChangingSource]  = useState(false)

  const refreshConnectedSource = useCallback(async () => {
    try {
      const res = await watcherService.list()
      const w = res.data.find(w => w.datasource_type === datasource.id && w.enabled)
      if (w) {
        setConnectedSource({ source_name: w.source_name, source_type: w.source_type, last_imported_at: w.last_imported_at, last_import_count: w.last_row_count })
        setChangingSource(false)
      }
    } catch {}
    setLoadingSource(false)
  }, [datasource.id])

  // Carga inicial — reutiliza la misma lógica que el refresh manual
  useEffect(() => {
    refreshConnectedSource()
  }, [refreshConnectedSource])

  // Auto-refresh cuando el browser-side auto-sync termina (isSyncing: true → false)
  const prevSyncingRef = useRef(false)
  useEffect(() => {
    if (prevSyncingRef.current && !isSyncing) refreshConnectedSource()
    prevSyncingRef.current = isSyncing
  }, [isSyncing, refreshConnectedSource])

  // Auto-refresh cuando el backend detecta cambios vía watcher (GSheets, file watcher)
  useWatcherRefresh(refreshConnectedSource)

  async function handleDisconnect() {
    try { await watcherService.remove(datasource.id) } catch {}
    unregisterWatch(datasource.id)
    localStorage.removeItem(STORAGE_KEY(datasource.id))
    setConnectedSource(null)
    setChangingSource(false)
  }

  // Google Sheets state
  const [gsUrl, setGsUrl] = useState('')
  const [gsSheets, setGsSheets] = useState([])
  const [gsSpreadsheetId, setGsSpreadsheetId] = useState('')
  const [gsSpreadsheetTitle, setGsSpreadsheetTitle] = useState('')
  const [gsSelectedSheet, setGsSelectedSheet] = useState('')
  const [gsConnecting, setGsConnecting] = useState(false)
  const [gsError, setGsError] = useState('')

  // Reset when switching source type
  function switchSourceType(type) {
    setSourceType(type)
    setFile(null); setSheets([]); setSelectedSheet('')
    setGsUrl(''); setGsSheets([]); setGsSpreadsheetId('')
    setGsSpreadsheetTitle(''); setGsSelectedSheet(''); setGsError('')
    setMapResponse(null); setConfirmedMapping(null); setStep('idle')
  }

  // ── Auto-map helpers ─────────────────────────────────────────────────────────

  async function runAutoMap(headers) {
    setStep('analyzing')
    try {
      const res = await mappingService.autoMap(headers, datasource.id)
      const data = res.data
      setMapResponse(data)
      if (data.has_saved_mappings && !data.structure_changed && data.all_mapped) {
        const autoMapping = {}
        for (const s of data.mappings) {
          if (s.target_column && s.csv_column !== s.target_column)
            autoMapping[s.csv_column] = s.target_column
        }
        setConfirmedMapping(autoMapping)
        setStep('idle')
      } else {
        setStep('mapping')
      }
    } catch {
      setStep('idle')
    }
  }

  function handleMappingConfirm(mapping) {
    setConfirmedMapping(mapping)
    setStep('idle')
    const fullMapping = {}
    if (mapResponse) {
      for (const s of mapResponse.mappings) {
        const target = mapping[s.csv_column] !== undefined
          ? (mapping[s.csv_column] || s.csv_column)
          : s.target_column
        if (target) fullMapping[s.csv_column] = target
      }
    }
    mappingService.save(datasource.id, fullMapping).catch(() => {})
  }

  function handleMappingCancel() {
    setStep('idle')
    setFile(null); setMapResponse(null); setConfirmedMapping(null)
    setGsSpreadsheetId(''); setGsSheets([]); setGsSelectedSheet('')
  }

  // ── CSV flow ─────────────────────────────────────────────────────────────────

  async function handleCSVFile(f, handle = null) {
    if (!f) return
    setFile(f); setResult(null); setConfirmedMapping(null)
    setFileHandle(handle)
    // Parse headers from first line for auto-map
    const headers = await parseCSVHeaders(f)
    await runAutoMap(headers)
  }

  // ── Excel flow ───────────────────────────────────────────────────────────────

  async function handleExcelFile(f, handle = null) {
    if (!f) return
    setFile(f); setResult(null); setConfirmedMapping(null)
    setFileHandle(handle)
    setSheets([]); setSelectedSheet('')
    setStep('analyzing')
    try {
      const res = await importService.getExcelSheets(f)
      const sheetList = res.data.sheets || []
      setSheets(sheetList)
      const firstSheet = sheetList[0] || ''
      setSelectedSheet(firstSheet)
      if (firstSheet) {
        // Fetch headers for the auto-selected first sheet and trigger mapping.
        // Use `f` directly (not `file` state, which hasn't batched yet).
        const formData = new FormData()
        formData.append('file', f)
        const headersRes = await fetch(
          `http://localhost:8000/api/import/excel/headers?sheet=${encodeURIComponent(firstSheet)}`,
          { method: 'POST', body: formData }
        )
        const headersData = await headersRes.json()
        await runAutoMap(headersData.headers || [])
      } else {
        setStep('idle')
      }
    } catch (err) {
      setStep('idle')
      setResult({ type: 'error', message: err.response?.data?.detail || 'Error leyendo hojas del Excel' })
    }
  }

  async function handleExcelSheetSelect(sheet) {
    setSelectedSheet(sheet)
    setConfirmedMapping(null)
    if (!file) return
    setStep('analyzing')
    try {
      const formData = new FormData()
      formData.append('file', file)
      const headersRes = await fetch(`http://localhost:8000/api/import/excel/headers?sheet=${encodeURIComponent(sheet)}`, {
        method: 'POST', body: formData
      })
      const headersData = await headersRes.json()
      await runAutoMap(headersData.headers || [])
    } catch {
      setStep('idle')
    }
  }

  // ── Google Sheets flow ────────────────────────────────────────────────────────

  async function handleGSConnect() {
    if (!gsUrl.trim()) return
    setGsConnecting(true); setGsError(''); setGsSheets([]); setGsSelectedSheet('')
    setConfirmedMapping(null)
    try {
      const res = await importService.getSheetsInfo(gsUrl.trim())
      const { sheets, spreadsheet_id, title } = res.data
      setGsSheets(sheets || [])
      setGsSpreadsheetId(spreadsheet_id || '')
      setGsSpreadsheetTitle(title || '')
      setGsSelectedSheet(sheets?.[0] || '')
    } catch (err) {
      setGsError(err.response?.data?.detail || t('config.upload.errorConectar'))
    } finally {
      setGsConnecting(false)
    }
  }

  async function handleGSSheetSelect(sheet) {
    setGsSelectedSheet(sheet)
    setConfirmedMapping(null)
    if (!gsSpreadsheetId) return
    setStep('analyzing')
    try {
      const res = await importService.getSheetsHeaders(gsSpreadsheetId, sheet)
      await runAutoMap(res.data.headers || [])
    } catch {
      setStep('idle')
    }
  }

  // ── Upload ───────────────────────────────────────────────────────────────────

  async function handleUpload() {
    setStep('uploading'); setUploading(true); setResult(null)
    try {
      let res
      if (sourceType === 'google_sheets') {
        // Import directly from Google Sheets API on backend
        res = await importService.importFromSheets(
          datasource.id, gsSpreadsheetId, gsSelectedSheet, confirmedMapping
        )
      } else {
        // CSV or Excel: upload file
        const sheet = sourceType === 'excel' ? selectedSheet : undefined
        res = await datasource.service.uploadCSV(file, confirmedMapping, sheet)
      }
      const data = res.data
      const label = sourceType === 'google_sheets'
        ? `${gsSpreadsheetTitle} › ${gsSelectedSheet}`
        : file?.name
      const successResult = { type: 'success', message: data.message, fileName: label, detail: data.data }
      setResult(successResult)
      localStorage.setItem(STORAGE_KEY(datasource.id), JSON.stringify(successResult))
      // Register auto-sync watch for local CSV/Excel files
      if ((sourceType === 'csv' || sourceType === 'excel') && fileHandle) {
        const sheet = sourceType === 'excel' ? selectedSheet : undefined
        registerWatch(datasource.id, {
          handle: fileHandle,
          confirmedMapping: confirmedMapping,
          sheet,
          uploadFn: (f, mapping, s) => datasource.service.uploadCSV(f, mapping, s),
        })
      }
      if (sourceType !== 'google_sheets') {
        setFile(null)
      }
      setConfirmedMapping(null); setMapResponse(null)
      await refreshConnectedSource()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || t('config.upload.errorSubir')
      setResult({ type: 'error', message: msg })
      localStorage.removeItem(STORAGE_KEY(datasource.id))
    } finally {
      setUploading(false); setStep('idle')
    }
  }

  const isMapping = step === 'mapping'
  const isAnalyzing = step === 'analyzing'
  const hasConfirmedMapping = confirmedMapping !== null

  // Ready to upload check per source type
  const canUpload = hasConfirmedMapping && (
    sourceType === 'csv' ? !!file :
    sourceType === 'excel' ? (!!file && !!selectedSheet) :
    (!!gsSpreadsheetId && !!gsSelectedSheet)
  )

  // ── Render ───────────────────────────────────────────────────────────────────

  if (loadingSource) {
    return (
      <div className={`bg-white dark:bg-gray-900 rounded-xl border ${c.border} p-5 animate-pulse`}>
        <div className="flex items-center gap-3 mb-4">
          <div className={`p-2 rounded-lg ${c.icon} text-xl`}>{datasource.icon}</div>
          <div className="flex-1">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-24 mb-1" />
            <div className="h-3 bg-gray-100 dark:bg-gray-800 rounded w-40" />
          </div>
        </div>
        <div className="h-20 bg-gray-100 dark:bg-gray-800 rounded-lg" />
      </div>
    )
  }

  if (connectedSource && !changingSource) {
    const srcIcon = sourceTypeIcon(connectedSource.source_type)
    const timeStr = relativeTime(connectedSource.last_imported_at)
    return (
      <div className={`bg-white dark:bg-gray-900 rounded-xl border ${c.border} p-5`}>
        <div className="flex items-center gap-3 mb-4">
          <div className={`p-2 rounded-lg ${c.icon} text-xl`}>{datasource.icon}</div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">{dsLabel}</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">{dsDesc}</p>
          </div>
          <span className="text-xs font-medium text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 px-2 py-1 rounded-full whitespace-nowrap flex-shrink-0">
            ✓ Conectado
          </span>
        </div>

        <div className={`p-3 rounded-lg ${c.bg} border ${c.border}`}>
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-base flex-shrink-0">{srcIcon}</span>
            <span className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate flex-1">
              {connectedSource.source_name || dsLabel}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
            {connectedSource.last_import_count != null && (
              <span>{connectedSource.last_import_count.toLocaleString()} registros</span>
            )}
            {timeStr && <span>· {timeStr}</span>}
          </div>
        </div>

        {hasPending && (
          <div className="mt-3 p-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-medium text-amber-800 dark:text-amber-300">Auto-sync pausado</p>
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                Haz clic para reactivar el seguimiento automático de cambios
              </p>
            </div>
            <button
              onClick={() => grantPermission(datasource.id)}
              className="px-3 py-1.5 text-xs font-medium bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors cursor-pointer whitespace-nowrap flex-shrink-0"
            >
              Reactivar
            </button>
          </div>
        )}

        {isSyncing && !hasPending && (
          <div className="mt-2 flex items-center gap-2 text-xs text-blue-600 dark:text-blue-400">
            <Spinner />Sincronizando...
          </div>
        )}

        <div className="flex gap-2 mt-4">
          <button
            onClick={() => { setChangingSource(true); setResult(null) }}
            className="flex-1 py-2 rounded-lg text-sm font-medium border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer"
          >
            Cambiar fuente
          </button>
          <button
            onClick={handleDisconnect}
            className="flex-1 py-2 rounded-lg text-sm font-medium border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950 transition-colors cursor-pointer"
          >
            Desconectar
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={`bg-white dark:bg-gray-900 rounded-xl border ${c.border} p-5`}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className={`p-2 rounded-lg ${c.icon} text-xl`}>{datasource.icon}</div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">{dsLabel}</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">{dsDesc}</p>
        </div>
        {changingSource && (
          <button onClick={() => setChangingSource(false)} className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 flex-shrink-0 cursor-pointer">
            ← Volver
          </button>
        )}
      </div>
      {changingSource && (
        <div className="mb-4 p-3 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 text-xs text-blue-700 dark:text-blue-300">
          Los datos actuales se mantienen hasta completar la nueva carga.
        </div>
      )}

      {/* Source type selector */}
      {!isMapping && (
        <div className="flex gap-1 mb-4 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
          {SOURCE_TYPES.map(type => (
            <button
              key={type}
              onClick={() => switchSourceType(type)}
              className={`flex-1 py-1.5 px-2 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                sourceType === type
                  ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
            >
              {type === 'csv' ? '📄 CSV'
               : type === 'excel' ? '📊 Excel'
               : '🌐 Sheets'}
            </button>
          ))}
        </div>
      )}

      {/* Mapping UI */}
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

        /* ── CSV ── */
        sourceType === 'csv' ? (
          <CSVDropZone
            file={file}
            dragging={dragging}
            isAnalyzing={isAnalyzing}
            hasConfirmedMapping={hasConfirmedMapping}
            c={c}
            t={t}
            inputRef={inputRef}
            onFile={handleCSVFile}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onClear={() => { setFile(null); setConfirmedMapping(null); setMapResponse(null) }}
            onEditMapping={() => setStep('mapping')}
            onUpload={handleUpload}
            uploading={uploading}
            canUpload={canUpload}
          />
        ) :

        /* ── Excel ── */
        sourceType === 'excel' ? (
          <ExcelDropZone
            file={file}
            dragging={dragging}
            isAnalyzing={isAnalyzing}
            sheets={sheets}
            selectedSheet={selectedSheet}
            hasConfirmedMapping={hasConfirmedMapping}
            c={c}
            t={t}
            inputRef={inputRef}
            onFile={handleExcelFile}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onClear={() => { setFile(null); setSheets([]); setSelectedSheet(''); setConfirmedMapping(null); setMapResponse(null) }}
            onSheetChange={handleExcelSheetSelect}
            onEditMapping={() => setStep('mapping')}
            onUpload={handleUpload}
            uploading={uploading}
            canUpload={canUpload}
          />
        ) :

        /* ── Google Sheets ── */
        (
          <GoogleSheetsForm
            url={gsUrl}
            onUrlChange={setGsUrl}
            connecting={gsConnecting}
            error={gsError}
            sheets={gsSheets}
            selectedSheet={gsSelectedSheet}
            spreadsheetTitle={gsSpreadsheetTitle}
            hasConfirmedMapping={hasConfirmedMapping}
            isAnalyzing={isAnalyzing}
            t={t}
            onConnect={handleGSConnect}
            onSheetChange={handleGSSheetSelect}
            onEditMapping={() => setStep('mapping')}
            onUpload={handleUpload}
            uploading={uploading}
            canUpload={canUpload}
          />
        )
      )}

      {/* Permiso requerido — handle restaurado de sesión anterior */}
      {hasPending && !isMapping && (
        <div className="mt-3 p-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-medium text-amber-800 dark:text-amber-300 truncate">
              🔄 Auto-sync guardado: <span className="font-mono">{pendingName}</span>
            </p>
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
              Haz clic para reactivar el seguimiento sin volver a subir el archivo
            </p>
          </div>
          <button
            onClick={() => grantPermission(datasource.id)}
            className="px-3 py-1.5 text-xs font-medium bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-colors cursor-pointer whitespace-nowrap flex-shrink-0"
          >
            Reactivar
          </button>
        </div>
      )}

      {/* Auto-sync activo — visible mientras el handle está registrado */}
      {isWatching && !hasPending && !isMapping && (
        <div className="mt-2 flex items-center gap-2">
          {isSyncing ? (
            <>
              <Spinner />
              <span className="text-xs text-blue-600 dark:text-blue-400">Sincronizando...</span>
            </>
          ) : (
            <span className="text-xs text-green-600 dark:text-green-400">🔄 Auto-sync activo — detecta cambios automáticamente</span>
          )}
        </div>
      )}

      {/* Resultado */}
      {result && !isMapping && (
        <div className={`mt-3 p-3 rounded-lg text-sm ${
          result.type === 'success'
            ? 'bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-400'
            : 'bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-400'
        }`}>
          <p className="font-medium">{result.type === 'success' ? '✓' : '✗'} {result.message}</p>
          {result.type === 'success' && result.fileName && (
            <p className="text-xs mt-0.5 opacity-70 font-mono truncate">{result.fileName}</p>
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

// ── Sub-components ─────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function UploadButton({ canUpload, uploading, t, onUpload }) {
  return (
    <button
      onClick={onUpload}
      disabled={!canUpload || uploading}
      className={`w-full py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer flex items-center justify-center gap-2 ${
        !canUpload || uploading
          ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed'
          : 'bg-blue-600 text-white hover:bg-blue-700'
      }`}
    >
      {uploading && <Spinner />}
      {uploading ? t('config.upload.cargando') : t('config.upload.subirCSV')}
    </button>
  )
}

function CSVDropZone({ file, dragging, isAnalyzing, hasConfirmedMapping, c, t, inputRef, onFile, onDragOver, onDragLeave, onClear, onEditMapping, onUpload, uploading, canUpload }) {
  async function handleDrop(e) {
    e.preventDefault()
    onDragLeave()
    const item = e.dataTransfer.items?.[0]
    let handle = null
    if (item?.getAsFileSystemHandle) {
      try { handle = await item.getAsFileSystemHandle() } catch {}
    }
    const f = e.dataTransfer.files[0]
    if (f) onFile(f, handle)
  }

  async function handleBrowse() {
    if (isAnalyzing) return
    if (window.showOpenFilePicker) {
      try {
        const [h] = await window.showOpenFilePicker({
          types: [{ description: 'CSV files', accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'] } }],
          multiple: false,
        })
        const f = await h.getFile()
        onFile(f, h)
      } catch { /* user cancelled */ }
    } else {
      inputRef.current?.click()
    }
  }

  return (
    <>
      <div
        onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={handleDrop}
        onClick={handleBrowse}
        className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
          isAnalyzing ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 cursor-wait'
          : dragging ? 'border-blue-400 dark:border-blue-600 bg-blue-50 dark:bg-blue-950 cursor-pointer'
          : file ? 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 cursor-pointer'
          : `border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 ${c.hover} cursor-pointer`
        }`}
      >
        <input ref={inputRef} type="file" accept=".csv" className="hidden"
          onChange={(e) => { onFile(e.target.files[0], null); e.target.value = '' }} />
        {isAnalyzing ? (
          <div className="flex items-center justify-center gap-2 text-sm text-blue-600 dark:text-blue-400">
            <Spinner />{t('config.upload.analizando')}
          </div>
        ) : file ? (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <span className="text-lg">📄</span>
            <span className="font-medium truncate max-w-48">{file.name}</span>
            {hasConfirmedMapping && (
              <span className="text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full">{t('config.upload.mapeoListo')}</span>
            )}
            <button onClick={(e) => { e.stopPropagation(); onClear() }} className="text-gray-400 hover:text-red-500 ml-1 cursor-pointer">✕</button>
          </div>
        ) : (
          <p className="text-sm text-gray-400 dark:text-gray-500">
            {t('config.upload.arrastraCSV')} <span className="text-blue-500 dark:text-blue-400 underline">{t('config.upload.seleccionaArchivo')}</span>
          </p>
        )}
      </div>
      {file && !isAnalyzing && (
        <div className="mt-3 space-y-2">
          {hasConfirmedMapping && (
            <button onClick={onEditMapping} className="text-xs text-blue-600 dark:text-blue-400 hover:underline cursor-pointer">
              {t('config.upload.editarMapeo')}
            </button>
          )}
          <UploadButton canUpload={canUpload} uploading={uploading} t={t} onUpload={onUpload} />
        </div>
      )}
    </>
  )
}

function ExcelDropZone({ file, dragging, isAnalyzing, sheets, selectedSheet, hasConfirmedMapping, c, t, inputRef, onFile, onDragOver, onDragLeave, onClear, onSheetChange, onEditMapping, onUpload, uploading, canUpload }) {
  async function handleDrop(e) {
    e.preventDefault()
    onDragLeave()
    const item = e.dataTransfer.items?.[0]
    let handle = null
    if (item?.getAsFileSystemHandle) {
      try { handle = await item.getAsFileSystemHandle() } catch {}
    }
    const f = e.dataTransfer.files[0]
    if (f) onFile(f, handle)
  }

  async function handleBrowse() {
    if (isAnalyzing || file) return
    if (window.showOpenFilePicker) {
      try {
        const [h] = await window.showOpenFilePicker({
          types: [{
            description: 'Excel files',
            accept: {
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
              'application/vnd.ms-excel': ['.xls', '.xlsm'],
            },
          }],
          multiple: false,
        })
        const f = await h.getFile()
        onFile(f, h)
      } catch { /* user cancelled */ }
    } else {
      inputRef.current?.click()
    }
  }

  return (
    <>
      <div
        onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={handleDrop}
        onClick={handleBrowse}
        className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
          isAnalyzing ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 cursor-wait'
          : dragging ? 'border-blue-400 cursor-pointer bg-blue-50 dark:bg-blue-950'
          : file ? 'border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-800'
          : `border-gray-200 dark:border-gray-600 ${c.hover} cursor-pointer bg-white dark:bg-gray-800`
        }`}
      >
        <input ref={inputRef} type="file" accept=".xlsx,.xls,.xlsm" className="hidden"
          onChange={(e) => { onFile(e.target.files[0], null); e.target.value = '' }} />
        {isAnalyzing ? (
          <div className="flex items-center justify-center gap-2 text-sm text-blue-600 dark:text-blue-400">
            <Spinner />{t('config.upload.buscandoHojas')}
          </div>
        ) : file ? (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <span className="text-lg">📊</span>
            <span className="font-medium truncate max-w-48">{file.name}</span>
            <button onClick={(e) => { e.stopPropagation(); onClear() }} className="text-gray-400 hover:text-red-500 cursor-pointer">✕</button>
          </div>
        ) : (
          <p className="text-sm text-gray-400 dark:text-gray-500">
            {t('config.upload.arrastraExcel')} <span className="text-blue-500 dark:text-blue-400 underline">{t('config.upload.seleccionaArchivo')}</span>
          </p>
        )}
      </div>

      {/* Sheet selector */}
      {file && sheets.length > 0 && (
        <div className="mt-3">
          <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{t('config.upload.seleccionaHoja')}</label>
          <select
            value={selectedSheet}
            onChange={(e) => onSheetChange(e.target.value)}
            className="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer"
          >
            {sheets.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      )}

      {selectedSheet && !isAnalyzing && (
        <div className="mt-3 space-y-2">
          {hasConfirmedMapping && (
            <button onClick={onEditMapping} className="text-xs text-blue-600 dark:text-blue-400 hover:underline cursor-pointer">
              {t('config.upload.editarMapeo')}
            </button>
          )}
          <UploadButton canUpload={canUpload} uploading={uploading} t={t} onUpload={onUpload} />
        </div>
      )}
    </>
  )
}

function GoogleSheetsForm({ url, onUrlChange, connecting, error, sheets, selectedSheet, spreadsheetTitle, hasConfirmedMapping, isAnalyzing, t, onConnect, onSheetChange, onEditMapping, onUpload, uploading, canUpload }) {
  const connected = sheets.length > 0

  return (
    <div className="space-y-3">
      {/* URL input + Connect */}
      <div>
        <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
          {t('config.upload.urlGSheets')}
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={url}
            onChange={(e) => onUrlChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onConnect()}
            placeholder={t('config.upload.urlGSheetsPlaceholder')}
            className="flex-1 text-xs border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400 min-w-0"
          />
          <button
            onClick={onConnect}
            disabled={connecting || !url.trim()}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors cursor-pointer ${
              connecting || !url.trim()
                ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {connecting && <Spinner />}
            {connecting ? t('config.upload.conectando') : t('config.upload.conectar')}
          </button>
        </div>
        {error && <p className="text-xs text-red-500 dark:text-red-400 mt-1">{error}</p>}
      </div>

      {/* Connected state */}
      {connected && (
        <>
          <div className="flex items-center gap-2 p-2 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg">
            <span className="text-green-600 dark:text-green-400 text-sm">✓</span>
            <span className="text-xs text-green-700 dark:text-green-400 font-medium truncate">
              {spreadsheetTitle || t('config.upload.gsheetConectado')}
            </span>
          </div>

          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{t('config.upload.seleccionaHoja')}</label>
            <select
              value={selectedSheet}
              onChange={(e) => onSheetChange(e.target.value)}
              className="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-400 cursor-pointer"
            >
              {sheets.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {isAnalyzing && (
            <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
              <Spinner />{t('config.upload.analizando')}
            </div>
          )}

          {selectedSheet && !isAnalyzing && (
            <div className="space-y-2">
              {hasConfirmedMapping && (
                <button onClick={onEditMapping} className="text-xs text-blue-600 dark:text-blue-400 hover:underline cursor-pointer">
                  {t('config.upload.editarMapeo')}
                </button>
              )}
              <UploadButton canUpload={canUpload} uploading={uploading} t={t} onUpload={onUpload} />
            </div>
          )}
        </>
      )}

      {/* Hint when not connected */}
      {!connected && !connecting && !error && (
        <p className="text-xs text-gray-400 dark:text-gray-500">
          {t('config.upload.sinApiKey')}
        </p>
      )}
    </div>
  )
}

// ── AlertasSection (configuración de reglas) ─────────────────────────────────

function AlertasSection() {
  const { t } = useLanguage()
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
        setError(t('common.errorConexionMsg'))
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
      let desc = r._descTemplate || r.description
      for (const pd of r.params_def) {
        const val = pd.key === key ? num : (newParams[pd.key] ?? pd.default)
        desc = desc.replaceAll(`{${pd.key}}`, String(val))
      }
      return { ...r, params: newParams, description: desc }
    }))

    const rule = rules.find(r => r.rule_id === ruleId)
    if (rule) {
      const fullParams = { ...rule.params, [key]: num }
      saveParams(ruleId, fullParams)
    }
  }

  useEffect(() => {
    if (rules.length > 0 && !rules[0]._descTemplate) {
      setRules(prev => prev.map(r => {
        let template = r.description
        for (const pd of (r.params_def || [])) {
          const val = r.params?.[pd.key] ?? pd.default
          template = template.replaceAll(String(val), `{${pd.key}}`)
        }
        return { ...r, _descTemplate: template }
      }))
    }
  }, [rules.length])

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
      setDetectResult({ type: 'success', message: res.data?.message || 'OK' })
    } catch {
      setDetectResult({ type: 'error', message: t('common.error') })
    } finally {
      setDetecting(false)
    }
  }

  return (
    <div>
      <div className="mb-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">{t('config.alertas.title')}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              {t('config.alertas.description')}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
              {t('config.alertas.reglasActivas', { enabled: enabledCount, total: rules.length })}
            </p>
          </div>
          <button
            onClick={handleDetectar}
            disabled={detecting}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer whitespace-nowrap ${
              detecting
                ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {detecting ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {t('config.alertas.detectando')}
              </>
            ) : (
              t('config.alertas.detectar')
            )}
          </button>
        </div>
        {detectResult && (
          <div className={`mt-3 p-3 rounded-lg text-sm ${
            detectResult.type === 'success'
              ? 'bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400'
              : 'bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400'
          }`}>
            {detectResult.message}
          </div>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 text-sm mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-16 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([tipo, tipoRules]) => {
            const group = TIPO_GROUP[tipo] || { icon: '📋', color: 'gray' }
            const groupLabel = t(`config.datasources.${tipo}.label`) || tipo
            return (
              <div key={tipo}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-lg">{group.icon}</span>
                  <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{groupLabel}</h4>
                </div>
                <div className="space-y-2">
                  {tipoRules.map(rule => (
                    <div
                      key={rule.rule_id}
                      className={`p-4 rounded-xl border transition-colors ${
                        rule.enabled
                          ? 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700'
                          : 'bg-gray-50 dark:bg-gray-800 border-gray-100 dark:border-gray-700 opacity-60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{rule.label}</p>
                            <span className={`text-xs px-2 py-0.5 rounded-full ${NIVEL_BADGE[rule.nivel] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}`}>
                              {rule.nivel === 'critical' ? t('config.alertas.critica') : t('config.alertas.aviso')}
                            </span>
                          </div>
                          <p className="text-xs text-gray-500 dark:text-gray-400">{rule.description}</p>
                        </div>
                        <button
                          onClick={() => handleToggle(rule.rule_id, rule.enabled)}
                          className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                            rule.enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600'
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

                      {rule.enabled && rule.params_def?.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700 flex flex-wrap gap-4">
                          {rule.params_def.map(pd => (
                            <label key={pd.key} className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
                              <span>{pd.label}:</span>
                              <span className="flex items-center gap-1">
                                {pd.prefix && <span className="text-gray-400 dark:text-gray-500">{pd.prefix}</span>}
                                <input
                                  type="number"
                                  min={pd.min}
                                  max={pd.max}
                                  step={pd.key === 'multiplicador' ? 0.5 : 1}
                                  value={rule.params?.[pd.key] ?? pd.default}
                                  onChange={e => handleParamChange(rule.rule_id, pd.key, e.target.value, pd)}
                                  className="w-16 px-2 py-1 text-xs text-center border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-400 focus:border-blue-400"
                                />
                                {pd.suffix && <span className="text-gray-400 dark:text-gray-500">{pd.suffix}</span>}
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

// ── Language Section ───────────────────────────────────────────────────────────

const LANGUAGES = [
  { id: 'es', flag: '🇪🇸', label: 'Español', desc: 'Interfaz en español' },
  { id: 'en', flag: '🇺🇸', label: 'English', desc: 'English interface' },
]

function LanguageSection() {
  const { lang, setLang, t } = useLanguage()

  return (
    <div>
      <div className="mb-5">
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">{t('config.language.title')}</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{t('config.language.description')}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg">
        {LANGUAGES.map((l) => (
          <button
            key={l.id}
            onClick={() => setLang(l.id)}
            className={`flex items-center gap-3 p-4 rounded-xl border-2 transition-colors cursor-pointer text-left ${
              lang === l.id
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-950 dark:border-blue-400'
                : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
          >
            <span className="text-3xl">{l.flag}</span>
            <div>
              <p className={`text-sm font-semibold ${lang === l.id ? 'text-blue-700 dark:text-blue-300' : 'text-gray-900 dark:text-gray-100'}`}>{l.label}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">{l.desc}</p>
            </div>
            {lang === l.id && (
              <span className="ml-auto text-blue-600 dark:text-blue-400">✓</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function Configuracion() {
  const { t } = useLanguage()
  const [activeTab, setActiveTab] = useState('fuentes')

  const TABS = [
    { id: 'fuentes', label: t('config.tabs.fuentes'), icon: '📂' },
    { id: 'alertas', label: t('config.tabs.alertas'), icon: '🔔' },
    { id: 'idioma',  label: t('config.tabs.idioma'),  icon: '🌐' },
  ]

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('config.title')}</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{t('config.subtitle')}</p>
      </div>

      {/* Tabs internos */}
      <div className="flex gap-1 mb-6 bg-gray-100 dark:bg-gray-700 p-1 rounded-xl w-fit">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              activeTab === tab.id
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
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
      {activeTab === 'idioma' && <LanguageSection />}
    </div>
  )
}

export default Configuracion
