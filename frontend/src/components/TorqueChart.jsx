import { useEffect, useRef } from 'react'

const SERIES = [
  { key: 'torque', label: 'Torque (N·m)', color: '#e57373' },
  { key: 'phi_dot', label: 'φ̇ (rad/s)', color: '#ce93d8' },
  { key: 'angular_momentum', label: 'L (kg·m²/s)', color: '#4db6ac' },
]

const CHART_HEIGHT = 150
const PADDING = { top: 10, right: 10, bottom: 20, left: 55 }

export default function TorqueChart({ getBuffer }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const draw = () => {
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.getBoundingClientRect()
      const w = rect.width
      const h = CHART_HEIGHT

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
        ctx.scale(dpr, dpr)
      }

      ctx.clearRect(0, 0, w, h)

      const buffer = getBuffer()
      const plotW = w - PADDING.left - PADDING.right
      const plotH = h - PADDING.top - PADDING.bottom

      ctx.fillStyle = '#1a1a2e'
      ctx.fillRect(PADDING.left, PADDING.top, plotW, plotH)

      ctx.strokeStyle = '#2a2a4a'
      ctx.lineWidth = 0.5
      for (let i = 0; i <= 4; i++) {
        const y = PADDING.top + (plotH / 4) * i
        ctx.beginPath()
        ctx.moveTo(PADDING.left, y)
        ctx.lineTo(PADDING.left + plotW, y)
        ctx.stroke()
      }

      if (buffer.length < 2) {
        animRef.current = requestAnimationFrame(draw)
        return
      }

      const tEnd = buffer[buffer.length - 1].time
      const tStart = buffer[0].time
      const tRange = Math.max(tEnd - tStart, 0.001)

      // Each series gets its own normalized scale (stacked display)
      for (const series of SERIES) {
        let yMin = Infinity
        let yMax = -Infinity
        for (const pt of buffer) {
          const v = pt[series.key] ?? 0
          if (v < yMin) yMin = v
          if (v > yMax) yMax = v
        }
        const yPad = (yMax - yMin) * 0.1 || 0.5
        yMin -= yPad
        yMax += yPad
        const yRange = yMax - yMin || 1

        ctx.strokeStyle = series.color
        ctx.lineWidth = 1.5
        ctx.beginPath()
        for (let i = 0; i < buffer.length; i++) {
          const pt = buffer[i]
          const v = pt[series.key] ?? 0
          const x = PADDING.left + ((pt.time - tStart) / tRange) * plotW
          const y = PADDING.top + plotH - ((v - yMin) / yRange) * plotH
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()
      }

      // Time axis
      ctx.fillStyle = '#888'
      ctx.font = '10px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`${tStart.toFixed(1)}s`, PADDING.left, h - 4)
      ctx.fillText(`${tEnd.toFixed(1)}s`, PADDING.left + plotW, h - 4)

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [getBuffer])

  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3>Torque & Wheel</h3>
        <div className="chart-legend">
          {SERIES.map((s) => (
            <span key={s.key} className="legend-item">
              <span className="legend-color" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>
      <canvas ref={canvasRef} style={{ width: '100%', height: CHART_HEIGHT }} />
    </div>
  )
}