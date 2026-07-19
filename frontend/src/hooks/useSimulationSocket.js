import { useCallback, useEffect, useRef, useState } from 'react'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/telemetry`
const MAX_BUFFER_SIZE = 900

/**
 * Hook managing the WebSocket connection to the simulation backend.
 *
 * Maintains a rolling buffer of telemetry messages and exposes
 * connection state and a send method for commands.
 */
export function useSimulationSocket() {
  const [connected, setConnected] = useState(false)
  const [latest, setLatest] = useState(null)
  const bufferRef = useRef([])
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) return
      setConnected(true)
    }

    ws.onmessage = (event) => {
      if (!mountedRef.current) return
      try {
        const data = JSON.parse(event.data)
        if (data.theta !== undefined) {
          bufferRef.current.push(data)
          if (bufferRef.current.length > MAX_BUFFER_SIZE) {
            bufferRef.current = bufferRef.current.slice(-MAX_BUFFER_SIZE)
          }
          setLatest(data)
        }
      } catch {
        // Ignore non-telemetry messages (e.g. status snapshots, errors)
      }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setConnected(false)
      wsRef.current = null
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  const send = useCallback((command) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(command))
    }
  }, [])

  const getBuffer = useCallback(() => bufferRef.current, [])

  const clearBuffer = useCallback(() => {
    bufferRef.current = []
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

  return { connected, latest, send, getBuffer, clearBuffer }
}