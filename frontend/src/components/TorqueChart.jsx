import { useEffect, useRef } from 'react'

const SERIES = [
  { key: 'voltage', label: 'ولتاژ', color: '#eb5757' },
  { key: 'current', label: 'جریان', color: '#bb86fc' },
  { key: 'phi_dot', label: 'سرعت چرخ', color: '#4dd0b8' },
]

const CHART_HEIGHT = 120
const PADDING = { top: 8, right: 8, bottom: 16, left: 44 }
const MIN_FRAME_MS = 33

export default function TorqueChart({ getBuffer }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let lastDraw = 0

    const draw = (timestamp) => {
      if (timestamp - lastDraw < MIN_FRAME_MS) {
        animRef.current = requestAnimationFrame(draw)
        return
      }
      lastDraw = timestamp
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

      ctx.fillStyle = '#0c0c1a'
      ctx.fillRect(PADDING.left, PADDING.top, plotW, plotH)

      ctx.strokeStyle = '#1e1e3a'
      ctx.lineWidth = 0.5
      for (let i = 0; i <= 3; i++) {
        const y = PADDING.top + (plotH / 3) * i
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
        ctx.lineWidth = 1.2
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

      ctx.fillStyle = '#555577'
      ctx.font = '9px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`${tStart.toFixed(1)}s`, PADDING.left, h - 3)
      ctx.fillText(`${tEnd.toFixed(1)}s`, PADDING.left + plotW, h - 3)

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [getBuffer])

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden shadow-card hover:border-border-light transition-colors duration-200">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border">
        <h3 className="text-[11px] font-bold text-text-dim">الکتریکی و چرخ</h3>
        <div className="flex gap-2">
          {SERIES.map((s) => (
            <span key={s.key} className="flex items-center gap-1 text-[10px] text-text-dim">
              <span className="w-2 h-[2px] rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>
      <canvas ref={canvasRef} style={{ width: '100%', height: CHART_HEIGHT }} />
    </div>
  )
}