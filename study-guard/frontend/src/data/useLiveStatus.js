import { useEffect, useRef, useState } from 'react'
import api from './api.js'

// Polling interval for /api/status. The backend's own status_writer
// loop (main.py) refreshes live_state.json roughly once a second, so
// polling faster than that just re-reads the same snapshot -- this
// stays a little slower to keep the UI responsive without hammering
// the local API (see STEP 18 -- no unnecessary polling / no full page
// reloads).
const POLL_INTERVAL_MS = 1500

/**
 * Polls /api/status on an interval and returns the latest snapshot.
 * Never throws into the caller -- a failed poll (e.g. backend still
 * starting up) just keeps the previous value and tries again next
 * tick, so the UI degrades to "last known state" instead of an error
 * screen during normal startup/shutdown.
 */
export function useLiveStatus() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    let timer = null

    const poll = async () => {
      try {
        const data = await api.getStatus()
        if (mountedRef.current) {
          setStatus(data)
          setError(null)
        }
      } catch (e) {
        if (mountedRef.current) setError(e)
      } finally {
        if (mountedRef.current) {
          timer = window.setTimeout(poll, POLL_INTERVAL_MS)
        }
      }
    }

    poll()

    return () => {
      mountedRef.current = false
      if (timer) window.clearTimeout(timer)
    }
  }, [])

  return { status, error }
}

export function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds || 0))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
}

export default useLiveStatus
