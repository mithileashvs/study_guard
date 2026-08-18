import './StatusBadge.css'

const toneDot = {
  good: 'var(--color-green)',
  bad: 'var(--color-red)',
  info: 'var(--color-blue)',
  neutral: 'var(--text-muted)',
}

export default function StatusBadge({ label, value, tone = 'good' }) {
  return (
    <span className="status-badge">
      <span className="status-dot" style={{ background: toneDot[tone] }} />
      <span className="status-label">{label}:</span>
      <span className="status-value">{value}</span>
    </span>
  )
}
