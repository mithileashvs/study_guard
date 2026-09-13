import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Route,
  Video,
  Calendar,
  BarChart3,
  Clock,
  Sparkles,
  Settings as SettingsIcon,
  Menu,
  X,
} from 'lucide-react'
import Logo from './Logo.jsx'
import './Sidebar.css'

const mainNav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/roadmap', label: 'Roadmap', icon: Route },
  { to: '/live-session', label: 'Live Session', icon: Video },
  { to: '/sessions', label: 'Sessions', icon: Calendar },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/history', label: 'History', icon: Clock },
]

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false)

  const closeMobile = () => setMobileOpen(false)

  return (
    <>
      {/* Mobile Header */}
      <header className="mobile-header">
        <div className="mobile-brand">
          <Logo size={22} color="#FFFFFF" />
          <span className="mobile-title">Study Guard</span>
        </div>
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'}
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* Backdrop for mobile */}
      {mobileOpen && <div className="sidebar-backdrop" onClick={closeMobile} />}

      <aside className={`sidebar${mobileOpen ? ' open' : ''}`}>
        {/* Brand Header */}
        <div className="sidebar-brand">
          <div className="sidebar-logo-wrap">
            <Logo size={22} color="#FFFFFF" />
          </div>
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-title">Study Guard</span>
            <span className="sidebar-brand-subtitle">Focus. Learn. Grow.</span>
          </div>
        </div>

        {/* Main Navigation */}
        <nav className="sidebar-nav">
          <ul>
            {mainNav.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  onClick={closeMobile}
                  className={({ isActive }) =>
                    'sidebar-nav-item' + (isActive ? ' active' : '')
                  }
                >
                  <Icon size={17} strokeWidth={1.9} className="nav-icon" />
                  <span className="nav-label">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>

          {/* Tools Section */}
          <div className="sidebar-section">
            <p className="sidebar-section-title">TOOLS</p>
            <ul>
              <li>
                <NavLink
                  to="/companion"
                  onClick={closeMobile}
                  className={({ isActive }) =>
                    'sidebar-nav-item' + (isActive ? ' active' : '')
                  }
                >
                  <Sparkles size={17} strokeWidth={1.9} className="nav-icon" />
                  <span className="nav-label">Study Companion</span>
                </NavLink>
              </li>
            </ul>
          </div>
        </nav>

        {/* Footer Area: Settings & Profile */}
        <div className="sidebar-footer">
          <NavLink
            to="/settings"
            onClick={closeMobile}
            className={({ isActive }) =>
              'sidebar-nav-item settings-item' + (isActive ? ' active' : '')
            }
          >
            <SettingsIcon size={17} strokeWidth={1.9} className="nav-icon" />
            <span className="nav-label">Settings</span>
          </NavLink>

          <div className="sidebar-user-profile">
            <div className="user-avatar" aria-hidden="true">
              M
            </div>
            <div className="user-meta">
              <span className="user-name">Mithileash</span>
              <span className="user-status">Stay consistent.</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
