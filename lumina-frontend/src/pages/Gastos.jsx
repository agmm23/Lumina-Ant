import { useState, useEffect, useMemo } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { gastosService } from '../services/api'

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
  const d = new Date(dateStr)
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short' })
}

// ── Constantes ────────────────────────────────────────────────────────────────

const PERIODS = [
  { value: '7d',   label: 'Últimos 7 días',  days: 7 },
  { value: '30d',  label: 'Últimos 30 días', days: 30 },
  { value: '90d',  label: 'Últimos 3 meses', days: 90 },
  { value: '180d', label: 'Últimos 6 meses', days: 180 },
  { value: '365d', label: 'Último año',       days: 365 },
  { value: 'all',  label: 'Todo el tiempo',  days: null },
]

const CATEGORY_COLORS = ['#f43f5e', '#fb923c', '#fbbf24', '#a78bfa', '#38bdf8', '#34d399', '#f472b6']

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiMini({ title, value, subtitle, icon, color }) {
  const colors = {
    red:    'text-red-600 bg-red-50 border-red-100',
    orange: 'text-orange-600 bg-orange-50 border-orange-100',
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

function CustomTooltipCurrency({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm px-3 py-2 text-xs">
      <p className="text-gray-500 mb-1">{fmtShortDate(label)}</p>
      <p className="font-semibold text-gray-900">{fmtCurrency(payload[0].value)}</p>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function Gastos() {
  const [gastos, setGastos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [period, setPeriod] = useState('30d')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

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

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)
      try {
        const res = await gastosService.getAll({ limit: 500 })
        setGastos(res.data)
      } catch {
        setError('No se pudo conectar con la API.')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  // Gastos filtrados
  const filteredGastos = useMemo(() => {
    if (dateFrom || dateTo) {
      return gastos.filter(g => {
        const day = g.fecha?.slice(0, 10) ?? ''
        if (dateFrom && day < dateFrom) return false
        if (dateTo && day > dateTo) return false
        return true
      })
    }
    const p = PERIODS.find(p => p.value === period)
    if (!p || p.days === null) return gastos
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - p.days)
    const cutoffStr = cutoff.toISOString().slice(0, 10)
    return gastos.filter(g => (g.fecha?.slice(0, 10) ?? '') >= cutoffStr)
  }, [gastos, period, dateFrom, dateTo])

  // KPIs calculados
  const kpis = useMemo(() => {
    if (!filteredGastos.length) return null
    const total = filteredGastos.reduce((acc, g) => acc + g.monto, 0)
    const count = filteredGastos.length
    const promedio = total / count
    const catMap = {}
    filteredGastos.forEach(g => {
      const cat = g.categoria || 'Sin categoría'
      catMap[cat] = (catMap[cat] || 0) + g.monto
    })
    const topCat = Object.entries(catMap).sort(([, a], [, b]) => b - a)[0]?.[0] ?? '—'
    const pagoMap = {}
    filteredGastos.forEach(g => {
      const tp = g.tipo_pago || 'No especificado'
      pagoMap[tp] = (pagoMap[tp] || 0) + g.monto
    })
    const topPago = Object.entries(pagoMap).sort(([, a], [, b]) => b - a)[0]?.[0] ?? '—'
    return { total, count, promedio, topCat, topPago }
  }, [filteredGastos])

  // Gastos por día
  const gastosPorDia = useMemo(() => {
    if (!filteredGastos.length) return []
    const map = {}
    filteredGastos.forEach(g => {
      const day = g.fecha?.slice(0, 10) ?? ''
      if (!map[day]) map[day] = 0
      map[day] += g.monto
    })
    return Object.entries(map)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([fecha, total]) => ({ fecha, total: Math.round(total) }))
  }, [filteredGastos])

  // Gastos por categoría
  const gastosPorCategoria = useMemo(() => {
    if (!filteredGastos.length) return []
    const map = {}
    filteredGastos.forEach(g => {
      const cat = g.categoria || 'Sin categoría'
      if (!map[cat]) map[cat] = 0
      map[cat] += g.monto
    })
    return Object.entries(map)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 7)
      .map(([categoria, total]) => ({ categoria, total: Math.round(total) }))
  }, [filteredGastos])

  // Top 5 proveedores
  const topProveedores = useMemo(() => {
    if (!filteredGastos.length) return []
    const map = {}
    filteredGastos.forEach(g => {
      const prov = g.nombre_proveedor || 'Sin proveedor'
      if (!map[prov]) map[prov] = 0
      map[prov] += g.monto
    })
    return Object.entries(map)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5)
      .map(([nombre, monto]) => ({
        nombre: nombre.length > 22 ? nombre.slice(0, 22) + '…' : nombre,
        monto: Math.round(monto),
      }))
  }, [filteredGastos])

  // Tabla — últimas 15
  const transacciones = filteredGastos.slice(0, 15)

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

  return (
    <div className="p-6 max-w-6xl">
      {/* Header con filtros */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Gastos</h2>
          <p className="text-sm text-gray-500 mt-0.5">Análisis de egresos por categoría y proveedor</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-1">
          <select
            value={usingCustomDates ? 'all' : period}
            onChange={e => handlePeriodChange(e.target.value)}
            disabled={!!usingCustomDates}
            className={`text-sm bg-white border rounded-lg px-3 py-2 shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-rose-300 ${
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
              className="text-sm bg-white border border-gray-200 rounded-lg px-2 py-2 text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-rose-300 cursor-pointer"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <label className="text-xs text-gray-400 whitespace-nowrap">Hasta</label>
            <input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={e => handleDateTo(e.target.value)}
              className="text-sm bg-white border border-gray-200 rounded-lg px-2 py-2 text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-rose-300 cursor-pointer"
            />
          </div>

          {usingCustomDates && (
            <button
              onClick={clearDates}
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

      {gastos.length === 0 && !error ? (
        <div className="p-8 bg-gray-50 border border-dashed border-gray-300 rounded-xl text-center text-gray-500">
          <p className="text-4xl mb-3">💸</p>
          <p className="font-medium">Sin datos de gastos</p>
          <p className="text-sm mt-1">Carga un CSV en Configuración para comenzar.</p>
        </div>
      ) : filteredGastos.length === 0 ? (
        <div className="p-8 bg-gray-50 border border-dashed border-gray-300 rounded-xl text-center text-gray-500">
          <p className="text-4xl mb-3">🔍</p>
          <p className="font-medium">Sin registros en este período</p>
          <p className="text-sm mt-1">No hay gastos para «{periodLabel}». Prueba un rango más amplio.</p>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <section className="mb-8">
            <SectionTitle>Resumen · {periodLabel}</SectionTitle>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <KpiMini
                title="Total gastos"
                value={fmtCurrency(kpis?.total)}
                icon="💸"
                color="red"
              />
              <KpiMini
                title="Registros"
                value={kpis?.count ?? '—'}
                subtitle={period !== 'all' ? `${gastos.length} totales cargados` : undefined}
                icon="🧾"
                color="orange"
              />
              <KpiMini
                title="Gasto promedio"
                value={fmtCurrency(kpis?.promedio)}
                icon="📊"
                color="purple"
              />
              <KpiMini
                title="Categoría principal"
                value={kpis?.topCat ?? '—'}
                subtitle={kpis?.topPago ? `Pago: ${kpis.topPago}` : undefined}
                icon="📂"
                color="amber"
              />
            </div>
          </section>

          {/* Área chart + Barras por categoría */}
          <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-5">
            {/* Área chart */}
            <div className="lg:col-span-3 bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Gastos por día · {periodLabel}</SectionTitle>
              {gastosPorDia.length > 1 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={gastosPorDia} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gradGastos" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="fecha"
                      tickFormatter={fmtShortDate}
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
                    <Tooltip content={<CustomTooltipCurrency />} />
                    <Area
                      type="monotone"
                      dataKey="total"
                      stroke="#f43f5e"
                      strokeWidth={2}
                      fill="url(#gradGastos)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 mt-4">No hay suficientes días para graficar.</p>
              )}
            </div>

            {/* Barras por categoría */}
            <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Por categoría</SectionTitle>
              {gastosPorCategoria.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={gastosPorCategoria}
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
                      {gastosPorCategoria.map((_, i) => (
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

          {/* Top 5 proveedores */}
          {topProveedores.length > 0 && (
            <section className="mb-8 bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Top 5 proveedores · {periodLabel}</SectionTitle>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={topProveedores}
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
                    formatter={v => [fmtCurrency(v), 'Total pagado']}
                    contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                  />
                  <Bar dataKey="monto" radius={[0, 4, 4, 0]} fill="#f43f5e" />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* Tabla de registros */}
          <section>
            <SectionTitle>Registros recientes · {periodLabel}</SectionTitle>
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Fecha</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Descripción</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Categoría</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Proveedor</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Pago</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Monto</th>
                  </tr>
                </thead>
                <tbody>
                  {transacciones.map((g, i) => (
                    <tr
                      key={g.id ?? i}
                      className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-2.5 text-gray-500 font-mono text-xs whitespace-nowrap">
                        {fmtDate(g.fecha)}
                      </td>
                      <td className="px-4 py-2.5 text-gray-800 font-medium max-w-40 truncate">
                        {g.descripcion}
                      </td>
                      <td className="px-4 py-2.5">
                        {g.categoria ? (
                          <span className="text-xs bg-rose-50 text-rose-700 px-2 py-0.5 rounded-full">
                            {g.categoria}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-300">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-gray-600 text-xs max-w-32 truncate">
                        {g.nombre_proveedor ?? <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-gray-500 text-xs">
                        {g.tipo_pago ?? <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right font-semibold text-rose-700">
                        {fmtCurrency(g.monto)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredGastos.length > 15 && (
                <p className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100">
                  Mostrando 15 de {filteredGastos.length} registros en este período.
                </p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  )
}

export default Gastos
