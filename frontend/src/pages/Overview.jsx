import { useEffect, useState } from 'react'
import { HeartPulse, BookOpen, TrendingUp } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import LiveFocusMonitor from '../components/LiveFocusMonitor.jsx'
import FocusBreakdown from '../components/FocusBreakdown.jsx'
import StatCard from '../components/StatCard.jsx'
import TimelineCard from '../components/TimelineCard.jsx'
import RecentAlerts from '../components/RecentAlerts.jsx'
import Footer from '../components/Footer.jsx'
import { user } from '../data/mockData.js'
import useLiveStatus, { formatDuration } from '../data/useLiveStatus.js'
import api from '../data/api.js'
import './Overview.css'

const ratingFromScore = (overall) => {
  if (overall >= 80) return { rating: 'Great', color: 'var(--color-green)', message: "You're doing great!" }
  if (overall >= 60) return { rating: 'Good', color: 'var(--color-green)', message: "You're doing great!" }
  if (overall >= 40) return { rating: 'Fair', color: 'var(--color-blue)', message: 'Room to refocus.' }
  return { rating: 'Needs Focus', color: 'var(--color-red)', message: "Let's get back on track." }
}

export default function Overview() {
  const { status } = useLiveStatus()
  const [score, setScore] = useState(null)

  useEffect(() => {
    let cancelled = false
    let timer = null
    const poll = async () => {
      try {
        const data = await api.getSessionScore()
        if (!cancelled) setScore(data)
      } catch {
        // keep previous value
      } finally {
        if (!cancelled) timer = window.setTimeout(poll, 5000)
      }
    }
    poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [])

  const running = Boolean(status && status.running)
  const elapsed = running ? formatDuration(status.session_time) : '--:--'
  const startedAt = running && status.updated_at
    ? new Date((status.updated_at - status.session_time) * 1000).toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
      })
    : '—'

  const health = score && score.available ? ratingFromScore(score.score.overall) : null
  const activityDetail = running ? (status.current_activity || 'No active window') : 'No session running'
  const activityType = running ? (status.distraction ? 'Distracted' : 'Studying') : 'Idle'

  return (
    <>
      <PageHeader
        title={`Good morning, ${user.name}! 👋`}
        subtitle="Stay focused. Stay consistent. Your goals are closer than you think."
      />

      <div className="row-2col">
        <LiveFocusMonitor />
        <FocusBreakdown />
      </div>

      <div className="row-4col">
        <StatCard
          title="Current Session"
          pill={running ? 'Active' : 'Idle'}
          value={elapsed}
          subtext={running ? `Started at ${startedAt}` : 'No session running'}
        />
        <StatCard
          title="Session Health"
          icon={HeartPulse}
          iconTone="purple"
          value={health ? health.rating : '—'}
          valueColor={health ? health.color : undefined}
          subtext={health ? health.message : 'Not enough data yet'}
        />
        <StatCard
          title="Current Activity"
          icon={BookOpen}
          iconTone="blue"
          value={activityType}
          subtext={activityDetail}
          subtextColor="var(--accent-purple-dark)"
        />
        <StatCard
          title="Study Progress"
          icon={TrendingUp}
          iconTone="green"
          value={health ? `${score.score.overall}%` : '—'}
          subtext="Session health score"
          subtextColor="var(--color-green)"
        />
      </div>

      <div className="row-2col">
        <TimelineCard />
        <RecentAlerts />
      </div>

      <Footer />
    </>
  )
}
