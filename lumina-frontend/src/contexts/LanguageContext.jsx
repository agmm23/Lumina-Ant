import { createContext, useContext, useState, useCallback, useMemo } from 'react'
import es from '../locales/es.json'
import en from '../locales/en.json'

const LOCALES = { es, en }
const LOCALE_MAP = { es: 'es-MX', en: 'en-US' }

const LanguageContext = createContext({
  lang: 'es',
  locale: 'es-MX',
  setLang: () => {},
  t: (key) => key,
})

function resolve(obj, path) {
  return path.split('.').reduce((acc, part) => acc?.[part], obj)
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => localStorage.getItem('lumina_lang') || 'es')

  const setLang = useCallback((newLang) => {
    if (LOCALES[newLang]) {
      setLangState(newLang)
      localStorage.setItem('lumina_lang', newLang)
    }
  }, [])

  const translations = LOCALES[lang] || es

  const t = useCallback((key, vars) => {
    let value = resolve(translations, key)
    if (value === undefined) {
      // Fallback to Spanish
      value = resolve(es, key)
    }
    if (value === undefined) return key
    if (typeof value !== 'string') return key

    // Interpolation: t('key', { n: 5 }) replaces {n} with 5
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        value = value.replaceAll(`{${k}}`, String(v))
      }
    }
    return value
  }, [translations])

  const locale = LOCALE_MAP[lang] || 'es-MX'

  const ctx = useMemo(() => ({ lang, locale, setLang, t }), [lang, locale, setLang, t])

  return (
    <LanguageContext.Provider value={ctx}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  return useContext(LanguageContext)
}
