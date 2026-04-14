import { useDark } from '../contexts/ThemeContext'
import { useLanguage } from '../contexts/LanguageContext'
import { useAuth } from '../contexts/AuthContext'

const navItems = [
  { id: 'dashboard', key: 'sidebar.dashboard', icon: '📊' },
  { id: 'ventas', key: 'sidebar.ventas', icon: '💰' },
  { id: 'gastos', key: 'sidebar.gastos', icon: '💸' },
  { id: 'inventario', key: 'sidebar.inventario', icon: '📦' },
  { id: 'clientes', key: 'sidebar.clientes', icon: '👥' },
  { id: 'chat', key: 'sidebar.chat', icon: '🤖' },
]

const bottomItems = [
  { id: 'configuracion', key: 'sidebar.config', icon: '⚙️' },
]

function UserAvatar({ user }) {
  const initial = (user.display_name || user.email || '?')[0].toUpperCase()
  if (user.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={user.display_name || user.email}
        className="w-7 h-7 rounded-full object-cover flex-shrink-0"
      />
    )
  }
  return (
    <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
      {initial}
    </div>
  )
}

function Sidebar({ activeTab, onTabChange }) {
  const { isDark, toggleDark } = useDark()
  const { t } = useLanguage()
  const { user, logout } = useAuth()

  return (
    <aside className="w-56 bg-gray-900 text-white flex flex-col h-screen fixed left-0 top-0">
      <div className="p-5 border-b border-gray-700">
        <h1 className="text-lg font-bold text-white">{t('sidebar.brand')}</h1>
        <p className="text-xs text-gray-400 mt-0.5">{t('sidebar.subtitle')}</p>
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
            <span>{t(item.key)}</span>
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
            <span>{t(item.key)}</span>
          </button>
        ))}

        <button
          onClick={toggleDark}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-white transition-colors text-left cursor-pointer"
          title={isDark ? t('sidebar.toggleLight') : t('sidebar.toggleDark')}
        >
          <span>{isDark ? '☀️' : '🌙'}</span>
          <span>{isDark ? t('sidebar.lightMode') : t('sidebar.darkMode')}</span>
        </button>

        {/* Zona de usuario + logout */}
        {user && (
          <div className="pt-1 border-t border-gray-700 mt-1">
            <div className="flex items-center gap-2 px-3 py-2">
              <UserAvatar user={user} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-gray-200 truncate">
                  {user.display_name || user.email}
                </p>
                {user.display_name && (
                  <p className="text-xs text-gray-500 truncate">{user.email}</p>
                )}
              </div>
            </div>
            <button
              onClick={logout}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-red-400 transition-colors text-left cursor-pointer"
            >
              <span>🚪</span>
              <span>{t('auth.logout')}</span>
            </button>
          </div>
        )}

        <p className="text-xs text-gray-600 px-3 pt-1">{t('sidebar.version')}</p>
      </div>
    </aside>
  )
}

export default Sidebar
