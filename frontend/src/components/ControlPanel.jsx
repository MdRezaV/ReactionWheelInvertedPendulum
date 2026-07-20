import { useState } from 'react'

const CONTROL_MODES = [
  { value: 'none', label: 'بدون کنترل' },
  { value: 'pid', label: 'تعادل PID' },
  { value: 'lqr', label: 'تعادل LQR' },
  { value: 'energy_swing_up', label: 'نوسان انرژی' },
  { value: 'sliding_mode', label: 'مد لغزشی' },
  { value: 'manual', label: 'گشتاور دستی' },
]

const SIM_PARAMS = [
  { key: 'pendulum_mass', label: 'جرم پاندول', unit: 'کیلوگرم', min: 0.1, max: 5, step: 0.1 },
  { key: 'pendulum_length', label: 'طول پاندول', unit: 'متر', min: 0.1, max: 2, step: 0.05 },
  { key: 'wheel_mass', label: 'جرم چرخ', unit: 'کیلوگرم', min: 0.05, max: 2, step: 0.05 },
  { key: 'wheel_radius', label: 'شعاع چرخ', unit: 'متر', min: 0.01, max: 0.2, step: 0.005 },
  { key: 'damping', label: 'میرایی', unit: 'نیوتن·متر·ثانیه', min: 0, max: 0.5, step: 0.005 },
  { key: 'wheel_damping', label: 'میرایی چرخ', unit: 'نیوتن·متر·ثانیه', min: 0, max: 0.1, step: 0.001 },
  { key: 'gravity', label: 'گرانش', unit: 'متر/ثانیه²', min: 1, max: 20, step: 0.1 },
  { key: 'max_voltage', label: 'حداکثر ولتاژ', unit: 'ولت', min: 1, max: 48, step: 1 },
  { key: 'motor_resistance', label: 'مقاومت موتور', unit: 'اهم', min: 0.1, max: 20, step: 0.1 },
  { key: 'motor_inductance', label: 'القای موتور', unit: 'هانری', min: 0.0001, max: 0.1, step: 0.0001 },
  { key: 'motor_constant', label: 'ثابت موتور', unit: 'نیوتن·متر/آمپر', min: 0.001, max: 0.5, step: 0.001 },
  { key: 'motor_rotor_inertia', label: 'اینرسی روتور', unit: 'کیلوگرم·متر²', min: 1e-6, max: 0.01, step: 1e-6 },
  { key: 'motor_viscous_friction', label: 'اصطکاک ویسکوز', unit: 'نیوتن·متر·ثانیه', min: 0, max: 0.01, step: 0.0001 },
  { key: 'gear_ratio', label: 'نسبت چرخ‌دنده', unit: '—', min: 1, max: 100, step: 1 },
  { key: 'time_step', label: 'گام زمانی', unit: 'ثانیه', min: 0.0005, max: 0.01, step: 0.0005 },
]

const CTRL_PARAMS = [
  { key: 'pid_kp', label: 'بهره تناسبی PID', min: 0, max: 200, step: 1 },
  { key: 'pid_ki', label: 'بهره انتگرالی PID', min: 0, max: 10, step: 0.05 },
  { key: 'pid_kd', label: 'بهره مشتقی PID', min: 0, max: 50, step: 0.5 },
  { key: 'lqr_q_theta', label: 'وزن زاویه LQR', min: 0, max: 500, step: 5 },
  { key: 'lqr_q_theta_dot', label: 'وزن سرعت پاندول LQR', min: 0, max: 50, step: 0.5 },
  { key: 'lqr_q_phi_dot', label: 'وزن سرعت چرخ LQR', min: 0, max: 100, step: 1 },
  { key: 'lqr_r', label: 'وزن ورودی LQR', min: 0.01, max: 10, step: 0.1 },
  { key: 'lqr_q_current', label: 'وزن جریان LQR', min: 0, max: 10, step: 0.01 },
  { key: 'energy_swing_up_gain', label: 'بهره نوسان انرژی', min: 0.1, max: 10, step: 0.1 },
  { key: 'smc_c1', label: 'ضریب سطح لغزش ۱', min: 0.1, max: 50, step: 0.5 },
  { key: 'smc_c2', label: 'ضریب سطح لغزش ۲', min: 0.1, max: 30, step: 0.5 },
  { key: 'smc_c3', label: 'ضریب سطح لغزش ۳', min: 0, max: 10, step: 0.1 },
  { key: 'smc_k', label: 'بهره رسیدن SMC', min: 0.1, max: 10, step: 0.1 },
  { key: 'smc_eta', label: 'نرخ همگرایی SMC', min: 0, max: 5, step: 0.1 },
  { key: 'smc_boundary', label: 'مرز پیوستگی SMC', min: 0.01, max: 0.5, step: 0.01 },
]

const TABS = [
  { id: 'controls', label: 'کنترل' },
  { id: 'sim-params', label: 'فیزیک' },
  { id: 'ctrl-params', label: 'بهره‌ها' },
]

export default function ControlPanel({
  status, params, onStart, onStop, onReset, onStep,
  onSetMode, onSetManualVoltage, onUpdateParams, onDisturbance, onSetSpeed,
}) {
  const [activeTab, setActiveTab] = useState('controls')
  const [manualTorque, setManualTorque] = useState(0)
  const [speed, setSpeed] = useState(1.0)

  const isRunning = status?.status === 'running'
  const isStopped = status?.status === 'stopped'

  const handleParamChange = (scope, key, value) => {
    const numVal = parseFloat(value)
    if (Number.isNaN(numVal)) return
    onUpdateParams({ [scope]: { [key]: numVal } })
  }

  const btn = 'px-2.5 py-1.5 text-[12px] font-medium rounded-md border transition-all duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.96]'

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-border bg-surface/60">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 px-1 text-[11px] font-bold border-b-2 transition-all duration-150 cursor-pointer
              ${activeTab === tab.id
                ? 'text-accent border-accent bg-accent-dim/20'
                : 'text-text-dim border-transparent hover:text-text'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'controls' && (
        <div className="p-3 flex flex-col gap-3 overflow-y-auto flex-1">
          <div className="grid grid-cols-3 gap-1.5">
            <button onClick={onStart} disabled={isRunning} className={`${btn} border-success/30 text-success bg-success/5`}>شروع</button>
            <button onClick={onStop} disabled={isStopped} className={`${btn} border-danger/30 text-danger bg-danger/5`}>توقف</button>
            <button onClick={onReset} className={`${btn} border-warning/30 text-warning bg-warning/5`}>بازنشانی</button>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            <button onClick={() => onStep(1)} className={`${btn} border-teal/30 text-teal bg-teal/5`}>یک گام</button>
            <button onClick={() => onStep(10)} className={`${btn} border-teal/30 text-teal bg-teal/5`}>ده گام</button>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-dim font-bold">حالت کنترل</label>
            <select
              value={status?.control_mode || 'none'}
              onChange={(e) => onSetMode(e.target.value)}
              className="px-2.5 py-1.5 text-[12px] rounded-md border border-border bg-card text-text-h cursor-pointer focus:border-accent focus:outline-none transition-colors"
            >
              {CONTROL_MODES.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          {status?.control_mode === 'manual' && (
            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-text-dim font-bold">
                ولتاژ دستی: <span className="text-accent font-mono">{manualTorque.toFixed(1)} ولت</span>
              </label>
              <input
                type="range" min={-12} max={12} step={0.1} value={manualTorque}
                onChange={(e) => { const v = parseFloat(e.target.value); setManualTorque(v); onSetManualVoltage(v) }}
              />
            </div>
          )}

          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-dim font-bold">
              سرعت شبیه‌سازی: <span className="text-accent font-mono">{speed.toFixed(1)} برابر</span>
            </label>
            <input
              type="range" min={0.1} max={5} step={0.1} value={speed}
              onChange={(e) => { const v = parseFloat(e.target.value); setSpeed(v); onSetSpeed(v) }}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-dim font-bold">اغتشاش</label>
            <div className="grid grid-cols-4 gap-1">
              <button onClick={() => onDisturbance(6, 20)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[11px]`}>+۶ ولت</button>
              <button onClick={() => onDisturbance(-6, 20)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[11px]`}>−۶ ولت</button>
              <button onClick={() => onDisturbance(12, 10)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[11px]`}>+۱۲ ولت</button>
              <button onClick={() => onDisturbance(-12, 10)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[11px]`}>−۱۲ ولت</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'sim-params' && (
        <div className="p-3 flex flex-col gap-2 overflow-y-auto flex-1">
          {SIM_PARAMS.map((p) => {
            const val = params?.simulation?.[p.key] ?? p.min
            return (
              <div key={p.key} className="flex flex-col gap-0.5">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] text-text-dim">{p.label}</label>
                  <span className="text-[10px] text-text-dim/60">{p.unit}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <input
                    type="range" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('simulation', p.key, e.target.value)}
                    className="flex-1"
                  />
                  <input
                    type="number" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('simulation', p.key, e.target.value)}
                    className="w-[60px] px-1 py-0.5 text-[11px] font-mono rounded border border-border bg-card text-text-h text-left focus:border-accent focus:outline-none"
                    dir="ltr"
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {activeTab === 'ctrl-params' && (
        <div className="p-3 flex flex-col gap-2 overflow-y-auto flex-1">
          {CTRL_PARAMS.map((p) => {
            const val = params?.control?.[p.key] ?? p.min
            return (
              <div key={p.key} className="flex flex-col gap-0.5">
                <label className="text-[11px] text-text-dim">{p.label}</label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="range" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('control', p.key, e.target.value)}
                    className="flex-1"
                  />
                  <input
                    type="number" min={p.min} max={p.max} step={p.step} value={val}
                    onChange={(e) => handleParamChange('control', p.key, e.target.value)}
                    className="w-[60px] px-1 py-0.5 text-[11px] font-mono rounded border border-border bg-card text-text-h text-left focus:border-accent focus:outline-none"
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