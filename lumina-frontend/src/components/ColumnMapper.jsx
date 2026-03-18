import { useState, useMemo } from 'react'
import { useLanguage } from '../contexts/LanguageContext'

const CONFIDENCE_COLORS = {
  high: { dot: 'bg-green-500', text: 'text-green-700 dark:text-green-400', bg: 'bg-green-50 dark:bg-green-950' },
  medium: { dot: 'bg-amber-400', text: 'text-amber-700 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950' },
  low: { dot: 'bg-red-400', text: 'text-red-700 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950' },
  none: { dot: 'bg-gray-300 dark:bg-gray-600', text: 'text-gray-500 dark:text-gray-400', bg: 'bg-gray-50 dark:bg-gray-800' },
}

function getConfLevel(confidence) {
  if (confidence >= 0.85) return 'high'
  if (confidence >= 0.6) return 'medium'
  if (confidence > 0) return 'low'
  return 'none'
}

const METHOD_KEYS = {
  exact: 'exacto',
  normalized: 'normalizado',
  saved: 'guardado',
  synonym: 'sinonimo',
  fuzzy: 'aproximado',
  none: '',
}

export default function ColumnMapper({
  suggestions,
  targetColumns,
  structureChanged,
  hasSavedMappings,
  onConfirm,
  onCancel,
  color = 'blue',
}) {
  const { t } = useLanguage()

  const [mapping, setMapping] = useState(() => {
    const initial = {}
    for (const s of suggestions) {
      initial[s.csv_column] = s.target_column || null
    }
    return initial
  })

  const requiredTargets = useMemo(
    () => new Set(targetColumns.filter(c => c.required).map(c => c.name)),
    [targetColumns]
  )

  const allTargetNames = useMemo(
    () => targetColumns.map(c => c.name),
    [targetColumns]
  )

  const usedTargets = useMemo(() => {
    const used = new Set()
    for (const val of Object.values(mapping)) {
      if (val) used.add(val)
    }
    return used
  }, [mapping])

  const mappedRequired = useMemo(() => {
    const mappedTargets = new Set(Object.values(mapping).filter(Boolean))
    return [...requiredTargets].filter(t => mappedTargets.has(t))
  }, [mapping, requiredTargets])

  const allRequiredMapped = mappedRequired.length === requiredTargets.size
  const unmappedRequired = [...requiredTargets].filter(t => !mappedRequired.includes(t))

  function handleChange(csvCol, newTarget) {
    setMapping(prev => ({ ...prev, [csvCol]: newTarget || null }))
  }

  function handleConfirm() {
    const finalMapping = {}
    for (const [csvCol, targetCol] of Object.entries(mapping)) {
      if (targetCol && csvCol !== targetCol) {
        finalMapping[csvCol] = targetCol
      }
    }
    onConfirm(finalMapping)
  }

  return (
    <div className="space-y-3">
      {structureChanged && hasSavedMappings && (
        <div className="p-3 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg text-sm text-amber-800 dark:text-amber-300">
          <p className="font-medium">{t('columnMapper.estructuraCambio')}</p>
          <p className="text-xs mt-0.5 text-amber-600 dark:text-amber-400">
            {t('columnMapper.estructuraCambioMsg')}
          </p>
        </div>
      )}

      <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
              <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-300">{t('columnMapper.columnaCSV')}</th>
              <th className="text-center px-2 py-2 font-medium text-gray-400 dark:text-gray-500 w-8"></th>
              <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-300">{t('columnMapper.campoDestino')}</th>
              <th className="text-center px-3 py-2 font-medium text-gray-500 dark:text-gray-400 w-24">{t('columnMapper.confianza')}</th>
            </tr>
          </thead>
          <tbody>
            {suggestions.map((s) => {
              const currentTarget = mapping[s.csv_column]
              const conf = currentTarget === s.target_column ? s.confidence : (currentTarget ? 1.0 : 0)
              const level = currentTarget === s.target_column ? getConfLevel(s.confidence) : (currentTarget ? 'high' : 'none')
              const colors = CONFIDENCE_COLORS[level]

              return (
                <tr key={s.csv_column} className="border-b border-gray-100 dark:border-gray-800 last:border-0">
                  <td className="px-3 py-2">
                    <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded font-mono dark:text-gray-300">
                      {s.csv_column}
                    </code>
                  </td>
                  <td className="text-center text-gray-300 dark:text-gray-600">→</td>
                  <td className="px-3 py-2">
                    <select
                      value={currentTarget || ''}
                      onChange={(e) => handleChange(s.csv_column, e.target.value)}
                      className={`w-full text-xs border rounded-md px-2 py-1.5 font-mono cursor-pointer ${
                        currentTarget
                          ? 'border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200'
                          : 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400'
                      }`}
                    >
                      <option value="">{t('columnMapper.noMapear')}</option>
                      {allTargetNames.map(tgt => {
                        const isUsedElsewhere = usedTargets.has(tgt) && tgt !== currentTarget
                        const req = requiredTargets.has(tgt)
                        return (
                          <option key={tgt} value={tgt} disabled={isUsedElsewhere}>
                            {tgt}{req ? t('columnMapper.requerido') : ''}{isUsedElsewhere ? t('columnMapper.yaAsignado') : ''}
                          </option>
                        )
                      })}
                    </select>
                  </td>
                  <td className="px-3 py-2 text-center">
                    {currentTarget && (
                      <span className={`inline-flex items-center gap-1.5 text-xs ${colors.text}`}>
                        <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
                        {s.method !== 'none' && currentTarget === s.target_column
                          ? t(`columnMapper.${METHOD_KEYS[s.method]}`)
                          : t('columnMapper.manual')}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>
          {t('columnMapper.mapeadas', { mapped: mappedRequired.length, required: requiredTargets.size })}
          {unmappedRequired.length > 0 && (
            <span className="text-red-500 dark:text-red-400 ml-1">
              {t('columnMapper.faltan', { unmapped: unmappedRequired.join(', ') })}
            </span>
          )}
        </span>
        <span className="text-gray-400 dark:text-gray-500">{t('columnMapper.requeridoLeyenda')}</span>
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleConfirm}
          disabled={!allRequiredMapped}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
            allRequiredMapped
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed'
          }`}
        >
          {t('columnMapper.confirmarMapeo')}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors cursor-pointer"
        >
          {t('common.cancelar')}
        </button>
      </div>
    </div>
  )
}
