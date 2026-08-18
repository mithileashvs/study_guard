import { useState } from 'react'
import { CheckCircle2 } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import { companions as initialCompanions } from '../data/mockData.js'
import './Companion.css'

export default function Companion() {
  // Local UI state only — selecting a companion here is a mock interaction.
  // Wire this up to a real "set active companion" API call later.
  const [companions, setCompanions] = useState(initialCompanions)
  const active = companions.find((c) => c.active)

  const selectCompanion = (id) => {
    setCompanions((prev) => prev.map((c) => ({ ...c, active: c.id === id })))
  }

  return (
    <>
      <PageHeader
        title="Study Companion"
        subtitle="Choose the companion that keeps you company while you study."
      />

      {active && (
        <Card className="companion-hero-card">
          <span className="companion-hero-emoji">{active.emoji}</span>
          <div className="companion-hero-body">
            <p className="companion-hero-name">{active.name}</p>
            <p className="companion-hero-desc">{active.description}</p>
            <div className="companion-hero-stats">
              <span>
                Mood <strong>{active.mood}</strong>
              </span>
              <span>
                Bond <strong>{active.bond}%</strong>
              </span>
            </div>
          </div>
        </Card>
      )}

      <div className="companion-grid">
        {companions.map((c) => (
          <Card
            key={c.id}
            className={`companion-option-card${c.active ? ' selected' : ''}`}
            onClick={() => selectCompanion(c.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && selectCompanion(c.id)}
          >
            {c.active && (
              <span className="companion-option-check">
                <CheckCircle2 size={18} strokeWidth={2.4} />
              </span>
            )}
            <span className="companion-option-emoji">{c.emoji}</span>
            <p className="companion-option-name">{c.name}</p>
            <p className="companion-option-tagline">{c.tagline}</p>
          </Card>
        ))}
      </div>

      <Footer />
    </>
  )
}
