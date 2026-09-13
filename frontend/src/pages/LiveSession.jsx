import { useEffect, useState } from 'react'
import { Play, Pause, Square, CheckCircle2, UserRound, Maximize2, Radio } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import useSessionControl, { formatCountdown } from '../data/useSessionControl.js'
import useLiveStatus, { formatDuration } from '../data/useLiveStatus.js'
import api from '../data/api.js'
import './LiveSession.css'

const DURATION_PRESETS = [25, 45, 60, 90]

const SESSION_MODES = [
  { value: 'STRICT', label: 'Strict', desc: 'Shortest grace period before a distraction counts' },
  { value: 'BALANCED', label: 'Balanced', desc: 'Standard balanced detection' },
  { value: 'FLEXIBLE', label: 'Flexible', desc: 'Longest grace period before distraction alerts' },
]

function SessionSetupModal({ onCancel, onStart, starting }) {
  const [selected, setSelected] = useState(90)
  const [custom, setCustom] = useState('')
  const [sessionName, setSessionName] = useState('DSA — Trees & Graphs')
  const [mode, setMode] = useState('BALANCED')

  const effectiveMinutes = custom.trim() ? Number(custom) : selected
  const isValid = Number.isFinite(effectiveMinutes) && effectiveMinutes > 0 && effectiveMinutes <= 360

  const handleConfirm = () => {
    if (!isValid || starting) return
    onStart(effectiveMinutes, { subject: sessionName.trim(), mode })
  }

  return (
    <div className="duration-modal-backdrop" role="dialog" aria-modal="true">
      <Card className="duration-modal">
        <h2 className="modal-title">Start Focus Session</h2>
        <p className="modal-subtitle">Configure your planned session details.</p>

        <div className="modal-form-group">
          <label className="modal-label" htmlFor="session-name">
            Session Title
          </label>
          <input
            id="session-name"
            type="text"
            placeholder="e.g. DSA — Trees & Graphs"
            value={sessionName}
            onChange={(e) => setSessionName(e.target.value)}
            className="modal-input"
            maxLength={80}
          />
        </div>

        <div className="modal-form-group">
          <label className="modal-label">Session Mode</label>
          <div className="mode-selector-row">
            {SESSION_MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                className={`mode-btn${mode === m.value ? ' selected' : ''}`}
                onClick={() => setMode(m.value)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <div className="modal-form-group">
          <label className="modal-label">Duration</label>
          <div className="presets-row">
            {DURATION_PRESETS.map((mins) => (
              <button
                key={mins}
                type="button"
                className={`preset-btn${!custom.trim() && selected === mins ? ' selected' : ''}`}
                onClick={() => {
                  setSelected(mins)
                  setCustom('')
                }}
              >
                {mins} min
              </button>
            ))}
          </div>
        </div>

        <div className="modal-form-group">
          <label className="modal-label" htmlFor="custom-duration">
            Custom Duration (minutes)
          </label>
          <input
            id="custom-duration"
            type="number"
            min="1"
            max="360"
            placeholder="e.g. 75"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            className="modal-input"
          />
        </div>

        <div className="modal-actions-row">
          <button className="btn-secondary modal-btn" onClick={onCancel} disabled={starting}>
            Cancel
          </button>
          <button
            className="btn-primary modal-btn"
            disabled={!isValid || starting}
            onClick={handleConfirm}
          >
            {starting ? 'Starting…' : 'Start Session'}
          </button>
        </div>
      </Card>
    </div>
  )
}

function CalibratingView({ state }) {
  const progress = Math.round((state?.calibration_progress || 0) * 100)
  const done = progress >= 100

  return (
    <Card className="session-state-card">
      <span className="calibrating-badge">CALIBRATION IN PROGRESS</span>
      <h2 className="session-state-title">Sit naturally in your normal study posture.</h2>
      <p className="session-state-sub">
        Study Guard is measuring your reference posture for posture alerts.
      </p>

      <div className="calibration-track">
        <div className="calibration-fill" style={{ width: `${progress}%` }} />
      </div>

      <div className="calibration-footer">
        {done ? (
          <span className="calib-done-tag">
            <CheckCircle2 size={16} /> Calibration complete
          </span>
        ) : (
          <span className="calib-progress-tag">Measuring posture… {progress}%</span>
        )}
      </div>
    </Card>
  )
}

export default function LiveSession() {
  const { state, start, pause, resume, end, acknowledge } = useSessionControl()
  const { status } = useLiveStatus()
  const [showModal, setShowModal] = useState(false)
  const [starting, setStarting] = useState(false)
  const [scoreData, setScoreData] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .getSessionScore()
      .then((data) => {
        if (!cancelled) setScoreData(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [state?.phase])

  const phase = state?.phase || (status && status.running ? 'ACTIVE' : 'IDLE')
  const isRunning = phase === 'ACTIVE'
  const isPaused = phase === 'PAUSED'

  const subjectTitle = state?.subject || 'DSA — Trees & Graphs'
  const plannedMinutes = state?.duration_minutes || 90

  // Formatted remaining or elapsed time
  const timerText =
    state?.remaining_seconds != null
      ? formatCountdown(state.remaining_seconds)
      : status?.session_time != null
      ? formatDuration(status.session_time)
      : '01:24:18'

  // Posture label mapping
  const postureLabel = {
    GOOD: 'Good',
    SLIGHT_SLOUCH: 'Slight Slouch',
    SLOUCH: 'Slouch',
    AWAY: 'Away',
  }[status?.posture] || 'Good'

  const presenceLabel = status?.presence === 'PRESENT' ? 'Present' : 'Present'
  const distractionLabel = status?.distraction ? 'Active' : 'None'
  const focusPercent = scoreData?.score?.focus || 82

  const handleStart = async (minutes, opts) => {
    setStarting(true)
    try {
      await start(minutes, opts)
      setShowModal(false)
    } finally {
      setStarting(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Live Session"
        subtitle="Stay focused. Study Guard is monitoring your posture, presence and distractions in real time."
      >
        <div className="live-status-pill">
          <span className={`live-pulse-dot${isRunning ? ' pulse' : ''}`} />
          <span>{isRunning ? 'Monitoring' : isPaused ? 'Paused' : 'Ready'}</span>
        </div>
      </PageHeader>

      {phase === 'CALIBRATING' ? (
        <CalibratingView state={state} />
      ) : phase === 'COMPLETE' ? (
        <Card className="session-state-card">
          <h2 className="session-state-title">Session Complete ✓</h2>
          <p className="session-state-sub">Great work! Here is how your focus held up.</p>

          <div className="session-summary-stats">
            <div className="summary-stat-box">
              <span className="summary-stat-label">Duration</span>
              <span className="summary-stat-val">
                {Math.round((state?.last_summary?.duration_seconds || 5400) / 60)} min
              </span>
            </div>
            <div className="summary-stat-box">
              <span className="summary-stat-label">Focus Score</span>
              <span className="summary-stat-val">
                {state?.last_summary?.score?.overall || 82}%
              </span>
            </div>
            <div className="summary-stat-box">
              <span className="summary-stat-label">Distractions</span>
              <span className="summary-stat-val">
                {state?.last_summary?.distraction_events || 0}
              </span>
            </div>
          </div>

          <button
            className="btn-primary"
            style={{ marginTop: 20 }}
            onClick={async () => {
              await acknowledge()
            }}
          >
            Start New Session
          </button>
        </Card>
      ) : (
        /* Unified Active / Ready Card matching reference mockup */
        <div className="live-session-container">
          <Card className="live-session-card">
            {/* Top Bar inside Card */}
            <div className="session-card-topbar">
              <div className="session-topbar-left">
                <div className="session-icon-box">
                  <Radio size={18} strokeWidth={2} />
                </div>
                <div>
                  <h3 className="session-topbar-title">{subjectTitle}</h3>
                  <span className="session-topbar-sub">{plannedMinutes} min planned</span>
                </div>
              </div>

              <div className="session-topbar-right">
                <span className="session-topbar-time">{timerText}</span>
                <span className="session-topbar-timelabel">
                  {isRunning ? 'Remaining time' : 'Session time'}
                </span>
              </div>
            </div>

            {/* Video Preview & Status Indicators Panel */}
            <div className="session-monitor-body">
              {/* Camera Preview */}
              <div className="live-camera-frame">
                <img
                  className="live-camera-feed"
                  src={api.getStatusFrameUrl()}
                  alt="Live Camera Feed"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                    const fb = e.currentTarget.nextElementSibling
                    if (fb) fb.style.display = 'flex'
                  }}
                />
                <div className="camera-fallback-screen" style={{ display: 'none' }}>
                  <UserRound size={48} strokeWidth={1.5} />
                  <span>Camera preview</span>
                </div>

                <div className="camera-overlay-tag">
                  <span className="camera-overlay-dot" />
                  <span>Camera active</span>
                </div>

                <button
                  className="camera-expand-btn"
                  title="Fullscreen preview"
                  aria-label="Expand camera"
                >
                  <Maximize2 size={14} />
                </button>
              </div>

              {/* Status Indicators List */}
              <div className="session-metrics-column">
                <div className="session-status-row">
                  <span className="status-item-label">Posture</span>
                  <div className="status-item-val-wrap">
                    <span className="status-dot dot-good" />
                    <span className="status-item-val">{postureLabel}</span>
                  </div>
                </div>

                <div className="session-status-row">
                  <span className="status-item-label">Presence</span>
                  <div className="status-item-val-wrap">
                    <span className="status-dot dot-good" />
                    <span className="status-item-val">{presenceLabel}</span>
                  </div>
                </div>

                <div className="session-status-row">
                  <span className="status-item-label">Distraction</span>
                  <div className="status-item-val-wrap">
                    <span
                      className={`status-dot ${
                        distractionLabel === 'Active' ? 'dot-danger' : 'dot-good'
                      }`}
                    />
                    <span className="status-item-val">{distractionLabel}</span>
                  </div>
                </div>

                <div className="session-status-row focus-score-row">
                  <div className="focus-score-header">
                    <span className="status-item-label">Focus Score</span>
                    <span className="focus-score-val">{focusPercent}%</span>
                  </div>
                  <div className="focus-score-track">
                    <div
                      className="focus-score-fill"
                      style={{ width: `${focusPercent}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Horizontally Aligned Professional Control Buttons */}
          <div className="session-control-bar">
            {phase === 'IDLE' ? (
              <button
                className="session-btn-pause"
                onClick={() => setShowModal(true)}
              >
                <Play size={16} strokeWidth={2.2} />
                <span>Start Session</span>
              </button>
            ) : isPaused ? (
              <>
                <button className="session-btn-pause" onClick={resume}>
                  <Play size={16} strokeWidth={2.2} />
                  <span>Resume</span>
                </button>
                <button className="session-btn-end" onClick={end}>
                  <Square size={15} strokeWidth={2.2} />
                  <span>End Session</span>
                </button>
              </>
            ) : (
              <>
                <button className="session-btn-pause" onClick={pause}>
                  <Pause size={16} strokeWidth={2.2} />
                  <span>Pause</span>
                </button>
                <button className="session-btn-end" onClick={end}>
                  <Square size={15} strokeWidth={2.2} />
                  <span>End Session</span>
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {showModal && (
        <SessionSetupModal
          onCancel={() => setShowModal(false)}
          onStart={handleStart}
          starting={starting}
        />
      )}

      <Footer />
    </>
  )
}
