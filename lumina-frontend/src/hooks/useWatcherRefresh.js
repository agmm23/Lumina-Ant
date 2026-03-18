import { useEffect, useRef } from 'react'
import { useDataSync } from '../contexts/DataSyncContext'

/**
 * Llama a `onNewData()` cuando el backend registra un import nuevo.
 * El polling HTTP se centraliza en DataSyncContext (una sola instancia).
 */
export default function useWatcherRefresh(onNewData) {
  const { importVersion } = useDataSync()
  const prevRef = useRef(importVersion)

  useEffect(() => {
    if (prevRef.current !== null && prevRef.current !== importVersion && importVersion !== null) {
      onNewData()
    }
    prevRef.current = importVersion
  }, [importVersion, onNewData])
}
