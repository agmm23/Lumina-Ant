import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ChatMessage from '../ChatMessage'

// ChatMessage no usa contextos, se puede renderizar directamente

const msgAsistente = {
  role: 'assistant',
  content: 'Hola, soy el copiloto.',
  intents: [],
  data_sources: [],
  suggested_followups: [],
  timestamp: new Date('2024-01-15T10:30:00').getTime(),
  usage: { total_tokens: 120, input_tokens: 80, output_tokens: 40, source: 'exact' },
}

const msgUsuario = {
  role: 'user',
  content: '¿Cuánto vendimos este mes?',
  timestamp: new Date('2024-01-15T10:29:00').getTime(),
}

describe('ChatMessage', () => {
  it('muestra el contenido del mensaje de usuario', () => {
    render(<ChatMessage message={msgUsuario} />)
    expect(screen.getByText('¿Cuánto vendimos este mes?')).toBeInTheDocument()
  })

  it('mensaje de usuario se alinea a la derecha', () => {
    const { container } = render(<ChatMessage message={msgUsuario} />)
    expect(container.firstChild.className).toMatch(/items-end/)
  })

  it('mensaje de asistente se alinea a la izquierda', () => {
    const { container } = render(<ChatMessage message={msgAsistente} />)
    expect(container.firstChild.className).toMatch(/items-start/)
  })

  it('mensaje de asistente muestra el contenido vía markdown', () => {
    render(<ChatMessage message={msgAsistente} />)
    expect(screen.getByText('Hola, soy el copiloto.')).toBeInTheDocument()
  })

  it('estado streaming muestra puntos animados cuando content está vacío', () => {
    const msg = { ...msgAsistente, content: '', streaming: true, timestamp: Date.now() }
    const { container } = render(<ChatMessage message={msg} />)
    // Los tres puntos animados están presentes
    const dots = container.querySelectorAll('.animate-bounce')
    expect(dots.length).toBe(3)
  })

  it('estado streaming con contenido muestra cursor parpadeante', () => {
    const msg = { ...msgAsistente, content: 'Procesando...', streaming: true }
    const { container } = render(<ChatMessage message={msg} />)
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('mensaje de error aplica estilo rojo', () => {
    const msg = { ...msgAsistente, isError: true }
    const { container } = render(<ChatMessage message={msg} />)
    const bubble = container.querySelector('[class*="red"]') || container.querySelector('[class*="bg-red"]')
    expect(bubble).toBeInTheDocument()
  })

  it('muestra follow-ups como botones clickeables', () => {
    const msg = {
      ...msgAsistente,
      suggested_followups: ['¿Y los gastos?', '¿Qué producto lideró?'],
    }
    render(<ChatMessage message={msg} onFollowupClick={vi.fn()} />)
    expect(screen.getByText(/¿Y los gastos\?/)).toBeInTheDocument()
    expect(screen.getByText(/¿Qué producto lideró\?/)).toBeInTheDocument()
  })

  it('follow-up llama a onFollowupClick al hacer click', () => {
    const mockFn = vi.fn()
    const msg = { ...msgAsistente, suggested_followups: ['¿Y los gastos?'] }
    render(<ChatMessage message={msg} onFollowupClick={mockFn} />)
    fireEvent.click(screen.getByText(/¿Y los gastos\?/))
    expect(mockFn).toHaveBeenCalledWith('¿Y los gastos?')
  })

  it('muestra tokens cuando usage.total_tokens > 0', () => {
    render(<ChatMessage message={msgAsistente} />)
    expect(screen.getByText(/120/)).toBeInTheDocument()
  })

  it('muestra fuentes de datos cuando existen', () => {
    const msg = { ...msgAsistente, data_sources: ['ventas', 'clientes'] }
    render(<ChatMessage message={msg} />)
    expect(screen.getByText(/ventas/)).toBeInTheDocument()
    expect(screen.getByText(/clientes/)).toBeInTheDocument()
  })

  it('no muestra follow-ups durante streaming', () => {
    const msg = {
      ...msgAsistente,
      streaming: true,
      suggested_followups: ['¿Y los gastos?'],
    }
    render(<ChatMessage message={msg} onFollowupClick={vi.fn()} />)
    expect(screen.queryByText(/¿Y los gastos\?/)).not.toBeInTheDocument()
  })

  it('muestra botón "Ver gráfica" cuando el contenido tiene una tabla con datos numéricos', () => {
    const conTabla = {
      ...msgAsistente,
      content: `Aquí los resultados:\n\n| Producto | Ventas |\n|----------|--------|\n| A        | 5000   |\n| B        | 8000   |`,
    }
    render(<ChatMessage message={conTabla} />)
    expect(screen.getByText(/Ver gráfica/)).toBeInTheDocument()
  })

  it('toggle del botón gráfica muestra y oculta el chart', () => {
    const conTabla = {
      ...msgAsistente,
      content: `| Mes | Ventas |\n|-----|--------|\n| Enero | 15000 |\n| Febrero | 18000 |`,
    }
    render(<ChatMessage message={conTabla} />)
    const btn = screen.getByText(/Ver gráfica/)
    fireEvent.click(btn)
    expect(screen.getByText(/Ocultar gráfica/)).toBeInTheDocument()
    fireEvent.click(screen.getByText(/Ocultar gráfica/))
    expect(screen.getByText(/Ver gráfica/)).toBeInTheDocument()
  })

  it('NO muestra botón gráfica cuando la tabla no tiene columnas numéricas', () => {
    const soloTexto = {
      ...msgAsistente,
      content: `| Nombre | Ciudad |\n|--------|--------|\n| Ana    | Madrid |`,
    }
    render(<ChatMessage message={soloTexto} />)
    expect(screen.queryByText(/Ver gráfica/)).not.toBeInTheDocument()
  })

  it('NO muestra botón gráfica en mensajes de usuario', () => {
    const userConTabla = {
      ...msgUsuario,
      content: `| Mes | Ventas |\n|-----|--------|\n| Enero | 15000 |`,
    }
    render(<ChatMessage message={userConTabla} />)
    expect(screen.queryByText(/Ver gráfica/)).not.toBeInTheDocument()
  })
})
