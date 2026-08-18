import { useCallback, useEffect, useRef, useState } from 'react'
import api from './api.js'

// Polling interval for /api/session/status. Faster than useLiveStatus's
// general status poll since this drives the countdown timer and
// calibration progress bar, both of which should feel responsive.
const POLL_INTERVAL_MS = 1000

/**
 * Polls /api/session/status and exposes the current session-control
 * phase (IDLE / CALIBRATING / ACTIVE / PAUSED / COMPLETE) plus action
 * functions that call the corresponding /api/session/* route. Actions
 * optimistically leave polling to reflect the outcome rather than
 * hand-rolling local state that could drift from the backend's own
 * source of truth (session_bridge, owned by main.SessionSupervisor).
 */
export function useSessionControl() {
  const [state, setState] = useState(null)
  const [error, setError] = useState(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    let timer = null

    const poll = async () => {
      try {
        const data = await api.getSessionStatus()
        if (mountedRef.current) {
          setState(data)
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

  const start = useCallback(async (durationMinutes, opts) => {
    await api.startSession(durationMinutes, opts)
  }, [])
  const pause = useCallback(async () => {
    await api.pauseSession()
  }, [])
  const resume = useCallback(async () => {
    await api.resumeSession()
  }, [])
  const end = useCallback(async () => {
    await api.endSession()
  }, [])
  const acknowledge = useCallback(async () => {
    await api.acknowledgeSession()
  }, [])

  return { state, error, start, pause, resume, end, acknowledge }
}

export function formatCountdown(totalSeconds) {
  const seconds = Math.max(0, Math.round(totalSeconds || 0))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
}

export default useSessionControl
