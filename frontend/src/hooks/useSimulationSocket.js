import { useCallback, useEffect, useRef, useState } from 'react'
import { decode } from '@msgpack/msgpack'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/telemetry`
const MAX_BUFFER_SIZE = 600

const INT_TO_MODE = ['none', 'pid', 'lqr', 'energy_swing_up', 'sliding_mode', 'manual', 'swing_up', 'swing_up_lqr', 'swing_up_pid']
const FIELD_NAMES = ['time', 'theta', 'theta_dot', 'theta_ddot', 'phi', 'phi_dot', 'phi_ddot', 'voltage', 'current', 'back_emf', 'motor_torque', 'wheel_torque', 'energy', 'kinetic_energy', 'potential_energy', 'angular_momentum', 'mode']

/**
 * Hook managing the WebSocket connection to the simulation backend.
 *
 * Receives binary MessagePack frames with batched, delta-encoded telemetry.
 * Maintains a rolling buffer of telemetry messages and exposes connection
 * state, latest sample, live status, and a send method for commands.
 */
export function useSimulationSocket() {
  const [connected, setConnected] = useState(false)
  const [latest, setLatest] = useState(null)
  const [status, setStatus] = useState(null)
  const [params, setParams] = useState(null)
  const [tuningProgress, setTuningProgress] = useState(null)
  const [tuningResponse, setTuningResponse] = useState(null)
  const bufferRef = useRef([])
  const lastFullRef = useRef(null)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const mountedRef = useRef(true)
  const metricsRef = useRef({ bytes: 0, messages: 0, errors: [] })

  const applyDelta = useCallback((delta) => {
    const base = lastFullRef.current
    if (!base) return null
    for (const [idx, val] of delta) {
      base[idx] = val
    }
    return base
  }, [])

  const sampleToObject = useCallback((arr, target) => {
    const obj = target || {}
    for (let i = 0; i < 16; i++) {
      obj[FIELD_NAMES[i]] = arr[i]
    }
    obj.mode = INT_TO_MODE[arr[16]] || 'none'
    return obj
  }, [])

  const latestObjRef = useRef({})

  const handleMessage = useCallback((msg) => {
    if (msg.t === 0) {
      let lastValid = null
      if (msg.full) {
        for (const sample of msg.data) {
          lastFullRef.current = sample
          const obj = sampleToObject(sample)
          if (!Number.isFinite(obj.theta) || !Number.isFinite(obj.theta_dot)) continue
          bufferRef.current.push(obj)
          lastValid = obj
        }
      } else {
        for (const delta of msg.data) {
          const sample = applyDelta(delta)
          if (!sample) continue
          const obj = sampleToObject(sample)
          if (!Number.isFinite(obj.theta) || !Number.isFinite(obj.theta_dot)) continue
          bufferRef.current.push(obj)
          lastValid = obj
        }
      }
      if (lastValid) {
        const t = latestObjRef.current
        for (const k in lastValid) t[k] = lastValid[k]
        setLatest({ ...t })
      }
      const excess = bufferRef.current.length - MAX_BUFFER_SIZE
      if (excess > 0) {
        bufferRef.current.splice(0, excess)
      }
    } else if (msg.t === 1) {
      setStatus({
        status: msg.status,
        time: msg.time,
        control_mode: msg.control_mode,
        client_count: msg.client_count,
        warnings: msg.warnings || [],
        speed_multiplier: msg.speed_multiplier ?? 1.0,
        active_disturbances: msg.active_disturbances || [],
      })
    } else if (msg.t === 3) {
      const { t, ...rest } = msg
      setParams(rest)
    } else if (msg.t === 4) {
      setTuningProgress({
        iteration: msg.iteration,
        status: msg.status,
        best: msg.best,
        current: msg.current,
        target: msg.target,
      })
    } else if (msg.t === 5) {
      setTuningResponse({
        time: msg.time,
        theta: msg.theta,
      })
    }
  }, [applyDelta, sampleToObject])

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      setConnected(true)
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      const data = event.data
      const byteLen = data instanceof ArrayBuffer ? data.byteLength : (data.size || 0)
      metricsRef.current.bytes += byteLen
      metricsRef.current.messages += 1
      try {
        const msg = decode(new Uint8Array(data))
        handleMessage(msg)
      } catch (err) {
        metricsRef.current.errors.push({ time: Date.now(), message: `Decode error: ${err.message}` })
        if (metricsRef.current.errors.length > 50) {
          metricsRef.current.errors = metricsRef.current.errors.slice(-50)
        }
      }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setConnected(false)
      wsRef.current = null
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => {
      metricsRef.current.errors.push({ time: Date.now(), message: 'WebSocket error' })
      if (metricsRef.current.errors.length > 50) {
        metricsRef.current.errors = metricsRef.current.errors.slice(-50)
      }
      ws.close()
    }
  }, [handleMessage])

  const send = useCallback((command) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(command))
    }
  }, [])

  const getBuffer = useCallback(() => bufferRef.current, [])

  const clearBuffer = useCallback(() => {
    bufferRef.current = []
    lastFullRef.current = null
    latestObjRef.current = {}
    setLatest(null)
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [connect])

  const getMetricsRef = useCallback(() => metricsRef, [])

  return { connected, latest, status, params, tuningProgress, tuningResponse, send, getBuffer, clearBuffer, getMetricsRef }
}