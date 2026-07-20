import { useEffect, useRef, useState } from 'react'

const SIZE = 220
const PADDING = 30
const MIN_FRAME_MS = 33

const AXIS_OPTIONS = [
  { x: 'theta', y: 'theta_dot', label: 'θ vs θ̇' },
  { x: 'theta', y: 'phi_dot', label: 'θ vs φ̇' },
  { x: 'phi_dot', y: 'theta_dot', label: 'φ̇ vs θ̇' },
  { x: 'theta', y: 'torque', label: 'θ vs τ' },
]

export default function PhasePlot({ getBuffer }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const [axisPair, setAxisPair] = useState(0)
  const axisRef = useRef(0)

  useEffect(() => { axisRef.current = axisPair }, [axisPair])

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
      const h = SIZE

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
        ctx.scale(dpr, dpr)
      }

      ctx.clearRect(0, 0, w, h)

      const plotW = w - PADDING * 2
      const plotH = h - PADDING * 2

      ctx.fillStyle = '#12121f'
      ctx.fillRect(PADDING, PADDING, plotW, plotH)

      ctx.strokeStyle = '#3a3a5a'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(PADDING + plotW / 2, PADDING)
      ctx.lineTo(PADDING + plotW / 2, PADDING + plotH)
      ctx.moveTo(PADDING, PADDING + plotH / 2)
      ctx.lineTo(PADDING + plotW, PADDING + plotH / 2)
      ctx.stroke()

      const buffer = getBuffer()
      if (buffer.length < 2) {
        animRef.current = requestAnimationFrame(draw)
        return
      }

      const axes = AXIS_OPTIONS[axisRef.current]
      const xKey = axes.x
      const yKey = axes.y

      let xMin = Infinity, xMax = -Infinity
      let yMin = Infinity, yMax = -Infinity
      for (const pt of buffer) {
        const xv = pt[xKey] ?? 0
        const yv = pt[yKey] ?? 0
        if (xv < xMin) xMin = xv
        if (xv > xMax) xMax = xv
        if (yv < yMin) yMin = yv
        if (yv > yMax) yMax = yv
      }
      const xRange = Math.max(xMax - xMin, 0.1)
      const yRange = Math.max(yMax - yMin, 0.1)
      const xMid = (xMin + xMax) / 2
      const yMid = (yMin + yMax) / 2
      const xHalf = xRange / 2 * 1.2
      const yHalf = yRange / 2 * 1.2

      const len = buffer.length
      for (let i = 1; i < len; i++) {
        const alpha = 0.2 + 0.8 * (i / len)
        const x1 = PADDING + ((buffer[i - 1][xKey] - (xMid - xHalf)) / (2 * xHalf)) * plotW
        const y1 = PADDING + plotH - ((buffer[i - 1][yKey] - (yMid - yHalf)) / (2 * yHalf)) * plotH
        const x2 = PADDING + ((buffer[i][xKey] - (xMid - xHalf)) / (2 * xHalf)) * plotW
        const y2 = PADDING + plotH - ((buffer[i][yKey] - (yMid - yHalf)) / (2 * yHalf)) * plotH

        ctx.strokeStyle = `rgba(79, 195, 247, ${alpha})`
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()
      }

      const last = buffer[len - 1]
      const cx = PADDING + ((last[xKey] - (xMid - xHalf)) / (2 * xHalf)) * plotW
      const cy = PADDING + plotH - ((last[yKey] - (yMid - yHalf)) / (2 * yHalf)) * plotH
      ctx.fillStyle = '#ff5252'
      ctx.beginPath()
      ctx.arc(cx, cy, 4, 0, Math.PI * 2)
      ctx.fill()

      ctx.fillStyle = '#888'
      ctx.font = '10px Vazirmatn, monospace'
      ctx.textAlign = 'center'
      ctx.fillText(xKey, PADDING + plotW / 2, h - 6)
      ctx.save()
      ctx.translate(10, PADDING + plotH / 2)
      ctx.rotate(-Math.PI / 2)
      ctx.fillText(yKey, 0, 0)
      ctx.restore()

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [getBuffer])

  return (
    <div className="flex-1 min-w-[240px] rounded-xl border border-border bg-card overflow-hidden shadow-card">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <h3 className="text-[13px] font-bold text-text-h">نمودار فاز</h3>
        <select
          value={axisPair}
          onChange={(e) => setAxisPair(Number(e.target.value))}
          className="px-2 py-0.5 text-[11px] rounded border border-border bg-card text-text-h cursor-pointer focus:border-accent focus:outline-none"
          dir="ltr"
        >
          {AXIS_OPTIONS.map((opt, i) => (
            <option key={i} value={i}>{opt.label}</option>
          ))}
        </select>
      </div>
      <canvas ref={canvasRef} style={{ width: '100%', height: SIZE }} />
    </div>
  )
}