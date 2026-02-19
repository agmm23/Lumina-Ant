import { useState } from 'react'

const NIVEL_CONFIG = {
  critical: { label: 'Crítica',   bg: 'bg-red-50',    border: 'border-red-200',   text: 'text-red-700',   badge: 'bg-red-100 text-red-700',   dot: 'bg-red-500'   },
  warning:  { label: 'Aviso',     bg: 'bg-amber-50',  border: 'border-amber-200', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-700', dot: 'bg-amber-400' },
  info:     { label: 'Info',      bg: 'bg-blue-50',   border: 'border-blue-200',  text: 'text-blue-700',  badge: 'bg-blue-100 text-blue-700',  dot: 'bg-blue-400'  },
}

const TIPO_BADGE = {
  ventas:     'bg-green-100 text-green-700',
  gastos:     'bg-rose-100 text-rose-700',
  inventario: 'bg-blue-100 text-blue-700',
  clientes:   'bg-purple-100 text-purple-700',
}

function fmtDateTime(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (isNaN(d)) return value
  return d.toLocaleString('es-MX', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function AlertCard({ alerta, onMarcarLeida }) {
  const [marking, setMarking] = useState(false)
  const n = NIVEL_CONFIG[alerta.nivel] ?? NIVEL_CONFIG.info

  async function handleMarcar() {
    setMarking(true)
    try {
      await onMarcarLeida(alerta.id)
    } finally {
      setMarking(false)
    }
  }

  return (
    <div className={`rounded-xl border p-4 transition-opacity ${n.bg} ${n.border} ${alerta.leida ? 'opacity-50' : ''}`}>
      <div className="flex items-start gap-3">
        <div className="mt-1 flex-shrink-0">
          <span className={`inline-block w-2 h-2 rounded-full ${alerta.leida ? 'bg-gray-300' : n.dot}`} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${n.badge}`}>
              {n.label}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${TIPO_BADGE[alerta.tipo] ?? 'bg-gray-100 text-gray-600'}`}>
              {alerta.tipo}
            </span>
            {alerta.leida && (
              <span className="text-xs text-gray-400">Leída</span>
            )}
          </div>

          <p className={`text-sm font-medium ${n.text}`}>{alerta.mensaje}</p>

          <p className="text-xs text-gray-400 mt-1">{fmtDateTime(alerta.fecha_creacion)}</p>
        </div>

        {!alerta.leida && (
          <button
            onClick={handleMarcar}
            disabled={marking}
            className="flex-shrink-0 text-xs text-gray-400 hover:text-gray-700 border border-gray-200 hover:border-gray-300 bg-white rounded-lg px-2.5 py-1.5 transition-colors cursor-pointer disabled:opacity-50"
          >
            {marking ? '...' : 'Marcar leída'}
          </button>
        )}
      </div>
    </div>
  )
}
