// Central mock data source. Swap these out for real API calls later —
// components consume this shape, not the source, so wiring up a backend
// means editing this file (or replacing it with fetch calls) only.

import { getRecommendedResources } from './roadmapResources.js'

export const user = {
  name: 'Mithileash',
  greeting: 'Good morning',
}

export const weather = {
  tempC: 30,
  condition: 'Mostly sunny',
  icon: 'sun',
}

export const liveFocusMonitor = {
  isLive: true,
  status: [
    { label: 'Posture', value: 'Good', tone: 'good' },
    { label: 'Presence', value: 'Present', tone: 'good' },
    { label: 'Distraction', value: 'Low', tone: 'good' },
  ],
}

export const focusBreakdown = {
  focusedPercent: 72,
  segments: [
    { label: 'Focused', value: 72, color: 'var(--color-green)' },
    { label: 'Distraction', value: 12, color: 'var(--color-red)' },
    { label: 'Posture', value: 8, color: 'var(--color-blue)' },
    { label: 'Presence', value: 8, color: 'var(--accent-purple)' },
  ],
}

export const currentSession = {
  elapsed: '01:24:36',
  startedAt: '09:15 AM',
  status: 'Active',
}

export const sessionHealth = {
  rating: 'Good',
  message: "You're doing great!",
}

export const currentActivity = {
  type: 'Studying',
  detail: 'DSA – Arrays & Strings',
}

export const studyProgress = {
  percent: 72,
  label: 'Daily Goal Progress',
}

export const timeline = {
  hours: ['9 AM', '10 AM', '11 AM', '12 PM', '1 PM', '2 PM'],
  segments: [
    { type: 'focused', widthPercent: 40 },
    { type: 'distraction', widthPercent: 8 },
    { type: 'focused', widthPercent: 22 },
    { type: 'break', widthPercent: 12 },
    { type: 'away', widthPercent: 18 },
  ],
  legend: [
    { label: 'Focused', duration: '3h 20m', tone: 'good' },
    { label: 'Distraction', duration: '25m', tone: 'bad' },
    { label: 'Break', duration: '20m', tone: 'info' },
    { label: 'Away', duration: '15m', tone: 'neutral' },
  ],
}

export const recentAlerts = [
  { id: 1, type: 'youtube', title: 'YouTube Distraction', time: '10:42 AM' },
  { id: 2, type: 'posture', title: 'Poor Posture Detected', time: '10:31 AM' },
  { id: 3, type: 'break', title: 'Break Time Missed', time: '09:45 AM' },
]

export const appMeta = {
  version: 'Study Guard v1.0.0',
  systemStatus: 'All systems normal',
}

// Companions are designed as a data-driven list so new companions can be
// added without touching component logic — just append to this array.
export const companions = [
  {
    id: 'study-cat',
    name: 'Study Cat',
    emoji: '🐱',
    tagline: 'Your current companion',
    description:
      'A calm, curious companion that keeps you company during long focus sessions and celebrates your streaks.',
    active: true,
    mood: 'Content',
    bond: 78,
  },
  {
    id: 'study-robot',
    name: 'Study Robot',
    emoji: '🤖',
    tagline: 'Precise & analytical',
    description:
      'Tracks your metrics closely and gives you sharp, data-driven nudges to stay on task.',
    active: false,
    mood: 'Focused',
    bond: 34,
  },
  {
    id: 'study-fox',
    name: 'Study Fox',
    emoji: '🦊',
    tagline: 'Playful & energetic',
    description:
      'Brings a bit of energy to your breaks and keeps sessions from feeling monotonous.',
    active: false,
    mood: 'Playful',
    bond: 12,
  },
]

export const activeCompanion = companions.find((c) => c.active) || companions[0]

export const roadmapMilestones = [
  { id: 1, title: 'Arrays & Strings', status: 'done', detail: 'Core patterns + 20 problems' },
  { id: 2, title: 'Linked Lists', status: 'done', detail: 'Singly, doubly, cyclic detection' },
  { id: 3, title: 'Trees & Graphs', status: 'in-progress', detail: 'BFS/DFS, traversals' },
  { id: 4, title: 'Dynamic Programming', status: 'upcoming', detail: '1D & 2D DP patterns' },
  { id: 5, title: 'System Design Basics', status: 'upcoming', detail: 'Scalability fundamentals' },
]

// Structured mock data for the redesigned Roadmap journey view.
// Kept separate from UI so it can later be swapped for real Study Guard backend data.
export const roadmapJourney = {
  title: 'DSA Mastery',
  overallProgress: 72,
  completedMilestones: 7,
  totalMilestones: 10,
  inProgressMilestones: 1,
  remainingMilestones: 2,
  estimatedDays: 18,
  milestones: [
    {
      id: 1,
      mile: 'MILE 01',
      title: 'Arrays',
      progress: 100,
      completedTopics: 10,
      totalTopics: 10,
      status: 'completed',
      studyTime: '5h 10m',
      topics: [
        { name: 'Two Pointers', done: true },
        { name: 'Sliding Window', done: true },
        { name: 'Prefix Sums', done: true },
        { name: 'Sorting Fundamentals', done: true },
        { name: 'Binary Search on Arrays', done: true },
      ],
      resources: getRecommendedResources('Arrays'),
    },
    {
      id: 2,
      mile: 'MILE 02',
      title: 'Strings',
      progress: 100,
      completedTopics: 8,
      totalTopics: 8,
      status: 'completed',
      studyTime: '3h 45m',
      topics: [
        { name: 'Pattern Matching', done: true },
        { name: 'String Hashing', done: true },
        { name: 'Palindromes', done: true },
        { name: 'Anagrams', done: true },
      ],
      resources: getRecommendedResources('Strings'),
    },
    {
      id: 3,
      mile: 'MILE 03',
      title: 'Linked Lists',
      progress: 65,
      completedTopics: 13,
      totalTopics: 20,
      status: 'current',
      studyTime: '4h 05m',
      topics: [
        { name: 'Singly Linked List', done: true },
        { name: 'Doubly Linked List', done: true },
        { name: 'Cycle Detection', done: true },
        { name: 'Reversal Patterns', done: false },
        { name: 'Merge & Sort', done: false },
      ],
      resources: getRecommendedResources('Linked Lists'),
    },
    {
      id: 4,
      mile: 'MILE 04',
      title: 'Stacks & Queues',
      progress: 0,
      completedTopics: 0,
      totalTopics: 12,
      status: 'locked',
      studyTime: '0h 00m',
      topics: [
        { name: 'Stack Basics', done: false },
        { name: 'Queue Basics', done: false },
        { name: 'Monotonic Stack', done: false },
        { name: 'Priority Queue', done: false },
      ],
      resources: getRecommendedResources('Stacks & Queues'),
    },
    {
      id: 5,
      mile: 'MILE 05',
      title: 'Recursion',
      progress: 0,
      completedTopics: 0,
      totalTopics: 10,
      status: 'locked',
      studyTime: '0h 00m',
      topics: [
        { name: 'Backtracking', done: false },
        { name: 'Divide & Conquer', done: false },
        { name: 'Memoized Recursion', done: false },
      ],
      resources: getRecommendedResources('Recursion'),
    },
    {
      id: 6,
      mile: 'MILE 06',
      title: 'Trees',
      progress: 0,
      completedTopics: 0,
      totalTopics: 20,
      status: 'locked',
      studyTime: '0h 00m',
      topics: [
        { name: 'Binary Trees', done: false },
        { name: 'Tree Traversal', done: false },
        { name: 'Binary Search Tree', done: false },
        { name: 'AVL Trees', done: false },
        { name: 'Heap', done: false },
        { name: 'Advanced Trees', done: false },
      ],
      resources: getRecommendedResources('Trees'),
    },
    {
      id: 7,
      mile: 'MILE 07',
      title: 'Graphs',
      progress: 0,
      completedTopics: 0,
      totalTopics: 18,
      status: 'locked',
      studyTime: '0h 00m',
      topics: [
        { name: 'BFS & DFS', done: false },
        { name: 'Shortest Paths', done: false },
        { name: 'Union-Find', done: false },
        { name: 'Topological Sort', done: false },
      ],
      resources: getRecommendedResources('Graphs'),
    },
    {
      id: 8,
      mile: 'MILE 08',
      title: 'Dynamic Programming',
      progress: 0,
      completedTopics: 0,
      totalTopics: 22,
      status: 'locked',
      studyTime: '0h 00m',
      topics: [
        { name: '1D DP Patterns', done: false },
        { name: '2D DP Patterns', done: false },
        { name: 'Knapsack Variants', done: false },
        { name: 'DP on Trees & Graphs', done: false },
      ],
      resources: getRecommendedResources('Dynamic Programming'),
    },
  ],
}

// Mock data for Settings → Distraction Control.
// Kept separate from UI; will later connect to the real Study Guard distraction engine.
export const distractionSettings = {
  allowedSites: ['ChatGPT', 'Visual Studio Code', 'Google'],
  allowedKeywords: ['Python', 'DSA', 'LeetCode', 'Programming'],
}

export const upcomingSessions = [
  { id: 1, title: 'DSA — Trees & Graphs', date: 'Today', time: '4:00 PM', duration: '90 min' },
  { id: 2, title: 'Mock Interview Practice', date: 'Tomorrow', time: '10:00 AM', duration: '60 min' },
  { id: 3, title: 'System Design Basics', date: 'Wed', time: '6:30 PM', duration: '75 min' },
]

export const pastSessions = [
  { id: 1, title: 'DSA – Arrays & Strings', date: 'Aug 17', duration: '1h 24m', focus: 72 },
  { id: 2, title: 'DSA – Linked Lists', date: 'Aug 16', duration: '2h 05m', focus: 81 },
  { id: 3, title: 'Mock Interview Practice', date: 'Aug 15', duration: '58m', focus: 65 },
  { id: 4, title: 'System Design Basics', date: 'Aug 14', duration: '1h 40m', focus: 77 },
]

export const weeklyAnalytics = [
  { day: 'Mon', focused: 68, distraction: 20, hours: 2.4 },
  { day: 'Tue', focused: 74, distraction: 14, hours: 3.1 },
  { day: 'Wed', focused: 61, distraction: 25, hours: 1.8 },
  { day: 'Thu', focused: 82, distraction: 10, hours: 3.6 },
  { day: 'Fri', focused: 72, distraction: 12, hours: 2.9 },
  { day: 'Sat', focused: 58, distraction: 28, hours: 1.5 },
  { day: 'Sun', focused: 76, distraction: 15, hours: 2.2 },
]

export const historyLog = [
  { id: 1, date: 'Aug 17, 2026', title: 'DSA – Arrays & Strings', duration: '1h 24m', focus: 72 },
  { id: 2, date: 'Aug 16, 2026', title: 'DSA – Linked Lists', duration: '2h 05m', focus: 81 },
  { id: 3, date: 'Aug 15, 2026', title: 'Mock Interview Practice', duration: '58m', focus: 65 },
  { id: 4, date: 'Aug 14, 2026', title: 'System Design Basics', duration: '1h 40m', focus: 77 },
  { id: 5, date: 'Aug 13, 2026', title: 'DSA – Sorting Algorithms', duration: '1h 12m', focus: 69 },
]
