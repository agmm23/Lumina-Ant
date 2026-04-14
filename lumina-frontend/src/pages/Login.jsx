import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useLanguage } from '../contexts/LanguageContext'
import { GoogleLogin } from '@react-oauth/google'

export default function Login() {
  const { login, register, loginWithGoogle } = useAuth()
  const { t } = useLanguage()

  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (isRegister) {
      if (password.length < 8) { setError(t('auth.errorPasswordShort')); return }
      if (password !== confirm) { setError(t('auth.errorPasswordMismatch')); return }
    }

    setLoading(true)
    try {
      if (isRegister) {
        await register(email, password, displayName || undefined)
      } else {
        await login(email, password)
      }
    } catch (err) {
      const status = err.response?.status
      if (status === 409) setError(t('auth.errorEmailTaken'))
      else if (status === 401) setError(t('auth.errorInvalidCredentials'))
      else setError(err.response?.data?.detail || t('common.errorInesperado'))
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSuccess = async ({ credential }) => {
    setError('')
    try {
      await loginWithGoogle(credential)
    } catch {
      setError(t('auth.errorGoogle'))
    }
  }

  const switchMode = () => {
    setIsRegister(v => !v)
    setError('')
    setPassword('')
    setConfirm('')
  }

  const inputClass =
    'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg ' +
    'bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm ' +
    'focus:outline-none focus:ring-2 focus:ring-blue-500'

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 p-4">
      <div className="w-full max-w-sm bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-8">

        {/* Logo / título */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Lumina Ant</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Business Intelligence</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Nombre (solo en registro) */}
          {isRegister && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('auth.displayName')}
              </label>
              <input
                type="text"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                autoComplete="name"
                className={inputClass}
              />
            </div>
          )}

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('auth.email')}
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
              className={inputClass}
            />
          </div>

          {/* Contraseña */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              {t('auth.password')}
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete={isRegister ? 'new-password' : 'current-password'}
              className={inputClass}
            />
          </div>

          {/* Confirmar contraseña (solo en registro) */}
          {isRegister && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {t('auth.confirmPassword')}
              </label>
              <input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                required
                autoComplete="new-password"
                className={inputClass}
              />
            </div>
          )}

          {/* Error inline */}
          {error && (
            <p className="text-sm text-red-500 dark:text-red-400">{error}</p>
          )}

          {/* Botón submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-lg text-sm transition-colors cursor-pointer"
          >
            {loading
              ? t('common.loading')
              : isRegister
                ? t('auth.register')
                : t('auth.login')}
          </button>
        </form>

        {/* Google OAuth (solo si está configurado) */}
        {googleClientId && (
          <div className="mt-4">
            <div className="relative flex items-center gap-3 my-4">
              <hr className="flex-1 border-gray-200 dark:border-gray-700" />
              <span className="text-xs text-gray-400">o</span>
              <hr className="flex-1 border-gray-200 dark:border-gray-700" />
            </div>
            <div className="flex justify-center">
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={() => setError(t('auth.errorGoogle'))}
                useOneTap={false}
              />
            </div>
          </div>
        )}

        {/* Toggle login / registro */}
        <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          <button
            onClick={switchMode}
            className="text-blue-500 hover:underline cursor-pointer"
          >
            {isRegister ? t('auth.hasAccount') : t('auth.noAccount')}
          </button>
        </p>
      </div>
    </div>
  )
}
