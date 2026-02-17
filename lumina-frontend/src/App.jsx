import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Configuracion from './pages/Configuracion'
import Ventas from './pages/Ventas'
import Gastos from './pages/Gastos'
import Inventario from './pages/Inventario'
import Clientes from './pages/Clientes'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="ml-56 flex-1 overflow-auto">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'ventas' && <Ventas />}
        {activeTab === 'gastos' && <Gastos />}
        {activeTab === 'inventario' && <Inventario />}
        {activeTab === 'clientes' && <Clientes />}
        {activeTab === 'configuracion' && <Configuracion />}
      </main>
    </div>
  )
}

export default App
