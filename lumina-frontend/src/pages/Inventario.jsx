import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { inventarioService } from '../services/api'
import useWatcherRefresh from '../hooks/useWatcherRefresh'
import SectionAlerts from '../components/SectionAlerts'

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtCurrency(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('es-MX', {
    style: 'currency', currency: 'MXN', maximumFractionDigits: 0,
  }).format(value)
}

function fmtNum(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('es-MX').format(value)
}

// ── Constantes ────────────────────────────────────────────────────────────────

const CATEGORY_COLORS = ['#3b82f6', '#6366f1', '#22d3ee', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6']

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiMini({ title, value, subtitle, icon, color }) {
  const colors = {
    blue:   'text-blue-600 bg-blue-50 border-blue-100',
    green:  'text-green-600 bg-green-50 border-green-100',
    indigo: 'text-indigo-600 bg-indigo-50 border-indigo-100',
    amber:  'text-amber-600 bg-amber-50 border-amber-100',
    red:    'text-red-600 bg-red-50 border-red-100',
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

function StockBadge({ actual, minimo }) {
  if (minimo == null) {
    return <span className="text-xs text-gray-400">Sin mín.</span>
  }
  if (actual <= minimo) {
    return (
      <span className="text-xs bg-red-50 text-red-700 px-2 py-0.5 rounded-full font-medium">
        ⚠ Bajo stock
      </span>
    )
  }
  return (
    <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">
      OK
    </span>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

function Inventario() {
  const [items, setItems] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filtros
  const [search, setSearch] = useState('')
  const [soloAlerta, setSoloAlerta] = useState(false)
  const [catFilter, setCatFilter] = useState('all')
  const [refreshKey, setRefreshKey] = useState(0)
  useWatcherRefresh(useCallback(() => setRefreshKey(k => k + 1), []))

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      setError(null)
      const [itemsRes, analyticsRes] = await Promise.allSettled([
        inventarioService.getAll(),
        inventarioService.getAnalytics(),
      ])
      if (itemsRes.status === 'fulfilled') setItems(itemsRes.value.data)
      if (analyticsRes.status === 'fulfilled') setAnalytics(analyticsRes.value.data)
      if (itemsRes.status === 'rejected') setError('No se pudo conectar con la API.')
      setLoading(false)
    }
    fetchData()
  }, [refreshKey])

  // Categorías únicas para el filtro
  const categorias = useMemo(() => {
    const set = new Set(items.map(i => i.categoria).filter(Boolean))
    return ['all', ...Array.from(set).sort()]
  }, [items])

  // Items filtrados
  const filteredItems = useMemo(() => {
    return items.filter(item => {
      if (soloAlerta) {
        if (item.cantidad_minima == null || item.cantidad_actual > item.cantidad_minima) return false
      }
      if (catFilter !== 'all' && item.categoria !== catFilter) return false
      if (search) {
        const q = search.toLowerCase()
        return (
          item.nombre_producto?.toLowerCase().includes(q) ||
          item.producto_id?.toLowerCase().includes(q) ||
          item.categoria?.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [items, soloAlerta, catFilter, search])

  // KPIs from backend analytics
  const kpis = analytics ? {
    totalProductos: analytics.total_productos,
    bajosStock: analytics.bajos_stock,
    totalUnidades: analytics.total_unidades,
    categoriasCuenta: analytics.categorias_count,
  } : { totalProductos: 0, bajosStock: 0, totalUnidades: 0, categoriasCuenta: 0 }

  // Stock por categoría
  const stockPorCategoria = useMemo(() => {
    if (!items.length) return []
    const map = {}
    items.forEach(i => {
      const cat = i.categoria || 'Sin categoría'
      if (!map[cat]) map[cat] = 0
      map[cat] += i.cantidad_actual || 0
    })
    return Object.entries(map)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8)
      .map(([categoria, cantidad]) => ({ categoria, cantidad }))
  }, [items])

  // Valor por categoría (precio_venta * cantidad_actual)
  const valorPorCategoria = useMemo(() => {
    if (!items.length) return []
    const map = {}
    items.forEach(i => {
      if (i.precio_venta == null) return
      const cat = i.categoria || 'Sin categoría'
      if (!map[cat]) map[cat] = 0
      map[cat] += (i.precio_venta * i.cantidad_actual) || 0
    })
    return Object.entries(map)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8)
      .map(([categoria, valor]) => ({ categoria, valor: Math.round(valor) }))
  }, [items])

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
          <h2 className="text-2xl font-bold text-gray-900">Inventario</h2>
          <p className="text-sm text-gray-500 mt-0.5">Estado actual del stock de productos</p>
        </div>

        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-2 mt-1">
          {/* Búsqueda */}
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-xs">🔍</span>
            <input
              type="text"
              placeholder="Buscar producto..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="text-sm bg-white border border-gray-200 rounded-lg pl-7 pr-3 py-2 text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-300 w-44"
            />
          </div>

          {/* Filtro por categoría */}
          {categorias.length > 1 && (
            <select
              value={catFilter}
              onChange={e => setCatFilter(e.target.value)}
              className="text-sm bg-white border border-gray-200 rounded-lg px-3 py-2 text-gray-700 shadow-sm cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
              <option value="all">Todas las categorías</option>
              {categorias.filter(c => c !== 'all').map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          )}

          {/* Toggle bajo stock */}
          <button
            onClick={() => setSoloAlerta(v => !v)}
            className={`text-sm px-3 py-2 rounded-lg border transition-colors cursor-pointer ${
              soloAlerta
                ? 'bg-red-50 border-red-200 text-red-700 font-medium'
                : 'bg-white border-gray-200 text-gray-500 hover:border-red-200 hover:text-red-600'
            }`}
          >
            ⚠ Solo bajo stock {soloAlerta && kpis.bajosStock > 0 ? `(${kpis.bajosStock})` : ''}
          </button>

          {/* Limpiar filtros */}
          {(search || soloAlerta || catFilter !== 'all') && (
            <button
              onClick={() => { setSearch(''); setSoloAlerta(false); setCatFilter('all') }}
              className="text-xs text-gray-400 hover:text-red-500 px-2 py-2 rounded-lg hover:bg-red-50 transition-colors cursor-pointer"
            >
              ✕ Limpiar
            </button>
          )}
        </div>
      </div>

      <SectionAlerts tipo="inventario" refreshKey={refreshKey} />

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
          {error}
        </div>
      )}

      {items.length === 0 && !error ? (
        <div className="p-8 bg-gray-50 border border-dashed border-gray-300 rounded-xl text-center text-gray-500">
          <p className="text-4xl mb-3">📦</p>
          <p className="font-medium">Sin datos de inventario</p>
          <p className="text-sm mt-1">Carga un CSV en Configuración para comenzar.</p>
        </div>
      ) : (
        <>
          {/* KPIs globales */}
          <section className="mb-8">
            <SectionTitle>Resumen general</SectionTitle>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <KpiMini
                title="Productos"
                value={fmtNum(kpis.totalProductos)}
                subtitle={`${kpis.categoriasCuenta} categorías`}
                icon="📦"
                color="blue"
              />
              <KpiMini
                title="Unidades en stock"
                value={fmtNum(kpis.totalUnidades)}
                icon="🏬"
                color="indigo"
              />
              <KpiMini
                title="Valor (venta)"
                value={fmtCurrency(analytics?.valor_inventario_venta)}
                icon="💵"
                color="green"
              />
              <KpiMini
                title="Costo (compra)"
                value={fmtCurrency(analytics?.costo_inventario)}
                icon="💳"
                color="amber"
              />
              <KpiMini
                title="Bajo stock"
                value={kpis.bajosStock}
                subtitle="requieren reposición"
                icon="⚠️"
                color={kpis.bajosStock > 0 ? 'red' : 'blue'}
              />
            </div>
          </section>

          {/* Gráficas */}
          <section className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Stock por categoría */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Unidades en stock por categoría</SectionTitle>
              {stockPorCategoria.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={stockPorCategoria}
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
                      dataKey="categoria"
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      tickLine={false}
                      axisLine={false}
                      width={85}
                    />
                    <Tooltip
                      formatter={v => [fmtNum(v), 'Unidades']}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    />
                    <Bar dataKey="cantidad" radius={[0, 4, 4, 0]}>
                      {stockPorCategoria.map((_, i) => (
                        <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 mt-4">Sin datos de categorías.</p>
              )}
            </div>

            {/* Valor por categoría */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <SectionTitle>Valor en stock por categoría</SectionTitle>
              {valorPorCategoria.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={valorPorCategoria}
                    layout="vertical"
                    margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
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
                      dataKey="categoria"
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      tickLine={false}
                      axisLine={false}
                      width={85}
                    />
                    <Tooltip
                      formatter={v => [fmtCurrency(v), 'Valor']}
                      contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #e5e7eb' }}
                    />
                    <Bar dataKey="valor" radius={[0, 4, 4, 0]} fill="#10b981" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 mt-4">Sin precios de venta registrados.</p>
              )}
            </div>
          </section>

          {/* Tabla de productos */}
          <section>
            <SectionTitle>
              Productos
              {filteredItems.length !== items.length
                ? ` — ${filteredItems.length} de ${items.length}`
                : ` — ${items.length} en total`}
            </SectionTitle>

            {filteredItems.length === 0 ? (
              <div className="p-6 bg-gray-50 border border-dashed border-gray-200 rounded-xl text-center text-gray-400 text-sm">
                Sin productos que coincidan con los filtros.
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Producto</th>
                      <th className="text-left px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Categoría</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Stock</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Mín.</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">P. Compra</th>
                      <th className="text-right px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">P. Venta</th>
                      <th className="text-center px-4 py-3 text-xs font-semibold text-gray-400 uppercase tracking-wide">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item, i) => {
                      const esBajo = item.cantidad_minima != null && item.cantidad_actual <= item.cantidad_minima
                      return (
                        <tr
                          key={item.id ?? i}
                          className={`border-b border-gray-50 hover:bg-gray-50 transition-colors ${esBajo ? 'bg-red-50/30' : ''}`}
                        >
                          <td className="px-4 py-2.5">
                            <p className="font-medium text-gray-800 truncate max-w-44">{item.nombre_producto}</p>
                            <p className="text-xs text-gray-400 font-mono">{item.producto_id}</p>
                          </td>
                          <td className="px-4 py-2.5">
                            {item.categoria ? (
                              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                                {item.categoria}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-300">—</span>
                            )}
                          </td>
                          <td className={`px-4 py-2.5 text-right font-semibold ${esBajo ? 'text-red-600' : 'text-gray-800'}`}>
                            {fmtNum(item.cantidad_actual)}
                            {item.unidad_medida && (
                              <span className="text-xs text-gray-400 font-normal ml-1">{item.unidad_medida}</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-right text-gray-500">
                            {item.cantidad_minima != null ? fmtNum(item.cantidad_minima) : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-right text-gray-600">
                            {item.precio_compra != null ? fmtCurrency(item.precio_compra) : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-right text-gray-800 font-medium">
                            {item.precio_venta != null ? fmtCurrency(item.precio_venta) : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            <StockBadge actual={item.cantidad_actual} minimo={item.cantidad_minima} />
                          </td>
                        </tr>
                      )
                    })}
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

export default Inventario
