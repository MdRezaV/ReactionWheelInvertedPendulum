import { useEffect, useRef } from 'react'

const SIZE = 220
const PADDING = 30

export default function PhasePlot({ getBuffer }) {
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
      const h = SIZE

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
        ctx.scale(dpr, dpr)
      }

      ctx.clearRect(0, 0, w, h)

      const plotW = w - PADDING * 2
      const plotH = h - PADDING * 2

      // Background
      ctx.fillStyle = '#1a1a2e'
      ctx.fillRect(PADDING, PADDING, plotW, plotH)

      // Axes
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

      // Auto-scale
      let thMin = Infinity, thMax = -Infinity
      let thdMin = Infinity, thdMax = -Infinity
      for (const pt of buffer) {
        if (pt.theta < thMin) thMin = pt.theta
        if (pt.theta > thMax) thMax = pt.theta
        if (pt.theta_dot < thdMin) thdMin = pt.theta_dot
        if (pt.theta_dot > thdMax) thdMax = pt.theta_dot
      }
      const thRange = Math.max(thMax - thMin, 0.1)
      const thdRange = Math.max(thdMax - thdMin, 0.1)
      const thMid = (thMin + thMax) / 2
      const thdMid = (thdMin + thdMax) / 2
      const thHalf = thRange / 2 * 1.2
      const thdHalf = thdRange / 2 * 1.2

      // Draw trajectory with fading
      const len = buffer.length
      for (let i = 1; i < len; i++) {
        const alpha = 0.2 + 0.8 * (i / len)
        const x1 = PADDING + ((buffer[i - 1].theta - (thMid - thHalf)) / (2 * thHalf)) * plotW
        const y1 = PADDING + plotH - ((buffer[i - 1].theta_dot - (thdMid - thdHalf)) / (2 * thdHalf)) * plotH
        const x2 = PADDING + ((buffer[i].theta - (thMid - thHalf)) / (2 * thHalf)) * plotW
        const y2 = PADDING + plotH - ((buffer[i].theta_dot - (thdMid - thdHalf)) / (2 * thdHalf)) * plotH

        ctx.strokeStyle = `rgba(79, 195, 247, ${alpha})`
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.stroke()
      }

      // Current point
      const last = buffer[len - 1]
      const cx = PADDING + ((last.theta - (thMid - thHalf)) / (2 * thHalf)) * plotW
      const cy = PADDING + plotH - ((last.theta_dot - (thdMid - thdHalf)) / (2 * thdHalf)) * plotH
      ctx.fillStyle = '#ff5252'
      ctx.beginPath()
      ctx.arc(cx, cy, 4, 0, Math.PI * 2)
      ctx.fill()

      // Labels
      ctx.fillStyle = '#888'
      ctx.font = '10px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('θ', PADDING + plotW / 2, h - 6)
      ctx.save()
      ctx.translate(10, PADDING + plotH / 2)
      ctx.rotate(-Math.PI / 2)
      ctx.fillText('θ̇', 0, 0)
      ctx.restore()

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
        <h3>Phase Portrait (θ vs θ̇)</h3>
      </div>
      <canvas ref={canvasRef} style={{ width: '100%', height: SIZE }} />
    </div>
  )
}