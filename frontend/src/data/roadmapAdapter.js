// Adapts roadmap_store.Roadmap.to_dict() (see api_server.py's
// /api/roadmap/* routes) into the {title, overallProgress, milestones}
// shape the Roadmap page's UI was built around. Kept as one small,
// pure mapping function so the UI components never need to know about
// the backend's field names (status/progress_pct/etc) directly.

const STATUS_MAP = {
  COMPLETED: 'completed',
  IN_PROGRESS: 'current',
  NEEDS_REVISION: 'current',
  NOT_STARTED: 'locked',
  LOCKED: 'locked',
}

function formatStudyTime(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds || 0))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${String(m).padStart(2, '0')}m`
}

function toMile(index) {
  return `MILE ${String(index + 1).padStart(2, '0')}`
}

function adaptResources(resourcesByCategory) {
  const out = []
  Object.values(resourcesByCategory || {}).forEach((items) => {
    items.forEach((r) => {
      out.push({ icon: '🔗', title: r.title, level: r.difficulty || r.source || '' })
    })
  })
  return out
}

export function adaptRoadmap(roadmap) {
  if (!roadmap) return null

  const topics = [...roadmap.topics].sort((a, b) => a.order - b.order)

  const milestones = topics.map((t, i) => {
    // A topic here maps 1:1 to a UI "milestone" (one card on the
    // journey). Individual sub-checklist items aren't tracked
    // separately by the backend, so the topic itself is shown as the
    // single checklist row -- real progress, not invented sub-steps.
    const uiStatus = STATUS_MAP[t.status] || 'locked'
    return {
      id: t.id,
      mile: toMile(i),
      title: t.name,
      progress: Math.round(t.progress_pct),
      completedTopics: t.status === 'COMPLETED' ? 1 : 0,
      totalTopics: 1,
      status: uiStatus,
      studyTime: formatStudyTime(t.time_spent_seconds),
      topics: [{ name: t.description || t.name, done: t.status === 'COMPLETED' }],
      resources: adaptResources(t.resources),
      _backendStatus: t.status,
    }
  })

  const completedMilestones = milestones.filter((m) => m.status === 'completed').length
  const inProgressMilestones = milestones.filter((m) => m._backendStatus === 'IN_PROGRESS' || m._backendStatus === 'NEEDS_REVISION').length
  const remainingMilestones = milestones.length - completedMilestones - inProgressMilestones

  const totalMinutes = topics.reduce((sum, t) => sum + (t.estimated_minutes || 0), 0)
  const dailyMinutes = roadmap.daily_minutes || 60
  const estimatedDays = dailyMinutes > 0 ? Math.max(1, Math.ceil(totalMinutes / dailyMinutes)) : roadmap.deadline_days

  // overall_progress_pct isn't included in to_dict() today -- compute
  // the same weighted formula roadmap_models.Roadmap.overall_progress_pct
  // uses, from the same real per-topic numbers, so this never drifts
  // from the backend's own definition of "done".
  const totalWeight = topics.reduce((sum, t) => sum + Math.max(t.estimated_minutes || 1, 1), 0) || 1
  const earned = topics.reduce(
    (sum, t) => sum + Math.max(t.estimated_minutes || 1, 1) * (t.progress_pct / 100),
    0
  )
  const overallProgress = Math.round((100 * earned) / totalWeight)

  return {
    id: roadmap.id,
    title: roadmap.goal,
    overallProgress,
    completedMilestones,
    totalMilestones: milestones.length,
    inProgressMilestones,
    remainingMilestones,
    estimatedDays,
    milestones,
  }
}

export default adaptRoadmap
