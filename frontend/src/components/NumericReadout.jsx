import { fmt, fmtAngle, fmtTorque } from '../utils/format'

const FIELDS = [
  { key: 'theta', label: 'θ', format: (v) => fmtAngle(v) },
  { key: 'theta_dot', label: 'θ̇', format: (v) => `${fmt(v, 3)} rad/s` },
  { key: 'theta_ddot', label: 'θ̈', format: (v) => `${fmt(v, 2)} rad/s²` },
  { key: 'phi', label: 'φ', format: (v) => `${fmt(v, 3)} rad` },
  { key: 'phi_dot', label: 'φ̇', format: (v) => `${fmt(v, 2)} rad/s` },
  { key: 'phi_ddot', label: 'φ̈', format: (v) => `${fmt(v, 1)} rad/s²` },
  { key: 'torque', label: 'τ', format: (v) => fmtTorque(v) },
  { key: 'energy', label: 'E', format: (v) => `${fmt(v, 4)} J` },
  { key: 'kinetic_energy', label: 'KE', format: (v) => `${fmt(v, 4)} J` },
  { key: 'potential_energy', label: 'PE', format: (v) => `${fmt(v, 4)} J` },
  { key: 'angular_momentum', label: 'L', format: (v) => `${fmt(v, 4)} kg·m²/s` },
  { key: 'time', label: 't', format: (v) => `${fmt(v, 3)} s` },
]

export default function NumericReadout({ latest }) {
  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3>Live Values</h3>
      </div>
      <div className="readout-grid">
        {FIELDS.map((f) => (
          <div key={f.key} className="readout-cell">
            <span className="readout-label">{f.label}</span>
            <span className="readout-value">
              {latest ? f.format(latest[f.key] ?? 0) : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}