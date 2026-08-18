import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar.jsx'
import FloatingCoachButton from './components/FloatingCoachButton.jsx'
import Overview from './pages/Overview.jsx'
import Roadmap from './pages/Roadmap.jsx'
import LiveSession from './pages/LiveSession.jsx'
import Sessions from './pages/Sessions.jsx'
import Analytics from './pages/Analytics.jsx'
import History from './pages/History.jsx'
import Companion from './pages/Companion.jsx'
import Settings from './pages/Settings.jsx'
import AICoach from './pages/AICoach.jsx'

export default function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-area">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/roadmap" element={<Roadmap />} />
          <Route path="/live-session" element={<LiveSession />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/history" element={<History />} />
          <Route path="/companion" element={<Companion />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/ai-coach" element={<AICoach />} />
        </Routes>
      </div>
      <FloatingCoachButton />
    </div>
  )
}
