import { Video, UserRound } from 'lucide-react'
import StatusBadge from './StatusBadge.jsx'
import Card from './Card.jsx'
import useLiveStatus from '../data/useLiveStatus.js'
import api from '../data/api.js'
import './LiveFocusMonitor.css'

// Maps real backend posture/presence/distraction values to the same
// {label, value, tone} shape the status badges were already built for.
function statusRowsFrom(status) {
  if (!status || !status.running) {
    return [
      { label: 'Posture', value: 'Unknown', tone: 'neutral' },
      { label: 'Presence', value: 'Away', tone: 'neutral' },
      { label: 'Distraction', value: 'Unknown', tone: 'neutral' },
    ]
  }

  const postureTone = { GOOD: 'good', SLIGHT_SLOUCH: 'info', SLOUCH: 'bad', AWAY: 'neutral', UNKNOWN: 'neutral' }
  const postureLabel = { GOOD: 'Good', SLIGHT_SLOUCH: 'Slight Slouch', SLOUCH: 'Slouch', AWAY: 'Away', UNKNOWN: 'Unknown' }

  const presenceTone = status.presence === 'PRESENT' ? 'good' : 'neutral'
  const presenceLabel = status.presence === 'PRESENT' ? 'Present' : 'Away'

  return [
    { label: 'Posture', value: postureLabel[status.posture] || 'Unknown', tone: postureTone[status.posture] || 'neutral' },
    { label: 'Presence', value: presenceLabel, tone: presenceTone },
    { label: 'Distraction', value: status.distraction ? 'Active' : 'Low', tone: status.distraction ? 'bad' : 'good' },
  ]
}

export default function LiveFocusMonitor() {
  const { status } = useLiveStatus()
  const isLive = Boolean(status && status.running)
  const rows = statusRowsFrom(status)

  return (
    <Card className="live-monitor-card">
      <div className="card-header-row">
        <h2 className="card-title">Live Focus Monitor</h2>
        <span className="card-icon-badge" style={{ background: 'var(--accent-purple-light)', color: 'var(--accent-purple-dark)' }}>
          <Video size={17} strokeWidth={2.2} />
        </span>
      </div>

      <div className="camera-frame">
        {isLive && (
          <span className="live-pill">
            <span className="live-dot" />
            LIVE
          </span>
        )}

        {isLive ? (
          <img
            className="camera-live-frame"
            src={api.getStatusFrameUrl()}
            alt="Live camera feed"
            onError={(e) => {
              e.currentTarget.style.display = 'none'
            }}
          />
        ) : (
          <div className="camera-placeholder" aria-label="Camera feed unavailable">
            <UserRound size={64} strokeWidth={1.4} />
            <p>{status ? 'Monitoring is not running' : 'Connecting to Study Guard…'}</p>
          </div>
        )}

        <div className="camera-status-row">
          {rows.map((s) => (
            <StatusBadge key={s.label} label={s.label} value={s.value} tone={s.tone} />
          ))}
        </div>
      </div>
    </Card>
  )
}
