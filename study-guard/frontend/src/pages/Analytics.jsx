import { useEffect, useState } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { TrendingUp, Clock, Target } from 'lucide-react'
import PageHeader from '../components/PageHeader.jsx'
import Card from '../components/Card.jsx'
import StatCard from '../components/StatCard.jsx'
import Footer from '../components/Footer.jsx'
import api from '../data/api.js'
import './Analytics.css'

export default function Analytics() {
  const [weeklyAnalytics, setWeeklyAnalytics] = useState([])

  useEffect(() => {
    let cancelled = false
    api
      .getWeeklyAnalytics()
      .then((data) => {
        if (!cancelled) setWeeklyAnalytics(data.days || [])
      })
      .catch(() => {
        // leave empty — real data unavailable
      })
    return () => {
      cancelled = true
    }
  }, [])

  const hasData = weeklyAnalytics.some((d) => d.hours > 0)
  const avgFocus = hasData
    ? Math.round(weeklyAnalytics.reduce((sum, d) => sum + d.focused, 0) / weeklyAnalytics.length)
    : 0
  const totalHours = hasData
    ? weeklyAnalytics.reduce((sum, d) => sum + d.hours, 0).toFixed(1)
    : '0.0'
  const bestDay = hasData
    ? weeklyAnalytics.reduce((best, d) => (d.focused > (best?.focused ?? -1) ? d : best), null)
    : null

  return (
    <>
      <PageHeader
        title="Analytics"
        subtitle="See how your focus and study time have trended this week."
      />

      <div className="row-4col">
        <StatCard
          title="Avg. Focus"
          icon={Target}
          iconTone="green"
          value={hasData ? `${avgFocus}%` : '—'}
          subtext="This week"
          subtextColor="var(--color-green)"
        />
        <StatCard
          title="Total Study Time"
          icon={Clock}
          iconTone="blue"
          value={hasData ? `${totalHours}h` : '—'}
          subtext="This week"
        />
        <StatCard
          title="Best Day"
          icon={TrendingUp}
          iconTone="purple"
          value={bestDay ? bestDay.day : '—'}
          subtext={bestDay ? `${bestDay.focused}% focused` : 'No data yet'}
          subtextColor="var(--accent-purple-dark)"
        />
      </div>

      <Card className="analytics-chart-card">
        <div className="card-header-row">
          <h2 className="card-title">Focused vs. Distraction — Weekly</h2>
        </div>
        <div className="analytics-chart-wrap">
          {hasData ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={weeklyAnalytics} barGap={4}>
                <CartesianGrid vertical={false} stroke="#eef0f7" />
                <XAxis
                  dataKey="day"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'var(--text-muted)', fontSize: 12.5 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: 'var(--text-muted)', fontSize: 12.5 }}
                  width={36}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: 12,
                    border: '1px solid #f1f2f8',
                    boxShadow: '0 4px 20px rgba(35,40,80,0.08)',
                    fontSize: 13,
                  }}
                />
                <Bar dataKey="focused" name="Focused %" fill="var(--color-green)" radius={[6, 6, 0, 0]} />
                <Bar dataKey="distraction" name="Distraction %" fill="var(--color-red)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="analytics-empty">Complete a few sessions this week to see your trends here.</p>
          )}
        </div>
      </Card>

      <Footer />
    </>
  )
}
