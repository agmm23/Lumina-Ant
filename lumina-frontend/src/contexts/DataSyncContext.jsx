/**
 * DataSyncContext — auto-sincronización de archivos locales (CSV / Excel).
 *
 * Cuando el usuario sube un archivo y el navegador proporciona un
 * FileSystemFileHandle (File System Access API, Chrome/Edge 86+), este
 * contexto lo almacena, lo persiste en IndexedDB y pollea cada 5 s.
 * Si detecta que el archivo cambió (lastModified distinto), re-sube
 * automáticamente usando el mismo mapeo de columnas confirmado.
 *
 * Al recargar la página o abrir el navegador de nuevo, los handles guardados
 * en IndexedDB se restauran:
 *   - Si el permiso sigue activo  → reanuda el polling sin intervención.
 *   - Si el permiso expiró        → expone pendingHandles para que el componente
 *                                   muestre un botón "Reactivar auto-sync".
 *
 * Limitación: funciona dentro del mismo navegador/perfil. No sincroniza entre
 * navegadores distintos porque el FileSystemFileHandle no expone la ruta absoluta.
 */
import { createContext, useContext, useRef, useState, useEffect } from 'react'
import { ventasService, gastosService, inventarioService, clientesService, watcherService } from '../services/api'

const DataSyncCtx = createContext(null)

const POLL_MS  = 5000
const DB_NAME  = 'lumina_datasync'
const DB_STORE = 'watches'

/** Función de upload reconstruible desde el datasource ID al restaurar de IDB. */
const UPLOAD_FN_MAP = {
  ventas:     (f, m, s) => ventasService.uploadCSV(f, m, s),
  gastos:     (f, m, s) => gastosService.uploadCSV(f, m, s),
  inventario: (f, m, s) => inventarioService.uploadCSV(f, m, s),
  clientes:   (f, m, s) => clientesService.uploadCSV(f, m, s),
}

// ── IndexedDB helpers ──────────────────────────────────────────────────────────

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = (e) => { e.target.result.createObjectStore(DB_STORE) }
    req.onsuccess = (e) => resolve(e.target.result)
    req.onerror   = (e) => reject(e.target.error)
  })
}

async function idbSet(key, value) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite')
    tx.objectStore(DB_STORE).put(value, key)
    tx.oncomplete = resolve
    tx.onerror    = () => reject(tx.error)
  })
}

async function idbDelete(key) {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(DB_STORE, 'readwrite')
    tx.objectStore(DB_STORE).delete(key)
    tx.oncomplete = resolve
    tx.onerror    = () => reject(tx.error)
  })
}

async function idbGetAll() {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx    = db.transaction(DB_STORE, 'readonly')
    const store = tx.objectStore(DB_STORE)
    const items = []
    store.openCursor().onsuccess = (e) => {
      const cursor = e.target.result
      if (cursor) { items.push({ key: cursor.key, value: cursor.value }); cursor.continue() }
      else resolve(items)
    }
    tx.onerror = () => reject(tx.error)
  })
}

// ── Provider ──────────────────────────────────────────────────────────────────

const WATCHER_POLL_MS = 10000

export function DataSyncProvider({ children }) {
  // Active watches: { [datasourceId]: { handle, confirmedMapping, sheet, uploadFn } }
  const watchesRef = useRef({})
  const lastModRef = useRef({})   // datasourceId → lastModified (number | null)

  // Estado visible a componentes
  const [syncStatus,     setSyncStatus]     = useState({}) // id → 'idle' | 'syncing'
  // Handles restaurados de IDB que necesitan que el usuario re-conceda permiso
  // { [datasourceId]: { handle, confirmedMapping, sheet, fileName } }
  const [pendingHandles, setPendingHandles] = useState({})

  // Versión del backend para detectar imports nuevos (Google Sheets, watcher loop)
  const watcherVersionRef = useRef(null)
  const [importVersion,   setImportVersion] = useState(null)

  // ── Restaurar handles de IndexedDB al montar ─────────────────────────────

  useEffect(() => {
    let mounted = true

    async function restore() {
      try {
        const saved = await idbGetAll()
        for (const { key: id, value: stored } of saved) {
          if (!stored?.handle) continue
          try {
            const state = await stored.handle.queryPermission({ mode: 'read' })
            if (!mounted) break

            if (state === 'granted') {
              // Permiso vigente → reanudar el polling automáticamente
              const uploadFn = UPLOAD_FN_MAP[id]
              if (!uploadFn) continue
              watchesRef.current[id] = {
                handle:           stored.handle,
                confirmedMapping: stored.confirmedMapping,
                sheet:            stored.sheet,
                uploadFn,
              }
              lastModRef.current[id] = null
              setSyncStatus(s => ({ ...s, [id]: 'idle' }))
            } else if (state === 'prompt') {
              // El navegador necesita un gesto del usuario para requestPermission
              setPendingHandles(p => ({
                ...p,
                [id]: {
                  handle:           stored.handle,
                  confirmedMapping: stored.confirmedMapping,
                  sheet:            stored.sheet,
                  fileName:         stored.handle.name,
                },
              }))
            } else {
              // 'denied' → limpiar de IDB
              await idbDelete(id)
            }
          } catch {
            await idbDelete(id)
          }
        }
      } catch { /* IDB no disponible (modo privado, versión muy antigua del navegador) */ }
    }

    restore()
    return () => { mounted = false }
  }, [])

  // ── Registrar watch nuevo (llamado tras upload exitoso) ───────────────────

  function registerWatch(datasourceId, { handle, confirmedMapping, sheet, uploadFn }) {
    watchesRef.current[datasourceId] = { handle, confirmedMapping, sheet, uploadFn }
    lastModRef.current[datasourceId] = null
    setSyncStatus(s => ({ ...s, [datasourceId]: 'idle' }))
    // Si estaba en pendientes por un restore previo, quitarlo
    setPendingHandles(p => { const n = { ...p }; delete n[datasourceId]; return n })
    // Persistir en IndexedDB (FileSystemFileHandle es serializable nativamente)
    if (handle) {
      idbSet(datasourceId, { handle, confirmedMapping, sheet }).catch(() => {})
    }
  }

  function unregisterWatch(datasourceId) {
    delete watchesRef.current[datasourceId]
    delete lastModRef.current[datasourceId]
    setSyncStatus(s => { const n = { ...s }; delete n[datasourceId]; return n })
    setPendingHandles(p => { const n = { ...p }; delete n[datasourceId]; return n })
    idbDelete(datasourceId).catch(() => {})
  }

  // ── Conceder permiso a un handle pendiente (requiere gesto del usuario) ───

  async function grantPermission(datasourceId) {
    const pending = pendingHandles[datasourceId]
    if (!pending) return
    try {
      const state = await pending.handle.requestPermission({ mode: 'read' })
      if (state === 'granted') {
        const uploadFn = UPLOAD_FN_MAP[datasourceId]
        if (!uploadFn) return
        watchesRef.current[datasourceId] = {
          handle:           pending.handle,
          confirmedMapping: pending.confirmedMapping,
          sheet:            pending.sheet,
          uploadFn,
        }
        lastModRef.current[datasourceId] = null
        setSyncStatus(s => ({ ...s, [datasourceId]: 'idle' }))
        setPendingHandles(p => { const n = { ...p }; delete n[datasourceId]; return n })
        idbSet(datasourceId, {
          handle:           pending.handle,
          confirmedMapping: pending.confirmedMapping,
          sheet:            pending.sheet,
        }).catch(() => {})
      } else {
        // Denegado → limpiar
        setPendingHandles(p => { const n = { ...p }; delete n[datasourceId]; return n })
        idbDelete(datasourceId).catch(() => {})
      }
    } catch { /* Usuario cerró el diálogo */ }
  }

  // ── Watcher status polling (una sola instancia global) ───────────────────

  useEffect(() => {
    let active = true

    async function pollWatcher() {
      if (!active) return
      try {
        const res = await watcherService.getStatus()
        const v = res.data.import_version
        if (watcherVersionRef.current !== null && v !== watcherVersionRef.current) {
          setImportVersion(v)
        }
        watcherVersionRef.current = v
      } catch { /* backend no disponible → silencioso */ }
    }

    pollWatcher()
    const id = setInterval(() => { if (active) pollWatcher() }, WATCHER_POLL_MS)
    return () => { active = false; clearInterval(id) }
  }, [])

  // ── File polling loop ──────────────────────────────────────────────────────

  useEffect(() => {
    let active = true

    async function pollAll() {
      if (!active) return
      const entries = Object.entries(watchesRef.current)
      for (const [id, w] of entries) {
        if (!w?.handle) continue
        try {
          const f   = await w.handle.getFile()
          const mod = f.lastModified
          // Solo re-sube si el archivo cambió DESPUÉS del registro inicial
          if (lastModRef.current[id] !== null && mod !== lastModRef.current[id]) {
            setSyncStatus(s => ({ ...s, [id]: 'syncing' }))
            try {
              await w.uploadFn(f, w.confirmedMapping, w.sheet || undefined)
            } catch {
              // Silencioso — el usuario verá el estado en la UI si algo falla
            }
            setSyncStatus(s => ({ ...s, [id]: 'idle' }))
          }
          lastModRef.current[id] = mod
        } catch {
          // Archivo bloqueado (Excel abierto) o permiso revocado → reintenta
        }
      }
    }

    const id = setInterval(pollAll, POLL_MS)
    return () => { active = false; clearInterval(id) }
  }, [])

  return (
    <DataSyncCtx.Provider value={{ registerWatch, unregisterWatch, syncStatus, pendingHandles, grantPermission, importVersion }}>
      {children}
    </DataSyncCtx.Provider>
  )
}

export function useDataSync() {
  return useContext(DataSyncCtx)
}
