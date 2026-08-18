import Card from './Card.jsx'
import './StatCard.css'

export default function StatCard({
  title,
  icon: Icon,
  iconTone = 'purple',
  value,
  valueColor,
  pill,
  subtext,
  subtextColor,
}) {
  return (
    <Card className="stat-card">
      <div className="stat-card-row">
        <span className="stat-card-title">{title}</span>
        {pill ? (
          <span className="stat-card-pill">
            <span className="stat-card-pill-dot" />
            {pill}
          </span>
        ) : (
          Icon && (
            <span className={`card-icon-badge tone-${iconTone}`}>
              <Icon size={16} strokeWidth={2.2} />
            </span>
          )
        )}
      </div>
      <p className="stat-card-value" style={valueColor ? { color: valueColor } : undefined}>
        {value}
      </p>
      {subtext && (
        <p className="stat-card-subtext" style={subtextColor ? { color: subtextColor } : undefined}>
          {subtext}
        </p>
      )}
    </Card>
  )
}
