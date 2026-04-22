import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '../AuthContext'

// Mock de api.js — se resuelve antes de que AuthProvider lo importe
vi.mock('../../services/api', () => {
  const mockApi = {
    defaults: { headers: { common: {} } },
    get: vi.fn(),
  }
  return {
    default: mockApi,
    authService: {
      login: vi.fn(),
      register: vi.fn(),
      loginWithGoogle: vi.fn(),
      getMe: vi.fn().mockRejectedValue(new Error('no token')),
      updateConfig: vi.fn(),
      logout: vi.fn(),
    },
  }
})

// Importar el mock para configurarlo en cada test
import api, { authService } from '../../services/api'

// Componente de prueba que expone el contexto en el DOM
function AuthConsumer({ onReady } = {}) {
  const auth = useAuth()
  return (
    <div>
      <span data-testid="authenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="loading">{String(auth.loading)}</span>
      <span data-testid="user">{auth.user?.email ?? 'null'}</span>
      <button
        onClick={() => auth.login('test@test.com', 'pass123')}
        data-testid="btn-login"
      >
        login
      </button>
      <button
        onClick={() => auth.register('new@test.com', 'pass123', 'Nuevo')}
        data-testid="btn-register"
      >
        register
      </button>
      <button onClick={auth.logout} data-testid="btn-logout">
        logout
      </button>
      <button
        onClick={() => auth.updateConfig({ theme: 'dark' })}
        data-testid="btn-config"
      >
        config
      </button>
    </div>
  )
}

function renderAuth() {
  return render(
    <AuthProvider>
      <AuthConsumer />
    </AuthProvider>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    // Por defecto: no hay token → getMe rechaza
    authService.getMe.mockRejectedValue(new Error('no token'))
    api.defaults.headers.common = {}
  })

  it('estado inicial: no autenticado una vez que loading termina', async () => {
    renderAuth()
    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(screen.getByTestId('user')).toHaveTextContent('null')
  })

  it('login() llama authService.login y actualiza el estado', async () => {
    authService.login.mockResolvedValue({
      data: {
        access_token: 'tok123',
        user: { email: 'test@test.com', id: 1 },
      },
    })
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByTestId('btn-login'))

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    })
    expect(screen.getByTestId('user')).toHaveTextContent('test@test.com')
  })

  it('login() guarda el token en localStorage', async () => {
    authService.login.mockResolvedValue({
      data: {
        access_token: 'tok123',
        user: { email: 'test@test.com', id: 1 },
      },
    })
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByTestId('btn-login'))

    await waitFor(() => {
      expect(localStorage.getItem('lumina_token')).toBe('tok123')
    })
  })

  it('logout() elimina el token y limpia el estado', async () => {
    authService.login.mockResolvedValue({
      data: {
        access_token: 'tok123',
        user: { email: 'test@test.com', id: 1 },
      },
    })
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByTestId('btn-login'))
    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))

    fireEvent.click(screen.getByTestId('btn-logout'))

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    })
    expect(localStorage.getItem('lumina_token')).toBeNull()
  })

  it('register() llama authService.register y autentica al usuario', async () => {
    authService.register.mockResolvedValue({
      data: {
        access_token: 'tok456',
        user: { email: 'new@test.com', id: 2 },
      },
    })
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByTestId('btn-register'))

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    })
    expect(screen.getByTestId('user')).toHaveTextContent('new@test.com')
  })

  it('restaura sesión desde localStorage si hay token guardado', async () => {
    localStorage.setItem('lumina_token', 'tok-guardado')
    authService.getMe.mockResolvedValue({
      data: { email: 'guardado@test.com', id: 3 },
    })

    renderAuth()

    await waitFor(() => {
      expect(screen.getByTestId('authenticated')).toHaveTextContent('true')
    })
    expect(screen.getByTestId('user')).toHaveTextContent('guardado@test.com')
  })

  it('si el token guardado es inválido, queda no autenticado y limpia localStorage', async () => {
    localStorage.setItem('lumina_token', 'tok-invalido')
    authService.getMe.mockRejectedValue(new Error('401 Unauthorized'))

    renderAuth()

    await waitFor(() => {
      expect(screen.getByTestId('loading')).toHaveTextContent('false')
    })
    expect(screen.getByTestId('authenticated')).toHaveTextContent('false')
    expect(localStorage.getItem('lumina_token')).toBeNull()
  })

  it('updateConfig() actualiza user.config en el estado', async () => {
    authService.login.mockResolvedValue({
      data: {
        access_token: 'tok123',
        user: { email: 'test@test.com', id: 1, config: {} },
      },
    })
    authService.updateConfig.mockResolvedValue({ data: { theme: 'dark' } })

    renderAuth()
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'))

    fireEvent.click(screen.getByTestId('btn-login'))
    await waitFor(() => expect(screen.getByTestId('authenticated')).toHaveTextContent('true'))

    fireEvent.click(screen.getByTestId('btn-config'))

    await waitFor(() => {
      expect(authService.updateConfig).toHaveBeenCalledWith({ theme: 'dark' })
    })
  })
})
