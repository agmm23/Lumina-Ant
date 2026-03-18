import { useState } from 'react'
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

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')

  return (
    <DataSyncProvider>
    <LanguageProvider>
    <ThemeProvider>
      <div className="flex min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
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
    </ThemeProvider>
    </LanguageProvider>
    </DataSyncProvider>
  )
}

export default App
