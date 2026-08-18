import { useEffect, useState } from 'react'
import { History as HistoryIcon } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
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
    return new Date(isoTimestamp).toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}

export default function History() {
  const [historyLog, setHistoryLog] = useState([])

  useEffect(() => {
    let cancelled = false
    api
      .getSessionsHistory()
      .then((data) => {
        if (cancelled) return
        setHistoryLog((data.sessions || []).filter((s) => s.completed))
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
        title="History"
        subtitle="A full log of your past study sessions."
      />

      <Card className="list-card">
        {historyLog.length > 0 ? (
          <ul className="session-row-list">
            {historyLog.map((s) => (
              <li key={s.session_id} className="session-row">
                <span className="session-row-icon">
                  <HistoryIcon size={17} strokeWidth={2.2} />
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
          <p className="list-empty">No session history yet — completed sessions will show up here.</p>
        )}
      </Card>

      <Footer />
    </>
  )
}
