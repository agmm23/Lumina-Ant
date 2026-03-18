import { useState } from 'react'
import { useLanguage } from '../contexts/LanguageContext'

const NIVEL_CONFIG = {
  critical: { key: 'critica',  bg: 'bg-red-50 dark:bg-red-950',    border: 'border-red-200 dark:border-red-800',   text: 'text-red-700 dark:text-red-400',   badge: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-400',   dot: 'bg-red-500'   },
  warning:  { key: 'aviso',    bg: 'bg-amber-50 dark:bg-amber-950',  border: 'border-amber-200 dark:border-amber-800', text: 'text-amber-700 dark:text-amber-400', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-400', dot: 'bg-amber-400' },
  info:     { key: 'info',     bg: 'bg-blue-50 dark:bg-blue-950',   border: 'border-blue-200 dark:border-blue-800',  text: 'text-blue-700 dark:text-blue-400',  badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-400',  dot: 'bg-blue-400'  },
}

const TIPO_BADGE = {
  ventas:     'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-400',
  gastos:     'bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-400',
  inventario: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-400',
  clientes:   'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-400',
}

export default function AlertCard({ alerta, onMarcarLeida }) {
  const [marking, setMarking] = useState(false)
  const { t, locale } = useLanguage()
  const n = NIVEL_CONFIG[alerta.nivel] ?? NIVEL_CONFIG.info

  function fmtDateTime(value) {
    if (!value) return '—'
    const d = new Date(value)
    if (isNaN(d)) return value
    return d.toLocaleString(locale, {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

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
          <span className={`inline-block w-2 h-2 rounded-full ${alerta.leida ? 'bg-gray-300 dark:bg-gray-600' : n.dot}`} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${n.badge}`}>
              {t(`alertCard.${n.key}`)}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${TIPO_BADGE[alerta.tipo] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'}`}>
              {alerta.tipo}
            </span>
            {alerta.leida && (
              <span className="text-xs text-gray-400 dark:text-gray-500">{t('alertCard.leida')}</span>
            )}
          </div>

          <p className={`text-sm font-medium ${n.text}`}>{alerta.mensaje}</p>

          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{fmtDateTime(alerta.fecha_creacion)}</p>
        </div>

        {!alerta.leida && (
          <button
            onClick={handleMarcar}
            disabled={marking}
            className="flex-shrink-0 text-xs text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 bg-white dark:bg-gray-800 rounded-lg px-2.5 py-1.5 transition-colors cursor-pointer disabled:opacity-50"
          >
            {marking ? '...' : t('alertCard.marcarLeida')}
          </button>
        )}
      </div>
    </div>
  )
}
