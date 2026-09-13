import { useEffect, useState } from 'react'
import { PieChart } from 'lucide-react'
import Card from './Card.jsx'
import api from '../data/api.js'
import './FocusBreakdown.css'

const SIZE = 160
const STROKE = 7 // Thin donut ring (6-8px)
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const REFRESH_MS = 5000

export default function FocusBreakdown() {
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
        if (!cancelled) timer = window.setTimeout(poll, REFRESH_MS)
      }
    }
    poll()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [])

  const available = score && score.available
  const focusedPercent = available ? score.score.focus : 82

  const segments = available
    ? [
        { label: 'Focused', value: score.score.focus, color: 'var(--accent-purple)' },
        { label: 'Distraction', value: score.score.distractions, color: '#F97316' },
        { label: 'Posture', value: score.score.posture, color: 'var(--color-info)' },
        { label: 'Presence', value: score.score.presence, color: 'var(--color-success)' },
      ]
    : [
        { label: 'Focused', value: 82, color: 'var(--accent-purple)' },
        { label: 'Distracted', value: 12, color: '#F97316' },
        { label: 'Away', value: 6, color: '#94A3B8' },
      ]

  const dash = (CIRCUMFERENCE * focusedPercent) / 100

  return (
    <Card className="focus-breakdown-card">
      <div className="card-header-row">
        <h2 className="card-title">Focus Breakdown</h2>
        <span
          className="card-icon-badge"
          style={{ background: 'var(--accent-purple-light)', color: 'var(--accent-purple)' }}
        >
          <PieChart size={16} strokeWidth={2} />
        </span>
      </div>

      <div className="focus-breakdown-body">
        <div className="focus-ring-wrap">
          <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
            <circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke="#F1F5F9"
              strokeWidth={STROKE}
            />
            <circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke="var(--accent-purple)"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
              transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
            />
          </svg>
          <div className="focus-ring-center">
            <span className="focus-ring-percent">{focusedPercent}%</span>
            <span className="focus-ring-label">Focus Score</span>
          </div>
        </div>

        <ul className="focus-legend">
          {segments.map((s) => (
            <li key={s.label}>
              <span className="focus-legend-dot" style={{ background: s.color }} />
              <span className="focus-legend-label">{s.label}</span>
              <span className="focus-legend-value">{s.value}%</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  )
}
