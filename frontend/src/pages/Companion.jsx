import { useEffect, useRef, useState } from 'react'
import {
  Send,
  Sparkles,
  Bot,
  Check,
} from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import api from '../data/api.js'
import './Companion.css'

const COMPANIONS = [
  {
    id: 'mischief-cat',
    emoji: '🐱',
    name: 'Mischief Cat',
    description: 'Playful & supportive',
  },
  {
    id: 'brainy-bot',
    emoji: '🤖',
    name: 'Brainy Bot',
    description: 'Precise & analytical',
  },
  {
    id: 'focus-fox',
    emoji: '🦊',
    name: 'Focus Fox',
    description: 'Calm & energetic',
  },
]

const SUGGESTIONS = [
  { label: 'Study tips', action: 'method', prompt: 'What study method do you recommend for retention?' },
  { label: 'Improve focus', action: 'focus', prompt: 'How can I avoid getting distracted during study sessions?' },
  { label: 'Exam preparation', action: 'plan', prompt: 'How should I structure my preparation for upcoming exams?' },
  { label: 'Time management', action: 'motivate', prompt: 'Help me set up an effective daily study schedule.' },
  { label: 'Stay motivated', action: 'motivate', prompt: 'Give me some motivation to stay consistent with my studies.' },
]

export default function Companion() {
  const [selectedCompanionId, setSelectedCompanionId] = useState('mischief-cat')
  const [customMessages, setCustomMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const chatScrollRef = useRef(null)

  const activeCompanion =
    COMPANIONS.find((c) => c.id === selectedCompanionId) || COMPANIONS[0]

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
    }
  }, [customMessages])

  const handleSelectCompanion = (id) => {
    setSelectedCompanionId(id)
  }

  const handleSend = async (textToSend, actionKey) => {
    const messageText = textToSend || input
    if (!messageText.trim() || loading) return

    const userMessage = { from: 'user', text: messageText }
    setCustomMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const res = await api.coachMessage(messageText, actionKey)
      if (res && res.reply) {
        setCustomMessages((prev) => [
          ...prev,
          { from: 'assistant', text: res.reply },
        ])
      }
    } catch {
      // Backend not running or no connection; per instructions, do not fabricate fake responses.
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    handleSend(input)
  }

  return (
    <>
      <PageHeader
        title="Study Companion"
        subtitle="Your AI study partner — here to support, guide and keep you consistent."
      />

      <div className="companion-page-wrapper">
        <Card className="companion-container-card">
          {/* Card Header */}
          <div className="companion-header-row">
            <div className="companion-header-icon-box">
              <Bot size={22} strokeWidth={2} />
            </div>
            <div className="companion-header-text">
              <h2 className="companion-header-title">AI Study Companion</h2>
              <p className="companion-header-subtitle">
                Get personalized study advice, motivation and feedback based on your study patterns.
              </p>
            </div>
          </div>

          {/* Three Companions Selection Grid */}
          <div className="companion-cards-grid">
            {COMPANIONS.map((companion) => {
              const isSelected = companion.id === selectedCompanionId
              return (
                <button
                  key={companion.id}
                  type="button"
                  className={`companion-select-card${isSelected ? ' selected' : ''}`}
                  onClick={() => handleSelectCompanion(companion.id)}
                  aria-pressed={isSelected}
                >
                  <span className="companion-card-emoji" aria-hidden="true">
                    {companion.emoji}
                  </span>

                  <div className="companion-card-details">
                    <span className="companion-card-name">{companion.name}</span>
                    <span className="companion-card-desc">{companion.description}</span>
                  </div>

                  {isSelected && (
                    <span className="companion-card-check">
                      <Check size={16} strokeWidth={2.5} />
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* Chat / Conversation Area */}
          <div className="companion-chat-box" ref={chatScrollRef}>
            {/* Dynamic Welcome Bubble */}
            <div className="companion-chat-message-row">
              <div className="companion-avatar-badge">
                <Sparkles size={14} strokeWidth={2.2} />
              </div>
              <div className="companion-chat-speech-bubble">
                <p className="speech-line-greeting">
                  Hey! I'm {activeCompanion.name} {activeCompanion.emoji}
                </p>
                <p className="speech-line-sub">
                  No session is running right now — start Study Guard and I'll keep you company.
                </p>
              </div>
            </div>

            {/* Custom interactive messages if user asks questions */}
            {customMessages.map((m, idx) => (
              <div
                key={idx}
                className={`companion-chat-message-row ${m.from === 'user' ? 'user-message' : ''}`}
              >
                {m.from === 'assistant' && (
                  <div className="companion-avatar-badge">
                    <Sparkles size={14} strokeWidth={2.2} />
                  </div>
                )}
                <div
                  className={`companion-chat-speech-bubble ${
                    m.from === 'user' ? 'user-bubble' : ''
                  }`}
                >
                  <p>{m.text}</p>
                </div>
              </div>
            ))}

            {loading && (
              <div className="companion-chat-message-row">
                <div className="companion-avatar-badge">
                  <Sparkles size={14} strokeWidth={2.2} />
                </div>
                <div className="companion-chat-speech-bubble typing-bubble">
                  <p>Thinking…</p>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input Field */}
          <form className="companion-input-container" onSubmit={handleSubmit}>
            <input
              type="text"
              placeholder="Ask anything about your studies..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              className="companion-text-input"
            />
            <button
              type="submit"
              className="companion-send-btn"
              disabled={!input.trim() || loading}
              aria-label="Send message"
            >
              <Send size={15} strokeWidth={2.2} />
            </button>
          </form>

          {/* Suggestion Chips */}
          <div className="companion-suggestions-area">
            <span className="companion-suggestions-label">SUGGESTIONS</span>
            <div className="companion-suggestions-list">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.label}
                  type="button"
                  className="companion-suggestion-pill"
                  onClick={() => handleSend(s.prompt, s.action)}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <Footer />
    </>
  )
}
