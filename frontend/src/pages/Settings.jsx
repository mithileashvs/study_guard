import { useEffect, useState } from 'react'
import {
  User,
  Camera,
  Bell,
  Target,
  Palette,
  Info,
  Check,
  X,
  ShieldCheck,
  CheckCircle2,
  Save,
} from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import api from '../data/api.js'
import './Settings.css'

const SETTINGS_TABS = [
  { id: 'general', label: 'General', icon: User },
  { id: 'monitoring', label: 'Monitoring', icon: Camera },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'focus', label: 'Focus Control', icon: Target },
  { id: 'appearance', label: 'Appearance', icon: Palette },
  { id: 'about', label: 'About', icon: Info },
]

function ChipInput({ placeholder, items, onAdd, onRemove }) {
  const [value, setValue] = useState('')

  const commit = () => {
    const trimmed = value.trim()
    if (!trimmed) return
    const exists = items.some((item) => item.toLowerCase() === trimmed.toLowerCase())
    if (exists) {
      setValue('')
      return
    }
    onAdd(trimmed)
    setValue('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      commit()
    }
  }

  return (
    <div className="settings-chip-block">
      <div className="settings-chip-input-row">
        <input
          type="text"
          className="settings-chip-input"
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button type="button" className="settings-chip-add-btn" onClick={commit}>
          Add
        </button>
      </div>
      {items.length > 0 && (
        <div className="settings-chip-list">
          {items.map((item) => (
            <span key={item} className="settings-chip">
              <span>{item}</span>
              <button
                type="button"
                className="settings-chip-remove"
                aria-label={`Remove ${item}`}
                onClick={() => onRemove(item)}
              >
                <X size={12} strokeWidth={2.4} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general')

  // Form states
  const [name, setName] = useState('Mithileash')
  const [email, setEmail] = useState('mithileash@example.com')
  const [theme, setTheme] = useState('Light')
  const [language, setLanguage] = useState('English')

  // Monitoring toggles
  const [cameraEnabled, setCameraEnabled] = useState(true)
  const [postureAlerts, setPostureAlerts] = useState(true)
  const [distractionAlerts, setDistractionAlerts] = useState(true)

  // Notifications
  const [soundEnabled, setSoundEnabled] = useState(true)
  const [breakReminders, setBreakReminders] = useState(true)

  // Focus Control: Allowed apps & keywords
  const [allowedSites, setAllowedSites] = useState([])
  const [allowedKeywords, setAllowedKeywords] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [savedToast, setSavedToast] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .getSettings()
      .then((data) => {
        if (cancelled) return
        setAllowedSites(data.allowed_apps || ['ChatGPT', 'Visual Studio Code', 'Google'])
        setAllowedKeywords(data.study_keywords || ['Python', 'DSA', 'LeetCode', 'Programming'])
        setLoaded(true)
      })
      .catch(() => {
        if (!cancelled) {
          setAllowedSites(['ChatGPT', 'Visual Studio Code', 'Google'])
          setAllowedKeywords(['Python', 'DSA', 'LeetCode', 'Programming'])
          setLoaded(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const persistSites = async (next, previous) => {
    setAllowedSites(next)
    try {
      await api.setAllowedApps(next)
      setSaveError('')
    } catch {
      setAllowedSites(previous)
      setSaveError('Could not sync with backend.')
    }
  }

  const persistKeywords = async (next, previous) => {
    setAllowedKeywords(next)
    try {
      await api.setStudyKeywords(next)
      setSaveError('')
    } catch {
      setAllowedKeywords(previous)
      setSaveError('Could not sync with backend.')
    }
  }

  const handleSaveAll = () => {
    setSavedToast(true)
    window.setTimeout(() => setSavedToast(false), 2400)
  }

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Customize your experience and focus preferences."
      >
        <button className="btn-primary" onClick={handleSaveAll}>
          {savedToast ? <Check size={15} /> : <Save size={15} />}
          <span>{savedToast ? 'Saved!' : 'Save Changes'}</span>
        </button>
      </PageHeader>

      <div className="settings-layout-grid">
        {/* Left Sub-Navigation Menu */}
        <Card className="settings-nav-card">
          <ul className="settings-nav-list">
            {SETTINGS_TABS.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <li key={tab.id}>
                  <button
                    type="button"
                    className={`settings-nav-btn${isActive ? ' active' : ''}`}
                    onClick={() => setActiveTab(tab.id)}
                  >
                    <Icon size={16} strokeWidth={1.9} />
                    <span>{tab.label}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </Card>

        {/* Center Main Settings Form Card */}
        <Card className="settings-content-card">
          {activeTab === 'general' && (
            <div className="settings-tab-panel">
              <div className="settings-panel-header">
                <h3 className="panel-title">General</h3>
                <p className="panel-sub">Basic information and preferences.</p>
              </div>

              <div className="settings-form-row">
                <label className="settings-label" htmlFor="user-name">
                  Name
                </label>
                <input
                  id="user-name"
                  type="text"
                  className="settings-text-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              <div className="settings-form-row">
                <label className="settings-label" htmlFor="user-email">
                  Email
                </label>
                <input
                  id="user-email"
                  type="email"
                  className="settings-text-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="settings-form-row">
                <label className="settings-label">Theme</label>
                <div className="theme-toggle-group">
                  {['Light', 'Dark', 'System'].map((t) => (
                    <button
                      key={t}
                      type="button"
                      className={`theme-option-btn${theme === t ? ' selected' : ''}`}
                      onClick={() => setTheme(t)}
                    >
                      <span className="theme-radio-dot" />
                      <span>{t}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="settings-form-row">
                <label className="settings-label" htmlFor="language-select">
                  Language
                </label>
                <select
                  id="language-select"
                  className="settings-select-input"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="English">English</option>
                  <option value="Spanish">Español</option>
                  <option value="German">Deutsch</option>
                  <option value="French">Français</option>
                </select>
              </div>
            </div>
          )}

          {activeTab === 'monitoring' && (
            <div className="settings-tab-panel">
              <div className="settings-panel-header">
                <h3 className="panel-title">Monitoring</h3>
                <p className="panel-sub">
                  Configure camera detection, posture thresholds, and focus alerts.
                </p>
              </div>

              <div className="settings-toggle-item">
                <div className="toggle-text-wrap">
                  <span className="toggle-item-title">Camera Monitoring</span>
                  <span className="toggle-item-sub">
                    Enables local webcam posture and presence tracking. No video is ever sent over the network.
                  </span>
                </div>
                <button
                  type="button"
                  className={`switch-track${cameraEnabled ? ' on' : ''}`}
                  onClick={() => setCameraEnabled(!cameraEnabled)}
                  role="switch"
                  aria-checked={cameraEnabled}
                  aria-label="Toggle camera monitoring"
                >
                  <span className="switch-thumb" />
                </button>
              </div>

              <div className="settings-toggle-item">
                <div className="toggle-text-wrap">
                  <span className="toggle-item-title">Posture Alerts</span>
                  <span className="toggle-item-sub">
                    Sends a gentle alert if slouching is detected for more than 15 seconds.
                  </span>
                </div>
                <button
                  type="button"
                  className={`switch-track${postureAlerts ? ' on' : ''}`}
                  onClick={() => setPostureAlerts(!postureAlerts)}
                  role="switch"
                  aria-checked={postureAlerts}
                  aria-label="Toggle posture alerts"
                >
                  <span className="switch-thumb" />
                </button>
              </div>

              <div className="settings-toggle-item">
                <div className="toggle-text-wrap">
                  <span className="toggle-item-title">Distraction Engine</span>
                  <span className="toggle-item-sub">
                    Monitors distraction patterns according to your session study mode.
                  </span>
                </div>
                <button
                  type="button"
                  className={`switch-track${distractionAlerts ? ' on' : ''}`}
                  onClick={() => setDistractionAlerts(!distractionAlerts)}
                  role="switch"
                  aria-checked={distractionAlerts}
                  aria-label="Toggle distraction alerts"
                >
                  <span className="switch-thumb" />
                </button>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="settings-tab-panel">
              <div className="settings-panel-header">
                <h3 className="panel-title">Notifications</h3>
                <p className="panel-sub">Control audible notifications and session alerts.</p>
              </div>

              <div className="settings-toggle-item">
                <div className="toggle-text-wrap">
                  <span className="toggle-item-title">Sound Alerts</span>
                  <span className="toggle-item-sub">
                    Play a subtle chime when milestone is completed or session timer ends.
                  </span>
                </div>
                <button
                  type="button"
                  className={`switch-track${soundEnabled ? ' on' : ''}`}
                  onClick={() => setSoundEnabled(!soundEnabled)}
                  role="switch"
                  aria-checked={soundEnabled}
                  aria-label="Toggle sound alerts"
                >
                  <span className="switch-thumb" />
                </button>
              </div>

              <div className="settings-toggle-item">
                <div className="toggle-text-wrap">
                  <span className="toggle-item-title">Break Reminders</span>
                  <span className="toggle-item-sub">
                    Remind you to stretch and rest your eyes after long continuous focus periods.
                  </span>
                </div>
                <button
                  type="button"
                  className={`switch-track${breakReminders ? ' on' : ''}`}
                  onClick={() => setBreakReminders(!breakReminders)}
                  role="switch"
                  aria-checked={breakReminders}
                  aria-label="Toggle break reminders"
                >
                  <span className="switch-thumb" />
                </button>
              </div>
            </div>
          )}

          {activeTab === 'focus' && (
            <div className="settings-tab-panel">
              <div className="settings-panel-header">
                <h3 className="panel-title">Focus Control</h3>
                <p className="panel-sub">
                  Define websites, tools, and keywords Study Guard should consider productive.
                </p>
              </div>

              <div className="settings-section-block">
                <span className="settings-block-title">Allowed Sites & Apps</span>
                <span className="settings-block-sub">
                  Applications that will never trigger a distraction notification.
                </span>
                <ChipInput
                  placeholder="e.g. Visual Studio Code, Figma, Notion..."
                  items={allowedSites}
                  onAdd={(site) => persistSites([...allowedSites, site], allowedSites)}
                  onRemove={(site) =>
                    persistSites(allowedSites.filter((s) => s !== site), allowedSites)
                  }
                />
              </div>

              <div className="settings-section-block">
                <span className="settings-block-title">Allowed Keywords</span>
                <span className="settings-block-sub">
                  Keywords that indicate productive study when matched in active tasks.
                </span>
                <ChipInput
                  placeholder="e.g. Algorithms, Data Structures, Documentation..."
                  items={allowedKeywords}
                  onAdd={(kw) => persistKeywords([...allowedKeywords, kw], allowedKeywords)}
                  onRemove={(kw) =>
                    persistKeywords(allowedKeywords.filter((k) => k !== kw), allowedKeywords)
                  }
                />
              </div>

              {saveError && <p className="settings-error-tag">{saveError}</p>}

              <div className="settings-info-card">
                <span className="info-card-header">
                  <ShieldCheck size={16} />
                  <span>How It Works</span>
                </span>
                <ul className="info-card-list">
                  <li>
                    <CheckCircle2 size={13} />
                    <span>Allowed sites and keywords prevent false distraction flags.</span>
                  </li>
                  <li>
                    <CheckCircle2 size={13} />
                    <span>Changes sync automatically to your local Study Guard desktop agent.</span>
                  </li>
                </ul>
              </div>
            </div>
          )}

          {activeTab === 'appearance' && (
            <div className="settings-tab-panel">
              <div className="settings-panel-header">
                <h3 className="panel-title">Appearance</h3>
                <p className="panel-sub">Visual theme and interface preferences.</p>
              </div>

              <div className="settings-form-row">
                <label className="settings-label">Color Theme</label>
                <div className="theme-toggle-group">
                  {['Light', 'Dark', 'System'].map((t) => (
                    <button
                      key={t}
                      type="button"
                      className={`theme-option-btn${theme === t ? ' selected' : ''}`}
                      onClick={() => setTheme(t)}
                    >
                      <span className="theme-radio-dot" />
                      <span>{t}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'about' && (
            <div className="settings-tab-panel">
              <div className="settings-panel-header">
                <h3 className="panel-title">About Study Guard</h3>
                <p className="panel-sub">System information and agent status.</p>
              </div>

              <div className="about-details-list">
                <div className="about-row">
                  <span className="about-label">Application Version</span>
                  <span className="about-value">Study Guard v1.0.0</span>
                </div>
                <div className="about-row">
                  <span className="about-label">Desktop Agent Status</span>
                  <span className="about-value active">Connected (127.0.0.1:8000)</span>
                </div>
                <div className="about-row">
                  <span className="about-label">Design System</span>
                  <span className="about-value">Minimalist Technical Indigo</span>
                </div>
              </div>
            </div>
          )}
        </Card>

        {/* Right Side Visual Banner Panel */}
        <div className="settings-visual-card">
          <img
            src="/assets/study_plant.jpg"
            alt="Minimalist houseplant"
            className="settings-visual-image"
          />
          <div className="settings-visual-overlay">
            <h3 className="settings-visual-quote">
              A focused tomorrow<br />starts with the<br />choices you make<br />today.
            </h3>
          </div>
        </div>
      </div>

      <Footer />
    </>
  )
}
