import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeProvider, useDark } from '../ThemeContext'

// Componente de prueba que consume el contexto
function TestConsumer() {
  const { isDark, toggleDark } = useDark()
  return (
    <div>
      <span data-testid="mode">{isDark ? 'dark' : 'light'}</span>
      <button onClick={toggleDark}>toggle</button>
    </div>
  )
}

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('inicia en modo claro si localStorage está vacío', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    expect(screen.getByTestId('mode')).toHaveTextContent('light')
  })

  it('inicia en modo oscuro si localStorage tiene "dark"', () => {
    localStorage.setItem('theme', 'dark')
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    expect(screen.getByTestId('mode')).toHaveTextContent('dark')
  })

  it('toggleDark cambia de claro a oscuro', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    expect(screen.getByTestId('mode')).toHaveTextContent('light')
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('mode')).toHaveTextContent('dark')
  })

  it('toggleDark cambia de oscuro a claro', () => {
    localStorage.setItem('theme', 'dark')
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('mode')).toHaveTextContent('light')
  })

  it('agrega clase "dark" al <html> en modo oscuro', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    fireEvent.click(screen.getByRole('button'))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('quita clase "dark" del <html> en modo claro', () => {
    localStorage.setItem('theme', 'dark')
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    fireEvent.click(screen.getByRole('button'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('persiste el tema en localStorage al cambiar', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    fireEvent.click(screen.getByRole('button'))
    expect(localStorage.getItem('theme')).toBe('dark')
    fireEvent.click(screen.getByRole('button'))
    expect(localStorage.getItem('theme')).toBe('light')
  })

  it('toggle múltiples veces funciona correctamente', () => {
    render(
      <ThemeProvider>
        <TestConsumer />
      </ThemeProvider>
    )
    const button = screen.getByRole('button')
    const modo = screen.getByTestId('mode')

    fireEvent.click(button)
    expect(modo).toHaveTextContent('dark')
    fireEvent.click(button)
    expect(modo).toHaveTextContent('light')
    fireEvent.click(button)
    expect(modo).toHaveTextContent('dark')
  })
})
