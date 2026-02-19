import { useEffect, useRef } from 'react'
import { watcherService } from '../services/api'

/**
 * Pollea GET /api/watcher/status cada `interval` ms.
 * Cuando `import_version` cambia, llama `onNewData()`.
 */
export default function useWatcherRefresh(onNewData, interval = 10000) {
  const versionRef = useRef(null)

  useEffect(() => {
    let active = true

    async function poll() {
      try {
        const res = await watcherService.getStatus()
        const v = res.data.import_version
        if (versionRef.current !== null && v !== versionRef.current) {
          onNewData()
        }
        versionRef.current = v
      } catch {
        // silencioso — el backend puede no estar corriendo
      }
    }

    poll()
    const id = setInterval(() => { if (active) poll() }, interval)
    return () => { active = false; clearInterval(id) }
  }, [onNewData, interval])
}
