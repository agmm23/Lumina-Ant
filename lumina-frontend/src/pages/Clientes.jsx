import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { clientesService } from '../services/api'
import useWatcherRefresh from '../hooks/useWatcherRefresh'
import SectionAlerts from '../components/SectionAlerts'
import { useDark } from '../contexts/ThemeContext'
import { useLanguage } from '../contexts/LanguageContext'

// ── Constantes ────────────────────────────────────────────────────────────────

const TYPE_COLORS = ['#8b5cf6', '#6366f1', '#a78bfa', '#7c3aed', '#c4b5fd', '#4f46e5', '#ddd6fe']

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiMini({ title, value, subtitle, icon, color }) {
  const colors = {
    purple: 'text-purple-600 bg-purple-50 border-purple-100 dark:text-purple-400 dark:bg-purple-950 dark:border-purple-800',
    indigo: 'text-indigo-600 bg-indigo-50 border-indigo-100 dark:text-indigo-400 dark:bg-indigo-950 dark:border-indigo-800',
    violet: 'text-violet-600 bg-violet-50 border-violet-100 dark:text-violet-400 dark:bg-violet-950 dark:border-violet-800',
    green:  'text-green-600 bg-green-50 border-green-100 dark:text-green-400 dark:bg-green-950 dark:border-green-800',
    gray:   'text-gray-600 bg-gray-50 border-gray-200 dark:text-gray-400 dark:bg-gray-800 dark:border-gray-700',
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

function ActivoBadge({ activo, t }) {
  if (activo) {
    return (
      <span className="text-xs bg-green-50 dark:bg-green-900 text-green-700 dark:text-green-400 px-2 py-0.5 rounded-full">
        {t('clientes.table.activo')}
      </span>
    )
  }
  return (
    <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 px-2 py-0.5 rounded-full">
      {t('clientes.table.inactivo')}
    </span>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function Clientes() {
  const { isDark } = useDark()
  const { t, locale } = useLanguage()
  const [clientes, setClientes] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Helpers (use locale from context)
  function fmtNum(value) {
    if (value == null) return '—'
    return new Intl.NumberFormat(locale).format(value)
  }

  function fmtDate(value) {
    if (!value) return '—'
    const d = new Date(value)
    if (isNaN(d)) return value
    return d.toLocaleDateString(locale, { day: '2-digit', month: 'short', year: 'numeric' })
  }

  // Filtros
  const [search, setSearch] = useState('')
  const [tipoFilter, setTipoFilter] = useState('all')
  const [activoFilter, setActivoFilter] = useState('activos')
  const [refreshKey, setRefreshKey] = useState(0)
  useWatcherRefresh(useCallback(() => setRefreshKey(k => k + 1), []))

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)
      const [clientesRes, analyticsRes] = await Promise.allSettled([
        clientesService.getAll({ solo_activos: false }),
        clientesService.getAnalytics(),
      ])
      if (clientesRes.status === 'fulfilled') setClientes(clientesRes.value.data)
      if (analyticsRes.status === 'fulfilled') setAnalytics(analyticsRes.value.data)
      if (clientesRes.status === 'rejected') setError(t('common.errorConexionMsg'))
      setLoading(false)
    }
    fetchData()
  }, [refreshKey])

  // Tipos únicos para el filtro
  const tipos = useMemo(() => {
    const set = new Set(clientes.map(c => c.tipo_cliente).filter(Boolean))
    return ['all', ...Array.from(set).sort()]
  }, [clientes])

  // Clientes filtrados
  const filteredClientes = useMemo(() => {
    return clientes.filter(c => {
      if (activoFilter === 'activos' && !c.activo) return false
      if (activoFilter === 'inactivos' && c.activo) return false
      if (tipoFilter !== 'all' && c.tipo_cliente !== tipoFilter) return false
      if (search) {
        const q = search.toLowerCase()
        return (
          c.nombre?.toLowerCase().includes(q) ||
          c.cliente_id?.toLowerCase().includes(q) ||
          c.ciudad?.toLowerCase().includes(q) ||
          c.email?.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [clientes, activoFilter, tipoFilter, search])

  // Charts from analytics
  const clientesPorTipo = analytics?.por_tipo ?? []
  const clientesPorCiudad = analytics?.por_ciudad ?? []
  const ciudadesUnicas = clientesPorCiudad.length

  const activeFilters = search || tipoFilter !== 'all' || activoFilter !== 'activos'

  // Filter toggle labels
  const filterLabels = {
    todos: t('clientes.todos'),
    activos: t('clientes.activos'),
    inactivos: t('clientes.inactivos'),
  }

  // Chart colors for dark mode
  const chartGrid = isDark ? '#374151' : '#f0f0f0'
  const chartTick = isDark ? '#9ca3af' : '#9ca3af'
  const chartTickCat = isDark ? '#d1d5db' : '#6b7280'
  const tooltipStyle = { fontSize: 11, borderRadius: 8, border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`, backgroundColor: isDark ? '#1f2937' : '#fff', color: isDark ? '#f9fafb' : '#111827' }

  if (loading) {
    return (
      <div className="p-6 max-w-6xl space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-32 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('clientes.title')}</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{t('clientes.subtitle')}</p>
        </div>

        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-2 mt-1">
          {/* Búsqueda */}
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">🔍</span>
            <input
              type="text"
              placeholder={t('clientes.buscarCliente')}
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg pl-7 pr-3 py-2 text-gray-700 dark:text-gray-200 shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-300 w-44"
            />
          </div>

          {/* Filtro por tipo */}
          {tipos.length > 1 && (
            <select
              value={tipoFilter}
              onChange={e => setTipoFilter(e.target.value)}
              className="text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 text-gray-700 dark:text-gray-200 shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-300"
            >
              <option value="all">{t('clientes.todosTipos')}</option>
              {tipos.filter(tp => tp !== 'all').map(tp => (
                <option key={tp} value={tp}>{tp}</option>
              ))}
            </select>
          )}

          {/* Toggle activo */}
          <div className="flex rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-sm overflow-hidden text-sm">
            {['todos', 'activos', 'inactivos'].map(opt => (
              <button
                key={opt}
                onClick={() => setActivoFilter(opt)}
                className={`px-3 py-2 capitalize cursor-pointer transition-colors ${
                  activoFilter === opt
                    ? 'bg-purple-600 text-white font-medium'
                    : 'text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
              >
                {filterLabels[opt]}
              </button>
            ))}
          </div>

          {/* Limpiar filtros */}
          {activeFilters && (
            <button
              onClick={() => { setSearch(''); setTipoFilter('all'); setActivoFilter('activos') }}
              className="text-xs text-gray-400 hover:text-red-500 px-2 py-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-950 transition-colors cursor-pointer"
            >
              ✕ {t('common.limpiar')}
            </button>
          )}
        </div>
      </div>

      <SectionAlerts tipo="clientes" refreshKey={refreshKey} />

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      {clientes.length === 0 && !error ? (
        <div className="p-8 bg-gray-50 dark:bg-gray-800 border border-dashed border-gray-300 dark:border-gray-600 rounded-xl text-center text-gray-500 dark:text-gray-400">
          <p className="text-4xl mb-3">👥</p>
          <p className="font-medium">{t('clientes.empty.sinDatos')}</p>
          <p className="text-sm mt-1">{t('clientes.empty.cargaCSV')}</p>
        </div>
      ) : (
        <>
          {/* KPIs globales */}
          <section className="mb-8">
            <SectionTitle>{t('clientes.sections.resumenGeneral')}</SectionTitle>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <KpiMini
                title={t('clientes.kpi.totalClientes')}
                value={fmtNum(analytics?.total_clientes ?? clientes.length)}
                icon="👥"
                color="purple"
              />
              <KpiMini
                title={t('clientes.kpi.activos')}
                value={fmtNum(analytics?.clientes_activos)}
                subtitle={t('clientes.kpi.enOperacion')}
                icon="✅"
                color="green"
              />
              <KpiMini
                title={t('clientes.kpi.inactivos')}
                value={fmtNum(analytics?.clientes_inactivos)}
                icon="💤"
                color="gray"
              />
              <KpiMini
                title={t('clientes.kpi.tipos')}
                value={fmtNum(clientesPorTipo.length)}
                subtitle={t('clientes.kpi.segmentos')}
                icon="🏷️"
                color="indigo"
              />
              <KpiMini
                title={t('clientes.kpi.ciudades')}
                value={fmtNum(ciudadesUnicas)}
                subtitle={t('clientes.kpi.conPresencia')}
                icon="📍"
                color="violet"
              />
            </div>
          </section>

          {/* Gráficas */}
          <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Clientes por tipo */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <SectionTitle>{t('clientes.sections.porTipo')}</SectionTitle>
              {clientesPorTipo.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={clientesPorTipo} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10, fill: chartTick }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="tipo" tick={{ fontSize: 10, fill: chartTickCat }} tickLine={false} axisLine={false} width={90} />
                    <Tooltip formatter={v => [fmtNum(v), t('clientes.sections.clientes')]} contentStyle={tooltipStyle} />
                    <Bar dataKey="cantidad" radius={[0, 4, 4, 0]}>
                      {clientesPorTipo.map((_, i) => (
                        <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 dark:text-gray-500 mt-4">{t('clientes.empty.sinTipos')}</p>
              )}
            </div>

            {/* Top ciudades */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <SectionTitle>{t('clientes.sections.topCiudades')}</SectionTitle>
              {clientesPorCiudad.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={clientesPorCiudad} layout="vertical" margin={{ top: 0, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chartGrid} horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10, fill: chartTick }} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="ciudad" tick={{ fontSize: 10, fill: chartTickCat }} tickLine={false} axisLine={false} width={90} />
                    <Tooltip formatter={v => [fmtNum(v), t('clientes.sections.clientes')]} contentStyle={tooltipStyle} />
                    <Bar dataKey="cantidad" radius={[0, 4, 4, 0]} fill="#a78bfa" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 dark:text-gray-500 mt-4">{t('clientes.empty.sinCiudades')}</p>
              )}
            </div>
          </section>

          {/* Tabla de clientes */}
          <section>
            <SectionTitle>
              {t('clientes.sections.clientes')}
              {filteredClientes.length !== clientes.length
                ? ` ${t('clientes.filtroResumen', { filtered: filteredClientes.length, total: clientes.length })}`
                : ` ${t('clientes.filtroTotal', { total: clientes.length })}`}
            </SectionTitle>

            {filteredClientes.length === 0 ? (
              <div className="p-6 bg-gray-50 dark:bg-gray-800 border border-dashed border-gray-200 dark:border-gray-600 rounded-xl text-center text-gray-400 dark:text-gray-500 text-sm">
                {t('clientes.empty.sinResultados')}
              </div>
            ) : (
              <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('clientes.table.cliente')}</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('clientes.table.tipo')}</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('clientes.table.ciudad')}</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('clientes.table.email')}</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('clientes.table.registro')}</th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">{t('clientes.table.estado')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredClientes.map((c, i) => (
                      <tr
                        key={c.id ?? i}
                        className={`border-b border-gray-50 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${!c.activo ? 'opacity-60' : ''}`}
                      >
                        <td className="px-4 py-2.5">
                          <p className="font-medium text-gray-800 dark:text-gray-200 truncate max-w-44">{c.nombre}</p>
                          <p className="text-xs text-gray-400 dark:text-gray-500 font-mono">{c.cliente_id}</p>
                        </td>
                        <td className="px-4 py-2.5">
                          {c.tipo_cliente ? (
                            <span className="text-xs bg-purple-50 dark:bg-purple-900 text-purple-700 dark:text-purple-400 px-2 py-0.5 rounded-full">
                              {c.tipo_cliente}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-300 dark:text-gray-600">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">
                          {c.ciudad || <span className="text-gray-300 dark:text-gray-600">—</span>}
                        </td>
                        <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 truncate max-w-40">
                          {c.email || <span className="text-gray-300 dark:text-gray-600">—</span>}
                        </td>
                        <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                          {fmtDate(c.fecha_registro)}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <ActivoBadge activo={c.activo} t={t} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}

export default Clientes
