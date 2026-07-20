import { useEffect, useRef } from 'react'

const CANVAS_SIZE = 280
const MIN_ARM_PX = 8
const MIN_WHEEL_PX = 4
const USABLE_RADIUS_PX = 95
const MIN_SCALE = 30
const MAX_SCALE = 400

export default function PendulumCanvas({ latest, params }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const stateRef = useRef({ theta: 0, phi_dot: 0, voltage: 0, current: 0, wheelAngle: 0, lastTime: 0 })
  const dimsRef = useRef({ armLength: 80, wheelRadius: 13 })

  useEffect(() => {
    if (latest) {
      stateRef.current.theta = latest.theta
      stateRef.current.phi_dot = latest.phi_dot
      stateRef.current.voltage = latest.voltage ?? 0
      stateRef.current.current = latest.current ?? 0
    }
  }, [latest])

  useEffect(() => {
    if (params?.simulation) {
      const len = params.simulation.pendulum_length ?? 0.3
      const rad = params.simulation.wheel_radius ?? 0.05
      const scale = Math.min(Math.max(USABLE_RADIUS_PX / (len + rad), MIN_SCALE), MAX_SCALE)
      dimsRef.current.armLength = Math.max(len * scale, MIN_ARM_PX)
      dimsRef.current.wheelRadius = Math.max(rad * scale, MIN_WHEEL_PX)
    }
  }, [params])

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
      const armLength = dimsRef.current.armLength
      const wheelRadius = dimsRef.current.wheelRadius

      const { theta, phi_dot, voltage, current } = stateRef.current

      const dt = stateRef.current.lastTime > 0
        ? Math.min((timestamp - stateRef.current.lastTime) / 1000, 0.05)
        : 0.016
      stateRef.current.lastTime = timestamp
      stateRef.current.wheelAngle += phi_dot * dt
      const wheelAngle = stateRef.current.wheelAngle

      const tipX = cx + armLength * Math.sin(theta)
      const tipY = cy - armLength * Math.cos(theta)

      ctx.fillStyle = '#3a3a5a'
      ctx.fillRect(cx - 20, cy, 40, 12)

      ctx.strokeStyle = '#b0bec5'
      ctx.lineWidth = 4
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(tipX, tipY)
      ctx.stroke()

      ctx.fillStyle = '#78909c'
      ctx.beginPath()
      ctx.arc(cx, cy, 6, 0, Math.PI * 2)
      ctx.fill()

      ctx.save()
      ctx.translate(tipX, tipY)
      ctx.rotate(wheelAngle)

      ctx.strokeStyle = '#4fc3f7'
      ctx.lineWidth = 3
      ctx.beginPath()
      ctx.arc(0, 0, wheelRadius, 0, Math.PI * 2)
      ctx.stroke()

      ctx.strokeStyle = '#4fc3f788'
      ctx.lineWidth = 1.5
      for (let i = 0; i < 4; i++) {
        const a = (Math.PI / 2) * i
        ctx.beginPath()
        ctx.moveTo(0, 0)
        ctx.lineTo(wheelRadius * Math.cos(a), wheelRadius * Math.sin(a))
        ctx.stroke()
      }

      ctx.fillStyle = '#4fc3f7'
      ctx.beginPath()
      ctx.arc(0, 0, 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()

      if (Math.abs(theta) > 0.01) {
        ctx.strokeStyle = '#ffb74d88'
        ctx.lineWidth = 1.5
        ctx.beginPath()
        const startAngle = -Math.PI / 2
        const endAngle = -Math.PI / 2 + theta
        ctx.arc(cx, cy, 30, startAngle, endAngle, theta < 0)
        ctx.stroke()
      }

      ctx.strokeStyle = '#ffffff22'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 4])
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(cx, cy - armLength - 20)
      ctx.stroke()
      ctx.setLineDash([])

      if (Math.abs(voltage) > 0.01) {
        const arrowDir = voltage > 0 ? 1 : -1
        const arrowLen = Math.min(Math.abs(voltage) * 2, 30)
        ctx.strokeStyle = '#e57373'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(tipX, tipY - wheelRadius - 5)
        ctx.lineTo(tipX + arrowDir * arrowLen, tipY - wheelRadius - 5)
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(tipX + arrowDir * arrowLen, tipY - wheelRadius - 5)
        ctx.lineTo(tipX + arrowDir * (arrowLen - 5), tipY - wheelRadius - 9)
        ctx.lineTo(tipX + arrowDir * (arrowLen - 5), tipY - wheelRadius - 1)
        ctx.closePath()
        ctx.fillStyle = '#e57373'
        ctx.fill()
      }

      ctx.fillStyle = '#aaa'
      ctx.font = '11px Vazirmatn, monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`θ = ${(theta * 180 / Math.PI).toFixed(1)}°`, 8, 16)
      ctx.fillText(`φ̇ = ${(phi_dot * 180 / Math.PI).toFixed(1)} °/s`, 8, 30)
      ctx.fillText(`ولتاژ = ${voltage.toFixed(2)} ولت`, 8, 44)
      ctx.fillText(`جریان = ${current.toFixed(3)} آمپر`, 8, 58)

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [])

  return (
    <div className="flex-1 min-w-[240px] rounded-xl border border-border bg-card overflow-hidden shadow-card">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <h3 className="text-[13px] font-bold text-text-h">پاندول</h3>
      </div>
      <canvas
        ref={canvasRef}
        style={{ width: CANVAS_SIZE, height: CANVAS_SIZE, display: 'block', margin: '0 auto' }}
      />
    </div>
  )
}