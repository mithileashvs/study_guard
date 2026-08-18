import { useEffect, useState } from 'react'
import { CalendarRange } from 'lucide-react'
import Card from './Card.jsx'
import './TimelineCard.css'

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''

const segmentColor = {
  focus: 'var(--color-green)',
  distraction: 'var(--color-red)',
  break: 'var(--color-blue)',
  away: 'var(--color-gray-light)',
}

const legendMeta = {
  focus: { label: 'Focused', tone: 'good' },
  distraction: { label: 'Distraction', tone: 'bad' },
  break: { label: 'Break', tone: 'info' },
  away: { label: 'Away', tone: 'neutral' },
}

const toneColor = {
  good: 'var(--color-green)',
  bad: 'var(--color-red)',
  info: 'var(--color-blue)',
  neutral: 'var(--color-gray-light)',
}

function formatDuration(seconds) {
  const s = Math.max(0, Math.round(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

// Refreshed on its own slower interval (timeline doesn't need to move
// every second the way the live status badges do) rather than piggy-
// backing on useLiveStatus, to avoid re-fetching this on every 1.5s tick.
const REFRESH_MS = 5000

export default function TimelineCard() {
  const [timeline, setTimeline] = useState(null)

  useEffect(() => {
    let cancelled = false
    let timer = null

    const fetchTimeline = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/session/timeline`)
        const data = await res.json()
        if (!cancelled) setTimeline(data)
      } catch {
        // keep previous value; try again next tick
      } finally {
        if (!cancelled) timer = window.setTimeout(fetchTimeline, REFRESH_MS)
      }
    }

    fetchTimeline()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [])

  const hasData = timeline && timeline.available && timeline.segments.length > 0

  return (
    <Card className="timeline-card">
      <div className="card-header-row">
        <h2 className="card-title">Today's Timeline</h2>
        <span className="card-icon-badge" style={{ background: 'var(--color-blue-light)', color: 'var(--color-blue)' }}>
          <CalendarRange size={17} strokeWidth={2.2} />
        </span>
      </div>

      {hasData ? (
        <>
          <div className="timeline-track">
            {timeline.segments.map((seg, i) => (
              <div
                key={i}
                className="timeline-segment"
                style={{ width: `${seg.width_percent}%`, background: segmentColor[seg.type] || segmentColor.away }}
              />
            ))}
          </div>

          <ul className="timeline-legend">
            {timeline.legend.map((item) => {
              const meta = legendMeta[item.type] || { label: item.type, tone: 'neutral' }
              return (
                <li key={item.type}>
                  <span className="timeline-legend-dot" style={{ background: toneColor[meta.tone] }} />
                  <span className="timeline-legend-label">{meta.label}</span>
                  <span className="timeline-legend-duration">{formatDuration(item.duration_seconds)}</span>
                </li>
              )
            })}
          </ul>
        </>
      ) : (
        <p className="timeline-empty">No session running yet — start Study Guard to see today's timeline.</p>
      )}
    </Card>
  )
}
