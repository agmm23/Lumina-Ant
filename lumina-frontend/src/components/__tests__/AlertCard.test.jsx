import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AlertCard from '../AlertCard'
import { LanguageProvider } from '../../contexts/LanguageContext'

// Wrapper con LanguageContext (AlertCard usa useLanguage)
function renderWithLang(ui) {
  return render(<LanguageProvider>{ui}</LanguageProvider>)
}

const alertaBase = {
  id: 1,
  tipo: 'ventas',
  nivel: 'warning',
  mensaje: 'Caída de ventas detectada',
  detalles: 'Promedio: $10,000',
  fecha_creacion: '2024-01-15T10:00:00Z',
  leida: false,
}

describe('AlertCard', () => {
  it('muestra el mensaje de la alerta', () => {
    renderWithLang(<AlertCard alerta={alertaBase} onMarcarLeida={vi.fn()} />)
    expect(screen.getByText('Caída de ventas detectada')).toBeInTheDocument()
  })

  it('muestra el tipo de alerta como badge', () => {
    renderWithLang(<AlertCard alerta={alertaBase} onMarcarLeida={vi.fn()} />)
    expect(screen.getByText('ventas')).toBeInTheDocument()
  })

  it('muestra botón de marcar leída cuando no está leída', () => {
    renderWithLang(<AlertCard alerta={alertaBase} onMarcarLeida={vi.fn()} />)
    // Busca el botón (texto depende de la traducción 'alertCard.marcarLeida')
    const button = screen.getByRole('button')
    expect(button).toBeInTheDocument()
  })

  it('NO muestra botón de marcar leída cuando ya está leída', () => {
    const alertaLeida = { ...alertaBase, leida: true }
    renderWithLang(<AlertCard alerta={alertaLeida} onMarcarLeida={vi.fn()} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('llama a onMarcarLeida al hacer click', async () => {
    const mockFn = vi.fn().mockResolvedValue(undefined)
    renderWithLang(<AlertCard alerta={alertaBase} onMarcarLeida={mockFn} />)
    const button = screen.getByRole('button')
    fireEvent.click(button)
    await waitFor(() => {
      expect(mockFn).toHaveBeenCalledWith(alertaBase.id)
    })
  })

  it('aplica opacidad reducida cuando está leída', () => {
    const alertaLeida = { ...alertaBase, leida: true }
    const { container } = renderWithLang(
      <AlertCard alerta={alertaLeida} onMarcarLeida={vi.fn()} />
    )
    expect(container.firstChild.className).toMatch(/opacity-50/)
  })

  it('no aplica opacidad cuando no está leída', () => {
    const { container } = renderWithLang(
      <AlertCard alerta={alertaBase} onMarcarLeida={vi.fn()} />
    )
    expect(container.firstChild.className).not.toMatch(/opacity-50/)
  })

  it('muestra la fecha de creación formateada', () => {
    renderWithLang(<AlertCard alerta={alertaBase} onMarcarLeida={vi.fn()} />)
    // La fecha debe aparecer formateada (no vacía)
    const { container } = renderWithLang(
      <AlertCard alerta={alertaBase} onMarcarLeida={vi.fn()} />
    )
    const textos = container.querySelectorAll('p')
    const fechaTexto = Array.from(textos).find(p =>
      p.textContent.match(/ene|jan|2024/i)
    )
    expect(fechaTexto).toBeTruthy()
  })

  it.each(['warning', 'critical', 'info'])(
    'renderiza sin errores con nivel %s',
    (nivel) => {
      const alerta = { ...alertaBase, nivel }
      expect(() =>
        renderWithLang(<AlertCard alerta={alerta} onMarcarLeida={vi.fn()} />)
      ).not.toThrow()
    }
  )

  it.each(['ventas', 'gastos', 'inventario', 'clientes'])(
    'renderiza sin errores con tipo %s',
    (tipo) => {
      const alerta = { ...alertaBase, tipo }
      expect(() =>
        renderWithLang(<AlertCard alerta={alerta} onMarcarLeida={vi.fn()} />)
      ).not.toThrow()
    }
  )

  it('muestra "..." mientras procesa el click', async () => {
    let resolve
    const mockFn = vi.fn().mockReturnValue(new Promise(r => { resolve = r }))
    renderWithLang(<AlertCard alerta={alertaBase} onMarcarLeida={mockFn} />)
    const button = screen.getByRole('button')
    fireEvent.click(button)
    await waitFor(() => {
      expect(screen.getByRole('button')).toHaveTextContent('...')
    })
    resolve()
  })
})
