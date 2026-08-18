// Mock "recommended resources" generator.
// This is intentionally templated (not a real search or AI call) — it exists so the
// roadmap UI has something relevant to show per-topic today. Swap the body of
// getRecommendedResources / getMoreResources for a real backend/AI/search call later;
// the shape returned ({ type, icon, title, level }[]) is what the UI expects.

const LEVELS = ['Beginner', 'Intermediate', 'Advanced']

export function getRecommendedResources(topic) {
  return [
    { type: 'video', icon: '📺', title: `${topic} Fundamentals`, level: 'Beginner' },
    { type: 'article', icon: '📄', title: `${topic} Explained`, level: 'Beginner' },
    { type: 'practice', icon: '💻', title: `${topic} Practice Problems`, level: 'Intermediate' },
  ]
}

// Called by "Find More Resources" — a distinct, non-overlapping set so a click
// visibly adds new results. In a real integration this would be a fresh search query.
export function getMoreResources(topic) {
  return [
    { type: 'video', icon: '📺', title: `${topic} Deep Dive`, level: 'Intermediate' },
    { type: 'article', icon: '📄', title: `${topic} Interview Questions`, level: 'Advanced' },
    { type: 'practice', icon: '💻', title: `${topic} Advanced Practice Set`, level: LEVELS[2] },
  ]
}
