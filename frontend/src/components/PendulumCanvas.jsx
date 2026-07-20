import { useEffect, useRef } from 'react'

const CANVAS_SIZE = 280

export default function PendulumCanvas({ latest }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const stateRef = useRef({ theta: 0, phi_dot: 0, voltage: 0, current: 0, wheelAngle: 0, lastTime: 0 })

  useEffect(() => {
    if (latest) {
      stateRef.current.theta = latest.theta
      stateRef.current.phi_dot = latest.phi_dot
      stateRef.current.voltage = latest.voltage ?? 0
      stateRef.current.current = latest.current ?? 0
    }
  }, [latest])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const draw = (timestamp) => {
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

      const { theta, phi_dot, voltage, current } = stateRef.current

      // Advance wheel visual angle using real frame delta
      const dt = stateRef.current.lastTime > 0
        ? Math.min((timestamp - stateRef.current.lastTime) / 1000, 0.05)
        : 0.016
      stateRef.current.lastTime = timestamp
      stateRef.current.wheelAngle += phi_dot * dt
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

      // Voltage indicator arrow at wheel
      if (Math.abs(voltage) > 0.01) {
        const arrowDir = voltage > 0 ? 1 : -1
        const arrowLen = Math.min(Math.abs(voltage) * 2, 30)
        ctx.strokeStyle = '#e57373'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(tipX, tipY - wheelRadius - 5)
        ctx.lineTo(tipX + arrowDir * arrowLen, tipY - wheelRadius - 5)
        ctx.stroke()
        // Arrowhead
        ctx.beginPath()
        ctx.moveTo(tipX + arrowDir * arrowLen, tipY - wheelRadius - 5)
        ctx.lineTo(tipX + arrowDir * (arrowLen - 5), tipY - wheelRadius - 9)
        ctx.lineTo(tipX + arrowDir * (arrowLen - 5), tipY - wheelRadius - 1)
        ctx.closePath()
        ctx.fillStyle = '#e57373'
        ctx.fill()
      }

      // Angle text
      ctx.fillStyle = '#aaa'
      ctx.font = '11px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`θ = ${(theta * 180 / Math.PI).toFixed(1)}°`, 8, 16)
      ctx.fillText(`φ̇ = ${phi_dot.toFixed(1)} rad/s`, 8, 30)
      ctx.fillText(`V = ${voltage.toFixed(2)} V`, 8, 44)
      ctx.fillText(`i = ${current.toFixed(3)} A`, 8, 58)

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