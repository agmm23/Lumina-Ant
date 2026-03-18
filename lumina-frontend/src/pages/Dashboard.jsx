import { useState, useEffect, useCallback } from 'react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend,
} from 'recharts'
import { analyticsService, ventasService, gastosService, inventarioService, clientesService } from '../services/api'
import KpiCard from '../components/KpiCard'
import AlertCard from '../components/AlertCard'
import useWatcherRefresh from '../hooks/useWatcherRefresh'
import { useDark } from '../contexts/ThemeContext'
import { useLanguage } from '../contexts/LanguageContext'

// ── Chart Card wrapper ────────────────────────────────────────────────────────

function ChartCard({ title, children, loading, controls }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{title}</h4>
        {controls && <div className="flex items-center gap-2">{controls}</div>}
      </div>
      {loading ? (
        <div className="h-[220px] bg-gray-50 dark:bg-gray-800 rounded-lg animate-pulse" />
      ) : children}
    </div>
  )
}

const BAR_COLORS = ['#6366f1', '#f43f5e', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899']

// ── Dashboard ─────────────────────────────────────────────────────────────────

function Dashboard() {
  const { isDark } = useDark()
  const { t, locale } = useLanguage()

  // ── Helpers (locale-aware) ────────────────────────────────────────────────

  function formatCurrency(value) {
    if (value == null) return '—'
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'MXN',
      maximumFractionDigits: 0,
    }).format(value)
  }

  function fmtShortDate(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr + 'T00:00:00')
    return d.toLocaleDateString(locale, { day: '2-digit', month: 'short' })
  }

  function fmtWeek(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr + 'T00:00:00')
    const end = new Date(d)
    end.setDate(d.getDate() + 6)
    const fmt = (dt) => dt.toLocaleDateString(locale, { day: '2-digit', month: 'short' })
    return `${fmt(d)} – ${fmt(end)}`
  }

  function fmtMonth(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr + 'T00:00:00')
    return d.toLocaleDateString(locale, { month: 'short', year: '2-digit' })
  }

  function fmtAxis(groupBy) {
    if (groupBy === 'mes') return fmtMonth
    if (groupBy === 'semana') return fmtWeek
    return fmtShortDate
  }

  // ── Periods / filters (translated) ───────────────────────────────────────

  const PERIODS = [
    { value: '7d',   label: t('periods.7d'),  days: 7 },
    { value: '30d',  label: t('periods.30d'), days: 30 },
    { value: '90d',  label: t('periods.3m'),  days: 90 },
    { value: '180d', label: t('periods.6m'),  days: 180 },
    { value: '365d', label: t('periods.1y'),  days: 365 },
    { value: 'all',  label: t('periods.all'), days: null },
  ]

  const ALERT_FILTERS = [
    { id: 'todas',    label: t('dashboard.alertas.todas') },
    { id: 'critical', label: t('dashboard.alertas.criticas') },
    { id: 'warning',  label: t('dashboard.alertas.avisos') },
  ]

  const GROUP_OPTIONS = [
    { value: 'dia',    label: t('common.dia') },
    { value: 'semana', label: t('common.semana') },
    { value: 'mes',    label: t('common.mes') },
  ]

  function periodToDates(period) {
    const p = PERIODS.find(x => x.value === period)
    if (!p || p.days === null) return {}
    const now = new Date()
    const from = new Date(now)
    from.setDate(now.getDate() - p.days)
    return { date_from: from.toISOString().slice(0, 10) }
  }

  // ── State ─────────────────────────────────────────────────────────────────

  const [salesStats, setSalesStats] = useState(null)
  const [gastosStats, setGastosStats] = useState(null)
  const [inventarioStats, setInventarioStats] = useState(null)
  const [clientesStats, setClientesStats] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [alertFilter, setAlertFilter] = useState('todas')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Chart data
  const [ventasSerie, setVentasSerie] = useState([])
  const [gastosCat, setGastosCat] = useState([])
  const [topProductos, setTopProductos] = useState([])
  const [ventasVsGastos, setVentasVsGastos] = useState([])

  // Chart controls
  const [groupBy, setGroupBy] = useState('dia')
  const [chartType, setChartType] = useState('area')

  // Time period filters
  const [period, setPeriod] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const usingCustomDates = dateFrom || dateTo

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

  /** Build date params from current period/date state */
  function buildDateParams() {
    const params = {}
    if (dateFrom || dateTo) {
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo
    } else {
      const dates = periodToDates(period)
      if (dates.date_from) params.date_from = dates.date_from
    }
    return params
  }

  // Separate loading for charts on groupBy change
  const [chartsLoading, setChartsLoading] = useState(false)

  const fetchAll = useCallback(async (dateParams, gb) => {
    try {
      setLoading(true)
      setError(null)

      const [ventasAnalRes, gastosAnalRes, invRes, invLowRes, clientesRes, alertsRes] =
        await Promise.allSettled([
          ventasService.getAnalytics({ group_by: gb, ...dateParams }),
          gastosService.getAnalytics({ group_by: gb, ...dateParams }),
          inventarioService.getCount(),
          inventarioService.getLowStock(),
          clientesService.getCount(),
          analyticsService.getAlerts(10, true),
        ])

      // Ventas KPIs + charts (date-filtered)
      let ventasData = []
      if (ventasAnalRes.status === 'fulfilled') {
        const vd = ventasAnalRes.value.data
        setSalesStats({
          total_ventas: vd.total_ventas,
          cantidad_transacciones: vd.num_transacciones,
          ticket_promedio: vd.ticket_promedio,
          producto_mas_vendido: vd.top_producto,
          categoria_principal: vd.top_categoria,
        })
        ventasData = vd.serie_temporal || []
        setVentasSerie(ventasData)
        setTopProductos((vd.top_productos || []).slice(0, 5))
      }

      // Gastos KPIs + charts (date-filtered)
      if (gastosAnalRes.status === 'fulfilled') {
        const gd = gastosAnalRes.value.data
        setGastosStats({
          monto_total: gd.total_gastos,
          total_gastos: gd.num_registros,
        })
        const gastosCategorias = gd.por_categoria || []
        setGastosCat(gastosCategorias.slice(0, 7))

        const gastosData = gd.serie_temporal || []
        const gastosMap = Object.fromEntries(gastosData.map(g => [g.fecha, g.total]))
        const ventasMap = Object.fromEntries(ventasData.map(v => [v.fecha, v.total]))
        const allDates = [...new Set([...Object.keys(ventasMap), ...Object.keys(gastosMap)])].sort()
        setVentasVsGastos(allDates.map(fecha => ({
          fecha,
          ventas: ventasMap[fecha] || 0,
          gastos: gastosMap[fecha] || 0,
        })))
      }

      // Inventario (not date-dependent)
      if (invRes.status === 'fulfilled') setInventarioStats(invRes.value.data)
      if (invLowRes.status === 'fulfilled') {
        const lowStockData = invLowRes.value.data
        const count = Array.isArray(lowStockData)
          ? lowStockData.length
          : (lowStockData?.total_bajo_stock ?? 0)
        setInventarioStats(prev => ({ ...prev, bajo_stock: count }))
      }

      // Clientes (not date-dependent)
      if (clientesRes.status === 'fulfilled') setClientesStats(clientesRes.value.data)

      // Alertas
      if (alertsRes.status === 'fulfilled') {
        const data = alertsRes.value.data
        setAlerts(Array.isArray(data) ? data : data?.alertas || [])
      }

      const allFailed = [ventasAnalRes, gastosAnalRes, invRes, clientesRes].every(
        r => r.status === 'rejected'
      )
      if (allFailed) {
        setError('connection')
      }
    } catch (err) {
      setError('unexpected')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Re-fetch only charts when groupBy changes (not full reload)
  const fetchChartsOnly = useCallback(async (dateParams, gb) => {
    setChartsLoading(true)
    try {
      const [ventasRes, gastosRes] = await Promise.allSettled([
        ventasService.getAnalytics({ group_by: gb, ...dateParams }),
        gastosService.getAnalytics({ group_by: gb, ...dateParams }),
      ])

      let ventasData = []
      if (ventasRes.status === 'fulfilled') {
        ventasData = ventasRes.value.data?.serie_temporal || []
        setVentasSerie(ventasData)
      }

      if (gastosRes.status === 'fulfilled') {
        const gastosData = gastosRes.value.data?.serie_temporal || []
        const gastosMap = Object.fromEntries(gastosData.map(g => [g.fecha, g.total]))
        const ventasMap = Object.fromEntries(ventasData.map(v => [v.fecha, v.total]))
        const allDates = [...new Set([...Object.keys(ventasMap), ...Object.keys(gastosMap)])].sort()
        setVentasVsGastos(allDates.map(fecha => ({
          fecha,
          ventas: ventasMap[fecha] || 0,
          gastos: gastosMap[fecha] || 0,
        })))
      }
    } finally {
      setChartsLoading(false)
    }
  }, [])

  // Initial load + period/date changes
  useEffect(() => {
    fetchAll(buildDateParams(), groupBy)
  }, [period, dateFrom, dateTo]) // eslint-disable-line react-hooks/exhaustive-deps

  // GroupBy changes only refresh charts
  const [initialLoad, setInitialLoad] = useState(true)
  useEffect(() => {
    if (initialLoad) { setInitialLoad(false); return }
    fetchChartsOnly(buildDateParams(), groupBy)
  }, [groupBy]) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh cuando el watcher detecta datos nuevos
  useWatcherRefresh(useCallback(() => {
    fetchAll(buildDateParams(), groupBy)
  }, [fetchAll, groupBy])) // eslint-disable-line react-hooks/exhaustive-deps

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
  const tickFmt = fmtAxis(groupBy)
  const isTimeLoading = loading || chartsLoading

  // Dark-aware chart colors
  const chartGrid = isDark ? '#374151' : '#f0f0f0'
  const chartTick = isDark ? '#9ca3af' : '#9ca3af'
  const chartTickCat = isDark ? '#d1d5db' : '#6b7280'
  const tooltipStyle = {
    fontSize: 11,
    borderRadius: 8,
    border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
    backgroundColor: isDark ? '#1f2937' : '#fff',
    color: isDark ? '#f9fafb' : '#111827',
  }

  // ── Sub-components (need t / locale in scope) ─────────────────────────────

  function GroupByToggle({ value, onChange }) {
    return (
      <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-0.5">
        {GROUP_OPTIONS.map(opt => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
              value === opt.value
                ? 'bg-white dark:bg-gray-600 text-indigo-600 dark:text-indigo-400 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    )
  }

  function ChartTypeToggle({ value, onChange }) {
    return (
      <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-0.5">
        <button
          onClick={() => onChange('area')}
          className={`px-2 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
            value === 'area' ? 'bg-white dark:bg-gray-600 text-indigo-600 dark:text-indigo-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
          }`}
          title={t('common.linea')}
        >
          📈
        </button>
        <button
          onClick={() => onChange('bar')}
          className={`px-2 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer ${
            value === 'bar' ? 'bg-white dark:bg-gray-600 text-indigo-600 dark:text-indigo-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
          }`}
          title={t('common.barras')}
        >
          📊
        </button>
      </div>
    )
  }

  // Shared chart components based on chartType
  function renderTimeSeries(data, config) {
    if (data.length === 0) {
      return <p className="text-sm text-gray-400 dark:text-gray-500 h-[220px] flex items-center justify-center">{config.emptyMsg}</p>
    }

    return (
      <ResponsiveContainer width="100%" height={220}>
        {chartType === 'area' ? (
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              {config.areas.map(a => (
                <linearGradient key={a.key} id={a.gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={a.color} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={a.color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
            <XAxis dataKey="fecha" tickFormatter={tickFmt} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} interval="preserveStartEnd" />
            <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} axisLine={false} width={45} />
            <Tooltip labelFormatter={tickFmt} formatter={v => formatCurrency(v)} contentStyle={tooltipStyle} />
            {config.areas.length > 1 && <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />}
            {config.areas.map(a => (
              <Area key={a.key} type="monotone" dataKey={a.key} stroke={a.color} fill={`url(#${a.gradId})`} strokeWidth={2} name={a.name} />
            ))}
          </AreaChart>
        ) : (
          <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} />
            <XAxis dataKey="fecha" tickFormatter={tickFmt} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} interval="preserveStartEnd" />
            <YAxis tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 10, fill: chartTick }} tickLine={false} axisLine={false} width={45} />
            <Tooltip labelFormatter={tickFmt} formatter={v => formatCurrency(v)} contentStyle={tooltipStyle} />
            {config.areas.length > 1 && <Legend iconType="square" wrapperStyle={{ fontSize: 12 }} />}
            {config.areas.map(a => (
              <Bar key={a.key} dataKey={a.key} fill={a.color} radius={[3, 3, 0, 0]} name={a.name} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    )
  }

  const timeControls = (
    <>
      <GroupByToggle value={groupBy} onChange={setGroupBy} />
      <ChartTypeToggle value={chartType} onChange={setChartType} />
    </>
  )

  return (
    <div className="p-6 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('dashboard.title')}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{t('dashboard.subtitle')}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2 mt-1">
          <select
            value={usingCustomDates ? 'all' : period}
            onChange={e => handlePeriodChange(e.target.value)}
            disabled={!!usingCustomDates}
            className={`text-sm bg-white dark:bg-gray-800 border rounded-lg px-3 py-2 shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-indigo-300 ${
              usingCustomDates
                ? 'border-gray-100 dark:border-gray-700 text-gray-300 dark:text-gray-600 cursor-not-allowed'
                : 'border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-200'
            }`}
          >
            {PERIODS.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>

          <span className="text-gray-300 dark:text-gray-600 text-sm select-none">|</span>

          <div className="flex items-center gap-1.5">
            <label className="text-xs text-gray-400 whitespace-nowrap">{t('common.desde')}</label>
            <input
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={e => handleDateFrom(e.target.value)}
              className="text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-2 text-gray-700 dark:text-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer"
            />
          </div>

          <div className="flex items-center gap-1.5">
            <label className="text-xs text-gray-400 whitespace-nowrap">{t('common.hasta')}</label>
            <input
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={e => handleDateTo(e.target.value)}
              className="text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-2 text-gray-700 dark:text-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 cursor-pointer"
            />
          </div>

          {usingCustomDates && (
            <button
              onClick={clearDates}
              title={t('common.limpiarFechas')}
              className="text-xs text-gray-400 hover:text-red-500 px-2 py-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 transition-colors cursor-pointer"
            >
              ✕ {t('common.limpiar')}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 text-sm">
          <p className="font-medium">{t('common.errorConexion')}</p>
          <p className="mt-0.5 text-red-600 dark:text-red-400">
            {error === 'connection' ? t('common.errorConexionMsg') : t('common.errorInesperado')}
          </p>
          <p className="mt-2 text-xs text-red-500 dark:text-red-500">
            {t('common.backendInstruccion')} <code className="bg-red-100 dark:bg-red-900 px-1 rounded">cd backend && uvicorn app.main:app --reload</code>
          </p>
        </div>
      )}

      {/* KPIs — Ventas */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">{t('dashboard.sections.ventas')}</h3>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard
            title={t('dashboard.kpi.ventasTotales')}
            value={formatCurrency(salesStats?.total_ventas)}
            subtitle={t('dashboard.kpi.transacciones', { n: salesStats?.cantidad_transacciones ?? '—' })}
            icon="💰"
            color="green"
            loading={loading}
          />
          <KpiCard
            title={t('dashboard.kpi.ticketPromedio')}
            value={formatCurrency(salesStats?.ticket_promedio)}
            icon="🧾"
            color="blue"
            loading={loading}
          />
          <KpiCard
            title={t('dashboard.kpi.topProducto')}
            value={salesStats?.producto_mas_vendido ?? '—'}
            subtitle={salesStats?.categoria_principal ?? ''}
            icon="⭐"
            color="purple"
            loading={loading}
          />
          <KpiCard
            title={t('dashboard.kpi.clientesActivos')}
            value={clientesStats?.clientes_activos ?? '—'}
            subtitle={t('dashboard.kpi.registrados', { n: clientesStats?.total_clientes ?? '—' })}
            icon="👥"
            color="blue"
            loading={loading}
          />
        </div>
      </section>

      {/* KPIs — Gastos e Inventario */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">{t('dashboard.sections.gastosInventario')}</h3>
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard
            title={t('dashboard.kpi.gastosTotales')}
            value={formatCurrency(gastosStats?.monto_total)}
            subtitle={t('dashboard.kpi.transacciones', { n: gastosStats?.total_gastos ?? '—' })}
            icon="💸"
            color="red"
            loading={loading}
          />
          <KpiCard
            title={t('dashboard.kpi.margenEstimado')}
            value={
              salesStats?.total_ventas && gastosStats?.monto_total
                ? formatCurrency(salesStats.total_ventas - gastosStats.monto_total)
                : '—'
            }
            subtitle={t('dashboard.kpi.ventasMenosGastos')}
            icon="📈"
            color="green"
            loading={loading}
          />
          <KpiCard
            title={t('dashboard.kpi.productosStock')}
            value={inventarioStats?.total_items ?? '—'}
            icon="🏬"
            color="blue"
            loading={loading}
          />
          <KpiCard
            title={t('dashboard.kpi.stockBajo')}
            value={inventarioStats?.bajo_stock ?? '—'}
            subtitle={t('dashboard.kpi.requierenReposicion')}
            icon="⚠️"
            color="yellow"
            loading={loading}
          />
        </div>
      </section>

      {/* Gráficas */}
      <section className="mb-8">
        <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">{t('dashboard.sections.resumenVisual')}</h3>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

          {/* Ventas por período */}
          <ChartCard title={t('dashboard.charts.ventas')} loading={isTimeLoading} controls={timeControls}>
            {renderTimeSeries(ventasSerie, {
              emptyMsg: t('dashboard.empty.ventas'),
              areas: [{ key: 'total', color: '#10b981', gradId: 'gradVentasDash', name: t('dashboard.charts.ventas') }],
            })}
          </ChartCard>

          {/* Gastos por categoría */}
          <ChartCard title={t('dashboard.charts.gastosPorCategoria')} loading={loading}>
            {gastosCat.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500 h-[220px] flex items-center justify-center">{t('dashboard.empty.gastos')}</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={gastosCat} layout="vertical" margin={{ left: 10, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} horizontal={false} />
                  <XAxis type="number" tickFormatter={v => formatCurrency(v)} tick={{ fontSize: 11, fill: chartTick }} />
                  <YAxis
                    type="category"
                    dataKey="categoria"
                    width={90}
                    tick={{ fontSize: 11, fill: chartTickCat }}
                    tickFormatter={v => v.length > 12 ? v.slice(0, 12) + '…' : v}
                  />
                  <Tooltip formatter={v => formatCurrency(v)} contentStyle={tooltipStyle} />
                  <Bar dataKey="total" radius={[0, 4, 4, 0]} name="Total">
                    {gastosCat.map((_, i) => (
                      <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          {/* Top 5 productos */}
          <ChartCard title={t('dashboard.charts.top5Productos')} loading={loading}>
            {topProductos.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-gray-500 h-[220px] flex items-center justify-center">{t('dashboard.empty.productos')}</p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={topProductos} layout="vertical" margin={{ left: 10, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} horizontal={false} />
                  <XAxis type="number" tickFormatter={v => formatCurrency(v)} tick={{ fontSize: 11, fill: chartTick }} />
                  <YAxis
                    type="category"
                    dataKey="nombre"
                    width={90}
                    tick={{ fontSize: 11, fill: chartTickCat }}
                    tickFormatter={v => v.length > 12 ? v.slice(0, 12) + '…' : v}
                  />
                  <Tooltip formatter={v => formatCurrency(v)} contentStyle={tooltipStyle} />
                  <Bar dataKey="monto_total" radius={[0, 4, 4, 0]} name="Monto">
                    {topProductos.map((_, i) => (
                      <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          {/* Ventas vs Gastos */}
          <ChartCard title={t('dashboard.charts.ventasVsGastos')} loading={isTimeLoading} controls={timeControls}>
            {renderTimeSeries(ventasVsGastos, {
              emptyMsg: t('dashboard.empty.comparar'),
              areas: [
                { key: 'ventas', color: '#10b981', gradId: 'gradVsVentas', name: t('dashboard.charts.ventas') },
                { key: 'gastos', color: '#f43f5e', gradId: 'gradVsGastos', name: t('dashboard.charts.gastos') },
              ],
            })}
          </ChartCard>

        </div>
      </section>

      {/* Alertas */}
      <section>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h3 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {t('dashboard.alertas.title')} {noLeidasCount > 0 && <span className="text-xs bg-red-500 text-white rounded-full px-1.5 py-0.5 ml-1.5 normal-case">{noLeidasCount}</span>}
          </h3>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {ALERT_FILTERS.map(f => (
                <button
                  key={f.id}
                  onClick={() => setAlertFilter(f.id)}
                  className={`text-xs px-2.5 py-1 rounded-lg border transition-colors cursor-pointer ${
                    alertFilter === f.id
                      ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-900 border-gray-800 dark:border-gray-200'
                      : 'bg-white dark:bg-gray-800 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            {noLeidasCount > 1 && (
              <button
                onClick={handleMarcarTodasLeidas}
                className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 rounded-lg px-2.5 py-1 transition-colors cursor-pointer"
              >
                {t('dashboard.alertas.marcarTodas')}
              </button>
            )}
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-gray-100 dark:bg-gray-800 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : filteredAlerts.length === 0 ? (
          <div className="p-4 bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 text-sm text-gray-500 dark:text-gray-400">
            {alertFilter === 'todas'
              ? t('dashboard.alertas.sinAlertas')
              : t('dashboard.alertas.sinAlertasFiltro')}
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
