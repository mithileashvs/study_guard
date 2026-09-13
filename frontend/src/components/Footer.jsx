import Logo from './Logo.jsx'
import { appMeta } from '../data/mockData.js'
import './Footer.css'

export default function Footer() {
  return (
    <footer className="app-footer">
      <div className="app-footer-brand">
        <Logo size={14} color="#635BFF" />
        <span>{appMeta.version}</span>
      </div>
      <div className="app-footer-status">
        <span className="app-footer-dot" />
        <span>{appMeta.systemStatus}</span>
      </div>
    </footer>
  )
}
