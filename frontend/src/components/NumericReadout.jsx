import { fmt } from '../utils/format'

const RAD2DEG = 180 / Math.PI

const FIELDS = [
  { key: 'theta', label: 'θ', format: (v) => `${fmt(v * RAD2DEG, 2)}°` },
  { key: 'theta_dot', label: 'θ̇', format: (v) => `${fmt(v * RAD2DEG, 2)} °/s` },
  { key: 'theta_ddot', label: 'θ̈', format: (v) => `${fmt(v * RAD2DEG, 1)} °/s²` },
  { key: 'phi', label: 'φ', format: (v) => `${fmt(v * RAD2DEG, 2)}°` },
  { key: 'phi_dot', label: 'φ̇', format: (v) => `${fmt(v * RAD2DEG, 2)} °/s` },
  { key: 'phi_ddot', label: 'φ̈', format: (v) => `${fmt(v * RAD2DEG, 1)} °/s²` },
  { key: 'voltage', label: 'ولتاژ', format: (v) => `${fmt(v, 2)} ولت` },
  { key: 'current', label: 'جریان', format: (v) => `${fmt(v, 3)} آمپر` },
  { key: 'back_emf', label: 'EMF', format: (v) => `${fmt(v, 2)} ولت` },
  { key: 'motor_torque', label: 'τ_m', format: (v) => `${fmt(v, 4)} نیوتن·متر` },
  { key: 'wheel_torque', label: 'τ_w', format: (v) => `${fmt(v, 4)} نیوتن·متر` },
  { key: 'energy', label: 'انرژی', format: (v) => `${fmt(v, 4)} ژول` },
  { key: 'kinetic_energy', label: 'جنبشی', format: (v) => `${fmt(v, 4)} ژول` },
  { key: 'potential_energy', label: 'پتانسیل', format: (v) => `${fmt(v, 4)} ژول` },
  { key: 'angular_momentum', label: 'L', format: (v) => `${fmt(v, 4)} کیلوگرم·متر²/ثانیه` },
  { key: 'time', label: 'زمان', format: (v) => `${fmt(v, 3)} ثانیه` },
]

export default function NumericReadout({ latest }) {
  return (
    <div className="flex-1 min-w-[240px] rounded-xl border border-border bg-card overflow-hidden shadow-card">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
        <h3 className="text-[13px] font-bold text-text-h">مقادیر زنده</h3>
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(130px,1fr))] gap-px bg-border">
        {FIELDS.map((f) => (
          <div key={f.key} className="flex flex-col px-2.5 py-1.5 bg-card">
            <span className="text-[10px] text-text-dim font-bold uppercase">{f.label}</span>
            <span className="text-xs font-mono text-text-h mt-0.5" dir="ltr">
              {latest ? f.format(latest[f.key] ?? 0) : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}