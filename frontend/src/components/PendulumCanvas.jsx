import { useEffect, useRef } from 'react'

const CANVAS_SIZE = 280

export default function PendulumCanvas({ latest }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const stateRef = useRef({ theta: 0, phi_dot: 0, wheelAngle: 0 })

  useEffect(() => {
    if (latest) {
      stateRef.current.theta = latest.theta
      stateRef.current.phi_dot = latest.phi_dot
    }
  }, [latest])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const draw = () => {
      const dpr = window.devicePixelRatio || 1
      const size = CANVAS_SIZE

      if (canvas.width !== size * dpr || canvas.height !== size * dpr) {
        canvas.width = size * dpr
        canvas.height = size * dpr
        ctx.scale(dpr, dpr)
      }

      ctx.clearRect(0, 0, size, size)

      const cx = size / 2
      const cy = size / 2 + 30
      const armLength = 100
      const wheelRadius = 18

      const { theta, phi_dot } = stateRef.current

      // Advance wheel visual angle
      stateRef.current.wheelAngle += phi_dot * 0.016
      const wheelAngle = stateRef.current.wheelAngle

      // Pendulum tip position (theta=0 is upright)
      const tipX = cx + armLength * Math.sin(theta)
      const tipY = cy - armLength * Math.cos(theta)

      // Draw pivot mount
      ctx.fillStyle = '#555'
      ctx.fillRect(cx - 20, cy, 40, 12)

      // Draw arm
      ctx.strokeStyle = '#b0bec5'
      ctx.lineWidth = 4
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(tipX, tipY)
      ctx.stroke()

      // Draw pivot
      ctx.fillStyle = '#78909c'
      ctx.beginPath()
      ctx.arc(cx, cy, 6, 0, Math.PI * 2)
      ctx.fill()

      // Draw reaction wheel
      ctx.save()
      ctx.translate(tipX, tipY)
      ctx.rotate(wheelAngle)

      // Wheel body
      ctx.strokeStyle = '#4fc3f7'
      ctx.lineWidth = 3
      ctx.beginPath()
      ctx.arc(0, 0, wheelRadius, 0, Math.PI * 2)
      ctx.stroke()

      // Wheel spokes
      ctx.strokeStyle = '#4fc3f788'
      ctx.lineWidth = 1.5
      for (let i = 0; i < 4; i++) {
        const a = (Math.PI / 2) * i
        ctx.beginPath()
        ctx.moveTo(0, 0)
        ctx.lineTo(wheelRadius * Math.cos(a), wheelRadius * Math.sin(a))
        ctx.stroke()
      }

      // Hub
      ctx.fillStyle = '#4fc3f7'
      ctx.beginPath()
      ctx.arc(0, 0, 4, 0, Math.PI * 2)
      ctx.fill()

      ctx.restore()

      // Draw angle arc
      if (Math.abs(theta) > 0.01) {
        ctx.strokeStyle = '#ffb74d88'
        ctx.lineWidth = 1.5
        ctx.beginPath()
        const startAngle = -Math.PI / 2
        const endAngle = -Math.PI / 2 + theta
        ctx.arc(cx, cy, 30, startAngle, endAngle, theta < 0)
        ctx.stroke()
      }

      // Upright reference line (dashed)
      ctx.strokeStyle = '#ffffff22'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(cx, cy - armLength - 20)
      ctx.stroke()
      ctx.setLineDash([])

      // Angle text
      ctx.fillStyle = '#aaa'
      ctx.font = '11px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`θ = ${(theta * 180 / Math.PI).toFixed(1)}°`, 8, 16)
      ctx.fillText(`φ̇ = ${phi_dot.toFixed(1)} rad/s`, 8, 30)

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [])

  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3>Pendulum</h3>
      </div>
      <canvas
        ref={canvasRef}
        style={{ width: CANVAS_SIZE, height: CANVAS_SIZE, display: 'block', margin: '0 auto' }}
      />
    </div>
  )
}