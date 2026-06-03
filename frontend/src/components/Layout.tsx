import { Outlet, NavLink } from 'react-router-dom'
import { Brain, Upload, Search, Wallet, Network, Zap, Coins } from 'lucide-react'
import { useWallet } from '../hooks/useWallet'

function Layout() {
  const { connected, publicKey, connecting, error, connect, disconnect } = useWallet()

  const navItems = [
    { to: '/', icon: Brain, label: 'Dashboard' },
    { to: '/upload', icon: Upload, label: 'Upload' },
    { to: '/search', icon: Search, label: 'Search' },
    { to: '/paid-search', icon: Zap, label: 'Paid Search' },
    { to: '/wallet', icon: Coins, label: 'Wallet & Earnings' },
    { to: '/graph', icon: Network, label: 'Knowledge Graph' },
  ]

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-dark-800 border-r border-dark-400 flex flex-col">
        <div className="p-6 border-b border-dark-400">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-stellar-600 rounded-lg flex items-center justify-center">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg">DecentraKnow</h1>
              <p className="text-xs text-dark-200">AI Knowledge Network</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? 'bg-stellar-600/20 text-stellar-400 border border-stellar-600/30'
                    : 'text-dark-100 hover:bg-dark-600 hover:text-white'
                }`
              }
            >
              <Icon className="w-5 h-5" />
              <span className="font-medium">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-dark-400">
          {connected ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm">
                <div className="w-2 h-2 bg-green-400 rounded-full" />
                <span className="text-dark-100 truncate">
                  {publicKey?.slice(0, 8)}...{publicKey?.slice(-4)}
                </span>
              </div>
              <button onClick={disconnect} className="btn-secondary w-full text-sm">
                Disconnect
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <button
                onClick={connect}
                disabled={connecting}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                <Wallet className="w-4 h-4" />
                {connecting ? 'Connecting...' : 'Connect Wallet'}
              </button>
              {error && (
                <p className="text-xs text-red-400 text-center">{error}</p>
              )}
            </div>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default Layout
