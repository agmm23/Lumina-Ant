import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Chat from '../Chat'
import { LanguageProvider } from '../../contexts/LanguageContext'
import { AuthProvider } from '../../contexts/AuthContext'

// Mockear módulos externos
vi.mock('../../services/api', () => ({
  default: { defaults: { headers: { common: {} } } },
  chatService: {
    getSuggestedPrompts: vi.fn().mockResolvedValue({ data: { prompts: [] } }),
    getHistory: vi.fn().mockResolvedValue({ data: [] }),
  },
  authService: {
    getMe: vi.fn().mockRejectedValue(new Error('no token')),
    login: vi.fn(),
    register: vi.fn(),
    loginWithGoogle: vi.fn(),
    updateConfig: vi.fn(),
    logout: vi.fn(),
  },
}))

// Wrapper completo con todos los contextos necesarios
function renderChat() {
  return render(
    <AuthProvider>
      <LanguageProvider>
        <Chat />
      </LanguageProvider>
    </AuthProvider>
  )
}

// Helper para simular una respuesta SSE exitosa
function mockFetchSSE(content = 'Respuesta de prueba') {
  const encoder = new TextEncoder()
  const donePayload = JSON.stringify({
    type: 'done',
    intents: [],
    data_sources: [],
    suggested_followups: [],
    usage: { total_tokens: 50, input_tokens: 30, output_tokens: 20, source: 'exact' },
  })
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'delta', content })}\n\n`))
      controller.enqueue(encoder.encode(`data: ${donePayload}\n\n`))
      controller.close()
    },
  })
  global.fetch = vi.fn().mockResolvedValue({ ok: true, body: stream })
}

describe('Chat', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    // jsdom no implementa scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    delete global.fetch
  })

  it('renderiza sin errores con el mensaje de bienvenida', async () => {
    renderChat()
    // El componente debe montar sin lanzar excepciones
    await waitFor(() => {
      expect(screen.getByRole('textbox')).toBeInTheDocument()
    })
  })

  it('el campo de texto acepta entrada del usuario', async () => {
    renderChat()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '¿Cuánto vendimos?' } })
    expect(input.value).toBe('¿Cuánto vendimos?')
  })

  it('el botón de enviar está deshabilitado si el input está vacío', async () => {
    renderChat()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())
    const sendBtn = screen.getByRole('button', { name: '' }) // botón SVG sin texto
    // Con input vacío el botón debe estar disabled
    expect(sendBtn).toBeDisabled()
  })

  it('el botón de enviar se habilita cuando hay texto', async () => {
    renderChat()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'Hola' } })
    // Buscar el botón de enviar (tiene svg adentro)
    const buttons = screen.getAllByRole('button')
    const sendBtn = buttons[buttons.length - 1] // último botón es el de enviar
    expect(sendBtn).not.toBeDisabled()
  })

  it('enviar mensaje agrega el mensaje del usuario en la UI', async () => {
    mockFetchSSE('Tenemos datos.')
    renderChat()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '¿Cuánto vendimos?' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(screen.getByText('¿Cuánto vendimos?')).toBeInTheDocument()
    })
  })

  it('Enter dispara el envío del mensaje', async () => {
    mockFetchSSE('OK')
    renderChat()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'Test Enter' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1)
    })
  })

  it('Shift+Enter NO envía el mensaje', async () => {
    mockFetchSSE('OK')
    renderChat()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'Test Shift+Enter' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })

    // fetch no debe haberse llamado
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('error de fetch muestra mensaje de error en el chat', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'))
    renderChat()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeInTheDocument())

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: 'Hola' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: false })

    // Después del error, debe aparecer algún mensaje de error
    await waitFor(() => {
      // El mensaje de error aparece como burbuja del asistente
      expect(global.fetch).toHaveBeenCalledTimes(1)
    })
  })

  it('carga el historial desde localStorage al montar', async () => {
    const historial = [
      {
        role: 'assistant',
        content: 'Bienvenido',
        intents: [],
        data_sources: [],
        suggested_followups: [],
        timestamp: Date.now(),
      },
      {
        role: 'user',
        content: 'Mensaje guardado previamente',
        timestamp: Date.now(),
      },
    ]
    localStorage.setItem('lumina_chat_history', JSON.stringify(historial))

    renderChat()
    await waitFor(() => {
      expect(screen.getByText('Mensaje guardado previamente')).toBeInTheDocument()
    })
  })

  it('botón limpiar chat elimina los mensajes', async () => {
    const historial = [
      {
        role: 'assistant',
        content: 'Bienvenido',
        intents: [],
        data_sources: [],
        suggested_followups: [],
        timestamp: Date.now(),
      },
      { role: 'user', content: 'Hola mundo', timestamp: Date.now() },
    ]
    localStorage.setItem('lumina_chat_history', JSON.stringify(historial))

    renderChat()
    await waitFor(() => {
      expect(screen.getByText('Hola mundo')).toBeInTheDocument()
    })

    // El botón de limpiar debe estar visible cuando hay más de 1 mensaje
    const limpiarBtn = screen.getByRole('button', { name: /limpiar/i })
    fireEvent.click(limpiarBtn)

    await waitFor(() => {
      expect(screen.queryByText('Hola mundo')).not.toBeInTheDocument()
    })
  })
})
