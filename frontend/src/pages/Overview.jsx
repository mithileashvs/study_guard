import { useEffect, useState } from 'react'
import { ShieldCheck, Sparkles, TrendingUp } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import StatCard from '../components/StatCard.jsx'
import Footer from '../components/Footer.jsx'
import { user } from '../data/mockData.js'
import useLiveStatus, { formatDuration } from '../data/useLiveStatus.js'
import api from '../data/api.js'
import './Overview.css'

export default function Overview() {
  const { status } = useLiveStatus()
  const [scoreData, setScoreData] = useState(null)
  const [historyCount, setHistoryCount] = useState(3)

  useEffect(() => {
    let cancelled = false
    let timer = null

    const fetchScore = async () => {
      try {
        const data = await api.getSessionScore()
        if (!cancelled) setScoreData(data)
      } catch {
        // preserve previous state
      } finally {
        if (!cancelled) timer = window.setTimeout(fetchScore, 5000)
      }
    }

    fetchScore()

    api
      .getSessionsHistory()
      .then((res) => {
        if (!cancelled && res.sessions?.length) {
          setHistoryCount(res.sessions.length)
        }
      })
      .catch(() => {})

    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [])

  const running = Boolean(status && status.running)
  const elapsedMinutes = running ? Math.round(status.session_time / 60) : 162 // default 2h 42m = 162m
  const hours = Math.floor(elapsedMinutes / 60)
  const mins = elapsedMinutes % 60
  const focusTimeDisplay = `${hours}h ${mins}m`

  // Dynamic or polished focus score
  const focusScore =
    scoreData && scoreData.available
      ? scoreData.score.focus || scoreData.score.overall
      : 87

  // Thin donut chart dimensions
  const size = 150
  const strokeWidth = 7
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (circumference * focusScore) / 100

  // Date formatting for subtitle pill
  const todayDate = new Date().toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <>
      <PageHeader
        title={`Good morning, ${user.name}!`}
        subtitle="Discipline today builds the life you want tomorrow."
      >
        <div className="overview-header-badge">
          <span className="overview-date">{todayDate}</span>
          <span className="overview-subpill">
            <Sparkles size={13} className="sparkle-icon" />
            Small steps every day lead to big results.
          </span>
        </div>
      </PageHeader>

      {/* Main Focus Area: Visual Banner + Today's Progress Card */}
      <div className="overview-hero-grid">
        {/* Left: Focus Environment Panel */}
        <div className="focus-hero-panel">
          <img
            src="/assets/study_workspace.jpg"
            alt="Clean focus workspace"
            className="focus-hero-image"
          />
          <div className="focus-hero-overlay">
            <h2 className="focus-hero-text">
              Focus today for a<br />brighter tomorrow.
            </h2>
          </div>
        </div>

        {/* Right: Today's Progress */}
        <Card className="todays-progress-card">
          <div className="card-header-row">
            <h2 className="card-title">Today's Progress</h2>
          </div>

          <div className="progress-donut-section">
            {/* Thin Donut Chart */}
            <div className="donut-chart-container">
              <svg width={size} height={size} className="donut-svg">
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke="#F1F5F9"
                  strokeWidth={strokeWidth}
                />
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke="#635BFF"
                  strokeWidth={strokeWidth}
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  transform={`rotate(-90 ${size / 2} ${size / 2})`}
                  className="donut-progress-stroke"
                />
              </svg>
              <div className="donut-chart-inner">
                <span className="donut-score-number">{focusScore}%</span>
                <span className="donut-score-label">Focus Score</span>
              </div>
            </div>

            {/* Metrics Legend */}
            <div className="donut-legend">
              <div className="legend-item">
                <span className="legend-dot dot-focused" />
                <div className="legend-text">
                  <span className="legend-label">Focused</span>
                  <span className="legend-value">{focusTimeDisplay}</span>
                </div>
              </div>

              <div className="legend-item">
                <span className="legend-dot dot-distracted" />
                <div className="legend-text">
                  <span className="legend-label">Distracted</span>
                  <span className="legend-value">18m</span>
                </div>
              </div>

              <div className="legend-item">
                <span className="legend-dot dot-away" />
                <div className="legend-text">
                  <span className="legend-label">Away</span>
                  <span className="legend-value">12m</span>
                </div>
              </div>
            </div>
          </div>

          {/* Encouragement Banner */}
          <div className="progress-feedback-banner">
            <ShieldCheck size={18} className="feedback-icon" />
            <div className="feedback-text">
              <span className="feedback-title">You're doing great!</span>
              <span className="feedback-sub">Keep going.</span>
            </div>
          </div>
        </Card>
      </div>

      {/* 4 Compact Metric Cards */}
      <div className="overview-metrics-grid">
        <StatCard
          title="Focus Time"
          value={focusTimeDisplay}
          delta="↑ 16%"
          deltaType="positive"
          subtext="vs. yesterday"
        />

        <StatCard
          title="Sessions"
          value={String(historyCount)}
          delta="↑ 1"
          deltaType="positive"
          subtext="vs. yesterday"
        />

        <StatCard
          title="Current Streak"
          value="5 days"
          subtext="Keep it going!"
        />

        <StatCard
          title="Study Goal"
          value="4h / day"
          progress={60}
          progressLabel="60%"
        />
      </div>

      <Footer />
    </>
  )
}
