import { useEffect, useRef } from 'react'

const SERIES_CONFIG = [
  { key: 'theta', label: 'θ (درجه)', color: '#4fc3f7' },
  { key: 'theta_dot', label: 'θ̇ (درجه/ثانیه)', color: '#81c784' },
  { key: 'phi_dot', label: 'φ̇ (درجه/ثانیه)', color: '#ffb74d' },
  { key: 'torque', label: 'گشتاور (نیوتن·متر)', color: '#e57373' },
]

const CHART_HEIGHT = 160
const PADDING = { top: 10, right: 10, bottom: 20, left: 50 }
const MIN_FRAME_MS = 33

export default function SimulationChart({ getBuffer }) {
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

      ctx.fillStyle = '#12121f'
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

      for (const series of SERIES_CONFIG) {
        let yMin = Infinity
        let yMax = -Infinity
        for (const pt of buffer) {
          const v = pt[series.key]
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
          const x = PADDING.left + ((pt.time - tStart) / tRange) * plotW
          const y = PADDING.top + plotH - ((pt[series.key] - yMin) / yRange) * plotH
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()
      }

      ctx.fillStyle = '#666'
      ctx.font = '9px Vazirmatn, monospace'
      ctx.textAlign = 'right'
      ctx.fillText('auto', PADDING.left - 4, PADDING.top + 8)
      ctx.fillText('scale', PADDING.left - 4, PADDING.top + plotH - 2)

      ctx.textAlign = 'center'
      ctx.fillText(`${tStart.toFixed(1)}s`, PADDING.left, h - 4)
      ctx.fillText(`${tEnd.toFixed(1)}s`, PADDING.left + plotW, h - 4)

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [getBuffer])

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden shadow-card">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <h3 className="text-[13px] font-bold text-text-h">سری زمانی</h3>
        <div className="flex gap-3 flex-wrap">
          {SERIES_CONFIG.map((s) => (
            <span key={s.key} className="flex items-center gap-1 text-[11px] text-text-dim">
              <span className="w-2.5 h-[3px] rounded-full" style={{ background: s.color }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>
      <canvas ref={canvasRef} style={{ width: '100%', height: CHART_HEIGHT }} />
    </div>
  )
}