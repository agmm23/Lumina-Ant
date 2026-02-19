import { useState, useMemo } from 'react'

const CONFIDENCE_COLORS = {
  high: { dot: 'bg-green-500', text: 'text-green-700', bg: 'bg-green-50' },
  medium: { dot: 'bg-amber-400', text: 'text-amber-700', bg: 'bg-amber-50' },
  low: { dot: 'bg-red-400', text: 'text-red-700', bg: 'bg-red-50' },
  none: { dot: 'bg-gray-300', text: 'text-gray-500', bg: 'bg-gray-50' },
}

function getConfLevel(confidence) {
  if (confidence >= 0.85) return 'high'
  if (confidence >= 0.6) return 'medium'
  if (confidence > 0) return 'low'
  return 'none'
}

const METHOD_LABELS = {
  exact: 'Exacto',
  normalized: 'Normalizado',
  saved: 'Guardado',
  synonym: 'Sinónimo',
  fuzzy: 'Aproximado',
  none: '',
}

/**
 * Componente de mapeo de columnas CSV.
 *
 * Props:
 * - suggestions: Array de { csv_column, target_column, confidence, method }
 * - targetColumns: Array de { name, required, hint? }
 * - structureChanged: bool — si la estructura del CSV cambió vs mapping guardado
 * - hasSavedMappings: bool — si ya existen mappings guardados
 * - onConfirm(mapping): callback con { csv_col: target_col } dict
 * - onCancel(): callback para cancelar
 * - color: string (color key del datasource)
 */
export default function ColumnMapper({
  suggestions,
  targetColumns,
  structureChanged,
  hasSavedMappings,
  onConfirm,
  onCancel,
  color = 'blue',
}) {
  // Estado: mapping actual como { csv_column: target_column | null }
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

  // Targets ya asignados (para evitar duplicados en dropdowns)
  const usedTargets = useMemo(() => {
    const used = new Set()
    for (const val of Object.values(mapping)) {
      if (val) used.add(val)
    }
    return used
  }, [mapping])

  // Cuántas columnas requeridas están mapeadas
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
    // Construir mapping solo para columnas que necesitan renombrar
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
      {/* Alerta de cambio de estructura */}
      {structureChanged && hasSavedMappings && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          <p className="font-medium">La estructura del archivo cambió</p>
          <p className="text-xs mt-0.5 text-amber-600">
            Las columnas de este CSV son diferentes al último archivo cargado. Revisa el mapeo antes de continuar.
          </p>
        </div>
      )}

      {/* Tabla de mapeo */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left px-3 py-2 font-medium text-gray-600">Columna CSV</th>
              <th className="text-center px-2 py-2 font-medium text-gray-400 w-8"></th>
              <th className="text-left px-3 py-2 font-medium text-gray-600">Campo destino</th>
              <th className="text-center px-3 py-2 font-medium text-gray-500 w-24">Confianza</th>
            </tr>
          </thead>
          <tbody>
            {suggestions.map((s) => {
              const currentTarget = mapping[s.csv_column]
              const conf = currentTarget === s.target_column ? s.confidence : (currentTarget ? 1.0 : 0)
              const level = currentTarget === s.target_column ? getConfLevel(s.confidence) : (currentTarget ? 'high' : 'none')
              const colors = CONFIDENCE_COLORS[level]
              const isRequired = currentTarget && requiredTargets.has(currentTarget)

              return (
                <tr key={s.csv_column} className="border-b border-gray-100 last:border-0">
                  <td className="px-3 py-2">
                    <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono">
                      {s.csv_column}
                    </code>
                  </td>
                  <td className="text-center text-gray-300">→</td>
                  <td className="px-3 py-2">
                    <select
                      value={currentTarget || ''}
                      onChange={(e) => handleChange(s.csv_column, e.target.value)}
                      className={`w-full text-xs border rounded-md px-2 py-1.5 font-mono cursor-pointer ${
                        currentTarget
                          ? 'border-gray-300 bg-white text-gray-800'
                          : 'border-red-300 bg-red-50 text-red-600'
                      }`}
                    >
                      <option value="">-- No mapear --</option>
                      {allTargetNames.map(t => {
                        const isUsedElsewhere = usedTargets.has(t) && t !== currentTarget
                        const req = requiredTargets.has(t)
                        return (
                          <option key={t} value={t} disabled={isUsedElsewhere}>
                            {t}{req ? ' *' : ''}{isUsedElsewhere ? ' (ya asignado)' : ''}
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
                          ? METHOD_LABELS[s.method]
                          : 'Manual'}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Resumen */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>
          {mappedRequired.length} de {requiredTargets.size} columnas requeridas mapeadas
          {unmappedRequired.length > 0 && (
            <span className="text-red-500 ml-1">
              (faltan: {unmappedRequired.join(', ')})
            </span>
          )}
        </span>
        <span className="text-gray-400">* = requerido</span>
      </div>

      {/* Botones */}
      <div className="flex gap-2">
        <button
          onClick={handleConfirm}
          disabled={!allRequiredMapped}
          className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
            allRequiredMapped
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          }`}
        >
          Confirmar mapeo y subir
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 border border-gray-200 hover:bg-gray-50 transition-colors cursor-pointer"
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}
