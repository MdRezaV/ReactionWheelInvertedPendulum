import { useCallback, useEffect, useRef, useState } from 'react'

const UPDATE_INTERVAL_MS = 1000
const MAX_ERRORS = 100

/**
 * Tracks rendering FPS via requestAnimationFrame and computes network
 * throughput metrics (bytes/sec, messages/sec) from socket accumulator refs.
 *
 * Parameters
 * ----------
 * socketMetricsRef : React.MutableRefObject
 *   Ref to an object with { bytes, messages, errors } accumulators
 *   updated by useSimulationSocket.
 *
 * Returns
 * -------
 * object with fps, bytesPerSec, msgsPerSec, errors, clearErrors
 */
export function usePerformanceMetrics(socketMetricsRef) {
  const [fps, setFps] = useState(0)
  const [bytesPerSec, setBytesPerSec] = useState(0)
  const [msgsPerSec, setMsgsPerSec] = useState(0)
  const [errors, setErrors] = useState([])

  const frameCountRef = useRef(0)
  const lastFpsTimeRef = useRef(performance.now())
  const lastBytesRef = useRef(0)
  const lastMsgsRef = useRef(0)
  const lastNetTimeRef = useRef(performance.now())
  const rafRef = useRef(null)
  const intervalRef = useRef(null)
  const errorsRef = useRef([])

  const addError = useCallback((message) => {
    const entry = { time: Date.now(), message }
    errorsRef.current = [...errorsRef.current.slice(-(MAX_ERRORS - 1)), entry]
    setErrors(errorsRef.current)
  }, [])

  const clearErrors = useCallback(() => {
    errorsRef.current = []
    setErrors([])
  }, [])

  useEffect(() => {
    const countFrame = () => {
      frameCountRef.current += 1
      rafRef.current = requestAnimationFrame(countFrame)
    }
    rafRef.current = requestAnimationFrame(countFrame)

    intervalRef.current = setInterval(() => {
      const now = performance.now()

      // FPS
      const fpsDelta = (now - lastFpsTimeRef.current) / 1000
      if (fpsDelta > 0) {
        setFps(Math.round(frameCountRef.current / fpsDelta))
      }
      frameCountRef.current = 0
      lastFpsTimeRef.current = now

      // Network throughput
      const metrics = socketMetricsRef.current
      const netDelta = (now - lastNetTimeRef.current) / 1000
      if (netDelta > 0 && metrics) {
        const bytesDelta = metrics.bytes - lastBytesRef.current
        const msgsDelta = metrics.messages - lastMsgsRef.current
        setBytesPerSec(Math.round(bytesDelta / netDelta))
        setMsgsPerSec(Math.round(msgsDelta / netDelta))
        lastBytesRef.current = metrics.bytes
        lastMsgsRef.current = metrics.messages
      }
      lastNetTimeRef.current = now
    }, UPDATE_INTERVAL_MS)

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [socketMetricsRef])

  return { fps, bytesPerSec, msgsPerSec, errors, addError, clearErrors }
}