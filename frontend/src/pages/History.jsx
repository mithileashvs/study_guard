import { useEffect, useState } from 'react'
import { Calendar, ChevronDown, Sparkles } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import api from '../data/api.js'
import './ListPages.css'

const DEFAULT_HISTORY = [
  {
    id: 'h1',
    date: 'Sep 12, 2026',
    title: 'DSA — Trees & Graphs',
    duration: '1h 24m',
    focus: 82,
    time: '4:00 PM',
  },
  {
    id: 'h2',
    date: 'Sep 11, 2026',
    title: 'Mock Interview Practice',
    duration: '58m',
    focus: 76,
    time: '10:00 AM',
  },
  {
    id: 'h3',
    date: 'Sep 10, 2026',
    title: 'System Design Basics',
    duration: '1h 10m',
    focus: 88,
    time: '6:30 PM',
  },
  {
    id: 'h4',
    date: 'Sep 9, 2026',
    title: 'DBMS Revision',
    duration: '1h 05m',
    focus: 80,
    time: '5:00 PM',
  },
  {
    id: 'h5',
    date: 'Sep 8, 2026',
    title: 'Operating Systems',
    duration: '45m',
    focus: 74,
    time: '4:00 PM',
  },
]

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
    return new Date(isoTimestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return ''
  }
}

function formatTime(isoTimestamp) {
  if (!isoTimestamp) return ''
  try {
    return new Date(isoTimestamp).toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

export default function History() {
  const [historyItems, setHistoryItems] = useState(DEFAULT_HISTORY)
  const [monthRange, setMonthRange] = useState('This Month')

  useEffect(() => {
    let cancelled = false
    api
      .getSessionsHistory()
      .then((data) => {
        if (cancelled) return
        const completed = (data.sessions || []).filter((s) => s.completed)
        if (completed.length > 0) {
          setHistoryItems(
            completed.map((s, idx) => ({
              id: s.session_id || `s-${idx}`,
              date: formatDate(s.started_at),
              title: s.subject || 'Study Session',
              duration: formatDuration(s.duration_seconds),
              focus: s.score?.overall || 80,
              time: formatTime(s.started_at),
            }))
          )
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <PageHeader
        title="History"
        subtitle="A complete log of your past study sessions."
      >
        <div className="analytics-range-selector">
          <span>{monthRange}</span>
          <ChevronDown size={14} />
        </div>
      </PageHeader>

      <Card className="history-main-card">
        <div className="history-timeline-container">
          {historyItems.map((item, index) => {
            const isLast = index === historyItems.length - 1

            return (
              <div key={item.id} className="history-timeline-entry">
                {/* Left Date Label */}
                <div className="history-date-label">
                  <span>{item.date}</span>
                </div>

                {/* Vertical Spine with Circular Marker */}
                <div className="history-spine-col">
                  <span className="history-dot-marker" />
                  {!isLast && <div className="history-line" />}
                </div>

                {/* Compact Session Card */}
                <div className="history-card-item">
                  <div className="history-card-icon">
                    <Calendar size={17} strokeWidth={1.9} />
                  </div>

                  <div className="history-card-content">
                    <h4 className="history-card-title">{item.title}</h4>
                    <span className="history-card-meta">
                      {item.duration} · Focus: {item.focus}%
                    </span>
                  </div>

                  <span className="history-card-time">{item.time}</span>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      {/* Quote Banner */}
      <div className="history-quote-wrapper">
        <div className="quote-banner">
          <Sparkles size={14} />
          <span>Look back to see how far you've come.</span>
        </div>
      </div>

      <Footer />
    </>
  )
}
