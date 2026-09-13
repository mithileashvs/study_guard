import { useLocation, useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import './FloatingCoachButton.css'

export default function FloatingCoachButton() {
  const location = useLocation()
  const navigate = useNavigate()

  // Don't render on the companion or ai-coach pages themselves
  if (location.pathname === '/companion' || location.pathname === '/ai-coach') {
    return null
  }

  const isLive = location.pathname === '/live-session'

  return (
    <button
      className={`floating-assistant-btn${isLive ? ' live-offset' : ''}`}
      onClick={() => navigate('/companion')}
      aria-label="Open AI Study Assistant"
      title="AI Study Assistant"
    >
      <Sparkles size={18} strokeWidth={2} />
    </button>
  )
}
