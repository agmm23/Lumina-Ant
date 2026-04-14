import { createContext, useContext, useState, useEffect } from 'react'
import { useAuth } from './AuthContext'

const ThemeContext = createContext({ isDark: false, toggleDark: () => {} })

export function ThemeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => localStorage.getItem('theme') === 'dark')
  const { user, isAuthenticated, updateConfig } = useAuth()

  // Aplicar clase dark al documento cuando cambia isDark
  useEffect(() => {
    const root = document.documentElement
    if (isDark) {
      root.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      root.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDark])

  // Sincronizar tema cuando el usuario inicia sesión
  useEffect(() => {
    if (user?.config?.theme) {
      setIsDark(user.config.theme === 'dark')
    }
  }, [user])

  const toggleDark = () => {
    setIsDark(prev => {
      const newDark = !prev
      // Persistir en el servidor si hay sesión activa
      if (isAuthenticated) {
        updateConfig({ theme: newDark ? 'dark' : 'light' }).catch(() => {})
      }
      return newDark
    })
  }

  return (
    <ThemeContext.Provider value={{ isDark, toggleDark }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useDark() {
  return useContext(ThemeContext)
}
