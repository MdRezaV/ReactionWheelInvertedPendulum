import { useState } from 'react'

const CONTROL_MODES = [
  { value: 'none', label: 'No Control' },
  { value: 'pid', label: 'PID Balance' },
  { value: 'lqr', label: 'LQR Balance' },
  { value: 'energy_swing_up', label: 'Energy Swing-Up' },
  { value: 'manual', label: 'Manual Torque' },
]

const SIM_PARAMS = [
  { key: 'pendulum_mass', label: 'Pendulum Mass', unit: 'kg', min: 0.1, max: 5, step: 0.1 },
  { key: 'pendulum_length', label: 'Pendulum Length', unit: 'm', min: 0.1, max: 2, step: 0.05 },
  { key: 'wheel_mass', label: 'Wheel Mass', unit: 'kg', min: 0.05, max: 2, step: 0.05 },
  { key: 'wheel_radius', label: 'Wheel Radius', unit: 'm', min: 0.01, max: 0.2, step: 0.005 },
  { key: 'damping', label: 'Damping', unit: 'N·m·s', min: 0, max: 0.5, step: 0.005 },
  { key: 'wheel_damping', label: 'Wheel Damping', unit: 'N·m·s', min: 0, max: 0.1, step: 0.001 },
  { key: 'gravity', label: 'Gravity', unit: 'm/s²', min: 1, max: 20, step: 0.1 },
  { key: 'max_motor_torque', label: 'Max Torque', unit: 'N·m', min: 0.1, max: 5, step: 0.1 },
  { key: 'time_step', label: 'Time Step', unit: 's', min: 0.0005, max: 0.01, step: 0.0005 },
]

const CTRL_PARAMS = [
  { key: 'pid_kp', label: 'PID Kp', min: 0, max: 200, step: 1 },
  { key: 'pid_ki', label: 'PID Ki', min: 0, max: 10, step: 0.05 },
  { key: 'pid_kd', label: 'PID Kd', min: 0, max: 50, step: 0.5 },
  { key: 'lqr_q_theta', label: 'LQR Q θ', min: 0, max: 500, step: 5 },
  { key: 'lqr_q_theta_dot', label: 'LQR Q θ̇', min: 0, max: 50, step: 0.5 },
  { key: 'lqr_q_phi_dot', label: 'LQR Q φ̇', min: 0, max: 100, step: 1 },
  { key: 'lqr_r', label: 'LQR R', min: 0.01, max: 10, step: 0.1 },
  { key: 'energy_swing_up_gain', label: 'Swing-Up Gain', min: 0.1, max: 10, step: 0.1 },
]

export default function ControlPanel({
  status,
  params,
  onStart,
  onStop,
  onPause,
  onResume,
  onReset,
  onStep,
  onSetMode,
  onSetManualTorque,
  onUpdateParams,
}) {
  const [activeTab, setActiveTab] = useState('controls')
  const [manualTorque, setManualTorque] = useState(0)

  const isRunning = status?.status === 'running'
  const isPaused = status?.status === 'paused'
  const isStopped = status?.status === 'stopped'

  const handleParamChange = (scope, key, value) => {
    const numVal = parseFloat(value)
    if (Number.isNaN(numVal)) return
    onUpdateParams({ [scope]: { [key]: numVal } })
  }

  return (
    <div className="control-panel">
      <div className="panel-tabs">
        <button
          className={activeTab === 'controls' ? 'active' : ''}
          onClick={() => setActiveTab('controls')}
        >
          Controls
        </button>
        <button
          className={activeTab === 'sim-params' ? 'active' : ''}
          onClick={() => setActiveTab('sim-params')}
        >
          Physics
        </button>
        <button
          className={activeTab === 'ctrl-params' ? 'active' : ''}
          onClick={() => setActiveTab('ctrl-params')}
        >
          Gains
        </button>
      </div>

      {activeTab === 'controls' && (
        <div className="panel-content">
          <div className="button-group">
            <button onClick={onStart} disabled={isRunning} className="btn-start">
              Start
            </button>
            <button onClick={onStop} disabled={isStopped} className="btn-stop">
              Stop
            </button>
            <button onClick={onPause} disabled={!isRunning} className="btn-pause">
              Pause
            </button>
            <button onClick={onResume} disabled={!isPaused} className="btn-resume">
              Resume
            </button>
            <button onClick={onReset} className="btn-reset">
              Reset
            </button>
            <button onClick={() => onStep(1)} className="btn-step">
              Step
            </button>
            <button onClick={() => onStep(10)} className="btn-step">
              Step ×10
            </button>
          </div>

          <div className="control-section">
            <label className="control-label">Control Mode</label>
            <select
              value={status?.control_mode || 'none'}
              onChange={(e) => onSetMode(e.target.value)}
              className="mode-select"
            >
              {CONTROL_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          {status?.control_mode === 'manual' && (
            <div className="control-section">
              <label className="control-label">
                Manual Torque: {manualTorque.toFixed(2)} N·m
              </label>
              <input
                type="range"
                min={-1}
                max={1}
                step={0.01}
                value={manualTorque}
                onChange={(e) => {
                  const v = parseFloat(e.target.value)
                  setManualTorque(v)
                  onSetManualTorque(v)
                }}
                className="param-slider"
              />
            </div>
          )}
        </div>
      )}

      {activeTab === 'sim-params' && (
        <div className="panel-content scrollable">
          {SIM_PARAMS.map((p) => {
            const val = params?.simulation?.[p.key] ?? p.min
            return (
              <div key={p.key} className="param-row">
                <label className="param-label">
                  {p.label} <span className="param-unit">({p.unit})</span>
                </label>
                <div className="param-input-row">
                  <input
                    type="range"
                    min={p.min}
                    max={p.max}
                    step={p.step}
                    value={val}
                    onChange={(e) => handleParamChange('simulation', p.key, e.target.value)}
                    className="param-slider"
                  />
                  <input
                    type="number"
                    min={p.min}
                    max={p.max}
                    step={p.step}
                    value={val}
                    onChange={(e) => handleParamChange('simulation', p.key, e.target.value)}
                    className="param-number"
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {activeTab === 'ctrl-params' && (
        <div className="panel-content scrollable">
          {CTRL_PARAMS.map((p) => {
            const val = params?.control?.[p.key] ?? p.min
            return (
              <div key={p.key} className="param-row">
                <label className="param-label">{p.label}</label>
                <div className="param-input-row">
                  <input
                    type="range"
                    min={p.min}
                    max={p.max}
                    step={p.step}
                    value={val}
                    onChange={(e) => handleParamChange('control', p.key, e.target.value)}
                    className="param-slider"
                  />
                  <input
                    type="number"
                    min={p.min}
                    max={p.max}
                    step={p.step}
                    value={val}
                    onChange={(e) => handleParamChange('control', p.key, e.target.value)}
                    className="param-number"
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}