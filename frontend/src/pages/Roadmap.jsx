import { useEffect, useRef, useState, useCallback } from 'react'
import { Flag, Trophy, Check, Lock, Circle, X, Loader2, Sparkles, Search } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import Footer from '../components/Footer.jsx'
import { roadmapGenerationSteps } from '../data/roadmapGenerator.js'
import { getMoreResources } from '../data/roadmapResources.js'
import adaptRoadmap from '../data/roadmapAdapter.js'
import api from '../data/api.js'
import './Roadmap.css'

const statusBadgeLabel = {
  completed: 'Completed',
  current: 'In Progress',
  locked: 'Locked',
}

// Shown only until a real roadmap is fetched from the backend (or
// while none has been generated yet) -- an empty/sample state, never
// mixed with real data once a backend roadmap exists.
const SAMPLE_ROADMAP = {
  title: 'No roadmap yet',
  overallProgress: 0,
  completedMilestones: 0,
  totalMilestones: 0,
  inProgressMilestones: 0,
  remainingMilestones: 0,
  estimatedDays: 0,
  milestones: [],
}

function MilestoneNode({ status }) {
  if (status === 'completed') return <Check size={18} strokeWidth={2.6} />
  if (status === 'locked') return <Lock size={16} strokeWidth={2.2} />
  return <span className="roadmap-current-dot" />
}

/* Recommended resources list, reused on the "current progress" card and inside
   the milestone detail modal. "Find More Resources" is a mock async step today,
   structured so it can call a real search/AI backend later. */
function ResourceList({ milestone, roadmapId, subtitle }) {
  const [extra, setExtra] = useState([])
  const [finding, setFinding] = useState(false)

  useEffect(() => {
    setExtra([])
    setFinding(false)
  }, [milestone.id])

  const findMore = () => {
    setFinding(true)
    // If this milestone came from a real backend roadmap, ask
    // roadmap_resources.py (via roadmap_store.get_or_refresh_resources)
    // for a fresh lookup -- no duplicate resource-finding logic here.
    // Falls back to the local mock list only when there's no backend
    // roadmap to ask (the built-in sample roadmap).
    if (roadmapId) {
      api
        .getTopicResources(roadmapId, milestone.id, true)
        .then((data) => {
          const flat = []
          Object.values(data.resources || {}).forEach((items) => {
            items.forEach((r) => flat.push({ icon: '🔗', title: r.title, level: r.difficulty || r.source || '' }))
          })
          setExtra(flat)
          setFinding(false)
        })
        .catch(() => {
          setExtra(getMoreResources(milestone.title))
          setFinding(false)
        })
    } else {
      window.setTimeout(() => {
        setExtra(getMoreResources(milestone.title))
        setFinding(false)
      }, 900)
    }
  }

  const allResources = [...milestone.resources, ...extra]

  return (
    <div className="roadmap-resources">
      {subtitle && <p className="roadmap-resources-sub">{subtitle}</p>}
      <ul className="roadmap-resource-list">
        {allResources.map((r, i) => (
          <li key={`${r.title}-${i}`} className="roadmap-resource-item">
            <span className="roadmap-resource-icon">{r.icon}</span>
            <div className="roadmap-resource-body">
              <p className="roadmap-resource-name">{r.title}</p>
              <p className="roadmap-resource-level">{r.level}</p>
            </div>
          </li>
        ))}
      </ul>
      {finding ? (
        <p className="roadmap-resources-finding">
          <Loader2 size={14} strokeWidth={2.4} className="spin" />
          Finding resources for: {milestone.title}
        </p>
      ) : (
        <button className="roadmap-resources-more" onClick={findMore}>
          <Search size={14} strokeWidth={2.2} />
          Find More Resources
        </button>
      )}
    </div>
  )
}

function MilestoneStop({ milestone, side, onOpen }) {
  const ref = useRef(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold: 0.2, rootMargin: '0px 0px -60px 0px' }
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      className={`roadmap-stop status-${milestone.status} side-${side}${inView ? ' in-view' : ''}`}
    >
      <div className="roadmap-stop-node-wrap">
        <div className="roadmap-stop-node">
          <MilestoneNode status={milestone.status} />
        </div>
        {milestone.status === 'current' && (
          <span className="roadmap-here-tag">✦ YOU ARE HERE ✦</span>
        )}
      </div>

      <div className="roadmap-stop-card" onClick={() => onOpen(milestone)}>
        <p className="roadmap-stop-mile">{milestone.mile}</p>
        <p className="roadmap-stop-title">{milestone.title}</p>
        <p className="roadmap-stop-percent">{milestone.progress}% Complete</p>
        <p className="roadmap-stop-topics">
          {milestone.completedTopics} / {milestone.totalTopics} topics
        </p>
        <span className="roadmap-stop-badge">{statusBadgeLabel[milestone.status]}</span>
      </div>
    </div>
  )
}

function MilestoneModal({ milestone, roadmapId, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="roadmap-modal-overlay" onClick={onClose}>
      <div className="roadmap-modal" onClick={(e) => e.stopPropagation()}>
        <button className="roadmap-modal-close" onClick={onClose} aria-label="Close">
          <X size={16} strokeWidth={2.4} />
        </button>

        <p className="roadmap-modal-mile">{milestone.mile}</p>
        <h2 className="roadmap-modal-title">{milestone.title}</h2>
        <p className="roadmap-modal-percent">{milestone.progress}% Complete</p>
        <div className="roadmap-modal-bar">
          <div className="roadmap-modal-bar-fill" style={{ width: `${milestone.progress}%` }} />
        </div>
        <p className="roadmap-modal-topics-count">
          {milestone.completedTopics} / {milestone.totalTopics} topics completed
        </p>

        <p className="roadmap-modal-section-title">Topics</p>
        <ul className="roadmap-modal-topic-list">
          {milestone.topics.map((t) => (
            <li key={t.name} className={`roadmap-modal-topic${t.done ? ' done' : ''}`}>
              {t.done ? (
                <Check size={15} strokeWidth={2.4} className="topic-icon" />
              ) : (
                <Circle size={15} strokeWidth={2.2} className="topic-icon" />
              )}
              {t.name}
            </li>
          ))}
        </ul>

        <p className="roadmap-modal-section-title">Recommended Resources</p>
        <ResourceList milestone={milestone} roadmapId={roadmapId} />

        <div className="roadmap-modal-meta">
          <div className="roadmap-modal-meta-item">
            <p>Study Time</p>
            <p>{milestone.studyTime}</p>
          </div>
          <div className="roadmap-modal-meta-item">
            <p>Status</p>
            <p>{statusBadgeLabel[milestone.status]}</p>
          </div>
        </div>

        <button className="roadmap-modal-cta" onClick={onClose}>
          Continue Learning
        </button>
      </div>
    </div>
  )
}

/* "My Portion" — free-form syllabus input that drives roadmap generation.
   The parsing itself is mock (see data/roadmapGenerator.js) so it can be
   swapped for a real AI/backend call later without touching this component. */
function PortionInput({ value, onChange, onGenerate, isGenerating, stepIndex, error }) {
  return (
    <Card className="roadmap-portion-card">
      <p className="roadmap-section-title">My Portion</p>
      <p className="roadmap-portion-subtitle">
        Enter your syllabus, subjects, or study portions and we'll turn them into a
        personalized learning roadmap.
      </p>

      <textarea
        className="roadmap-portion-textarea"
        placeholder={
          'Type or paste your portion here...\n\nExample:\nUnit 1 - Arrays\nUnit 2 - Linked Lists\nUnit 3 - Stacks and Queues\nUnit 4 - Trees\nUnit 5 - Graphs'
        }
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={7}
        disabled={isGenerating}
      />

      {error && <p className="roadmap-portion-error">{error}</p>}

      <button className="roadmap-generate-btn" onClick={onGenerate} disabled={isGenerating}>
        {isGenerating ? (
          <Loader2 size={16} strokeWidth={2.4} className="spin" />
        ) : (
          <Sparkles size={16} strokeWidth={2.2} />
        )}
        Generate My Roadmap
      </button>

      {isGenerating && (
        <p className="roadmap-generate-step">{roadmapGenerationSteps[stepIndex]}</p>
      )}
    </Card>
  )
}

export default function Roadmap() {
  const [portionText, setPortionText] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [portionError, setPortionError] = useState('')
  const [generatedRoadmap, setGeneratedRoadmap] = useState(null)
  const [activeMilestone, setActiveMilestone] = useState(null)
  const [loadingActive, setLoadingActive] = useState(true)

  const mountedRef = useRef(true)
  useEffect(
    () => () => {
      mountedRef.current = false
    },
    []
  )

  // Load whatever roadmap is already active on the backend (STEP 12 —
  // real Study Guard data, not a fabricated default) as soon as the
  // page mounts, so a roadmap created in a previous session shows up
  // immediately instead of the built-in sample.
  useEffect(() => {
    let cancelled = false
    api
      .getActiveRoadmap()
      .then((data) => {
        if (cancelled) return
        if (data.roadmap) setGeneratedRoadmap(adaptRoadmap(data.roadmap))
      })
      .catch(() => {
        // No backend reachable yet -- fall back to the sample roadmap below.
      })
      .finally(() => {
        if (!cancelled) setLoadingActive(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const openMilestone = useCallback((m) => setActiveMilestone(m), [])
  const closeMilestone = useCallback(() => setActiveMilestone(null), [])

  const handleGenerate = async () => {
    if (!portionText.trim()) {
      setPortionError('Please enter your syllabus or study portion first.')
      return
    }
    setPortionError('')
    setIsGenerating(true)
    setActiveMilestone(null)

    for (let i = 0; i < roadmapGenerationSteps.length; i++) {
      if (!mountedRef.current) return
      setStepIndex(i)
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => window.setTimeout(resolve, 550))
    }

    if (!mountedRef.current) return

    // Real roadmap generation happens on the backend (roadmap_generator.py
    // via roadmap_store.create_roadmap) -- this only sends the raw text
    // as the "goal" and displays whatever topics the backend actually
    // produced. No second/duplicate generation logic here.
    try {
      const { roadmap } = await api.createRoadmap({ goal: portionText.trim() })
      if (!mountedRef.current) return
      setGeneratedRoadmap(adaptRoadmap(roadmap))
    } catch (e) {
      if (!mountedRef.current) return
      setPortionError(e.message || "Couldn't generate a roadmap — is Study Guard running?")
    }
    setIsGenerating(false)
  }

  const roadmapData = generatedRoadmap || SAMPLE_ROADMAP
  const {
    title,
    overallProgress,
    completedMilestones,
    totalMilestones,
    inProgressMilestones,
    remainingMilestones,
    estimatedDays,
    milestones,
  } = roadmapData

  const currentMilestone = milestones.find((m) => m.status === 'current')

  return (
    <>
      <PageHeader
        title="Learning Roadmap"
        subtitle="Build your path. Track your progress. Reach your goal."
      />

      <PortionInput
        value={portionText}
        onChange={setPortionText}
        onGenerate={handleGenerate}
        isGenerating={isGenerating}
        stepIndex={stepIndex}
        error={portionError}
      />

      <Card className="roadmap-summary-card">
        <div className="roadmap-summary-top">
          <div>
            <p className="roadmap-summary-label">{title}</p>
            <p className="roadmap-summary-heading">Overall Progress</p>
          </div>
          <p className="roadmap-summary-percent">{overallProgress}%</p>
        </div>

        <div className="roadmap-summary-bar">
          <div className="roadmap-summary-bar-fill" style={{ width: `${overallProgress}%` }} />
        </div>
        <p className="roadmap-summary-sub">
          {completedMilestones} / {totalMilestones} milestones completed
        </p>

        <div className="roadmap-summary-stats">
          <span className="roadmap-stat">
            <span className="dot green" />
            Completed <strong>{completedMilestones}</strong>
          </span>
          <span className="roadmap-stat">
            <span className="dot purple" />
            In Progress <strong>{inProgressMilestones}</strong>
          </span>
          <span className="roadmap-stat">
            <span className="dot gray" />
            Remaining <strong>{remainingMilestones}</strong>
          </span>
          <span className="roadmap-summary-eta">
            Estimated completion <strong>{estimatedDays} days</strong>
          </span>
        </div>
      </Card>

      {currentMilestone && (
        <Card className="roadmap-current-resources-card">
          <p className="roadmap-section-title">Recommended Resources</p>
          <p className="roadmap-current-resources-topic">{currentMilestone.title}</p>
          <ResourceList
            milestone={currentMilestone}
            roadmapId={roadmapData.id}
            subtitle="Recommended for your current progress:"
          />
        </Card>
      )}

      {milestones.length === 0 && !loadingActive ? (
        <Card className="roadmap-summary-card">
          <p className="roadmap-portion-subtitle">
            No roadmap yet — enter your syllabus or study portion above and generate one to see
            your learning journey here.
          </p>
        </Card>
      ) : (
      <div className="roadmap-journey">
        <div className="roadmap-endpoint start">
          <span className="roadmap-endpoint-badge">
            <Flag size={22} strokeWidth={2.2} />
          </span>
          <span className="roadmap-endpoint-label">Start</span>
        </div>

        {milestones.map((m, i) => (
          <MilestoneStop
            key={m.id}
            milestone={m}
            side={i % 2 === 0 ? 'left' : 'right'}
            onOpen={openMilestone}
          />
        ))}

        <div className="roadmap-endpoint goal">
          <span className="roadmap-endpoint-badge">
            <Trophy size={24} strokeWidth={2.2} />
          </span>
          <span className="roadmap-endpoint-label">Final Goal</span>
          <span className="roadmap-endpoint-sub">{title}</span>
        </div>
      </div>
      )}

      {activeMilestone && <MilestoneModal milestone={activeMilestone} roadmapId={roadmapData.id} onClose={closeMilestone} />}

      <Footer />
    </>
  )
}
