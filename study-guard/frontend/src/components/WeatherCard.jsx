import { Sun } from 'lucide-react'
import { weather } from '../data/mockData.js'
import './WeatherCard.css'

export default function WeatherCard() {
  return (
    <div className="weather-card">
      <span className="weather-icon">
        <Sun size={22} strokeWidth={2.2} />
      </span>
      <div>
        <p className="weather-temp">{weather.tempC}°C</p>
        <p className="weather-condition">{weather.condition}</p>
      </div>
    </div>
  )
}
