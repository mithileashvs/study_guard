import { useEffect, useRef, useState, useCallback } from 'react'
import { Sparkles, Check, X, Loader2, BookOpen, ChevronRight, ExternalLink } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import { roadmapJourney } from '../data/mockData.js'
import { roadmapGenerationSteps, generateRoadmapFromPortion } from '../data/roadmapGenerator.js'
import adaptRoadmap from '../data/roadmapAdapter.js'
import api from '../data/api.js'
import './Roadmap.css'

// Default structured milestones if none on backend yet
const DEFAULT_ROADMAP = {
  title: 'DSA Interview Preparation',
  overallProgress: 42,
  durationWeeks: '12 weeks',
  milestones: [
    {
      id: 'm1',
      number: 1,
      title: 'Arrays & Hashing',
      topicsCount: 8,
      duration: '3h 20m',
      progress: 100,
      status: 'completed',
      actionLabel: 'Review',
      topics: [
        { name: 'Two Pointers & Sliding Window', done: true },
        { name: 'Prefix Sums & Frequency Arrays', done: true },
        { name: 'Hash Maps & Hash Sets Lookup', done: true },
      ],
      resources: [
        { title: 'NeetCode 150 — Arrays & Hashing', level: 'Video & Practice' },
        { title: 'LeetCode Explore: Array 101', level: 'Interactive Tutorial' },
      ],
    },
    {
      id: 'm2',
      number: 2,
      title: 'Linked Lists',
      topicsCount: 6,
      duration: '2h 10m',
      progress: 72,
      status: 'current',
      actionLabel: 'Continue',
      topics: [
        { name: 'Singly & Doubly Linked List Traversal', done: true },
        { name: 'Fast & Slow Pointers (Cycle Detection)', done: true },
        { name: 'In-place List Reversal', done: false },
      ],
      resources: [
        { title: 'Visualgo Linked List Visualizer', level: 'Visual Demonstration' },
        { title: 'LeetCode: Reverse Linked List II', level: 'Medium Problem' },
      ],
    },
    {
      id: 'm3',
      number: 3,
      title: 'Stacks and Queues',
      topicsCount: 5,
      duration: '1h 30m',
      progress: 20,
      status: 'in-progress',
      actionLabel: 'Start',
      topics: [
        { name: 'Stack Operations & Balanced Parentheses', done: true },
        { name: 'Monotonic Stack Fundamentals', done: false },
        { name: 'Queue & Double-Ended Queue (Deque)', done: false },
      ],
      resources: [
        { title: 'Monotonic Stack Deep Dive', level: 'Written Guide' },
      ],
    },
    {
      id: 'm4',
      number: 4,
      title: 'Trees',
      topicsCount: 12,
      duration: 'Not started',
      progress: 0,
      status: 'not-started',
      actionLabel: 'Start',
      topics: [
        { name: 'Binary Trees & Traversals (Inorder, Preorder, Postorder)', done: false },
        { name: 'Binary Search Tree (BST) Properties & Search', done: false },
        { name: 'Breadth-First Search (Level Order)', done: false },
      ],
      resources: [
        { title: 'Tree Visualizations by CS50', level: 'Video Lecture' },
      ],
    },
    {
      id: 'm5',
      number: 5,
      title: 'Graphs',
      topicsCount: 10,
      duration: 'Not started',
      progress: 0,
      status: 'not-started',
      actionLabel: 'Start',
      topics: [
        { name: 'Graph Representations (Adjacency Matrix vs List)', done: false },
        { name: 'DFS & BFS on Directed and Undirected Graphs', done: false },
        { name: 'Topological Sort (Kahn’s Algorithm)', done: false },
      ],
      resources: [
        { title: 'Graph Theory Algorithms Guide', level: 'Comprehensive Guide' },
      ],
    },
  ],
}

function MilestoneDetailModal({ milestone, onClose }) {
  useEffect(() => {
    const handleEsc = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  return (
    <div className="roadmap-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="roadmap-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-top-row">
          <div>
            <span className="modal-milestone-number">MILESTONE {milestone.number}</span>
            <h2 className="modal-milestone-title">{milestone.title}</h2>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <div className="modal-progress-strip">
          <div className="modal-progress-bar">
            <div
              className="modal-progress-fill"
              style={{ width: `${milestone.progress}%` }}
            />
          </div>
          <span className="modal-progress-text">{milestone.progress}% complete</span>
        </div>

        <div className="modal-section">
          <h4 className="modal-section-title">Topics in this milestone</h4>
          <ul className="modal-topics-list">
            {milestone.topics?.map((t, idx) => (
              <li key={idx} className={`modal-topic-item${t.done ? ' done' : ''}`}>
                <span className="topic-checkbox">
                  {t.done && <Check size={12} strokeWidth={2.8} />}
                </span>
                <span className="topic-name">{t.name}</span>
              </li>
            ))}
          </ul>
        </div>

        {milestone.resources?.length > 0 && (
          <div className="modal-section">
            <h4 className="modal-section-title">Recommended Resources</h4>
            <ul className="modal-resources-list">
              {milestone.resources.map((r, idx) => (
                <li key={idx} className="modal-resource-item">
                  <BookOpen size={15} className="resource-icon" />
                  <div className="resource-body">
                    <span className="resource-title">{r.title}</span>
                    <span className="resource-level">{r.level}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="modal-bottom-actions">
          <button className="btn-primary" onClick={onClose} style={{ width: '100%' }}>
            Continue Milestone
          </button>
        </div>
      </div>
    </div>
  )
}

function AIGenerateModal({ onClose, onGenerated }) {
  const [prompt, setPrompt] = useState('')
  const [generating, setGenerating] = useState(false)
  const [stepIdx, setStepIdx] = useState(0)

  const handleGenerate = async () => {
    if (!prompt.trim() || generating) return
    setGenerating(true)

    // Cycle through real generation steps
    let currentStep = 0
    const interval = setInterval(() => {
      currentStep++
      if (currentStep < roadmapGenerationSteps.length) {
        setStepIdx(currentStep)
      }
    }, 450)

    try {
      // Backend create or generator
      const result = await api
        .createRoadmap({
          title: prompt.split('\n')[0].replace(/^#*\s*/, '') || 'My Custom Roadmap',
          syllabus: prompt,
        })
        .catch(() => generateRoadmapFromPortion(prompt))

      clearInterval(interval)
      onGenerated(result)
      onClose()
    } catch {
      clearInterval(interval)
      setGenerating(false)
    }
  }

  return (
    <div className="roadmap-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="roadmap-modal generate-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-top-row">
          <div>
            <h3 className="modal-milestone-title">Generate Learning Roadmap</h3>
            <p className="modal-subtitle">
              Paste your syllabus, subjects, or study goals below.
            </p>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <textarea
          className="generate-textarea"
          placeholder="e.g.&#10;Unit 1 — Arrays and Hashing&#10;Unit 2 — Linked Lists&#10;Unit 3 — Stacks & Queues&#10;Unit 4 — Binary Trees&#10;Unit 5 — Graphs"
          rows={6}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={generating}
        />

        {generating && (
          <div className="generating-indicator">
            <Loader2 size={16} className="spin-icon" />
            <span>{roadmapGenerationSteps[stepIdx]}</span>
          </div>
        )}

        <div className="modal-bottom-actions">
          <button className="btn-secondary" onClick={onClose} disabled={generating}>
            Cancel
          </button>
          <button
            className="btn-primary"
            onClick={handleGenerate}
            disabled={!prompt.trim() || generating}
          >
            <Sparkles size={15} />
            {generating ? 'Generating…' : 'Generate Roadmap'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Roadmap() {
  const [activeRoadmap, setActiveRoadmap] = useState(DEFAULT_ROADMAP)
  const [selectedMilestone, setSelectedMilestone] = useState(null)
  const [showGenerateModal, setShowGenerateModal] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .getActiveRoadmap()
      .then((data) => {
        if (cancelled) return
        if (data && data.roadmap) {
          const adapted = adaptRoadmap(data.roadmap)
          if (adapted && adapted.milestones?.length) {
            setActiveRoadmap({
              title: adapted.title || 'DSA Interview Preparation',
              overallProgress: adapted.overallProgress || 42,
              durationWeeks: '12 weeks',
              milestones: adapted.milestones.map((m, idx) => ({
                id: m.id || `m-${idx}`,
                number: idx + 1,
                title: m.title,
                topicsCount: m.topics?.length || 5,
                duration: m.studyTime || '2h 10m',
                progress: m.progress || 0,
                status: m.status,
                actionLabel: m.progress === 100 ? 'Review' : m.progress > 0 ? 'Continue' : 'Start',
                topics: m.topics || [],
                resources: m.resources || [],
              })),
            })
          }
        }
      })
      .catch(() => {})

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <>
      <PageHeader
        title="Learning Roadmap"
        subtitle="Turn your goals into milestones. Track your progress."
      >
        <button
          className="btn-primary generate-cta-btn"
          onClick={() => setShowGenerateModal(true)}
        >
          <Sparkles size={15} />
          <span>Generate with AI</span>
        </button>
      </PageHeader>

      <Card className="roadmap-main-card">
        {/* Goal Title & Overall Progress */}
        <div className="roadmap-header-strip">
          <div className="roadmap-title-box">
            <h3 className="roadmap-headline">{activeRoadmap.title}</h3>
            <span className="roadmap-subhead">
              {activeRoadmap.overallProgress}% complete · {activeRoadmap.durationWeeks}
            </span>
          </div>

          <div className="roadmap-progress-track">
            <div
              className="roadmap-progress-bar"
              style={{ width: `${activeRoadmap.overallProgress}%` }}
            />
          </div>
        </div>

        {/* Vertical Timeline with Thin Lines and Compact Numbered Nodes */}
        <div className="roadmap-timeline">
          {activeRoadmap.milestones.map((m, index) => {
            const isLast = index === activeRoadmap.milestones.length - 1
            const isDone = m.progress === 100
            const isCurrent = m.status === 'current' || (m.progress > 0 && m.progress < 100)

            return (
              <div key={m.id} className="roadmap-timeline-node">
                {/* Node marker & vertical line */}
                <div className="node-marker-column">
                  <div
                    className={`node-number-bubble ${
                      isDone ? 'done' : isCurrent ? 'current' : 'upcoming'
                    }`}
                  >
                    {isDone ? <Check size={13} strokeWidth={2.8} /> : m.number}
                  </div>
                  {!isLast && <div className="node-connecting-line" />}
                </div>

                {/* Milestone Row Details */}
                <div
                  className="milestone-content-card"
                  onClick={() => setSelectedMilestone(m)}
                >
                  <div className="milestone-left">
                    <h4 className="milestone-title">{m.title}</h4>
                    <span className="milestone-meta">
                      {m.topicsCount} topics · {m.duration}
                    </span>
                  </div>

                  <div className="milestone-right">
                    {m.progress > 0 && m.progress < 100 && (
                      <span className="milestone-pct-badge">{m.progress}%</span>
                    )}

                    <button
                      className={`milestone-action-btn ${
                        m.actionLabel === 'Continue'
                          ? 'btn-continue'
                          : m.actionLabel === 'Review'
                          ? 'btn-review'
                          : 'btn-start'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedMilestone(m)
                      }}
                    >
                      {m.actionLabel}
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      {/* Inspirational bottom quote */}
      <div className="roadmap-quote-wrapper">
        <div className="quote-banner">
          <Sparkles size={14} />
          <span>Big goals start with small, consistent steps.</span>
        </div>
      </div>

      {selectedMilestone && (
        <MilestoneDetailModal
          milestone={selectedMilestone}
          onClose={() => setSelectedMilestone(null)}
        />
      )}

      {showGenerateModal && (
        <AIGenerateModal
          onClose={() => setShowGenerateModal(false)}
          onGenerated={(newRoadmap) => {
            if (newRoadmap) {
              const adapted = adaptRoadmap(newRoadmap) || newRoadmap
              if (adapted.milestones) {
                setActiveRoadmap({
                  title: adapted.title || 'My Learning Roadmap',
                  overallProgress: adapted.overallProgress || 0,
                  durationWeeks: '8 weeks',
                  milestones: adapted.milestones.map((m, idx) => ({
                    id: m.id || `gen-${idx}`,
                    number: idx + 1,
                    title: m.title,
                    topicsCount: m.topics?.length || 5,
                    duration: m.studyTime || 'Not started',
                    progress: m.progress || 0,
                    status: m.status || 'not-started',
                    actionLabel: 'Start',
                    topics: m.topics || [],
                    resources: m.resources || [],
                  })),
                })
              }
            }
          }}
        />
      )}

      <Footer />
    </>
  )
}
