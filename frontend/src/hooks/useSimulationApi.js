import { useCallback } from 'react'

const BASE = '/api/simulation'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API ${res.status}: ${text}`)
  }
  return res.json()
}

/**
 * Hook providing REST API methods for simulation control.
 */
export function useSimulationApi() {
  const getStatus = useCallback(() => request('/status'), [])
  const getParams = useCallback(() => request('/params'), [])

  const updateParams = useCallback((body) => {
    return request('/params', { method: 'POST', body: JSON.stringify(body) })
  }, [])

  const start = useCallback(() => request('/start', { method: 'POST' }), [])
  const stop = useCallback(() => request('/stop', { method: 'POST' }), [])
  const pause = useCallback(() => request('/pause', { method: 'POST' }), [])
  const resume = useCallback(() => request('/resume', { method: 'POST' }), [])
  const reset = useCallback(() => request('/reset', { method: 'POST' }), [])

  const step = useCallback((steps = 1) => {
    return request('/step', { method: 'POST', body: JSON.stringify({ steps }) })
  }, [])

  const setControlMode = useCallback((mode) => {
    return request('/control-mode', { method: 'POST', body: JSON.stringify({ mode }) })
  }, [])

  const setManualTorque = useCallback((torque) => {
    return request('/manual-torque', { method: 'POST', body: JSON.stringify({ torque }) })
  }, [])

  const applyDisturbance = useCallback((torque, durationSteps = 10) => {
    return request('/disturbance', {
      method: 'POST',
      body: JSON.stringify({ torque, duration_steps: durationSteps }),
    })
  }, [])

  const setSpeed = useCallback((multiplier) => {
    return request('/speed', { method: 'POST', body: JSON.stringify({ multiplier }) })
  }, [])

  return {
    getStatus,
    getParams,
    updateParams,
    start,
    stop,
    pause,
    resume,
    reset,
    step,
    setControlMode,
    setManualTorque,
    applyDisturbance,
    setSpeed,
  }
}