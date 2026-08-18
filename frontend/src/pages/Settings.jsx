import { useEffect, useState } from 'react'
import { Bell, Camera, Moon, User, ShieldCheck, X, CheckCircle2 } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import api from '../data/api.js'
import './Settings.css'

const initialToggles = [
  { id: 'notifications', label: 'Notifications', desc: 'Get alerted about distractions and posture', icon: Bell, on: true },
  { id: 'camera', label: 'Camera monitoring', desc: 'Allow Study Guard to use your camera during sessions', icon: Camera, on: true },
  { id: 'darkmode', label: 'Dark mode', desc: 'Switch to a darker color theme', icon: Moon, on: false },
]

function ChipInput({ placeholder, items, onAdd, onRemove }) {
  const [value, setValue] = useState('')
  const [pulseKey, setPulseKey] = useState(null)

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
    setPulseKey(trimmed)
    window.setTimeout(() => setPulseKey(null), 900)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      commit()
    }
  }

  const handleRemove = (item) => {
    onRemove(item)
  }

  return (
    <div className="chip-input-block">
      <div className="chip-input-row">
        <input
          type="text"
          className="chip-input"
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button type="button" className="chip-input-add" onClick={commit}>
          Add
        </button>
      </div>
      {items.length > 0 && (
        <ul className="chip-list">
          {items.map((item) => (
            <li key={item} className={`chip${pulseKey === item ? ' chip-added' : ''}`}>
              {item}
              <button
                type="button"
                className="chip-remove"
                aria-label={`Remove ${item}`}
                onClick={() => handleRemove(item)}
              >
                <X size={13} strokeWidth={2.4} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function Settings() {
  const [toggles, setToggles] = useState(initialToggles)
  const [allowedSites, setAllowedSites] = useState([])
  const [allowedKeywords, setAllowedKeywords] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .getSettings()
      .then((data) => {
        if (cancelled) return
        setAllowedSites(data.allowed_apps || [])
        setAllowedKeywords(data.study_keywords || [])
        setLoaded(true)
      })
      .catch(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const toggle = (id) =>
    setToggles((prev) => prev.map((t) => (t.id === id ? { ...t, on: !t.on } : t)))

  // Every add/remove is pushed straight to the backend (STEP 9/10 —
  // these settings must reach Python, not just live in local state).
  // Optimistic UI update first, then persist; on failure the chip
  // list is reverted so the UI never shows a setting that didn't
  // actually make it to the backend.
  const persistSites = async (next, previous) => {
    setAllowedSites(next)
    try {
      await api.setAllowedApps(next)
      setSaveError('')
    } catch {
      setAllowedSites(previous)
      setSaveError('Could not save — is Study Guard running?')
    }
  }

  const persistKeywords = async (next, previous) => {
    setAllowedKeywords(next)
    try {
      await api.setStudyKeywords(next)
      setSaveError('')
    } catch {
      setAllowedKeywords(previous)
      setSaveError('Could not save — is Study Guard running?')
    }
  }

  const addSite = (site) => persistSites([...allowedSites, site], allowedSites)
  const removeSite = (site) => persistSites(allowedSites.filter((s) => s !== site), allowedSites)
  const addKeyword = (keyword) => persistKeywords([...allowedKeywords, keyword], allowedKeywords)
  const removeKeyword = (keyword) =>
    persistKeywords(allowedKeywords.filter((k) => k !== keyword), allowedKeywords)

  return (
    <>
      <PageHeader title="Settings" subtitle="Manage your account and Study Guard preferences." />

      <Card className="settings-card">
        <div className="settings-profile-row">
          <span className="settings-avatar">
            <User size={22} strokeWidth={2.2} />
          </span>
          <div>
            <p className="settings-profile-name">Mithileash</p>
            <p className="settings-profile-email">mithileash@example.com</p>
          </div>
        </div>
      </Card>

      <Card className="settings-card">
        <p className="section-title">Preferences</p>
        <ul className="settings-toggle-list">
          {toggles.map((t) => (
            <li key={t.id} className="settings-toggle-row">
              <span className="settings-toggle-icon">
                <t.icon size={17} strokeWidth={2.2} />
              </span>
              <div className="settings-toggle-body">
                <p className="settings-toggle-label">{t.label}</p>
                <p className="settings-toggle-desc">{t.desc}</p>
              </div>
              <button
                className={`toggle-switch${t.on ? ' on' : ''}`}
                role="switch"
                aria-checked={t.on}
                aria-label={t.label}
                onClick={() => toggle(t.id)}
              >
                <span className="toggle-knob" />
              </button>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="settings-card">
        <p className="section-title">Distraction Control</p>
        <p className="settings-section-subtitle">
          Choose which websites, applications, and keywords Study Guard should ignore while
          monitoring your focus.
        </p>

        <div className="distraction-block">
          <p className="distraction-block-title">Allowed Sites &amp; Apps</p>
          <p className="distraction-block-desc">
            Websites and applications that should never trigger distraction alerts.
          </p>
          <ChipInput
            placeholder="Enter website or application..."
            items={allowedSites}
            onAdd={addSite}
            onRemove={removeSite}
          />
        </div>

        <div className="distraction-block">
          <p className="distraction-block-title">Allowed Keywords</p>
          <p className="distraction-block-desc">
            Keywords that should not be treated as distractions when they appear in the active
            window.
          </p>
          <ChipInput
            placeholder="Enter keyword..."
            items={allowedKeywords}
            onAdd={addKeyword}
            onRemove={removeKeyword}
          />
        </div>

        {saveError && <p className="settings-save-error">{saveError}</p>}
        {!loaded && <p className="settings-save-error">Loading current settings…</p>}

        <div className="distraction-info-card">
          <p className="distraction-info-title">
            <ShieldCheck size={16} strokeWidth={2.2} />
            How It Works
          </p>
          <ul className="distraction-info-list">
            <li>
              <CheckCircle2 size={14} strokeWidth={2.4} />
              Allowed sites won't trigger distraction alerts.
            </li>
            <li>
              <CheckCircle2 size={14} strokeWidth={2.4} />
              Allowed keywords can be used to identify productive activity.
            </li>
            <li>
              <CheckCircle2 size={14} strokeWidth={2.4} />
              You can change these settings anytime.
            </li>
          </ul>
        </div>
      </Card>

      <Footer />
    </>
  )
}
