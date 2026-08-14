import { useCallback, useEffect, useRef } from 'react'
import { toPersianDigits } from '../utils/format'

const STATUS_LABELS = {
  idle: 'بیکار',
  running: 'در حال اجرا',
  complete: 'تکمیل شد',
}

export default function TuningTab({ send, tuningProgress, tuningResponse }) {
  const canvasRef = useRef(null)

  const startTuner = useCallback(() => {
    send({ type: 'auto_tuner_start' })
  }, [send])

  const stopTuner = useCallback(() => {
    send({ type: 'auto_tuner_stop' })
  }, [send])

  const progress = tuningProgress || {}
  const best = progress.best || {}
  const current = progress.current || {}
  const status = progress.status || 'idle'
  const iteration = progress.iteration ?? 0
  const isRunning = status === 'running'

  const timeData = tuningResponse?.time || null
  const thetaData = tuningResponse?.theta || null

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    if (w === 0 || h === 0) return
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    const padL = 44
    const padR = 12
    const padT = 12
    const padB = 28
    const plotW = w - padL - padR
    const plotH = h - padT - padB

    // Background
    ctx.fillStyle = '#14142a'
    ctx.fillRect(0, 0, w, h)

    // Grid
    ctx.strokeStyle = '#222244'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = padT + (plotH / 4) * i
      ctx.beginPath()
      ctx.moveTo(padL, y)
      ctx.lineTo(padL + plotW, y)
      ctx.stroke()
    }
    for (let i = 0; i <= 6; i++) {
      const x = padL + (plotW / 6) * i
      ctx.beginPath()
      ctx.moveTo(x, padT)
      ctx.lineTo(x, padT + plotH)
      ctx.stroke()
    }

    // Zero reference line
    const yZero = padT + plotH / 2
    ctx.strokeStyle = '#333360'
    ctx.lineWidth = 1.5
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(padL, yZero)
    ctx.lineTo(padL + plotW, yZero)
    ctx.stroke()
    ctx.setLineDash([])

    // Axis labels
    ctx.fillStyle = '#6a6a88'
    ctx.font = '11px Vazirmatn, monospace'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.fillText('θ (°)', padL + 4, padT + 2)
    ctx.fillText('زمان (s)', padL + plotW - 50, h - 16)

    if (!timeData || !thetaData || timeData.length < 2) {
      ctx.fillStyle = '#6a6a88'
      ctx.font = '13px Vazirmatn'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('پاسخ مرحله‌ای پس از تکمیل تنظیم نمایش داده می‌شود', w / 2, h / 2)
      return
    }

    const RAD2DEG = 180 / Math.PI
    const thetaDeg = thetaData.map(v => v * RAD2DEG)

    const tMax = Math.max(...timeData, 1)
    const thMin = Math.min(...thetaDeg, -5)
    const thMax = Math.max(...thetaDeg, 5)
    const thRange = thMax - thMin || 1

    const toX = (t) => padL + (t / tMax) * plotW
    const toY = (th) => padT + (1 - (th - thMin) / thRange) * plotH

    // Response curve
    ctx.strokeStyle = '#56ccf2'
    ctx.lineWidth = 2
    ctx.beginPath()
    for (let i = 0; i < timeData.length; i++) {
      const x = toX(timeData[i])
      const y = toY(thetaDeg[i])
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()

    // Y-axis tick labels
    ctx.fillStyle = '#6a6a88'
    ctx.font = '10px Vazirmatn, monospace'
    ctx.textAlign = 'right'
    ctx.textBaseline = 'middle'
    ctx.fillText(toPersianDigits(thMax.toFixed(2)), padL - 4, padT)
    ctx.fillText(toPersianDigits('0.00'), padL - 4, yZero)
    ctx.fillText(toPersianDigits(thMin.toFixed(2)), padL - 4, padT + plotH)

    // X-axis tick label
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillText(toPersianDigits(tMax.toFixed(1)), padL + plotW, padT + plotH + 6)
  }, [timeData, thetaData])

  const btn = 'px-2.5 py-1.5 text-[14px] font-medium rounded-md border transition-all duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.96]'

  const fmt = (v) => v !== undefined ? toPersianDigits(v.toFixed(4)) : '—'

  return (
    <div dir="rtl" className="flex flex-col gap-3 h-full w-full overflow-y-auto">
      <div className="flex items-center justify-between flex-shrink-0">
        <h2 className="text-[16px] font-bold text-text-h">تنظیم خودکار بهره‌های PID</h2>
        <div className="flex gap-1.5">
          <button onClick={startTuner} disabled={isRunning} className={`${btn} border-success/30 text-success bg-success/5`}>شروع تنظیم</button>
          <button onClick={stopTuner} disabled={!isRunning} className={`${btn} border-danger/30 text-danger bg-danger/5`}>توقف تنظیم</button>
        </div>
      </div>

      <div className="flex items-center gap-3 px-3 py-2 rounded-md border border-border bg-surface/60 text-[13px] flex-shrink-0">
        <span className="text-text-dim">وضعیت:</span>
        <span className={`font-bold ${isRunning ? 'text-success' : status === 'complete' ? 'text-accent' : 'text-text-dim'}`}>{STATUS_LABELS[status] || status}</span>
        <span className="text-text-dim/40">|</span>
        <span className="text-text-dim">تکرار:</span>
        <span className="font-mono text-text" dir="ltr">{toPersianDigits(String(iteration))}</span>
      </div>

      <div className="grid grid-cols-2 gap-3 flex-shrink-0">
        <div className="flex flex-col gap-2 p-3 rounded-md border border-accent/30 bg-card">
          <span className="text-[13px] font-bold text-accent">بهترین بهره‌ها</span>
          <div className="flex flex-col gap-1 text-[13px]">
            <div className="flex justify-between">
              <span className="text-text-dim">هزینه</span>
              <span className="font-mono text-text" dir="ltr">{fmt(best.cost)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim">K_p</span>
              <span className="font-mono text-text" dir="ltr">{fmt(best.kp)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim">K_i</span>
              <span className="font-mono text-text" dir="ltr">{fmt(best.ki)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim">K_d</span>
              <span className="font-mono text-text" dir="ltr">{fmt(best.kd)}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-2 p-3 rounded-md border border-border bg-card">
          <span className="text-[13px] font-bold text-text-h">بهره‌های فعلی</span>
          <div className="flex flex-col gap-1 text-[13px]">
            <div className="flex justify-between">
              <span className="text-text-dim">هزینه</span>
              <span className="font-mono text-text" dir="ltr">{fmt(current.cost)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim">K_p</span>
              <span className="font-mono text-text" dir="ltr">{fmt(current.kp)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim">K_i</span>
              <span className="font-mono text-text" dir="ltr">{fmt(current.ki)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-dim">K_d</span>
              <span className="font-mono text-text" dir="ltr">{fmt(current.kd)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-1 flex-1 min-h-0">
        <span className="text-[13px] font-bold text-text-dim">پاسخ مرحله‌ای بهترین اجرا</span>
        <div className="flex-1 min-h-[180px] rounded-md border border-border bg-card overflow-hidden">
          <canvas ref={canvasRef} className="w-full h-full block" />
        </div>
      </div>
    </div>
  )
}