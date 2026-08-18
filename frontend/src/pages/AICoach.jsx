import { useEffect, useRef, useState } from 'react'
import { Bot, Send, Zap, Flame, BookOpen, Frown, Timer, BarChart3 } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import api from '../data/api.js'
import './AICoach.css'

// Mirrors ai_coach.py's QUICK_ACTIONS exactly (key, label) -- the icon
// is chosen locally since the backend only sends an emoji glyph, and
// lucide icons fit this app's existing visual language better than
// rendering raw emoji in a chip.
const QUICK_ACTIONS = [
  { key: 'focus', label: 'Help me focus', icon: Zap },
  { key: 'motivate', label: 'Motivate me', icon: Flame },
  { key: 'method', label: 'Study method', icon: BookOpen },
  { key: 'distracted', label: "I'm distracted", icon: Frown },
  { key: 'plan', label: 'Plan my session', icon: Timer },
  { key: 'explain', label: 'Explain my session', icon: BarChart3 },
]

export default function AICoach() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingGreeting, setLoadingGreeting] = useState(true)
  const scrollRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    api.coachGreeting()
      .then((data) => {
        if (!cancelled) setMessages([{ from: 'coach', text: data.greeting }])
      })
      .catch(() => {
        if (!cancelled) setMessages([{ from: 'coach', text: "Hi! I'm your study coach. How can I help?" }])
      })
      .finally(() => { if (!cancelled) setLoadingGreeting(false) })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const send = async (text, actionKey) => {
    const label = text ?? QUICK_ACTIONS.find((a) => a.key === actionKey)?.label ?? ''
    if (!label.trim() || sending) return

    setMessages((prev) => [...prev, { from: 'user', text: label }])
    setInput('')
    setSending(true)
    try {
      const data = await api.coachMessage(text ?? '', actionKey)
      setMessages((prev) => [...prev, { from: 'coach', text: data.reply }])
    } catch {
      setMessages((prev) => [...prev, { from: 'coach', text: "Sorry, I couldn't reach the coach service just now." }])
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    send(input)
  }

  return (
    <>
      <PageHeader title="AI Coach" subtitle="Your personal study companion — ask anything." />

      <Card className="coach-card">
        <div className="coach-thread" ref={scrollRef}>
          {loadingGreeting && <div className="coach-bubble coach-bubble-coach coach-bubble-loading">…</div>}
          {messages.map((m, i) => (
            <div key={i} className={`coach-bubble coach-bubble-${m.from}`}>
              {m.from === 'coach' && <Bot size={15} strokeWidth={2.4} className="coach-bubble-icon" />}
              <span>{m.text}</span>
            </div>
          ))}
        </div>

        <div className="coach-quick-actions">
          {QUICK_ACTIONS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              className="coach-quick-action-btn"
              onClick={() => send(undefined, key)}
              disabled={sending}
            >
              <Icon size={14} strokeWidth={2.3} />
              {label}
            </button>
          ))}
        </div>

        <form className="coach-input-row" onSubmit={handleSubmit}>
          <input
            className="coach-input"
            placeholder="Ask your coach anything..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button type="submit" className="coach-send-btn" disabled={sending || !input.trim()} aria-label="Send">
            <Send size={16} strokeWidth={2.4} />
          </button>
        </form>
      </Card>

      <Footer />
    </>
  )
}
