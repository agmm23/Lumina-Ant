import { useState, useEffect, useCallback } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { gastosService } from '../services/api'
import useWatcherRefresh from '../hooks/useWatcherRefresh'
import SectionAlerts from '../components/SectionAlerts'
import { useDark } from '../contexts/ThemeContext'
import { useLanguage } from '../contexts/LanguageContext'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCurrency(value, locale) {
  if (value == null) return '—'
  return new Intl.NumberFormat(locale, {
    style: 'currency', currency: 'MXN', maximumFractionDigits: 0,
  }).format(value)
}

function fmtDate(dateStr, locale) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString(locale, { day: '2-digit', month: 'short', year: '2-digit' })
}

function fmtShortDate(dateStr, locale) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString(locale, { day: '2-digit', month: 'short' })
}

function fmtWeek(dateStr, locale) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  const end = new Date(d)
  end.setDate(d.getDate() + 6)
  const fmt = (dt) => dt.toLocaleDateString(locale, { day: '2-digit', month: 'short' })
  return `${fmt(d)} – ${fmt(end)}`
}

function fmtMonth(dateStr, locale) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString(locale, { month: 'short', year: '2-digit' })
}

function periodToDates(period) {
  const p = PERIODS.find(x => x.value === period)
  if (!p || p.days === null) return {}
  const now = new Date()
  const from = new Date(now)
  from.setDate(now.getDate() - p.days)
  return { date_from: from.toISOString().slice(0, 10) }
}

const PERIODS = [
  { value: '7d',   key: 'periods.7d',  days: 7 },
  { value: '30d',  key: 'periods.30d', days: 30 },
  { value: '90d',  key: 'periods.3m',  days: 90 },
  { value: '180d', key: 'periods.6m',  days: 180 },
  { value: '365d', key: 'periods.1y',  days: 365 },
  { value: 'all',  key: 'periods.all', days: null },
]

const CATEGORY_COLORS = ['#f43f5e', '#fb923c', '#fbbf24', '#a78bfa', '#38bdf8', '#34d399', '#f472b6']

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiMini({ title, value, subtitle, icon, color }) {
  const colors = {
    red:    'text-red-600 bg-red-50 border-red-100 dark:text-red-400 dark:bg-red-950 dark:border-red-800',
    orange: 'text-orange-600 bg-orange-50 border-orange-100 dark:text-orange-400 dark:bg-orange-950 dark:border-orange-800',
    purple: 'text-purple-600 bg-purple-50 border-purple-100 dark:text-purple-400 dark:bg-purple-950 dark:border-purple-800',
    amber:  'text-amber-600 bg-amber-50 border-amber-100 dark:text-amber-400 dark:bg-amber-950 dark:border-amber-800',
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
    <h3 className="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3">
      {children}
    </h3>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function Gastos() {
  const { isDark } = useDark()
  const { t, locale } = useLanguage()
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

  const GROUP_OPTIONS = [
    { value: 'dia', label: t('common.dia') },
    { value: 'semana', label: t('common.semana') },
    { value: 'mes', label: t('common.mes') },
  ]

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
    let cancelled = false
    async function fetchData() {
      setLoading(true)
      setError(null)
      try {
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
          gastosService.getAnalytics(params),
          gastosService.getAll({ ...params, limit: 15 }),
        ])
        if (!cancelled) {
          setAnalytics(analyticsRes.data)
          setTransacciones(txRes.data)
        }
      } catch {
        if (!cancelled) setError(t('common.errorConexionMsg'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchData()
    return () => { cancelled = true }
  }, [period, groupBy, dateFrom, dateTo, refreshKey])

  const periodLabel = usingCustomDates
    ? `${dateFrom || '…'} → ${dateTo || '…'}`
    : (PERIODS.find(p => p.value === period) ? t(PERIODS.find(p => p.value === period).key) : '')

  // Chart colors for dark mode
  const chartGrid = isDark ? '#374151' : '#f0f0f0'
  const chartTick = isDark ? '#9ca3af' : '#9ca3af'
  const chartTickCat = isDark ? '#d1d5db' : '#6b7280'
  const tooltipStyle = { fontSize: 11, borderRadius: 8, border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`, backgroundColor: isDark ? '#1f2937' : '#fff', color: isDark ? '#f9fafb' : '#111827' }

  const groupByLabel = groupBy === 'dia' ? t('common.dia').toLowerCase() : groupBy === 'semana' ? t('common.semana').toLowerCase() : t('common.mes').toLowerCase()

  // Locale-aware formatters bound to current locale
  const fmtCurrencyL = (v) => fmtCurrency(v, locale)
  const fmtDateL = (v) => fmtDate(v, locale)
  const fmtShortDateL = (v) => fmtShortDate(v, locale)
  const fmtWeekL = (v) => fmtWeek(v, locale)
  const fmtMonthL = (v) => fmtMonth(v, locale)

  if (loading) {
    return (
      <div className="p-6 max-w-6xl space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  const noData = !analytics || analytics.num_registros === 0

  return (
    <div className="p-6 max-w-6xl">
      {/* Header con filtros */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('gastos.title')}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{t('gastos.subtitle')}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-1">
          <select
            value={usingCustomDates ? 'all' : period}
            onChange={e => handlePeriodChange(e.target.value)}
            disabled={!!usingCustomDates}
            className={`text-sm bg-white dark:bg-gray-800 border rounded-lg px-3 py-2 shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-rose-300 ${
              usingCustomDates
                ? 'border-gray-100 dark:border-gray-700 text-gray-300 dark:text-gray-600 cursor-not-allowed'
                : 'border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200'
            }`}
          >
            {PERIODS.map(p => (
              <option key={p.value} value={p.value}>{t(p.key)}</option>
            ))}
          </select>

          <span className="text-gray-300 dark:text-gray-600 text-sm select-none">|</span>

          <div className="flex items-center gap-1.5">
            <label className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">{t('common.desde')}</label>
            <input
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={e => handleDateFrom(e.target.value)}
              className="text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-2 text-gray-700 dark:text-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-rose-300 cursor-pointer"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <label className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">{t('common.hasta')}</label>
            <input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={e => handleDateTo(e.target.value)}
              className="text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-2 text-gray-700 dark:text-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-rose-300 cursor-pointer"
            />
          </div>

          {usingCustomDates && (
            <button
              onClick={clearDates}
              className="text-xs text-gray-400 hover:text-red-500 px-2 py-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 transition-colors cursor-pointer"
            >
              ✕ {t('common.limpiar')}
            </button>
          )}
        </div>
      </div>

      <SectionAlerts tipo="gastos" refreshKey={refreshKey} />

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      {noData && !error ? (
        <div className="p-8 bg-gray-50 dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-600 rounded-xl text-center text-gray-500 dark:text-gray-400">
          <p className="text-4xl mb-3">💸</p>
          <p className="font-medium">{t('gastos.empty.sinDatos')}</p>
          <p className="text-sm mt-1">{t('gastos.empty.cargaCSV')}</p>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <section className="mb-8">
            <SectionTitle>{t('gastos.sections.resumen')} · {periodLabel}</SectionTitle>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <KpiMini
                title={t('gastos.kpi.totalGastos')}
                value={fmtCurrencyL(analytics.total_gastos)}
                icon="💸"
                color="red"
              />
              <KpiMini
                title={t('gastos.kpi.registros')}
                value={analytics.num_registros.toLocaleString()}
                icon="🧾"
                color="orange"
              />
              <KpiMini
                title={t('gastos.kpi.gastoPromedio')}
                value={fmtCurrencyL(analytics.gasto_promedio)}
                icon="📊"
                color="purple"
              />
              <KpiMini
                title={t('gastos.kpi.categoriaPrincipal')}
                value={analytics.top_categoria}
                subtitle={analytics.top_tipo_pago ? `${t('gastos.table.pago')}: ${analytics.top_tipo_pago}` : undefined}
                icon="📂"
                color="amber"
              />
            </div>
          </section>

          {/* Área chart + Barras por categoría */}
          <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <div className="flex items-center justify-between mb-3">
                <SectionTitle>{t('gastos.sections.gastosPorGrupo', { groupBy: groupByLabel })} · {periodLabel}</SectionTitle>
                <div className="flex items-center gap-2">
                  <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-0.5">
                    {GROUP_OPTIONS.map(opt => (
                      <button
                        key={opt.value}
                        onClick={() => setGroupBy(opt.value)}
                        className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                          groupBy === opt.value
                            ? 'bg-white dark:bg-gray-600 text-rose-600 dark:text-rose-400 shadow-sm'
                            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                        }`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                  <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-0.5">
                    <button
                      onClick={() => setChartType('area')}
                      className={`px-2 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                        chartType === 'area' ? 'bg-white dark:bg-gray-600 text-rose-600 dark:text-rose-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                      }`}
                      title={t('common.linea')}
                    >
                      📈
                    </button>
                    <button
                      onClick={() => setChartType('bar')}
                      className={`px-2 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
                        chartType === 'bar' ? 'bg-white dark:bg-gray-600 text-rose-600 dark:text-rose-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                      }`}
                      title={t('common.barras')}
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
                      <linearGradient id="gradGastos" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
                    <XAxis dataKey="fecha" tickFormatter={groupBy === 'mes' ? fmtMonthL : groupBy === 'semana' ? fmtWeekL : fmtShortDateL} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} interval="preserveStartEnd" />
                    <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} axisLine={false} width={40} />
                    <Tooltip labelFormatter={groupBy === 'mes' ? fmtMonthL : groupBy === 'semana' ? fmtWeekL : fmtShortDateL} formatter={v => [fmtCurrencyL(v), t('common.total')]} contentStyle={tooltipStyle} />
                    <Area type="monotone" dataKey="total" stroke="#f43f5e" strokeWidth={2} fill="url(#gradGastos)" />
                  </AreaChart>
                  ) : (
                  <BarChart data={analytics.serie_temporal} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
                    <XAxis dataKey="fecha" tickFormatter={groupBy === 'mes' ? fmtMonthL : groupBy === 'semana' ? fmtWeekL : fmtShortDateL} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} interval="preserveStartEnd" />
                    <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} axisLine={false} width={40} />
                    <Tooltip labelFormatter={groupBy === 'mes' ? fmtMonthL : groupBy === 'semana' ? fmtWeekL : fmtShortDateL} formatter={v => [fmtCurrencyL(v), t('common.total')]} contentStyle={tooltipStyle} />
                    <Bar dataKey="total" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                  )}
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 dark:text-gray-500 mt-4">{t('gastos.empty.sinPuntos')}</p>
              )}
            </div>

            <div className="lg:col-span-2 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <SectionTitle>{t('gastos.sections.porCategoria')}</SectionTitle>
              {analytics.por_categoria.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={analytics.por_categoria} layout="vertical" margin={{ top: 0, right: 4, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} horizontal={false} />
                    <XAxis type="number" tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 9, fill: chartTick }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="categoria" tick={{ fontSize: 10, fill: chartTickCat }} tickLine={false} axisLine={false} width={80} />
                    <Tooltip formatter={v => [fmtCurrencyL(v), t('common.total')]} contentStyle={tooltipStyle} />
                    <Bar dataKey="total" radius={[0, 4, 4, 0]}>
                      {analytics.por_categoria.map((_, i) => (
                        <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 dark:text-gray-500 mt-4">{t('gastos.empty.sinCategorias')}</p>
              )}
            </div>
          </section>

          {/* Top 5 proveedores */}
          {analytics.top_proveedores.length > 0 && (
            <section className="mb-8 bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <SectionTitle>{t('gastos.sections.top5Proveedores')} · {periodLabel}</SectionTitle>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={analytics.top_proveedores} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} horizontal={false} />
                  <XAxis type="number" tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="nombre" tick={{ fontSize: 10, fill: chartTickCat }} tickLine={false} axisLine={false} width={115} />
                  <Tooltip formatter={v => [fmtCurrencyL(v), t('gastos.table.totalPagado')]} contentStyle={tooltipStyle} />
                  <Bar dataKey="monto" radius={[0, 4, 4, 0]} fill="#f43f5e" />
                </BarChart>
              </ResponsiveContainer>
            </section>
          )}

          {/* Tabla de registros */}
          <section>
            <SectionTitle>{t('gastos.sections.registrosRecientes')} · {periodLabel}</SectionTitle>
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('gastos.table.fecha')}</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('gastos.table.descripcion')}</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('gastos.table.categoria')}</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('gastos.table.proveedor')}</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('gastos.table.pago')}</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('gastos.table.monto')}</th>
                  </tr>
                </thead>
                <tbody>
                  {transacciones.map((g, i) => (
                    <tr
                      key={g.id ?? i}
                      className="border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                    >
                      <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 font-mono text-xs whitespace-nowrap">
                        {fmtDateL(g.fecha)}
                      </td>
                      <td className="px-4 py-2.5 text-gray-800 dark:text-gray-200 font-medium max-w-40 truncate">
                        {g.descripcion}
                      </td>
                      <td className="px-4 py-2.5">
                        {g.categoria ? (
                          <span className="text-xs bg-rose-50 dark:bg-rose-900 text-rose-700 dark:text-rose-400 px-2 py-0.5 rounded-full">
                            {g.categoria}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-300 dark:text-gray-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400 text-xs max-w-32 truncate">
                        {g.nombre_proveedor ?? <span className="text-gray-300 dark:text-gray-600">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 text-xs">
                        {g.tipo_pago ?? <span className="text-gray-300 dark:text-gray-600">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right font-semibold text-rose-700 dark:text-rose-400">
                        {fmtCurrencyL(g.monto)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {analytics.num_registros > 15 && (
                <p className="px-4 py-2 text-xs text-gray-400 dark:text-gray-500 border-t border-gray-100 dark:border-gray-700">
                  {t('gastos.mostrando', { total: analytics.num_registros.toLocaleString() })}
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
