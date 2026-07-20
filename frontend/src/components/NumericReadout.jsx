import { useEffect, useRef, useState } from 'react'
import { fmt } from '../utils/format'

const RAD2DEG = 180 / Math.PI
const LERP_FACTOR = 0.14

const FIELDS = [
  { key: 'theta', label: 'زاویه پاندول', format: (v) => `${fmt(v * RAD2DEG, 1)}°` },
  { key: 'theta_dot', label: 'سرعت پاندول', format: (v) => `${fmt(v * RAD2DEG, 1)}°/s` },
  { key: 'phi_dot', label: 'سرعت چرخ', format: (v) => `${fmt(v * RAD2DEG, 0)}°/s` },
  { key: 'voltage', label: 'ولتاژ', format: (v) => `${fmt(v, 2)} V` },
  { key: 'current', label: 'جریان', format: (v) => `${fmt(v, 3)} A` },
  { key: 'motor_torque', label: 'گشتاور موتور', format: (v) => `${fmt(v, 4)}` },
  { key: 'energy', label: 'انرژی کل', format: (v) => `${fmt(v, 3)} J` },
  { key: 'angular_momentum', label: 'تکانه زاویه‌ای', format: (v) => `${fmt(v, 4)}` },
]

export default function NumericReadout({ latest }) {
  const displayRef = useRef({})
  const targetRef = useRef({})
  const [display, setDisplay] = useState({})
  const rafRef = useRef(null)

  useEffect(() => {
    if (latest) {
      for (const f of FIELDS) {
        targetRef.current[f.key] = latest[f.key] ?? 0
      }
    }
  }, [latest])

  useEffect(() => {
    const animate = () => {
      let changed = false
      for (const f of FIELDS) {
        const target = targetRef.current[f.key] ?? 0
        const current = displayRef.current[f.key] ?? 0
        const next = current + (target - current) * LERP_FACTOR
        if (Math.abs(next - target) < 1e-6) {
          displayRef.current[f.key] = target
        } else {
          displayRef.current[f.key] = next
          changed = true
        }
      }
      if (changed) {
        setDisplay({ ...displayRef.current })
      }
      rafRef.current = requestAnimationFrame(animate)
    }
    rafRef.current = requestAnimationFrame(animate)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [])

  const values = Object.keys(display).length > 0 ? display : (latest || {})

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden shadow-card hover:border-border-light transition-colors duration-200">
      <div className="px-3 py-1.5 border-b border-border">
        <h3 className="text-[11px] font-bold text-text-dim uppercase tracking-wide">مقادیر زنده</h3>
      </div>
      <div className="grid grid-cols-4 gap-px bg-border/50">
        {FIELDS.map((f) => (
          <div key={f.key} className="flex flex-col px-2 py-1.5 bg-card">
            <span className="text-[9px] text-text-dim font-bold">{f.label}</span>
            <span className="text-[11px] font-mono text-text-h mt-0.5" dir="ltr">
              {latest ? f.format(values[f.key] ?? 0) : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}