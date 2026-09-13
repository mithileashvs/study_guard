import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calendar, Play, MoreHorizontal, Clock, Plus } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import { upcomingSessions as defaultUpcoming } from '../data/mockData.js'
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
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('upcoming')
  const [pastSessions, setPastSessions] = useState([])

  useEffect(() => {
    let cancelled = false
    api
      .getSessionsHistory()
      .then((data) => {
        if (cancelled) return
        const completed = (data.sessions || []).filter((s) => s.completed)
        setPastSessions(completed)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const handleStartSession = (session) => {
    navigate('/live-session')
  }

  return (
    <>
      <PageHeader
        title="Sessions"
        subtitle="Plan upcoming study sessions and review how recent ones went."
      >
        <button
          className="btn-primary"
          onClick={() => navigate('/live-session')}
        >
          <Plus size={15} />
          <span>New Session</span>
        </button>
      </PageHeader>

      <Card className="sessions-container-card">
        {/* Tab navigation */}
        <div className="sessions-tabs-bar">
          <button
            className={`session-tab-btn${activeTab === 'upcoming' ? ' active' : ''}`}
            onClick={() => setActiveTab('upcoming')}
          >
            Upcoming
          </button>
          <button
            className={`session-tab-btn${activeTab === 'past' ? ' active' : ''}`}
            onClick={() => setActiveTab('past')}
          >
            Past Sessions
          </button>
        </div>

        {/* Content according to tab */}
        {activeTab === 'upcoming' ? (
          <div className="sessions-list">
            {defaultUpcoming.map((item) => (
              <div key={item.id} className="session-compact-row">
                <div className="session-calendar-badge">
                  <Calendar size={17} strokeWidth={1.9} />
                </div>

                <div className="session-info-col">
                  <h4 className="session-item-title">{item.title}</h4>
                  <span className="session-item-date">
                    {item.date} · {item.time}
                  </span>
                </div>

                <div className="session-right-col">
                  <span className="session-item-duration">{item.duration}</span>
                  
                  <button
                    className="session-play-btn"
                    title="Start this session"
                    onClick={() => handleStartSession(item)}
                    aria-label={`Start ${item.title}`}
                  >
                    <Play size={13} fill="currentColor" strokeWidth={0} />
                  </button>

                  <button
                    className="session-more-btn"
                    title="Options"
                    aria-label="More options"
                  >
                    <MoreHorizontal size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="sessions-list">
            {pastSessions.length > 0 ? (
              pastSessions.map((item) => (
                <div key={item.session_id} className="session-compact-row">
                  <div className="session-calendar-badge">
                    <Clock size={17} strokeWidth={1.9} />
                  </div>

                  <div className="session-info-col">
                    <h4 className="session-item-title">{item.subject}</h4>
                    <span className="session-item-date">
                      {formatDate(item.started_at)} · {formatDuration(item.duration_seconds)}
                    </span>
                  </div>

                  <div className="session-right-col">
                    <span className="session-item-focus">
                      {item.score ? `${item.score.overall}% focus` : '—'}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state-wrap">
                <Clock size={28} className="empty-state-icon" />
                <h4 className="empty-state-title">No sessions yet</h4>
                <p className="empty-state-sub">
                  Complete your first focus session to start building your study history.
                </p>
              </div>
            )}
          </div>
        )}
      </Card>

      <Footer />
    </>
  )
}
