import { Shield } from 'lucide-react'
import { appMeta } from '../data/mockData.js'
import './Footer.css'

export default function Footer() {
  return (
    <footer className="app-footer">
      <span className="app-footer-brand">
        <Shield size={15} strokeWidth={2.2} />
        {appMeta.version}
      </span>
      <span className="app-footer-status">
        {appMeta.systemStatus}
        <span className="app-footer-dot" />
      </span>
    </footer>
  )
}
