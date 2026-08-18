import { getRecommendedResources } from './roadmapResources.js'

// Shape the UI expects. Kept here as documentation of the contract between
// the (currently mock) parser and the Roadmap page.
export const emptyPortionInput = {
  text: '',
}

export const emptyRoadmapData = {
  title: '',
  overallProgress: 0,
  milestones: [],
}

const UNIT_HEADER = /^(unit|module|week|chapter|part)\s*[-:#]?\s*\d*\s*[:\-]?\s*/i

function toMile(index) {
  return `MILE ${String(index + 1).padStart(2, '0')}`
}

// Pads a thin topic list (e.g. a single "Arrays" line) into a small checklist
// so the milestone has something to track progress against. Real parsing/AI
// would replace this with an actual topic breakdown.
function expandTopics(title, rawTopics) {
  if (rawTopics.length >= 3) return rawTopics.slice(0, 8)

  // rawTopics[0] is reused as the milestone title, so don't repeat it as a
  // checklist item too — only real extra topics (rawTopics[1+]) count.
  const extras = rawTopics.slice(1)
  const fillerPool = [
    `${title} Basics`,
    `${title} Core Concepts`,
    `${title} Practice Problems`,
    `${title} Advanced Concepts`,
  ]

  const combined = [...extras]
  for (const filler of fillerPool) {
    if (combined.length >= 3) break
    if (!combined.includes(filler)) combined.push(filler)
  }
  return combined.slice(0, 3)
}

function buildMilestone(rawTopics, index) {
  const title = rawTopics[0]
  const topicNames = expandTopics(title, rawTopics)
  const status = index === 0 ? 'current' : 'locked'

  return {
    id: index + 1,
    mile: toMile(index),
    title,
    progress: 0,
    completedTopics: 0,
    totalTopics: topicNames.length,
    status,
    studyTime: '0h 00m',
    topics: topicNames.map((name) => ({ name, done: false })),
    resources: getRecommendedResources(title),
  }
}

// Groups raw, free-form lines into blocks of topics. Each block becomes one milestone.
function groupLinesIntoBlocks(lines) {
  const hasUnitHeaders = lines.some((line) => UNIT_HEADER.test(line))

  if (hasUnitHeaders) {
    const blocks = []
    let current = null
    lines.forEach((line) => {
      if (UNIT_HEADER.test(line)) {
        if (current && current.length) blocks.push(current)
        const rest = line.replace(UNIT_HEADER, '').trim()
        current = rest ? [rest] : []
      } else if (current) {
        current.push(line)
      }
      // Lines before the first unit header (e.g. a title) are ignored as a preamble.
    })
    if (current && current.length) blocks.push(current)
    return blocks
  }

  // Flat mode: skip a leading label-only line like "Data Structures:" and
  // treat every remaining non-empty line as its own block.
  let working = lines
  if (working.length > 1) {
    const first = working[0]
    if (/:$/.test(first) && !first.includes(',')) {
      working = working.slice(1)
    }
  }
  return working.map((line) => [line])
}

/**
 * Mock "portion text → roadmap" parser.
 * Not real AI/backend analysis — a placeholder heuristic so the roadmap UI has
 * something to render from free-form input today. Replace the body of this
 * function with a real API/AI call later; keep the return shape the same.
 */
export function generateRoadmapFromPortion(text) {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)

  if (lines.length === 0) return null

  const blocks = groupLinesIntoBlocks(lines)

  const topicBlocks = blocks
    .map((block) =>
      block
        .join(', ')
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
    )
    .filter((topics) => topics.length > 0)

  if (topicBlocks.length === 0) return null

  const milestones = topicBlocks.map((topics, index) => buildMilestone(topics, index))

  const totalMilestones = milestones.length
  const completedMilestones = milestones.filter((m) => m.status === 'completed').length
  const inProgressMilestones = milestones.filter((m) => m.status === 'current').length
  const remainingMilestones = milestones.filter((m) => m.status === 'locked').length
  const overallProgress =
    totalMilestones === 0
      ? 0
      : Math.round(milestones.reduce((sum, m) => sum + m.progress, 0) / totalMilestones)

  return {
    title: 'Your Study Roadmap',
    overallProgress,
    completedMilestones,
    totalMilestones,
    inProgressMilestones,
    remainingMilestones,
    estimatedDays: Math.max(7, totalMilestones * 3),
    milestones,
  }
}

// Sequenced loading copy shown while the mock parser "runs". Kept as data so a
// real async pipeline (upload → AI → backend) can drive the same steps later.
export const roadmapGenerationSteps = [
  'Analyzing your portion...',
  'Organizing topics...',
  'Building your learning path...',
  'Preparing resources...',
]
