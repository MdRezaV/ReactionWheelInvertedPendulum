import { useState } from 'react'

const CONTROL_MODES = [
  { value: 'none', label: 'بدون کنترل' },
  { value: 'pid', label: 'تعادل PID' },
  { value: 'lqr', label: 'تعادل LQR' },
  { value: 'energy_swing_up', label: 'نوسان انرژی' },
  { value: 'sliding_mode', label: 'مد لغزشی (SMC)' },
  { value: 'manual', label: 'گشتاور دستی' },
]

const SIM_PARAMS = [
  { key: 'pendulum_mass', label: 'جرم پاندول', unit: 'kg', min: 0.1, max: 5, step: 0.1 },
  { key: 'pendulum_length', label: 'طول پاندول', unit: 'm', min: 0.1, max: 2, step: 0.05 },
  { key: 'wheel_mass', label: 'جرم چرخ', unit: 'kg', min: 0.05, max: 2, step: 0.05 },
  { key: 'wheel_radius', label: 'شعاع چرخ', unit: 'm', min: 0.01, max: 0.2, step: 0.005 },
  { key: 'damping', label: 'میرایی', unit: 'N·m·s', min: 0, max: 0.5, step: 0.005 },
  { key: 'wheel_damping', label: 'میرایی چرخ', unit: 'N·m·s', min: 0, max: 0.1, step: 0.001 },
  { key: 'gravity', label: 'گرانش', unit: 'm/s²', min: 1, max: 20, step: 0.1 },
  { key: 'max_voltage', label: 'حداکثر ولتاژ', unit: 'V', min: 1, max: 48, step: 1 },
  { key: 'motor_resistance', label: 'مقاومت موتور', unit: 'Ω', min: 0.1, max: 20, step: 0.1 },
  { key: 'motor_inductance', label: 'القای موتور', unit: 'H', min: 0.0001, max: 0.1, step: 0.0001 },
  { key: 'motor_constant', label: 'ثابت موتور', unit: 'N·m/A', min: 0.001, max: 0.5, step: 0.001 },
  { key: 'motor_rotor_inertia', label: 'اینرسی روتور', unit: 'kg·m²', min: 1e-6, max: 0.01, step: 1e-6 },
  { key: 'motor_viscous_friction', label: 'اصطکاک ویسکوز', unit: 'N·m·s', min: 0, max: 0.01, step: 0.0001 },
  { key: 'gear_ratio', label: 'نسبت چرخ‌دنده', unit: '—', min: 1, max: 100, step: 1 },
  { key: 'time_step', label: 'گام زمانی', unit: 's', min: 0.0005, max: 0.01, step: 0.0005 },
]

const CTRL_PARAMS = [
  { key: 'pid_kp', label: 'PID Kp', min: 0, max: 200, step: 1 },
  { key: 'pid_ki', label: 'PID Ki', min: 0, max: 10, step: 0.05 },
  { key: 'pid_kd', label: 'PID Kd', min: 0, max: 50, step: 0.5 },
  { key: 'lqr_q_theta', label: 'LQR Q θ', min: 0, max: 500, step: 5 },
  { key: 'lqr_q_theta_dot', label: 'LQR Q θ̇', min: 0, max: 50, step: 0.5 },
  { key: 'lqr_q_phi_dot', label: 'LQR Q φ̇', min: 0, max: 100, step: 1 },
  { key: 'lqr_r', label: 'LQR R', min: 0.01, max: 10, step: 0.1 },
  { key: 'lqr_q_current', label: 'LQR Q i_a', min: 0, max: 10, step: 0.01 },
  { key: 'energy_swing_up_gain', label: 'بهره نوسان', min: 0.1, max: 10, step: 0.1 },
  { key: 'smc_c1', label: 'SMC c₁', min: 0.1, max: 50, step: 0.5 },
  { key: 'smc_c2', label: 'SMC c₂', min: 0.1, max: 30, step: 0.5 },
  { key: 'smc_c3', label: 'SMC c₃', min: 0, max: 10, step: 0.1 },
  { key: 'smc_k', label: 'SMC K', min: 0.1, max: 10, step: 0.1 },
  { key: 'smc_eta', label: 'SMC η', min: 0, max: 5, step: 0.1 },
  { key: 'smc_boundary', label: 'SMC مرز', min: 0.01, max: 0.5, step: 0.01 },
]

const TABS = [
  { id: 'controls', label: 'کنترل‌ها' },
  { id: 'sim-params', label: 'فیزیک' },
  { id: 'ctrl-params', label: 'بهره‌ها' },
]

export default function ControlPanel({
  status, params, onStart, onStop, onPause, onResume, onReset, onStep,
  onSetMode, onSetManualVoltage, onUpdateParams, onDisturbance, onSetSpeed,
}) {
  const [activeTab, setActiveTab] = useState('controls')
  const [manualTorque, setManualTorque] = useState(0)
  const [speed, setSpeed] = useState(1.0)

  const isRunning = status?.status === 'running'
  const isPaused = status?.status === 'paused'
  const isStopped = status?.status === 'stopped'

  const handleParamChange = (scope, key, value) => {
    const numVal = parseFloat(value)
    if (Number.isNaN(numVal)) return
    onUpdateParams({ [scope]: { [key]: numVal } })
  }

  const btnBase = 'px-3 py-2 text-[13px] font-medium rounded-lg border transition-all duration-200 cursor-pointer disabled:opacity-35 disabled:cursor-not-allowed hover:shadow-md active:scale-[0.97]'

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2.5 px-2 text-xs font-semibold border-b-2 transition-all duration-200 cursor-pointer
              ${activeTab === tab.id
                ? 'text-accent border-accent bg-accent-dim/30'
                : 'text-text-dim border-transparent hover:text-text-h'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'controls' && (
        <div className="p-4 flex flex-col gap-4 overflow-y-auto flex-1">
          <div className="grid grid-cols-2 gap-2">
            <button onClick={onStart} disabled={isRunning} className={`${btnBase} border-success/40 text-success hover:bg-success/10`}>شروع</button>
            <button onClick={onStop} disabled={isStopped} className={`${btnBase} border-danger/40 text-danger hover:bg-danger/10`}>توقف</button>
            <button onClick={onPause} disabled={!isRunning} className={`${btnBase} border-warning/40 text-warning hover:bg-warning/10`}>مکث</button>
            <button onClick={onResume} disabled={!isPaused} className={`${btnBase} border-green/40 text-green hover:bg-green/10`}>ادامه</button>
            <button onClick={onReset} className={`${btnBase} border-warning/40 text-warning hover:bg-warning/10`}>بازنشانی</button>
            <button onClick={() => onStep(1)} className={`${btnBase} border-teal/40 text-teal hover:bg-teal/10`}>گام</button>
            <button onClick={() => onStep(10)} className={`${btnBase} border-teal/40 text-teal hover:bg-teal/10 col-span-2`}>گام ×۱۰</button>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-text-dim font-semibold">حالت کنترل</label>
            <select
              value={status?.control_mode || 'none'}
              onChange={(e) => onSetMode(e.target.value)}
              className="px-3 py-2 text-[13px] rounded-lg border border-border bg-card text-text-h cursor-pointer focus:border-accent focus:outline-none transition-colors"
            >
              {CONTROL_MODES.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          {status?.control_mode === 'manual' && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs text-text-dim font-semibold">
                ولتاژ دستی: {manualTorque.toFixed(1)} V
              </label>
              <input
                type="range" min={-12} max={12} step={0.1} value={manualTorque}
                onChange={(e) => { const v = parseFloat(e.target.value); setManualTorque(v); onSetManualVoltage(v) }}
              />
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-text-dim font-semibold">
              سرعت: {speed.toFixed(1)}×
            </label>
            <input
              type="range" min={0.1} max={5} step={0.1} value={speed}
              onChange={(e) => { const v = parseFloat(e.target.value); setSpeed(v); onSetSpeed(v) }}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-text-dim font-semibold">اختلال</label>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => onDisturbance(6, 20)} className={`${btnBase} border-purple/40 text-purple hover:bg-purple/10`}>+6V</button>
              <button onClick={() => onDisturbance(-6, 20)} className={`${btnBase} border-purple/40 text-purple hover:bg-purple/10`}>−6V</button>
              <button onClick={() => onDisturbance(12, 10)} className={`${btnBase} border-purple/40 text-purple hover:bg-purple/10`}>+12V</button>
              <button onClick={() => onDisturbance(-12, 10)} className={`${btnBase} border-purple/40 text-purple hover:bg-purple/10`}>−12V</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'sim-params' && (
        <div className="p-4 flex flex-col gap-3 overflow-y-auto flex-1">
          {SIM_PARAMS.map((p) => {
            const val = params?.simulation?.[p.key] ?? p.min
            return (
              <div key={p.key} className="flex flex-col gap-1">
                <label className="text-xs text-text-dim">
                  {p.label} <span className="text-text-dim/60 text-[11px]">({p.unit})</span>
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="range" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('simulation', p.key, e.target.value)}
                    className="flex-1"
                  />
                  <input
                    type="number" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('simulation', p.key, e.target.value)}
                    className="w-[72px] px-1.5 py-1 text-xs font-mono rounded border border-border bg-card text-text-h text-left focus:border-accent focus:outline-none"
                    dir="ltr"
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {activeTab === 'ctrl-params' && (
        <div className="p-4 flex flex-col gap-3 overflow-y-auto flex-1">
          {CTRL_PARAMS.map((p) => {
            const val = params?.control?.[p.key] ?? p.min
            return (
              <div key={p.key} className="flex flex-col gap-1">
                <label className="text-xs text-text-dim">{p.label}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="range" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('control', p.key, e.target.value)}
                    className="flex-1"
                  />
                  <input
                    type="number" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('control', p.key, e.target.value)}
                    className="w-[72px] px-1.5 py-1 text-xs font-mono rounded border border-border bg-card text-text-h text-left focus:border-accent focus:outline-none"
                    dir="ltr"
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