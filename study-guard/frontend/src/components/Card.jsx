export default function Card({ children, className = '', ...rest }) {
  return (
    <div className={`ui-card ${className}`} {...rest}>
      {children}
    </div>
  )
}
