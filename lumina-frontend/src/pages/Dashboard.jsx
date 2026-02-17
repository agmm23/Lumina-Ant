import { useState, useEffect } from 'react'
import { analyticsService, gastosService, inventarioService, clientesService } from '../services/api'
import KpiCard from '../components/KpiCard'
import AlertBadge from '../components/AlertBadge'

function formatCurrency(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 0,
  }).format(value)
}

function Dashboard() {
  const [salesStats, setSalesStats] = useState(null)
  const [gastosStats, setGastosStats] = useState(null)
  const [inventarioStats, setInventarioStats] = useState(null)
  const [clientesStats, setClientesStats] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true)
        setError(null)

        const [salesRes, gastosRes, gastosCatRes, invRes, invLowRes, clientesRes, alertsRes] =
          await Promise.allSettled([
            analyticsService.getSalesStats(),       // ventas totales
            gastosService.getCount(),               // { total_gastos }
            gastosService.getPorCategoria(),         // [{ categoria, total, cantidad }]
            inventarioService.getCount(),            // { total_items }
            inventarioService.getLowStock(),         // lista bajo stock
            clientesService.getCount(),              // { total_clientes, clientes_activos }
            analyticsService.getAlerts(5),           // alertas
          ])

        if (salesRes.status === 'fulfilled') setSalesStats(salesRes.value.data)
        if (gastosRes.status === 'fulfilled') setGastosStats(gastosRes.value.data)

        // Calcular total de gastos sumando por categoría
        // El endpoint devuelve { status: "success", data: [{ categoria, total, cantidad }] }
        if (gastosCatRes.status === 'fulfilled') {
          const categorias = gastosCatRes.value.data?.data || []
          const total = Array.isArray(categorias)
            ? categorias.reduce((acc, cat) => acc + (cat.total || 0), 0)
            : 0
          setGastosStats(prev => ({ ...prev, monto_total: total }))
        }

        if (invRes.status === 'fulfilled') {
          const invData = invRes.value.data
          setInventarioStats(invData)
        }
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

        // Si TODAS fallaron, mostrar error de conexión
        const allFailed = [salesRes, gastosRes, invRes, clientesRes].every(
          r => r.status === 'rejected'
        )
        if (allFailed) {
          setError('No se pudo conectar con la API. Asegúrate de que el servidor esté corriendo.')
        }
      } catch (err) {
        setError('Error inesperado al cargar los datos.')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  return (
    <div className="p-6 max-w-6xl">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-sm text-gray-500 mt-0.5">Resumen general del negocio</p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          <p className="font-medium">Error de conexión</p>
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
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Alertas recientes
        </h3>
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-gray-100 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : alerts.length === 0 ? (
          <div className="p-4 bg-gray-50 rounded-xl border border-gray-200 text-sm text-gray-500">
            Sin alertas activas. ¡Todo en orden!
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map((alert, i) => (
              <AlertBadge key={alert.id ?? i} alert={alert} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export default Dashboard
