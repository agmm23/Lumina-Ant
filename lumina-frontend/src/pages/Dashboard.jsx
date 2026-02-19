import { useState, useEffect, useCallback } from 'react'
import { analyticsService, gastosService, inventarioService, clientesService } from '../services/api'
import KpiCard from '../components/KpiCard'
import AlertCard from '../components/AlertCard'
import useWatcherRefresh from '../hooks/useWatcherRefresh'

function formatCurrency(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 0,
  }).format(value)
}

const ALERT_FILTERS = [
  { id: 'todas',    label: 'Todas' },
  { id: 'critical', label: 'Cr\u00edticas' },
  { id: 'warning',  label: 'Avisos' },
]

function Dashboard() {
  const [salesStats, setSalesStats] = useState(null)
  const [gastosStats, setGastosStats] = useState(null)
  const [inventarioStats, setInventarioStats] = useState(null)
  const [clientesStats, setClientesStats] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [alertFilter, setAlertFilter] = useState('todas')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const [salesRes, gastosRes, gastosCatRes, invRes, invLowRes, clientesRes, alertsRes] =
        await Promise.allSettled([
          analyticsService.getSalesStats(),
          gastosService.getCount(),
          gastosService.getPorCategoria(),
          inventarioService.getCount(),
          inventarioService.getLowStock(),
          clientesService.getCount(),
          analyticsService.getAlerts(10, true),
        ])

      if (salesRes.status === 'fulfilled') setSalesStats(salesRes.value.data)
      if (gastosRes.status === 'fulfilled') setGastosStats(gastosRes.value.data)

      if (gastosCatRes.status === 'fulfilled') {
        const categorias = gastosCatRes.value.data?.data || []
        const total = Array.isArray(categorias)
          ? categorias.reduce((acc, cat) => acc + (cat.total || 0), 0)
          : 0
        setGastosStats(prev => ({ ...prev, monto_total: total }))
      }

      if (invRes.status === 'fulfilled') setInventarioStats(invRes.value.data)
      if (invLowRes.status === 'fulfilled') {
        const lowStockData = invLowRes.value.data
        const count = Array.isArray(lowStockData)
          ? lowStockData.length
          : (lowStockData?.total_bajo_stock ?? 0)
        setInventarioStats(prev => ({ ...prev, bajo_stock: count }))
      }

      if (clientesRes.status === 'fulfilled') setClientesStats(clientesRes.value.data)

      if (alertsRes.status === 'fulfilled') {
        const data = alertsRes.value.data
        setAlerts(Array.isArray(data) ? data : data?.alertas || [])
      }

      const allFailed = [salesRes, gastosRes, invRes, clientesRes].every(
        r => r.status === 'rejected'
      )
      if (allFailed) {
        setError('No se pudo conectar con la API. Aseg\u00farate de que el servidor est\u00e9 corriendo.')
      }
    } catch (err) {
      setError('Error inesperado al cargar los datos.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  // Auto-refresh cuando el watcher detecta datos nuevos
  useWatcherRefresh(fetchData)

  async function handleMarcarLeida(id) {
    try {
      await analyticsService.marcarLeida(id)
      setAlerts(prev => prev.filter(a => a.id !== id))
    } catch {
      // silencioso
    }
  }

  async function handleMarcarTodasLeidas() {
    const ids = alerts.filter(a => !a.leida).map(a => a.id)
    await Promise.allSettled(ids.map(id => analyticsService.marcarLeida(id)))
    setAlerts([])
  }

  const filteredAlerts = alerts.filter(a => {
    if (alertFilter === 'critical') return a.nivel === 'critical'
    if (alertFilter === 'warning') return a.nivel === 'warning'
    return true
  })

  const noLeidasCount = alerts.filter(a => !a.leida).length

  return (
    <div className="p-6 max-w-6xl">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-sm text-gray-500 mt-0.5">Resumen general del negocio</p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          <p className="font-medium">Error de conexi&oacute;n</p>
          <p className="mt-0.5 text-red-600">{error}</p>
          <p className="mt-2 text-xs text-red-500">
            Inicia el backend: <code className="bg-red-100 px-1 rounded">cd backend &amp;&amp; uvicorn app.main:app --reload</code>
          </p>
        </div>
      )}

      {/* KPIs — Ventas */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Ventas</h3>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard
            title="Ventas totales"
            value={formatCurrency(salesStats?.total_ventas)}
            subtitle={`${salesStats?.cantidad_transacciones ?? '—'} transacciones`}
            icon="💰"
            color="green"
            loading={loading}
          />
          <KpiCard
            title="Ticket promedio"
            value={formatCurrency(salesStats?.ticket_promedio)}
            icon="🧾"
            color="blue"
            loading={loading}
          />
          <KpiCard
            title="Top producto"
            value={salesStats?.producto_mas_vendido ?? '—'}
            subtitle={salesStats?.categoria_principal ?? ''}
            icon="⭐"
            color="purple"
            loading={loading}
          />
          <KpiCard
            title="Clientes activos"
            value={clientesStats?.clientes_activos ?? '—'}
            subtitle={`${clientesStats?.total_clientes ?? '—'} registrados`}
            icon="👥"
            color="blue"
            loading={loading}
          />
        </div>
      </section>

      {/* KPIs — Gastos e Inventario */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Gastos e Inventario</h3>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard
            title="Gastos totales"
            value={formatCurrency(gastosStats?.monto_total)}
            subtitle={`${gastosStats?.total_gastos ?? '—'} registros`}
            icon="💸"
            color="red"
            loading={loading}
          />
          <KpiCard
            title="Margen estimado"
            value={
              salesStats?.total_ventas && gastosStats?.monto_total
                ? formatCurrency(salesStats.total_ventas - gastosStats.monto_total)
                : '—'
            }
            subtitle="ventas − gastos"
            icon="📈"
            color="green"
            loading={loading}
          />
          <KpiCard
            title="Productos en stock"
            value={inventarioStats?.total_items ?? '—'}
            icon="🏬"
            color="blue"
            loading={loading}
          />
          <KpiCard
            title="Stock bajo"
            value={inventarioStats?.bajo_stock ?? '—'}
            subtitle="requieren reposición"
            icon="⚠️"
            color="yellow"
            loading={loading}
          />
        </div>
      </section>

      {/* Alertas */}
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Alertas {noLeidasCount > 0 && <span className="text-xs bg-red-500 text-white rounded-full px-1.5 py-0.5 ml-1.5 normal-case">{noLeidasCount}</span>}
          </h3>
          <div className="flex items-center gap-2">
            {/* Filtros */}
            <div className="flex gap-1">
              {ALERT_FILTERS.map(f => (
                <button
                  key={f.id}
                  onClick={() => setAlertFilter(f.id)}
                  className={`text-xs px-2.5 py-1 rounded-lg border transition-colors cursor-pointer ${
                    alertFilter === f.id
                      ? 'bg-gray-800 text-white border-gray-800'
                      : 'bg-white text-gray-500 border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            {noLeidasCount > 1 && (
              <button
                onClick={handleMarcarTodasLeidas}
                className="text-xs text-gray-500 hover:text-gray-800 border border-gray-200 bg-white rounded-lg px-2.5 py-1 transition-colors cursor-pointer"
              >
                Marcar todas le\u00eddas
              </button>
            )}
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div className="p-4 bg-gray-50 rounded-xl border border-gray-200 text-sm text-gray-500">
            {alertFilter === 'todas'
              ? 'Sin alertas activas. \u00a1Todo en orden!'
              : 'No hay alertas en este filtro.'}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredAlerts.map((alert) => (
              <AlertCard key={alert.id} alerta={alert} onMarcarLeida={handleMarcarLeida} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export default Dashboard
