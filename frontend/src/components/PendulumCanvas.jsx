import { useEffect, useRef } from 'react'

const MIN_ARM_PX = 12
const MIN_WHEEL_PX = 6
const MIN_SCALE = 30
const MAX_SCALE = 400

export default function PendulumCanvas({ latest, params }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const stateRef = useRef({ theta: 0, phi_dot: 0, theta_dot: 0, voltage: 0, current: 0, wheelAngle: 0, lastTime: 0, trail: [] })
  const dimsRef = useRef({ armLength: 70, wheelRadius: 12 })

  useEffect(() => {
    if (latest) {
      stateRef.current.theta = latest.theta
      stateRef.current.theta_dot = latest.theta_dot ?? 0
      stateRef.current.phi_dot = latest.phi_dot
      stateRef.current.voltage = latest.voltage ?? 0
      stateRef.current.current = latest.current ?? 0
    }
  }, [latest])

  useEffect(() => {
    if (params?.simulation) {
      const len = params.simulation.pendulum_length ?? 0.3
      const rad = params.simulation.wheel_radius ?? 0.05
      const usable = 130
      const scale = Math.min(Math.max(usable / (len + rad), MIN_SCALE), MAX_SCALE)
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
      const rect = canvas.getBoundingClientRect()
      const w = rect.width
      const h = rect.height

      if (w === 0 || h === 0) {
        animRef.current = requestAnimationFrame(draw)
        return
      }

      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr
        canvas.height = h * dpr
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      }

      ctx.clearRect(0, 0, w, h)

      const size = Math.min(w, h)
      const cx = w / 2
      const cy = h / 2 + size * 0.06
      const scaleFactor = size / 300
      const armLength = dimsRef.current.armLength * scaleFactor
      const wheelRadius = dimsRef.current.wheelRadius * scaleFactor

      const { theta, theta_dot, phi_dot, voltage, current } = stateRef.current

      const dt = stateRef.current.lastTime > 0
        ? Math.min((timestamp - stateRef.current.lastTime) / 1000, 0.05)
        : 0.016
      stateRef.current.lastTime = timestamp
      stateRef.current.wheelAngle += phi_dot * dt
      const wheelAngle = stateRef.current.wheelAngle

      const tipX = cx + armLength * Math.sin(theta)
      const tipY = cy - armLength * Math.cos(theta)

      const trail = stateRef.current.trail
      trail.push({ x: tipX, y: tipY })
      if (trail.length > 28) trail.shift()

      // Radial grid
      ctx.strokeStyle = '#ffffff08'
      ctx.lineWidth = 0.5
      for (let r = 1; r <= 3; r++) {
        ctx.beginPath()
        ctx.arc(cx, cy, (armLength / 3) * r, 0, Math.PI * 2)
        ctx.stroke()
      }
      for (let a = 0; a < 8; a++) {
        const angle = (Math.PI / 4) * a
        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(cx + armLength * Math.cos(angle), cy + armLength * Math.sin(angle))
        ctx.stroke()
      }

      // Ground shadow
      const shadowScale = Math.abs(Math.sin(theta))
      ctx.fillStyle = `rgba(0, 0, 0, ${0.25 - shadowScale * 0.15})`
      ctx.beginPath()
      ctx.ellipse(cx, cy + 14, 18 + shadowScale * 12, 4, 0, 0, Math.PI * 2)
      ctx.fill()

      // Trail
      for (let i = 0; i < trail.length; i++) {
        const alpha = (i / trail.length) * 0.35
        const radius = 1.5 + (i / trail.length) * 2
        ctx.fillStyle = `rgba(86, 204, 242, ${alpha})`
        ctx.beginPath()
        ctx.arc(trail[i].x, trail[i].y, radius, 0, Math.PI * 2)
        ctx.fill()
      }

      // Base
      ctx.fillStyle = '#2a2a4a'
      ctx.fillRect(cx - 16, cy, 32, 10)

      // Arm with velocity-based color
      const speedNorm = Math.min(Math.abs(theta_dot) / 8, 1)
      const armR = Math.round(86 + speedNorm * (235 - 86))
      const armG = Math.round(153 + speedNorm * (87 - 153))
      const armB = Math.round(170 + speedNorm * (87 - 170))
      ctx.strokeStyle = `rgb(${armR}, ${armG}, ${armB})`
      ctx.lineWidth = 3.5
      ctx.lineCap = 'round'
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(tipX, tipY)
      ctx.stroke()

      ctx.fillStyle = '#667788'
      ctx.beginPath()
      ctx.arc(cx, cy, 5, 0, Math.PI * 2)
      ctx.fill()

      ctx.save()
      ctx.translate(tipX, tipY)
      ctx.rotate(wheelAngle)

      ctx.strokeStyle = '#56ccf2'
      ctx.lineWidth = 2.5
      ctx.beginPath()
      ctx.arc(0, 0, wheelRadius, 0, Math.PI * 2)
      ctx.stroke()

      ctx.strokeStyle = '#56ccf266'
      ctx.lineWidth = 1
      for (let i = 0; i < 4; i++) {
        const a = (Math.PI / 2) * i
        ctx.beginPath()
        ctx.moveTo(0, 0)
        ctx.lineTo(wheelRadius * Math.cos(a), wheelRadius * Math.sin(a))
        ctx.stroke()
      }

      ctx.fillStyle = '#56ccf2'
      ctx.beginPath()
      ctx.arc(0, 0, 3, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()

      // Speed arc around wheel
      const maxSpeed = 30
      const wheelSpeedNorm = Math.min(Math.abs(phi_dot) / maxSpeed, 1)
      if (wheelSpeedNorm > 0.01) {
        const arcRadius = wheelRadius + 5
        const sweepAngle = wheelSpeedNorm * Math.PI * 1.8
        const startA = -Math.PI / 2 - sweepAngle / 2
        const endA = -Math.PI / 2 + sweepAngle / 2
        const gR = Math.round(111 + speedNorm * (235 - 111))
        const gG = Math.round(207 + speedNorm * (87 - 207))
        const gB = Math.round(151 + speedNorm * (87 - 151))
        ctx.strokeStyle = `rgba(${gR}, ${gG}, ${gB}, 0.8)`
        ctx.lineWidth = 3
        ctx.lineCap = 'round'
        ctx.beginPath()
        ctx.arc(tipX, tipY, arcRadius, startA, endA)
        ctx.stroke()
      }

      if (Math.abs(theta) > 0.01) {
        ctx.strokeStyle = '#f2994a66'
        ctx.lineWidth = 1.5
        ctx.beginPath()
        const startAngle = -Math.PI / 2
        const endAngle = -Math.PI / 2 + theta
        ctx.arc(cx, cy, 24, startAngle, endAngle, theta < 0)
        ctx.stroke()
      }

      ctx.strokeStyle = '#ffffff18'
      ctx.lineWidth = 1
      ctx.setLineDash([3, 3])
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(cx, cy - armLength - 15)
      ctx.stroke()
      ctx.setLineDash([])

      if (Math.abs(voltage) > 0.01) {
        const arrowDir = voltage > 0 ? 1 : -1
        const arrowLen = Math.min(Math.abs(voltage) * 2, 25)
        ctx.strokeStyle = '#eb5757'
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(tipX, tipY - wheelRadius - 4)
        ctx.lineTo(tipX + arrowDir * arrowLen, tipY - wheelRadius - 4)
        ctx.stroke()
        ctx.beginPath()
        ctx.moveTo(tipX + arrowDir * arrowLen, tipY - wheelRadius - 4)
        ctx.lineTo(tipX + arrowDir * (arrowLen - 4), tipY - wheelRadius - 7)
        ctx.lineTo(tipX + arrowDir * (arrowLen - 4), tipY - wheelRadius - 1)
        ctx.closePath()
        ctx.fillStyle = '#eb5757'
        ctx.fill()
      }

      ctx.fillStyle = '#8888aa'
      ctx.font = '10px Vazirmatn, sans-serif'
      ctx.textAlign = 'right'
      ctx.fillText(`زاویه: ${(theta * 180 / Math.PI).toFixed(1)}°`, w - 6, 14)
      ctx.fillText(`سرعت چرخ: ${(phi_dot * 180 / Math.PI).toFixed(0)}°/s`, w - 6, 27)
      ctx.fillText(`ولتاژ: ${voltage.toFixed(1)} V`, w - 6, 40)

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [])

  return (
    <div className="flex-1 flex flex-col rounded-lg border border-border bg-card overflow-hidden shadow-card hover:border-border-light transition-colors duration-200 min-h-0">
      <div className="px-3 py-1.5 border-b border-border flex-shrink-0">
        <h3 className="text-[11px] font-bold text-text-dim">پاندول</h3>
      </div>
      <div className="flex-1 min-h-0">
        <canvas ref={canvasRef} className="w-full h-full block" />
      </div>
    </div>
  )
}