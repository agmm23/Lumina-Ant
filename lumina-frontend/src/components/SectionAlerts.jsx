import { useState, useEffect, useCallback } from 'react'
import { analyticsService } from '../services/api'
import AlertCard from './AlertCard'

/**
 * Muestra alertas no leídas filtradas por tipo (ventas, gastos, inventario).
 * Se puede usar en cualquier página de sección.
 *
 * Props:
 *  - tipo: string ('ventas' | 'gastos' | 'inventario' | 'clientes')
 *  - refreshKey: optional number — cuando cambia, re-fetch alertas
 */
export default function SectionAlerts({ tipo, refreshKey }) {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await analyticsService.getAlerts(10, true, tipo)
      const data = res.data
      setAlerts(Array.isArray(data) ? data : [])
    } catch {
      // silencioso
    } finally {
      setLoading(false)
    }
  }, [tipo])

  useEffect(() => { fetchAlerts() }, [fetchAlerts, refreshKey])

  async function handleMarcarLeida(id) {
    try {
      await analyticsService.marcarLeida(id)
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch {
      // silencioso
    }
  }

  if (loading) return null
  if (alerts.length === 0) return null

  return (
    <section className="mb-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Alertas
      </h3>
      <div className="space-y-2">
        {alerts.map(alert => (
          <AlertCard key={alert.id} alerta={alert} onMarcarLeida={handleMarcarLeida} />
        ))}
      </div>
    </section>
  )
}
