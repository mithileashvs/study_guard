import { useEffect, useState } from 'react'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { ChevronDown, Sparkles } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import StatCard from '../components/StatCard.jsx'
import Footer from '../components/Footer.jsx'
import api from '../data/api.js'
import './Analytics.css'

const DEFAULT_WEEKLY = [
  { day: 'Mon', focused: 68, distraction: 12, away: 20, hours: 2.4 },
  { day: 'Tue', focused: 74, distraction: 16, away: 10, hours: 3.1 },
  { day: 'Wed', focused: 61, distraction: 22, away: 17, hours: 1.8 },
  { day: 'Thu', focused: 82, distraction: 10, away: 8, hours: 3.9 },
  { day: 'Fri', focused: 72, distraction: 14, away: 14, hours: 2.9 },
  { day: 'Sat', focused: 58, distraction: 24, away: 18, hours: 1.5 },
  { day: 'Sun', focused: 76, distraction: 15, away: 9, hours: 2.2 },
]

export default function Analytics() {
  const [weeklyData, setWeeklyData] = useState(DEFAULT_WEEKLY)
  const [timeRange, setTimeRange] = useState('This Week')

  useEffect(() => {
    let cancelled = false
    api
      .getWeeklyAnalytics()
      .then((data) => {
        if (cancelled) return
        if (data && data.days?.length) {
          setWeeklyData(
            data.days.map((d) => ({
              ...d,
              away: Math.max(0, 100 - (d.focused + d.distraction)),
            }))
          )
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  // Metrics computation or defaults
  const totalHours = weeklyData.reduce((acc, d) => acc + (d.hours || 0), 0)
  const totalHoursFormatted = `${Math.floor(totalHours)}h ${Math.round((totalHours % 1) * 60)}m`

  const avgFocus = Math.round(
    weeklyData.reduce((acc, d) => acc + (d.focused || 0), 0) / (weeklyData.length || 1)
  )

  const bestDayObj = weeklyData.reduce(
    (best, d) => ((d.hours || 0) > (best?.hours || 0) ? d : best),
    weeklyData[3]
  )

  // Thin donut chart constants
  const size = 160
  const strokeWidth = 6 // 5-7px per instructions
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  // Donut slices for Focus vs Distraction
  const focusedVal = 82
  const distractedVal = 12
  const awayVal = 6

  const focusedDash = (circumference * focusedVal) / 100
  const distractedDash = (circumference * distractedVal) / 100
  const awayDash = (circumference * awayVal) / 100

  return (
    <>
      <PageHeader
        title="Analytics"
        subtitle="See how your focus and study time have trended."
      >
        <div className="analytics-range-selector">
          <span>{timeRange}</span>
          <ChevronDown size={14} />
        </div>
      </PageHeader>

      {/* 4 Top Metric Cards */}
      <div className="analytics-metrics-grid">
        <StatCard
          title="Total Study Time"
          value={totalHoursFormatted || '18h 42m'}
          delta="↑ 14%"
          deltaType="positive"
        />

        <StatCard
          title="Avg. Focus Score"
          value={`${avgFocus || 82}%`}
          delta="↑ 8%"
          deltaType="positive"
        />

        <StatCard
          title="Distraction Time"
          value="2h 14m"
          delta="↓ 18%"
          deltaType="positive"
        />

        <StatCard
          title="Best Day"
          value={bestDayObj ? bestDayObj.day : 'Thu'}
          subtext={bestDayObj ? `${bestDayObj.hours}h ${Math.round((bestDayObj.hours % 1) * 60)}m` : '3h 52m'}
        />
      </div>

      {/* 2 Chart Cards */}
      <div className="analytics-charts-grid">
        {/* Left: Focus vs Distraction Thin Donut */}
        <Card className="analytics-chart-box">
          <div className="chart-header">
            <h3 className="chart-title">Focus vs. Distraction</h3>
          </div>

          <div className="donut-viz-wrapper">
            <div className="thin-donut-container">
              <svg width={size} height={size} className="donut-svg">
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke="#F1F5F9"
                  strokeWidth={strokeWidth}
                />
                {/* Away segment */}
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke="#94A3B8"
                  strokeWidth={strokeWidth}
                  strokeDasharray={`${circumference} ${circumference}`}
                  transform={`rotate(-90 ${size / 2} ${size / 2})`}
                />
                {/* Distracted segment */}
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke="#F97316"
                  strokeWidth={strokeWidth}
                  strokeDasharray={`${focusedDash + distractedDash} ${circumference}`}
                  transform={`rotate(-90 ${size / 2} ${size / 2})`}
                />
                {/* Focused segment */}
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke="#635BFF"
                  strokeWidth={strokeWidth}
                  strokeDasharray={`${focusedDash} ${circumference}`}
                  strokeLinecap="round"
                  transform={`rotate(-90 ${size / 2} ${size / 2})`}
                />
              </svg>
              <div className="thin-donut-center">
                <span className="donut-big-pct">{focusedVal}%</span>
              </div>
            </div>

            {/* Restrained Legend */}
            <div className="chart-legend-list">
              <div className="chart-legend-row">
                <span className="legend-dot-bullet dot-focused" />
                <span className="legend-name">Focused</span>
                <span className="legend-score">{focusedVal}%</span>
              </div>

              <div className="chart-legend-row">
                <span className="legend-dot-bullet dot-distracted" />
                <span className="legend-name">Distracted</span>
                <span className="legend-score">{distractedVal}%</span>
              </div>

              <div className="chart-legend-row">
                <span className="legend-dot-bullet dot-away" />
                <span className="legend-name">Away</span>
                <span className="legend-score">{awayVal}%</span>
              </div>
            </div>
          </div>
        </Card>

        {/* Right: Study Time Trend Line Chart */}
        <Card className="analytics-chart-box">
          <div className="chart-header">
            <h3 className="chart-title">Study Time Trend</h3>
          </div>

          <div className="trend-chart-area">
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={weeklyData} margin={{ top: 12, right: 12, left: -24, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#F1F5F9" />
                <XAxis
                  dataKey="day"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#94A3B8', fontSize: 11.5 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#94A3B8', fontSize: 11.5 }}
                  unit="h"
                  domain={[0, 6]}
                />
                <Tooltip
                  contentStyle={{
                    background: '#FFFFFF',
                    borderRadius: 8,
                    border: '1px solid #E5E7EB',
                    boxShadow: '0 4px 12px rgba(17, 24, 39, 0.08)',
                    fontSize: 12,
                  }}
                  formatter={(val) => [`${val} hrs`, 'Study Time']}
                />
                <Line
                  type="monotone"
                  dataKey="hours"
                  stroke="#635BFF"
                  strokeWidth={2.2}
                  dot={{ fill: '#635BFF', r: 3.5, strokeWidth: 0 }}
                  activeDot={{ r: 5, fill: '#635BFF', stroke: '#FFFFFF', strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Quote banner */}
      <div className="analytics-quote-wrapper">
        <div className="quote-banner">
          <Sparkles size={14} />
          <span>Consistency today creates a better tomorrow.</span>
        </div>
      </div>

      <Footer />
    </>
  )
}
