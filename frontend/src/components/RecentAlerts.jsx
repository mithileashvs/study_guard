import { useEffect, useState } from 'react'
import { Bell, Youtube, PersonStanding, Coffee } from 'lucide-react'
import Card from './Card.jsx'
import './RecentAlerts.css'

const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''
const REFRESH_MS = 5000

const alertIcon = {
  distraction: { Icon: Youtube, tone: 'red' },
  posture: { Icon: PersonStanding, tone: 'purple' },
  break: { Icon: Coffee, tone: 'blue' },
}

function formatTime(isoTimestamp) {
  if (!isoTimestamp) return ''
  try {
    return new Date(isoTimestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  } catch {
    return ''
  }
}

export default function RecentAlerts() {
  const [alerts, setAlerts] = useState([])

  useEffect(() => {
    let cancelled = false
    let timer = null

    const fetchAlerts = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/session/alerts`)
        const data = await res.json()
        if (!cancelled) setAlerts(data.alerts || [])
      } catch {
        // keep previous value
      } finally {
        if (!cancelled) timer = window.setTimeout(fetchAlerts, REFRESH_MS)
      }
    }

    fetchAlerts()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [])

  return (
    <Card className="alerts-card">
      <div className="card-header-row">
        <h2 className="card-title">Recent Alerts</h2>
        <span className="card-icon-badge" style={{ background: 'var(--color-red-light)', color: 'var(--color-red)' }}>
          <Bell size={17} strokeWidth={2.2} />
        </span>
      </div>

      {alerts.length > 0 ? (
        <ul className="alerts-list">
          {alerts.map((alert) => {
            const { Icon, tone } = alertIcon[alert.type] || { Icon: Bell, tone: 'purple' }
            return (
              <li key={alert.id} className="alert-item">
                <span className={`alert-icon tone-${tone}`}>
                  <Icon size={16} strokeWidth={2.2} />
                </span>
                <span className="alert-title">{alert.title}</span>
                <span className="alert-time">{formatTime(alert.time)}</span>
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="alerts-empty">No alerts yet this session.</p>
      )}
    </Card>
  )
}
