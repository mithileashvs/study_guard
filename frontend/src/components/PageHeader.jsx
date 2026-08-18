import WeatherCard from './WeatherCard.jsx'
import './PageHeader.css'

export default function PageHeader({ title, subtitle, showWeather = false }) {
  return (
    <header className="page-header">
      <div>
        <h1 className="page-header-title">{title}</h1>
        {subtitle && <p className="page-header-subtitle">{subtitle}</p>}
      </div>
      {showWeather && <WeatherCard />}
    </header>
  )
}
