import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api, { authService } from '../services/api'

const AuthContext = createContext({
  user: null,
  token: null,
  loading: true,
  isAuthenticated: false,
  login: async () => {},
  loginWithGoogle: async () => {},
  register: async () => {},
  logout: () => {},
  updateConfig: async () => {},
})

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(true)

  // Restaurar sesión al montar si hay token guardado
  useEffect(() => {
    const stored = localStorage.getItem('lumina_token')
    if (stored) {
      api.defaults.headers.common['Authorization'] = `Bearer ${stored}`
      authService.getMe()
        .then(res => {
          setToken(stored)
          setUser(res.data)
        })
        .catch(() => {
          localStorage.removeItem('lumina_token')
          delete api.defaults.headers.common['Authorization']
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const _applySession = (tokenStr, userData) => {
    localStorage.setItem('lumina_token', tokenStr)
    api.defaults.headers.common['Authorization'] = `Bearer ${tokenStr}`
    setToken(tokenStr)
    setUser(userData)
  }

  const login = useCallback(async (email, password) => {
    const res = await authService.login(email, password)
    _applySession(res.data.access_token, res.data.user)
  }, [])

  const loginWithGoogle = useCallback(async (credential) => {
    const res = await authService.loginWithGoogle(credential)
    _applySession(res.data.access_token, res.data.user)
  }, [])

  const register = useCallback(async (email, password, displayName) => {
    const res = await authService.register(email, password, displayName)
    _applySession(res.data.access_token, res.data.user)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('lumina_token')
    delete api.defaults.headers.common['Authorization']
    setToken(null)
    setUser(null)
  }, [])

  const updateConfig = useCallback(async (patch) => {
    const res = await authService.updateConfig(patch)
    setUser(prev => prev ? { ...prev, config: res.data } : prev)
    return res.data
  }, [])

  return (
    <AuthContext.Provider value={{
      user,
      token,
      loading,
      isAuthenticated: !!user,
      login,
      loginWithGoogle,
      register,
      logout,
      updateConfig,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
