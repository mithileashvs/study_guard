import { useEffect, useState } from 'react'
import { Play, Pause, Square, CheckCircle2 } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import LiveFocusMonitor from '../components/LiveFocusMonitor.jsx'
import useSessionControl, { formatCountdown } from '../data/useSessionControl.js'
import api from '../data/api.js'
import './LiveSession.css'

const DURATION_PRESETS = [25, 45, 60]

// Mirrors config.STUDY_MODES on the backend (session_context.create_session
// upper-cases and falls back to DEFAULT_STUDY_MODE for anything else, so
// this list only needs to stay in sync for a sensible UI -- it isn't the
// source of truth for validation).
const SESSION_MODES = [
  { value: 'STRICT', label: 'Strict', desc: 'Shortest grace period before a distraction counts' },
  { value: 'BALANCED', label: 'Balanced', desc: 'Default grace period' },
  { value: 'FLEXIBLE', label: 'Flexible', desc: 'Longest grace period before a distraction counts' },
]
const DEFAULT_SESSION_MODE = 'BALANCED'

function ReadinessRow() {
  const [readiness, setReadiness] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.getSessionReadiness()
      .then((data) => { if (!cancelled) setReadiness(data) })
      .catch(() => { if (!cancelled) setReadiness({ camera_ready: false, posture_ready: false, focus_monitor_ready: false }) })
    return () => { cancelled = true }
  }, [])

  const items = [
    { label: 'Camera Ready', ok: readiness?.camera_ready },
    { label: 'Posture Ready', ok: readiness?.posture_ready },
    { label: 'Focus Monitor Ready', ok: readiness?.focus_monitor_ready },
  ]

  return (
    <Card className="readiness-card">
      {items.map((item) => (
        <span className="readiness-item" key={item.label}>
          <span className={`readiness-dot${item.ok ? ' ok' : ''}`} />
          {item.label}
        </span>
      ))}
    </Card>
  )
}

// The one and only session-start configuration surface. Everything the
// backend's /api/session/start accepts (see data/api.js -> startSession,
// and desktop-agent/session_bridge.py -> request_start) is collected here
// -- session name (-> "subject"), session mode, and duration -- before the
// user can confirm, so there's a single place building the payload rather
// than a parallel/duplicate session-start path elsewhere.
function SessionSetupModal({ onCancel, onStart, starting }) {
  const [selected, setSelected] = useState(45)
  const [custom, setCustom] = useState('')
  const [sessionName, setSessionName] = useState('')
  const [mode, setMode] = useState(DEFAULT_SESSION_MODE)

  const effectiveMinutes = custom.trim() ? Number(custom) : selected
  const isValid = Number.isFinite(effectiveMinutes) && effectiveMinutes > 0 && effectiveMinutes <= 360

  const handleConfirm = () => {
    if (!isValid || starting) return
    onStart(effectiveMinutes, { subject: sessionName.trim(), mode })
  }

  return (
    <div className="duration-modal-backdrop" role="dialog" aria-modal="true">
      <Card className="duration-modal">
        <h2 className="duration-modal-title">Start Study Session</h2>
        <p className="duration-modal-subtitle">Set up your session, then confirm to begin.</p>

        <label className="duration-custom-label" htmlFor="session-name">
          Session name
        </label>
        <div className="duration-custom-row">
          <input
            id="session-name"
            type="text"
            placeholder="e.g. Algebra Homework"
            value={sessionName}
            onChange={(e) => setSessionName(e.target.value)}
            className="duration-custom-input"
            maxLength={80}
          />
        </div>

        <label className="duration-custom-label" htmlFor="session-mode">
          Session mode
        </label>
        <div className="duration-presets">
          {SESSION_MODES.map((m) => (
            <button
              key={m.value}
              type="button"
              title={m.desc}
              className={`duration-preset-btn${mode === m.value ? ' selected' : ''}`}
              onClick={() => setMode(m.value)}
            >
              {m.label}
            </button>
          ))}
        </div>

        <label className="duration-custom-label">
          Duration
        </label>
        <div className="duration-presets">
          {DURATION_PRESETS.map((mins) => (
            <button
              key={mins}
              className={`duration-preset-btn${!custom.trim() && selected === mins ? ' selected' : ''}`}
              onClick={() => { setSelected(mins); setCustom('') }}
            >
              {mins} min
            </button>
          ))}
        </div>

        <label className="duration-custom-label" htmlFor="custom-duration">
          Custom duration
        </label>
        <div className="duration-custom-row">
          <input
            id="custom-duration"
            type="number"
            min="1"
            max="360"
            placeholder="e.g. 90"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            className="duration-custom-input"
          />
          <span className="duration-custom-unit">minutes</span>
        </div>

        <div className="duration-modal-actions">
          <button className="control-btn" onClick={onCancel} disabled={starting}>Cancel</button>
          <button
            className="control-btn control-btn-primary"
            disabled={!isValid || starting}
            onClick={handleConfirm}
          >
            {starting ? 'STARTING…' : 'START SESSION'}
          </button>
        </div>
      </Card>
    </div>
  )
}

function CalibratingState({ state }) {
  const progress = Math.round((state?.calibration_progress || 0) * 100)
  const done = progress >= 100

  return (
    <Card className="session-hero-card">
      <p className="session-hero-eyebrow">Preparing your study session...</p>
      {(state?.subject || state?.study_mode) && (
        <p className="session-active-subject">
          {state?.subject}{state?.subject && state?.study_mode ? ' · ' : ''}{state?.study_mode}
        </p>
      )}
      <p className="session-hero-title">Sit comfortably and maintain your normal good posture.</p>

      <div className="calibration-progress-track">
        <div className="calibration-progress-fill" style={{ width: `${progress}%` }} />
      </div>

      {done ? (
        <p className="calibration-status done">Calibration complete <CheckCircle2 size={16} strokeWidth={2.6} /></p>
      ) : (
        <p className="calibration-status">Calibrating posture... {progress}%</p>
      )}

      <div className="calibration-readiness-row">
        <span className="readiness-item"><span className="readiness-dot ok" />Camera: Connected</span>
        <span className="readiness-item"><span className={`readiness-dot${done ? ' ok' : ''}`} />Posture: {done ? 'Calibrated' : 'Calibrating'}</span>
        <span className="readiness-item"><span className="readiness-dot ok" />Focus Monitor: Ready</span>
      </div>
    </Card>
  )
}

function ActiveState({ state, onPause, onEnd }) {
  const remaining = formatCountdown(state?.remaining_seconds)

  return (
    <>
      <div className="session-active-header">
        <span className="session-active-pill">SESSION ACTIVE</span>
        {(state?.subject || state?.study_mode) && (
          <p className="session-active-subject">
            {state?.subject}{state?.subject && state?.study_mode ? ' · ' : ''}{state?.study_mode}
          </p>
        )}
        <p className="session-active-timer">{remaining} remaining</p>
      </div>

      <LiveFocusMonitor />

      <div className="session-controls-buttons">
        <button className="control-btn" onClick={onPause}>
          <Pause size={16} strokeWidth={2.4} />
          PAUSE SESSION
        </button>
        <button className="control-btn control-btn-danger" onClick={onEnd}>
          <Square size={16} strokeWidth={2.4} />
          END SESSION
        </button>
      </div>
    </>
  )
}

function PausedState({ state, onResume, onEnd }) {
  const remaining = formatCountdown(state?.remaining_seconds)

  return (
    <Card className="session-hero-card">
      <p className="session-hero-eyebrow">SESSION PAUSED</p>
      {(state?.subject || state?.study_mode) && (
        <p className="session-active-subject">
          {state?.subject}{state?.subject && state?.study_mode ? ' · ' : ''}{state?.study_mode}
        </p>
      )}
      <p className="session-active-timer">{remaining} remaining</p>

      <div className="session-controls-buttons centered">
        <button className="control-btn control-btn-primary" onClick={onResume}>
          <Play size={16} strokeWidth={2.4} />
          RESUME SESSION
        </button>
        <button className="control-btn control-btn-danger" onClick={onEnd}>
          <Square size={16} strokeWidth={2.4} />
          END SESSION
        </button>
      </div>
    </Card>
  )
}

function CompleteState({ state, onStartNew, auto }) {
  const summary = state?.last_summary
  const minutes = summary ? Math.round(summary.duration_seconds / 60) : 0
  const focusPct = summary && summary.duration_seconds > 0
    ? Math.round(100 * summary.focus_seconds / summary.duration_seconds)
    : null
  const postureScore = summary?.score?.posture ?? null

  return (
    <Card className="session-hero-card">
      <p className="session-hero-title">{auto ? 'SESSION COMPLETE 🎉' : 'SESSION COMPLETE ✓'}</p>
      {auto && <p className="session-hero-eyebrow">Your study session is finished.</p>}

      {summary && (
        <div className="session-summary-grid">
          <div><span className="summary-label">Study duration</span><span className="summary-value">{minutes} min</span></div>
          <div><span className="summary-label">Focus score</span><span className="summary-value">{summary.score ? `${summary.score.overall}%` : '—'}</span></div>
          <div><span className="summary-label">Distractions</span><span className="summary-value">{summary.distraction_events}</span></div>
          <div><span className="summary-label">Posture</span><span className="summary-value">{postureScore != null ? `${postureScore}%` : (focusPct != null ? `${focusPct}% good` : '—')}</span></div>
        </div>
      )}

      <button className="control-btn control-btn-primary" onClick={onStartNew}>
        START NEW SESSION
      </button>
    </Card>
  )
}

export default function LiveSession() {
  const { state, start, pause, resume, end, acknowledge } = useSessionControl()
  const [showDurationPicker, setShowDurationPicker] = useState(false)
  const [starting, setStarting] = useState(false)

  const phase = state?.phase || 'IDLE'

  const handleStart = async (minutes, opts) => {
    setStarting(true)
    try {
      await start(minutes, opts)
      setShowDurationPicker(false)
    } finally {
      setStarting(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Live Session"
        subtitle="Everything you need to begin a focused study session."
      />

      {phase === 'IDLE' && (
        <>
          <Card className="session-hero-card">
            <span className="session-hero-icon"><Play size={28} strokeWidth={2.6} /></span>
            <p className="session-hero-title">Ready to study?</p>
            <p className="session-hero-subtitle">Start your session and calibrate posture.</p>
            <button className="control-btn control-btn-primary control-btn-lg" onClick={() => setShowDurationPicker(true)}>
              START STUDY SESSION
            </button>
          </Card>
          <ReadinessRow />
        </>
      )}

      {phase === 'CALIBRATING' && <CalibratingState state={state} />}

      {phase === 'ACTIVE' && <ActiveState state={state} onPause={pause} onEnd={end} />}

      {phase === 'PAUSED' && <PausedState state={state} onResume={resume} onEnd={end} />}

      {phase === 'COMPLETE' && (
        <CompleteState
          state={state}
          auto={state?.last_summary?.duration_seconds >= (state?.duration_seconds || Infinity)}
          onStartNew={async () => { await acknowledge() }}
        />
      )}

      {showDurationPicker && (
        <SessionSetupModal
          onCancel={() => setShowDurationPicker(false)}
          onStart={handleStart}
          starting={starting}
        />
      )}

      <Footer />
    </>
  )
}
