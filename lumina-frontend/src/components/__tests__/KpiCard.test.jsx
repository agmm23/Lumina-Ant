import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import KpiCard from '../KpiCard'

describe('KpiCard', () => {
  it('muestra el título y valor correctamente', () => {
    render(<KpiCard title="Total Ventas" value="$50,000" />)
    expect(screen.getByText('Total Ventas')).toBeInTheDocument()
    expect(screen.getByText('$50,000')).toBeInTheDocument()
  })

  it('muestra el subtítulo si se provee', () => {
    render(<KpiCard title="Ventas" value="$100" subtitle="vs mes anterior" />)
    expect(screen.getByText('vs mes anterior')).toBeInTheDocument()
  })

  it('no muestra subtítulo si no se provee', () => {
    render(<KpiCard title="Ventas" value="$100" />)
    expect(screen.queryByText('vs mes anterior')).not.toBeInTheDocument()
  })

  it('muestra skeleton de carga cuando loading=true', () => {
    const { container } = render(<KpiCard title="Ventas" value="$100" loading={true} />)
    // En modo loading, no debe mostrar el título ni el valor
    expect(screen.queryByText('Ventas')).not.toBeInTheDocument()
    // Debe tener la clase animate-pulse
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('muestra contenido normal cuando loading=false', () => {
    render(<KpiCard title="Ventas" value="$100" loading={false} />)
    expect(screen.getByText('Ventas')).toBeInTheDocument()
    expect(screen.getByText('$100')).toBeInTheDocument()
  })

  it('muestra el icono si se provee', () => {
    render(<KpiCard title="Ventas" value="$100" icon="💰" />)
    expect(screen.getByText('💰')).toBeInTheDocument()
  })

  it('no muestra el icono si no se provee', () => {
    const { container } = render(<KpiCard title="Ventas" value="$100" />)
    expect(container.querySelector('.text-xl')).not.toBeInTheDocument()
  })

  it('aplica color azul por defecto', () => {
    const { container } = render(<KpiCard title="Ventas" value="$100" />)
    const card = container.firstChild
    expect(card.className).toMatch(/bg-blue-50|border/)
  })

  it.each(['blue', 'green', 'red', 'yellow', 'purple'])(
    'acepta color %s sin errores',
    (color) => {
      expect(() =>
        render(<KpiCard title="Test" value="0" color={color} />)
      ).not.toThrow()
    }
  )

  it('acepta valores numéricos como string', () => {
    render(<KpiCard title="KPI" value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('acepta valores de cadena con formato', () => {
    render(<KpiCard title="KPI" value="1,234.56" />)
    expect(screen.getByText('1,234.56')).toBeInTheDocument()
  })
})
