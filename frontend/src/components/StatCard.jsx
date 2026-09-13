import Card from './Card.jsx'
import './StatCard.css'

export default function StatCard({
  title,
  value,
  subtext,
  delta,
  deltaType = 'positive', // 'positive' | 'negative' | 'neutral'
  progress, // 0 to 100 optional
  progressLabel,
  className = '',
}) {
  return (
    <Card className={`stat-card ${className}`}>
      <span className="stat-card-title">{title}</span>
      <div className="stat-card-main">
        <span className="stat-card-value">{value}</span>
      </div>
      
      {progress !== undefined && (
        <div className="stat-card-progress-wrap">
          <div className="stat-card-progress-track">
            <div
              className="stat-card-progress-fill"
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
          {progressLabel && <span className="stat-card-progress-label">{progressLabel}</span>}
        </div>
      )}

      {(delta || subtext) && (
        <div className="stat-card-footer">
          {delta && (
            <span className={`stat-card-delta ${deltaType}`}>
              {delta}
            </span>
          )}
          {subtext && <span className="stat-card-subtext">{subtext}</span>}
        </div>
      )}
    </Card>
  )
}
