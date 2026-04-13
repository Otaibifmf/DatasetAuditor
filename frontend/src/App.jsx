import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './components/Dashboard'
import DatasetDetail from './components/DatasetDetail'
import Leaderboard from './components/Leaderboard'
import TrendView from './components/TrendView'
import History from './components/History'

const NAV = [
  { to: '/',            label: 'Dashboard',   end: true },
  { to: '/leaderboard', label: 'Leaderboard', end: false },
  { to: '/trends',      label: 'Trends',      end: false },
  { to: '/history',     label: 'History',     end: false },
]

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* ── Header ───────────────────────────────────────────── */}
      <header className="bg-brand-900 text-white shadow-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center h-14 gap-6">
            {/* Logo */}
            <div className="flex items-center gap-2.5 flex-shrink-0">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-400 to-brand-600 rounded-lg flex items-center justify-center font-black text-xs tracking-tight shadow-inner">
                DC
              </div>
              <span className="font-bold text-base tracking-tight">DataChecker</span>
              <span className="text-brand-300 text-xs hidden sm:block border-l border-brand-700 pl-2.5">
                Saudi Open Data Auditor
              </span>
            </div>

            {/* Nav */}
            <nav className="flex gap-0.5 ml-2">
              {NAV.map(({ to, label, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-brand-700/80 text-white shadow-sm'
                        : 'text-brand-200 hover:text-white hover:bg-brand-800'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>

            <div className="ml-auto text-xs text-brand-400 hidden md:block">
              data.gov.sa · Vision 2030
            </div>
          </div>
        </div>
      </header>

      {/* ── Main ─────────────────────────────────────────────── */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8">
        <Routes>
          <Route path="/"               element={<Dashboard />} />
          <Route path="/dataset/:id"    element={<DatasetDetail />} />
          <Route path="/leaderboard"    element={<Leaderboard />} />
          <Route path="/trends"         element={<TrendView />} />
          <Route path="/history"        element={<History />} />
        </Routes>
      </main>

      <footer className="border-t border-gray-200 py-4 text-center text-xs text-gray-400">
        DataChecker · Saudi Open Data Quality Platform · Vision 2030 Accountability
      </footer>
    </div>
  )
}
