import { useEffect, useState } from 'react'
import { CalendarClock } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import { upcomingSessions } from '../data/mockData.js'
import api from '../data/api.js'
import './ListPages.css'

function formatDuration(seconds) {
  if (!seconds) return '—'
  const s = Math.round(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function formatDate(isoTimestamp) {
  if (!isoTimestamp) return ''
  try {
    return new Date(isoTimestamp).toLocaleDateString([], { month: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}

export default function Sessions() {
  const [pastSessions, setPastSessions] = useState([])

  useEffect(() => {
    let cancelled = false
    api
      .getSessionsHistory()
      .then((data) => {
        if (cancelled) return
        const completed = (data.sessions || []).filter((s) => s.completed)
        setPastSessions(completed.slice(0, 10))
      })
      .catch(() => {
        // leave list empty — real data unavailable
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <PageHeader
        title="Sessions"
        subtitle="Plan upcoming study sessions and review how recent ones went."
      />

      <div className="row-2col-stack">
        <Card className="list-card">
          <p className="section-title">Upcoming</p>
          <ul className="session-row-list">
            {upcomingSessions.map((s) => (
              <li key={s.id} className="session-row">
                <span className="session-row-icon">
                  <CalendarClock size={17} strokeWidth={2.2} />
                </span>
                <div className="session-row-body">
                  <p className="session-row-title">{s.title}</p>
                  <p className="session-row-meta">
                    {s.date} · {s.time}
                  </p>
                </div>
                <span className="session-row-duration">{s.duration}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="list-card">
          <p className="section-title">Past sessions</p>
          {pastSessions.length > 0 ? (
            <ul className="session-row-list">
              {pastSessions.map((s) => (
                <li key={s.session_id} className="session-row">
                  <span className="session-row-icon">
                    <CalendarClock size={17} strokeWidth={2.2} />
                  </span>
                  <div className="session-row-body">
                    <p className="session-row-title">{s.subject}</p>
                    <p className="session-row-meta">
                      {formatDate(s.started_at)} · {formatDuration(s.duration_seconds)}
                    </p>
                  </div>
                  <span className="session-row-focus">
                    {s.score ? `${s.score.overall}% focus` : '—'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="list-empty">No completed sessions yet.</p>
          )}
        </Card>
      </div>

      <Footer />
    </>
  )
}
