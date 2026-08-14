import { useEffect, useRef } from 'react'
import { toPersianDigits } from '../utils/format'

const MIN_ARM_PX = 12
const MIN_WHEEL_PX = 6
const MIN_SCALE = 30
const MAX_SCALE = 400

export default function PendulumCanvas({ latest, params }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const TRAIL_LEN = 28
  const stateRef = useRef({ theta: 0, targetTheta: 0, phi_dot: 0, theta_dot: 0, voltage: 0, current: 0, wheelAngle: 0, lastTime: 0, smoothSpeedNorm: 0, trailX: new Float64Array(TRAIL_LEN), trailY: new Float64Array(TRAIL_LEN), trailHead: 0, trailCount: 0 })
  const dimsRef = useRef({ armLength: 70, wheelRadius: 12, wheelInnerRadius: 6, switchAngle: 0.3 })

  useEffect(() => {
    if (latest) {
      stateRef.current.targetTheta = latest.theta
      stateRef.current.theta_dot = latest.theta_dot ?? 0
      stateRef.current.phi_dot = latest.phi_dot
      stateRef.current.voltage = latest.voltage ?? 0
      stateRef.current.current = latest.current ?? 0
    }
  }, [latest])

  useEffect(() => {
    if (params?.simulation) {
      const len = params.simulation.pendulum_length ?? 0.3
      const rad = params.simulation.wheel_outer_radius ?? 0.05
      const innerRad = params.simulation.wheel_inner_radius ?? 0.04
      const usable = 130
      const scale = Math.min(Math.max(usable / (len + rad), MIN_SCALE), MAX_SCALE)
      dimsRef.current.armLength = Math.max(len * scale, MIN_ARM_PX)
      dimsRef.current.wheelRadius = Math.max(rad * scale, MIN_WHEEL_PX)
      dimsRef.current.wheelInnerRadius = Math.max(innerRad * scale, MIN_WHEEL_PX)
    }
    dimsRef.current.switchAngle = params?.control?.upright_angle_threshold ?? 0.3
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

      const pw = Math.round(w * dpr)
      const ph = Math.round(h * dpr)
      if (canvas.width !== pw || canvas.height !== ph) {
        canvas.width = pw
        canvas.height = ph
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      }

      ctx.fillStyle = '#060610'
      ctx.fillRect(0, 0, w, h)

      const size = Math.min(w, h)
      const cx = w / 2
      const cy = h / 2 + size * 0.06
      const scaleFactor = size / 300
      const armLength = dimsRef.current.armLength * scaleFactor
      const wheelRadius = dimsRef.current.wheelRadius * scaleFactor
      const wheelInnerRadius = Math.min(dimsRef.current.wheelInnerRadius * scaleFactor, wheelRadius * 0.85)

      const dt = stateRef.current.lastTime > 0
        ? Math.min((timestamp - stateRef.current.lastTime) / 1000, 0.05)
        : 0.016
      stateRef.current.lastTime = timestamp

      // Dead-reckon theta for smooth 60fps motion between telemetry updates
      const targetTheta = stateRef.current.targetTheta
      let diff = targetTheta - stateRef.current.theta
      while (diff > Math.PI) diff -= Math.PI * 2
      while (diff < -Math.PI) diff += Math.PI * 2
      stateRef.current.theta += stateRef.current.theta_dot * dt + diff * Math.min(dt * 10, 1)

      stateRef.current.wheelAngle += stateRef.current.phi_dot * dt

      const { theta, theta_dot, phi_dot, voltage, current } = stateRef.current
      const wheelAngle = stateRef.current.wheelAngle

      const tipX = cx + armLength * Math.sin(theta)
      const tipY = cy - armLength * Math.cos(theta)

      const st = stateRef.current
      st.trailX[st.trailHead] = tipX
      st.trailY[st.trailHead] = tipY
      st.trailHead = (st.trailHead + 1) % TRAIL_LEN
      if (st.trailCount < TRAIL_LEN) st.trailCount++

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

      // Equilibrium / danger zone wedges
      const zoneRadius = armLength + 8
      const safeHalf = dimsRef.current.switchAngle
      const cautionHalf = Math.min(safeHalf * 2, Math.PI / 2)
      const up = -Math.PI / 2

      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.arc(cx, cy, zoneRadius, up - safeHalf, up + safeHalf)
      ctx.closePath()
      ctx.fillStyle = 'rgba(111, 207, 151, 0.07)'
      ctx.fill()

      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.arc(cx, cy, zoneRadius, up + safeHalf, up + cautionHalf)
      ctx.closePath()
      ctx.fillStyle = 'rgba(242, 201, 76, 0.05)'
      ctx.fill()
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.arc(cx, cy, zoneRadius, up - cautionHalf, up - safeHalf)
      ctx.closePath()
      ctx.fillStyle = 'rgba(242, 201, 76, 0.05)'
      ctx.fill()



      // Ground shadow
      const shadowScale = Math.abs(Math.sin(theta))
      ctx.fillStyle = `rgba(0, 0, 0, ${0.25 - shadowScale * 0.15})`
      ctx.beginPath()
      ctx.ellipse(cx, cy + 14, 18 + shadowScale * 12, 4, 0, 0, Math.PI * 2)
      ctx.fill()

      // Trail path (smooth quadratic curve with gradient fade)
      const tc = st.trailCount
      if (tc > 2) {
        const tX = st.trailX
        const tY = st.trailY
        const head = st.trailHead
        const oldest = (head - tc + TRAIL_LEN) % TRAIL_LEN
        const newest = (head - 1 + TRAIL_LEN) % TRAIL_LEN
        const grad = ctx.createLinearGradient(tX[oldest], tY[oldest], tX[newest], tY[newest])
        grad.addColorStop(0, 'rgba(86, 204, 242, 0)')
        grad.addColorStop(1, 'rgba(86, 204, 242, 0.45)')
        ctx.strokeStyle = grad
        ctx.lineWidth = 2
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        ctx.beginPath()
        ctx.moveTo(tX[oldest], tY[oldest])
        for (let i = 1; i < tc - 1; i++) {
          const ci = (oldest + i) % TRAIL_LEN
          const ni = (oldest + i + 1) % TRAIL_LEN
          const mx = (tX[ci] + tX[ni]) / 2
          const my = (tY[ci] + tY[ni]) / 2
          ctx.quadraticCurveTo(tX[ci], tY[ci], mx, my)
        }
        ctx.lineTo(tX[newest], tY[newest])
        ctx.stroke()
      }

      // Base
      ctx.fillStyle = '#2a2a4a'
      ctx.fillRect(cx - 16, cy, 32, 10)

      // Arm
      ctx.strokeStyle = '#8899aa'
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

      ctx.beginPath()
      ctx.arc(0, 0, wheelRadius, 0, Math.PI * 2)
      ctx.arc(0, 0, wheelInnerRadius, 0, Math.PI * 2, true)
      ctx.fillStyle = 'rgba(86, 204, 242, 0.12)'
      ctx.fill('evenodd')

      ctx.strokeStyle = '#56ccf2'
      ctx.lineWidth = 2.5
      ctx.beginPath()
      ctx.arc(0, 0, wheelRadius, 0, Math.PI * 2)
      ctx.stroke()

      ctx.strokeStyle = '#56ccf266'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.arc(0, 0, wheelInnerRadius, 0, Math.PI * 2)
      ctx.stroke()

      for (let i = 0; i < 4; i++) {
        const a = (Math.PI / 2) * i
        ctx.beginPath()
        ctx.moveTo(wheelInnerRadius * Math.cos(a), wheelInnerRadius * Math.sin(a))
        ctx.lineTo(wheelRadius * Math.cos(a), wheelRadius * Math.sin(a))
        ctx.stroke()
      }

      ctx.fillStyle = '#56ccf2'
      ctx.beginPath()
      ctx.arc(0, 0, 3, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()

      // Speed arc around wheel — smooth color transition cyan → orange → red
      const maxSpeed = 30
      const targetSpeedNorm = Math.min(Math.abs(phi_dot) / maxSpeed, 1)
      st.smoothSpeedNorm += (targetSpeedNorm - st.smoothSpeedNorm) * Math.min(dt * 6, 1)
      const sn = st.smoothSpeedNorm
      if (sn > 0.01) {
        const arcRadius = wheelRadius + 5
        const sweepAngle = sn * Math.PI * 1.8
        const startA = -Math.PI / 2 - sweepAngle / 2
        const endA = -Math.PI / 2 + sweepAngle / 2
        let arcR, arcG, arcB
        if (sn < 0.5) {
          const t = sn / 0.5
          arcR = Math.round(86 + t * (242 - 86))
          arcG = Math.round(204 + t * (153 - 204))
          arcB = Math.round(242 + t * (74 - 242))
        } else {
          const t = (sn - 0.5) / 0.5
          arcR = Math.round(242 + t * (235 - 242))
          arcG = Math.round(153 + t * (87 - 153))
          arcB = Math.round(74 + t * (87 - 74))
        }
        ctx.strokeStyle = `rgba(${arcR}, ${arcG}, ${arcB}, 0.85)`
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
      ctx.font = '12px Vazirmatn, sans-serif'
      ctx.textAlign = 'right'
      ctx.fillText(`زاویه: ${toPersianDigits((theta * 180 / Math.PI).toFixed(1))}°`, w - 6, 14)
      ctx.fillText(`سرعت چرخ: ${toPersianDigits((phi_dot * 30 / Math.PI).toFixed(0))} RPM`, w - 6, 27)
      ctx.fillText(`ولتاژ: ${toPersianDigits(voltage.toFixed(1))} V`, w - 6, 40)

      animRef.current = requestAnimationFrame(draw)
    }

    animRef.current = requestAnimationFrame(draw)
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current) }
  }, [])

  return (
    <div className="flex-1 flex flex-col rounded-lg border border-border bg-card overflow-hidden shadow-card hover:border-border-light transition-colors duration-200 min-h-0">
      <div className="px-3 py-2 border-b border-border flex-shrink-0">
        <h3 className="text-[13px] font-bold text-text-dim">پاندول</h3>
      </div>
      <div className="flex-1 min-h-0">
        <canvas ref={canvasRef} className="w-full h-full block" />
      </div>
    </div>
  )
}