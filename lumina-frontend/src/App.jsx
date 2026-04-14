import { useState } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { LanguageProvider } from './contexts/LanguageContext'
import { DataSyncProvider } from './contexts/DataSyncContext'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Configuracion from './pages/Configuracion'
import Ventas from './pages/Ventas'
import Gastos from './pages/Gastos'
import Inventario from './pages/Inventario'
import Clientes from './pages/Clientes'
import Chat from './pages/Chat'
import Login from './pages/Login'

// Spinner de carga de sesión
function SessionLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-gray-500 dark:text-gray-400">Cargando sesión…</p>
      </div>
    </div>
  )
}

// Shell principal de la app (requiere auth)
function AppShell({ activeTab, onTabChange }) {
  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
      <Sidebar activeTab={activeTab} onTabChange={onTabChange} />
      <main className="ml-56 flex-1 overflow-auto">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'ventas' && <Ventas />}
        {activeTab === 'gastos' && <Gastos />}
        {activeTab === 'inventario' && <Inventario />}
        {activeTab === 'clientes' && <Clientes />}
        {activeTab === 'chat' && <Chat />}
        {activeTab === 'configuracion' && <Configuracion />}
      </main>
    </div>
  )
}

// Componente interno: accede a AuthContext y decide qué mostrar
function AppContent() {
  const { isAuthenticated, loading } = useAuth()
  const [activeTab, setActiveTab] = useState('dashboard')

  if (loading) return <SessionLoader />
  if (!isAuthenticated) return <Login />
  return <AppShell activeTab={activeTab} onTabChange={setActiveTab} />
}

// AuthProvider va más afuera para que LanguageProvider y ThemeProvider
// puedan leer user.config al iniciar sesión
export default function App() {
  return (
    <AuthProvider>
      <DataSyncProvider>
        <LanguageProvider>
          <ThemeProvider>
            <AppContent />
          </ThemeProvider>
        </LanguageProvider>
      </DataSyncProvider>
    </AuthProvider>
  )
}
