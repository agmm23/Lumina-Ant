const navItems = [
  { id: 'dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'ventas', label: 'Ventas', icon: '💰' },
  { id: 'gastos', label: 'Gastos', icon: '💸' },
  { id: 'inventario', label: 'Inventario', icon: '📦' },
  { id: 'clientes', label: 'Clientes', icon: '👥' },
]

const bottomItems = [
  { id: 'configuracion', label: 'Configuración', icon: '⚙️' },
]

function Sidebar({ activeTab, onTabChange }) {
  return (
    <aside className="w-56 bg-gray-900 text-white flex flex-col h-screen fixed left-0 top-0">
      <div className="p-5 border-b border-gray-700">
        <h1 className="text-lg font-bold text-white">Lumina Ant</h1>
        <p className="text-xs text-gray-400 mt-0.5">Business Intelligence</p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left cursor-pointer ${
              activeTab === item.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            }`}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="p-3 border-t border-gray-700 space-y-1">
        {bottomItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left cursor-pointer ${
              activeTab === item.id
                ? 'bg-blue-600 text-white'
                : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            }`}
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
        <p className="text-xs text-gray-600 px-3 pt-1">v0.1.0 — Fase 1</p>
      </div>
    </aside>
  )
}

export default Sidebar
