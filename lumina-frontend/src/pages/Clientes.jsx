import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { clientesService } from '../services/api'
import useWatcherRefresh from '../hooks/useWatcherRefresh'
import SectionAlerts from '../components/SectionAlerts'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtNum(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('es-MX').format(value)
}

function fmtDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (isNaN(d)) return value
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })
}

// ── Constantes ────────────────────────────────────────────────────────────────

const TYPE_COLORS = ['#8b5cf6', '#6366f1', '#a78bfa', '#7c3aed', '#c4b5fd', '#4f46e5', '#ddd6fe']

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiMini({ title, value, subtitle, icon, color }) {
  const colors = {
    purple: 'text-purple-600 bg-purple-50 border-purple-100',
    indigo: 'text-indigo-600 bg-indigo-50 border-indigo-100',
    violet: 'text-violet-600 bg-violet-50 border-violet-100',
    green:  'text-green-600 bg-green-50 border-green-100',
    gray:   'text-gray-600 bg-gray-50 border-gray-200',
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

function ActivoBadge({ activo }) {
  if (activo) {
    return (
      <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">
        Activo
      </span>
    )
  }
  return (
    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
      Inactivo
    </span>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function Clientes() {
  const [clientes, setClientes] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

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
      if (clientesRes.status === 'rejected') setError('No se pudo conectar con la API.')
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
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Clientes</h2>
          <p className="text-sm text-gray-500 mt-0.5">Directorio y segmentación de clientes</p>
        </div>

        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-2 mt-1">
          {/* Búsqueda */}
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">🔍</span>
            <input
              type="text"
              placeholder="Buscar cliente..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="text-sm bg-white border border-gray-200 rounded-lg pl-7 pr-3 py-2 text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-300 w-44"
            />
          </div>

          {/* Filtro por tipo */}
          {tipos.length > 1 && (
            <select
              value={tipoFilter}
              onChange={e => setTipoFilter(e.target.value)}
              className="text-sm bg-white border border-gray-200 rounded-lg px-3 py-2 text-gray-700 shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-300"
            >
              <option value="all">Todos los tipos</option>
              {tipos.filter(t => t !== 'all').map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          )}

          {/* Toggle activo */}
          <div className="flex rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden text-sm">
            {['todos', 'activos', 'inactivos'].map(opt => (
              <button
                key={opt}
                onClick={() => setActivoFilter(opt)}
                className={`px-3 py-2 capitalize cursor-pointer transition-colors ${
                  activoFilter === opt
                    ? 'bg-purple-600 text-white font-medium'
                    : 'text-gray-500 hover:bg-gray-50'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>

          {/* Limpiar filtros */}
          {activeFilters && (
            <button
              onClick={() => { setSearch(''); setTipoFilter('all'); setActivoFilter('activos') }}
              className="text-xs text-gray-400 hover:text-red-500 px-2 py-2 rounded-lg hover:bg-red-50 transition-colors cursor-pointer"
            >
              ✕ Limpiar
            </button>
          )}
        </div>
      </div>

      <SectionAlerts tipo="clientes" refreshKey={refreshKey} />

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {clientes.length === 0 && !error ? (
        <div className="p-8 bg-gray-50 border border-dashed border-gray-300 rounded-xl text-center text-gray-500">
          <p className="text-4xl mb-3">👥</p>
          <p className="font-medium">Sin datos de clientes</p>
          <p className="text-sm mt-1">Carga un CSV en Configuración para comenzar.</p>
        </div>
      ) : (
        <>
          {/* KPIs globales */}
          <section className="mb-8">
            <SectionTitle>Resumen general</SectionTitle>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <KpiMini
                title="Total clientes"
                value={fmtNum(analytics?.total_clientes ?? clientes.length)}
                icon="👥"
                color="purple"
              />
              <KpiMini
                title="Activos"
                value={fmtNum(analytics?.clientes_activos)}
                subtitle="en operación"
                icon="✅"
                color="green"
              />
              <KpiMini
                title="Inactivos"
                value={fmtNum(analytics?.clientes_inactivos)}
                icon="💤"
                color="gray"
              />
              <KpiMini
                title="Tipos"
                value={fmtNum(clientesPorTipo.length)}
                subtitle="segmentos"
                icon="🏷️"
                color="indigo"
              />
              <KpiMini
                title="Ciudades"
                value={fmtNum(ciudadesUnicas)}
                subtitle="con presencia"
                icon="📍"
                color="violet"
              />
            </div>
          </section>

          {/* Gráficas */}
          <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Clientes por tipo */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Clientes por tipo</SectionTitle>
              {clientesPorTipo.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={clientesPorTipo}
                    layout="vertical"
                    margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="tipo"
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      tickLine={false}
                      axisLine={false}
                      width={90}
                    />
                    <Tooltip
                      formatter={v => [fmtNum(v), 'Clientes']}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    />
                    <Bar dataKey="cantidad" radius={[0, 4, 4, 0]}>
                      {clientesPorTipo.map((_, i) => (
                        <Cell key={i} fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 mt-4">Sin datos de tipos.</p>
              )}
            </div>

            {/* Top ciudades */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Top ciudades</SectionTitle>
              {clientesPorCiudad.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={clientesPorCiudad}
                    layout="vertical"
                    margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                    <XAxis
                      type="number"
                      tick={{ fontSize: 10, fill: '#9ca3af' }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="ciudad"
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      tickLine={false}
                      axisLine={false}
                      width={90}
                    />
                    <Tooltip
                      formatter={v => [fmtNum(v), 'Clientes']}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    />
                    <Bar dataKey="cantidad" radius={[0, 4, 4, 0]} fill="#a78bfa" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 mt-4">Sin datos de ciudades.</p>
              )}
            </div>
          </section>

          {/* Tabla de clientes */}
          <section>
            <SectionTitle>
              Clientes
              {filteredClientes.length !== clientes.length
                ? ` — ${filteredClientes.length} de ${clientes.length}`
                : ` — ${clientes.length} en total`}
            </SectionTitle>

            {filteredClientes.length === 0 ? (
              <div className="p-6 bg-gray-50 border border-dashed border-gray-200 rounded-xl text-center text-gray-400 text-sm">
                Sin clientes que coincidan con los filtros.
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Cliente</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Tipo</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Ciudad</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Email</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Registro</th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredClientes.map((c, i) => (
                      <tr
                        key={c.id ?? i}
                        className={`border-b border-gray-50 hover:bg-gray-50 transition-colors ${!c.activo ? 'opacity-60' : ''}`}
                      >
                        <td className="px-4 py-2.5">
                          <p className="font-medium text-gray-800 truncate max-w-44">{c.nombre}</p>
                          <p className="text-xs text-gray-400 font-mono">{c.cliente_id}</p>
                        </td>
                        <td className="px-4 py-2.5">
                          {c.tipo_cliente ? (
                            <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
                              {c.tipo_cliente}
                            </span>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-gray-600">
                          {c.ciudad || <span className="text-gray-300">—</span>}
                        </td>
                        <td className="px-4 py-2.5 text-gray-500 truncate max-w-40">
                          {c.email || <span className="text-gray-300">—</span>}
                        </td>
                        <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap">
                          {fmtDate(c.fecha_registro)}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <ActivoBadge activo={c.activo} />
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
