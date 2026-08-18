import { useLocation, useNavigate } from 'react-router-dom'
import { Bot } from 'lucide-react'
import './FloatingCoachButton.css'

// Routes where the floating button would sit on top of controls that
// matter more in the moment (End Session, timer, pause) -- the button
// nudges up/left there rather than disappearing, so it's never lost
// entirely, per spec ("adjust its offset ... if necessary").
const COMPACT_OFFSET_ROUTES = ['/live-session']

export default function FloatingCoachButton() {
  const location = useLocation()
  const navigate = useNavigate()

  // Don't render on the AI Coach page itself -- no point floating a
  // button to open the page you're already on.
  if (location.pathname === '/ai-coach') return null

  const compact = COMPACT_OFFSET_ROUTES.includes(location.pathname)

  return (
    <button
      className={`floating-coach-btn${compact ? ' floating-coach-btn-compact' : ''}`}
      onClick={() => navigate('/ai-coach')}
      aria-label="Open AI Coach"
      title="AI Coach"
    >
      <span className="floating-coach-btn-glow" />
      <Bot size={24} strokeWidth={2.2} />
    </button>
  )
}
