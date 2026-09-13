import './PageHeader.css'

export default function PageHeader({ title, subtitle, rightElement, children }) {
  return (
    <header className="page-header">
      <div className="page-header-content">
        <h1 className="page-header-title">{title}</h1>
        {subtitle && <p className="page-header-subtitle">{subtitle}</p>}
      </div>
      {(rightElement || children) && (
        <div className="page-header-actions">
          {rightElement}
          {children}
        </div>
      )}
    </header>
  )
}
