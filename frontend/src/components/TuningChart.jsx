import { useEffect, useRef } from 'react'

export default function TuningChart({ tuningResponse }) {
  const canvasRef = useRef(null)
  const dataRef = useRef(tuningResponse)

  useEffect(() => {
    dataRef.current = tuningResponse
  }, [tuningResponse])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    let rafId

    const draw = () => {
      const width = canvas.width
      const height = canvas.height

      ctx.clearRect(0, 0, width, height)
      ctx.fillStyle = '#1e1e1e'
      ctx.fillRect(0, 0, width, height)

      ctx.strokeStyle = '#444'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(0, height / 2)
      ctx.lineTo(width, height / 2)
      ctx.stroke()

      const data = dataRef.current
      if (data && data.time && data.theta && data.time.length > 1) {
        const time = data.time
        const theta = data.theta
        const tMin = time[0]
        const tMax = time[time.length - 1]
        const thMin = Math.min(...theta)
        const thMax = Math.max(...theta)
        const tRange = tMax - tMin || 1
        const thRange = thMax - thMin || 1

        ctx.strokeStyle = '#00ff00'
        ctx.lineWidth = 2
        ctx.beginPath()
        for (let i = 0; i < time.length; i++) {
          const x = ((time[i] - tMin) / tRange) * width
          const y = height - ((theta[i] - thMin) / thRange) * height
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()
      }

      rafId = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      cancelAnimationFrame(rafId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      width={400}
      height={200}
      style={{ border: '1px solid #555', backgroundColor: '#1e1e1e' }}
    />
  )
}