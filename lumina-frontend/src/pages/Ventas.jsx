import { useState, useEffect, useCallback } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { ventasService } from '../services/api'
import useWatcherRefresh from '../hooks/useWatcherRefresh'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCurrency(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('es-MX', {
    style: 'currency', currency: 'MXN', maximumFractionDigits: 0,
  }).format(value)
}

function fmtDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: '2-digit' })
}

function fmtShortDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short' })
}

function fmtWeek(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  const end = new Date(d)
  end.setDate(d.getDate() + 6)
  const fmt = (dt) => dt.toLocaleDateString('es-MX', { day: '2-digit', month: 'short' })
  return `${fmt(d)} – ${fmt(end)}`
}

function fmtMonth(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('es-MX', { month: 'short', year: '2-digit' })
}

/** Convert a period value to { date_from, date_to } for the API */
function periodToDates(period) {
  const p = PERIODS.find(x => x.value === period)
  if (!p || p.days === null) return {}
  const now = new Date()
  const from = new Date(now)
  from.setDate(now.getDate() - p.days)
  return { date_from: from.toISOString().slice(0, 10) }
}

const GROUP_OPTIONS = [
  { value: 'dia', label: 'Día' },
  { value: 'semana', label: 'Semana' },
  { value: 'mes', label: 'Mes' },
]

// ── Constantes ────────────────────────────────────────────────────────────────

const PERIODS = [
  { value: '7d',   label: 'Últimos 7 días',  days: 7 },
  { value: '30d',  label: 'Últimos 30 días', days: 30 },
  { value: '90d',  label: 'Últimos 3 meses', days: 90 },
  { value: '180d', label: 'Últimos 6 meses', days: 180 },
  { value: '365d', label: 'Último año',       days: 365 },
  { value: 'all',  label: 'Todo el tiempo',  days: null },
]

const CATEGORY_COLORS = ['#6366f1', '#22d3ee', '#f59e0b', '#10b981', '#f43f5e', '#8b5cf6', '#3b82f6']

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiMini({ title, value, subtitle, icon, color }) {
  const colors = {
    green:  'text-green-600 bg-green-50 border-green-100',
    blue:   'text-blue-600 bg-blue-50 border-blue-100',
    purple: 'text-purple-600 bg-purple-50 border-purple-100',
    amber:  'text-amber-600 bg-amber-50 border-amber-100',
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{icon}</span>
        <p className="text-xs font-medium opacity-70">{title}</p>
      </div>
      <p className="text-xl font-bold">{value}</p>
      {subtitle && <p className="text-xs opacity-60 mt-0.5">{subtitle}</p>}
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
      {children}
    </h3>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function Ventas() {
  const [analytics, setAnalytics] = useState(null)
  const [transacciones, setTransacciones] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [period, setPeriod] = useState('all')
  const [groupBy, setGroupBy] = useState('dia')
  const [chartType, setChartType] = useState('area') // 'area' | 'bar'
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  useWatcherRefresh(useCallback(() => setRefreshKey(k => k + 1), []))

  function handlePeriodChange(val) {
    setPeriod(val)
    setDateFrom('')
    setDateTo('')
  }

  function handleDateFrom(val) {
    setDateFrom(val)
    if (val) setPeriod('all')
  }
  function handleDateTo(val) {
    setDateTo(val)
    if (val) setPeriod('all')
  }

  function clearDates() {
    setDateFrom('')
    setDateTo('')
    setPeriod('30d')
  }

  const usingCustomDates = dateFrom || dateTo

  // Fetch analytics + transacciones from backend
  useEffect(() => {
    let cancelled = false
    async function fetchData() {
      setLoading(true)
      setError(null)
      try {
        // Build params
        const params = { group_by: groupBy }
        if (dateFrom || dateTo) {
          if (dateFrom) params.date_from = dateFrom
          if (dateTo) params.date_to = dateTo
        } else {
          const dates = periodToDates(period)
          if (dates.date_from) params.date_from = dates.date_from
          if (dates.date_to) params.date_to = dates.date_to
        }

        const [analyticsRes, txRes] = await Promise.all([
          ventasService.getAnalytics(params),
          ventasService.getAll({ ...params, limit: 15 }),
        ])
        if (!cancelled) {
          setAnalytics(analyticsRes.data)
          setTransacciones(txRes.data)
        }
      } catch {
        if (!cancelled) setError('No se pudo conectar con la API.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchData()
    return () => { cancelled = true }
  }, [period, groupBy, dateFrom, dateTo, refreshKey])

  const periodLabel = usingCustomDates
    ? `${dateFrom || '…'} → ${dateTo || '…'}`
    : (PERIODS.find(p => p.value === period)?.label ?? '')

  if (loading) {
    return (
      <div className="p-6 max-w-6xl space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  const noData = !analytics || analytics.num_transacciones === 0

  return (
    <div className="p-6 max-w-6xl">
      {/* Header con filtros */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Ventas</h2>
          <p className="text-sm text-gray-500 mt-0.5">Análisis de transacciones y tendencias</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-1">
          <select
            value={usingCustomDates ? 'all' : period}
            onChange={e => handlePeriodChange(e.target.value)}
            disabled={!!usingCustomDates}
            className={`text-sm bg-white border rounded-lg px-3 py-2 shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-300 ${
              usingCustomDates
                ? 'border-gray-100 text-gray-300 cursor-not-allowed'
                : 'border-gray-200 text-gray-700'
            }`}
          >
            {PERIODS.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>

          <span className="text-gray-300 text-sm select-none">|</span>

          <div className="flex items-center gap-1.5">
            <label className="text-xs text-gray-400 whitespace-nowrap">Desde</label>
            <input
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={e => handleDateFrom(e.target.value)}
              className="text-sm bg-white border border-gray-200 rounded-lg px-2 py-2 text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <label className="text-xs text-gray-400 whitespace-nowrap">Hasta</label>
            <input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={e => handleDateTo(e.target.value)}
              className="text-sm bg-white border border-gray-200 rounded-lg px-2 py-2 text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer"
            />
          </div>

          {usingCustomDates && (
            <button
              onClick={clearDates}
              title="Limpiar fechas"
              className="text-xs text-gray-400 hover:text-red-500 px-2 py-2 rounded-lg hover:bg-red-50 transition-colors cursor-pointer"
            >
              ✕ Limpiar
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {noData && !error ? (
        <div className="p-8 bg-gray-50 border border-dashed border-gray-300 rounded-xl text-center text-gray-500">
          <p className="text-4xl mb-3">💰</p>
          <p className="font-medium">Sin datos de ventas</p>
          <p className="text-sm mt-1">Carga un CSV en Configuración para comenzar, o prueba un rango más amplio.</p>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <section className="mb-8">
            <SectionTitle>Resumen · {periodLabel}</SectionTitle>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <KpiMini
                title="Total ventas"
                value={fmtCurrency(analytics.total_ventas)}
                icon="💰"
                color="green"
              />
              <KpiMini
                title="Transacciones"
                value={analytics.num_transacciones.toLocaleString()}
                icon="🧾"
                color="blue"
              />
              <KpiMini
                title="Ticket promedio"
                value={fmtCurrency(analytics.ticket_promedio)}
                icon="📊"
                color="purple"
              />
              <KpiMini
                title="Producto líder"
                value={analytics.top_producto}
                subtitle={analytics.top_categoria}
                icon="⭐"
                color="amber"
              />
            </div>
          </section>

          {/* Área chart + Barras por categoría */}
          <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3 bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-3">
                <SectionTitle>Ventas por {groupBy === 'dia' ? 'día' : groupBy} · {periodLabel}</SectionTitle>
                <div className="flex items-center gap-2">
                  <div className="flex bg-gray-100 rounded-lg p-0.5">
                    {GROUP_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => setGroupBy(opt.value)}
                        className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                          groupBy === opt.value
                            ? 'bg-white text-indigo-600 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                  <div className="flex bg-gray-100 rounded-lg p-0.5">
                    <button
                      onClick={() => setChartType('area')}
                      className={`px-2 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                        chartType === 'area' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                      }`}
                      title="Línea"
                    >
                      📈
                    </button>
                    <button
                      onClick={() => setChartType('bar')}
                      className={`px-2 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                        chartType === 'bar' ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                      }`}
                      title="Barras"
                    >
                      📊
                    </button>
                  </div>
                </div>
              </div>
              {analytics.serie_temporal.length > 1 ? (
                <ResponsiveContainer width="100%" height={220}>
                  {chartType === 'area' ? (
                  <AreaChart data={analytics.serie_temporal} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gradVentas" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="fecha"
                      tickFormatter={groupBy === 'mes' ? fmtMonth : groupBy === 'semana' ? fmtWeek : fmtShortDate}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      tickLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      tickLine={false}
                      axisLine={false}
                      width={40}
                    />
                    <Tooltip
                      labelFormatter={groupBy === 'mes' ? fmtMonth : groupBy === 'semana' ? fmtWeek : fmtShortDate}
                      formatter={v => [fmtCurrency(v), 'Total']}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="total"
                      stroke="#6366f1"
                      strokeWidth={2}
                      fill="url(#gradVentas)"
                    />
                  </AreaChart>
                  ) : (
                  <BarChart data={analytics.serie_temporal} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="fecha"
                      tickFormatter={groupBy === 'mes' ? fmtMonth : groupBy === 'semana' ? fmtWeek : fmtShortDate}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      tickLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      tickLine={false}
                      axisLine={false}
                      width={40}
                    />
                    <Tooltip
                      labelFormatter={groupBy === 'mes' ? fmtMonth : groupBy === 'semana' ? fmtWeek : fmtShortDate}
                      formatter={v => [fmtCurrency(v), 'Total']}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    />
                    <Bar dataKey="total" fill="#6366f1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                  )}
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 mt-4">No hay suficientes puntos para graficar.</p>
              )}
            </div>

            <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Por categoría</SectionTitle>
              {analytics.por_categoria.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={analytics.por_categoria}
                    layout="vertical"
                    margin={{ top: 0, right: 4, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                    <XAxis
                      type="number"
                      tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                      tick={{ fontSize: 9, fill: '#9ca3af' }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="categoria"
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      tickLine={false}
                      axisLine={false}
                      width={80}
                    />
                    <Tooltip
                      formatter={v => [fmtCurrency(v), 'Total']}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    />
                    <Bar dataKey="total" radius={[0, 4, 4, 0]}>
                      {analytics.por_categoria.map((_, i) => (
                        <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 mt-4">Sin datos de categorías.</p>
              )}
            </div>
          </section>

          {/* Top 5 productos */}
          {analytics.top_productos.length > 0 && (
            <section className="mb-8 bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Top 5 productos · {periodLabel}</SectionTitle>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={analytics.top_productos}
                  layout="vertical"
                  margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                  <XAxis
                    type="number"
                    tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                    tick={{ fontSize: 10, fill: '#9ca3af' }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="nombre"
                    tick={{ fontSize: 10, fill: '#6b7280' }}
                    tickLine={false}
                    axisLine={false}
                    width={115}
                  />
                  <Tooltip
                    formatter={v => [fmtCurrency(v), 'Monto total']}
                    contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  />
                  <Bar dataKey="monto" radius={[0, 4, 4, 0]} fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* Tabla de transacciones */}
          <section>
            <SectionTitle>Transacciones recientes · {periodLabel}</SectionTitle>
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Fecha</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Producto</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Categoría</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Cant.</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Monto</th>
                  </tr>
                </thead>
                <tbody>
                  {transacciones.map((v, i) => (
                    <tr
                      key={v.id ?? i}
                      className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-2.5 text-gray-500 font-mono text-xs whitespace-nowrap">
                        {fmtDate(v.fecha)}
                      </td>
                      <td className="px-4 py-2.5 text-gray-800 font-medium max-w-48 truncate">
                        {v.nombre_producto}
                      </td>
                      <td className="px-4 py-2.5">
                        {v.categoria ? (
                          <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full">
                            {v.categoria}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-600">{v.cantidad}</td>
                      <td className="px-4 py-2.5 text-right font-semibold text-gray-900">
                        {fmtCurrency(v.monto_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {analytics.num_transacciones > 15 && (
                <p className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100">
                  Mostrando 15 de {analytics.num_transacciones.toLocaleString()} transacciones en este período.
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  )
}

export default Ventas
