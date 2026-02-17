function AlertBadge({ alert }) {
  const styles = {
    critical: 'bg-red-100 border-red-300 text-red-800',
    warning: 'bg-yellow-100 border-yellow-300 text-yellow-800',
    info: 'bg-blue-100 border-blue-300 text-blue-800',
  }

  const icons = {
    critical: '🔴',
    warning: '⚠️',
    info: 'ℹ️',
  }

  const nivel = alert.nivel || 'info'

  return (
    <div className={`flex items-start gap-2 p-3 rounded-lg border text-sm ${styles[nivel]}`}>
      <span className="mt-0.5 shrink-0">{icons[nivel]}</span>
      <div>
        <p className="font-medium">{alert.mensaje || alert.message}</p>
        {alert.tipo && (
          <p className="text-xs opacity-70 mt-0.5 capitalize">{alert.tipo}</p>
        )}
      </div>
    </div>
  )
}

export default AlertBadge
