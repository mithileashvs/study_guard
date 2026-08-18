import { NavLink, useNavigate } from 'react-router-dom'
import {
  Shield,
  Home,
  Target,
  Video,
  CalendarDays,
  BarChart3,
  History as HistoryIcon,
  Settings as SettingsIcon,
  ChevronRight,
} from 'lucide-react'
import { activeCompanion } from '../data/mockData.js'
import './Sidebar.css'

const navItems = [
  { to: '/', label: 'Overview', icon: Home, tone: 'purple' },
  { to: '/roadmap', label: 'Roadmap', icon: Target, tone: 'red' },
  { to: '/live-session', label: 'Live Session', icon: Video, tone: 'purple' },
  { to: '/sessions', label: 'Sessions', icon: CalendarDays, tone: 'blue' },
  { to: '/analytics', label: 'Analytics', icon: BarChart3, tone: 'green' },
  { to: '/history', label: 'History', icon: HistoryIcon, tone: 'purple' },
]

export default function Sidebar() {
  const navigate = useNavigate()

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <Shield size={20} strokeWidth={2.4} />
        </div>
        <div>
          <p className="sidebar-brand-title">Study Guard</p>
          <p className="sidebar-brand-subtitle">Your focus companion</p>
        </div>
      </div>

      <nav className="sidebar-nav">
        <ul>
          {navItems.map(({ to, label, icon: Icon, tone }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  'sidebar-nav-item' + (isActive ? ' active' : '')
                }
              >
                <span className={`sidebar-nav-icon tone-${tone}`}>
                  <Icon size={18} strokeWidth={2.2} />
                </span>
                <span className="sidebar-nav-label">{label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="sidebar-divider" />

      <div className="sidebar-companion-section">
        <p className="sidebar-section-title">Study Companion</p>
        <button
          className="companion-card"
          onClick={() => navigate('/companion')}
          aria-label={`Open ${activeCompanion.name} companion page`}
        >
          <span className="companion-emoji" aria-hidden="true">
            {activeCompanion.emoji}
          </span>
          <span className="companion-info">
            <span className="companion-name">{activeCompanion.name}</span>
            <span className="companion-tagline">{activeCompanion.tagline}</span>
          </span>
          <ChevronRight size={18} className="companion-chevron" />
        </button>
      </div>

      <div className="sidebar-footer">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            'sidebar-settings-item' + (isActive ? ' active' : '')
          }
        >
          <SettingsIcon size={18} strokeWidth={2.2} />
          <span>Settings</span>
        </NavLink>
      </div>
    </aside>
  )
}
