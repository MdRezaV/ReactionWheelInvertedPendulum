import { useCallback, useEffect, useRef, useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import * as Select from '@radix-ui/react-select'
import * as Slider from '@radix-ui/react-slider'
import { toPersianDigits, toWesternDigits } from '../utils/format'

const CONTROL_MODES = [
  { value: 'none', label: 'بدون کنترل' },
  { value: 'pid', label: 'تعادل PID' },
  { value: 'lqr', label: 'تعادل LQR' },
  { value: 'energy_swing_up', label: 'نوسان انرژی' },
  { value: 'sliding_mode', label: 'مد لغزشی' },
  { value: 'manual', label: 'ورودی دستی' },
]

const SIM_PARAMS = [
  { key: 'pendulum_mass', label: 'جرم پاندول', unit: 'کیلوگرم', min: 0.1, max: 5, step: 0.1 },
  { key: 'pendulum_length', label: 'طول پاندول', unit: 'متر', min: 0.1, max: 2, step: 0.05 },
  { key: 'wheel_mass', label: 'جرم چرخ', unit: 'کیلوگرم', min: 0.05, max: 2, step: 0.05 },
  { key: 'wheel_inner_radius', label: 'شعاع داخلی چرخ', unit: 'متر', min: 0.001, max: 0.2, step: 0.001 },
  { key: 'wheel_outer_radius', label: 'شعاع خارجی چرخ', unit: 'متر', min: 0.01, max: 0.2, step: 0.005 },
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

function roundToStep(value, step) {
  const decimals = (String(step).split('.')[1] || '').length
  return parseFloat(value.toFixed(decimals))
}

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
  const speedSliderVal = Math.log10(Math.max(speed, 0.001))
  const [selectedMode, setSelectedMode] = useState(status?.control_mode || 'none')

  useEffect(() => {
    if (status?.control_mode) {
      setSelectedMode(status.control_mode)
    }
  }, [status?.control_mode])

  const isRunning = status?.status === 'running'
  const isStopped = status?.status === 'stopped'

  const [localOverrides, setLocalOverrides] = useState({})

  useEffect(() => {
    setLocalOverrides({})
  }, [params])

  const debounceRef = useRef(null)
  const pendingRef = useRef({})

  const handleParamChange = useCallback((scope, key, value) => {
    const numVal = parseFloat(value)
    if (Number.isNaN(numVal)) return
    setLocalOverrides(prev => ({ ...prev, [key]: numVal }))

    if (!pendingRef.current[scope]) pendingRef.current[scope] = {}
    pendingRef.current[scope][key] = numVal

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const payload = {}
      if (pendingRef.current.simulation) {
        payload.simulation = { ...(params?.simulation || {}), ...pendingRef.current.simulation }
      }
      if (pendingRef.current.control) {
        payload.control = { ...(params?.control || {}), ...pendingRef.current.control }
      }
      onUpdateParams(payload)
      pendingRef.current = {}
    }, 100)
  }, [onUpdateParams, params])

  const btn = 'px-2.5 py-1.5 text-[14px] font-medium rounded-md border transition-all duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed hover:brightness-110 active:scale-[0.96]'

  return (
    <div className="flex flex-col h-full">
              <Tabs.Root value={activeTab} onValueChange={setActiveTab} dir="rtl" className="flex flex-col h-full">
        <Tabs.List className="flex border-b border-border bg-surface/60">
          {TABS.map((tab) => (
            <Tabs.Trigger
              key={tab.id}
              value={tab.id}
              className="flex-1 py-2 px-1 text-[13px] font-bold border-b-2 border-transparent text-text-dim transition-all duration-150 cursor-pointer hover:text-text data-[state=active]:text-accent data-[state=active]:border-accent data-[state=active]:bg-accent-dim/20 focus:outline-none focus-visible:ring-1 focus-visible:ring-accent"
            >
              {tab.label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="controls" className="p-3 flex flex-col gap-3 overflow-y-auto flex-1 focus:outline-none">
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
            <label className="text-[13px] text-text-dim font-bold">حالت کنترل</label>
            <Select.Root value={selectedMode} onValueChange={(mode) => { setSelectedMode(mode); onSetMode(mode) }} dir="rtl">
              <Select.Trigger className="flex items-center justify-between px-2.5 py-1.5 text-[14px] rounded-md border border-border bg-card text-text-h cursor-pointer focus:border-accent focus:outline-none transition-colors hover:border-border-light">
                <Select.Value />
                <Select.Icon className="text-text-dim">
                  <svg width="10" height="6" viewBox="0 0 10 6" fill="none"><path d="M1 1l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </Select.Icon>
              </Select.Trigger>
              <Select.Portal>
                <Select.Content position="popper" sideOffset={4} className="bg-card border border-border-light rounded-md shadow-card overflow-hidden z-50 animate-[slide-down_150ms_ease-out]">
                  <Select.Viewport className="p-1">
                    {CONTROL_MODES.map((m) => (
                      <Select.Item
                        key={m.value}
                        value={m.value}
                        className="flex items-center px-2.5 py-1.5 text-[14px] rounded-sm text-text cursor-pointer outline-none data-[highlighted]:bg-accent-dim data-[highlighted]:text-accent data-[state=checked]:text-accent"
                      >
                        <Select.ItemText>{m.label}</Select.ItemText>
                        <Select.ItemIndicator className="ms-auto pe-1">
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                        </Select.ItemIndicator>
                      </Select.Item>
                    ))}
                  </Select.Viewport>
                </Select.Content>
              </Select.Portal>
            </Select.Root>
          </div>

          {selectedMode === 'manual' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] text-text-dim font-bold">
                ولتاژ دستی: <span className="text-accent font-mono">{toPersianDigits(manualTorque.toFixed(1))} ولت</span>
              </label>
              <Slider.Root
                value={[manualTorque]}
                min={-12}
                max={12}
                step={0.1}
                onValueChange={([v]) => { setManualTorque(v); onSetManualVoltage(v) }}
                dir="rtl"
                className="relative flex items-center h-4 select-none touch-none"
              >
                <Slider.Track className="relative h-[3px] flex-1 rounded-full bg-border">
                  <Slider.Range className="absolute h-full rounded-full bg-accent" />
                </Slider.Track>
                <Slider.Thumb className="w-3 h-3 rounded-full bg-accent cursor-pointer shadow-[0_0_8px_rgba(86,204,242,0.5)] transition-transform hover:scale-125 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50" />
              </Slider.Root>
            </div>
          )}

          <div className="flex flex-col gap-1">
            <label className="text-[13px] text-text-dim font-bold">
              سرعت شبیه‌سازی: <span className="text-accent font-mono">{toPersianDigits(speed < 0.01 ? speed.toFixed(3) : speed < 0.1 ? speed.toFixed(2) : speed.toFixed(1))} برابر</span>
            </label>
            <Slider.Root
              value={[speedSliderVal]}
              min={-3}
              max={0.699}
              step={0.01}
              onValueChange={([v]) => { const s = Math.pow(10, v); setSpeed(s); onSetSpeed(s) }}
              dir="rtl"
              className="relative flex items-center h-4 select-none touch-none"
            >
              <Slider.Track className="relative h-[3px] flex-1 rounded-full bg-border">
                <Slider.Range className="absolute h-full rounded-full bg-accent" />
              </Slider.Track>
              <Slider.Thumb className="w-3 h-3 rounded-full bg-accent cursor-pointer shadow-[0_0_8px_rgba(86,204,242,0.5)] transition-transform hover:scale-125 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50" />
            </Slider.Root>
            <div className="flex justify-between text-[10px] text-text-dim/50 px-0.5">
              <span>۰٫۰۰۱×</span>
              <span>۱×</span>
              <span>۵×</span>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-[13px] text-text-dim font-bold">اغتشاش</label>
            <div className="grid grid-cols-4 gap-1">
              <button onClick={() => onDisturbance(6, 20)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[13px]`}>+۶ ولت</button>
              <button onClick={() => onDisturbance(-6, 20)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[13px]`}>−۶ ولت</button>
              <button onClick={() => onDisturbance(12, 10)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[13px]`}>+۱۲ ولت</button>
              <button onClick={() => onDisturbance(-12, 10)} className={`${btn} border-purple/30 text-purple bg-purple/5 text-[13px]`}>−۱۲ ولت</button>
            </div>
          </div>
        </Tabs.Content>

        <Tabs.Content value="sim-params" className="p-3 flex flex-col gap-2 overflow-y-auto flex-1 focus:outline-none">
          {SIM_PARAMS.map((p) => {
            const val = localOverrides[p.key] ?? params?.simulation?.[p.key] ?? p.min
            const outerRadius = localOverrides['wheel_outer_radius'] ?? params?.simulation?.wheel_outer_radius ?? 0.05
            const effectiveMax = p.key === 'wheel_inner_radius'
              ? Math.max(p.min, parseFloat(outerRadius) - p.step)
              : p.max
            return (
              <div key={p.key} className="flex flex-col gap-0.5">
                <div className="flex items-center justify-between">
                  <label className="text-[13px] text-text-dim">{p.label}</label>
                  <span className="text-[12px] text-text-dim/60">{p.unit}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Slider.Root
                    value={[val]}
                    min={p.min}
                    max={effectiveMax}
                    step={p.step}
                    onValueChange={([v]) => handleParamChange('simulation', p.key, String(v))}
                    dir="rtl"
                    className="relative flex items-center h-4 flex-1 select-none touch-none"
                  >
                    <Slider.Track className="relative h-[3px] flex-1 rounded-full bg-border">
                      <Slider.Range className="absolute h-full rounded-full bg-accent/60" />
                    </Slider.Track>
                    <Slider.Thumb className="w-3 h-3 rounded-full bg-accent cursor-pointer shadow-[0_0_8px_rgba(86,204,242,0.5)] transition-transform hover:scale-125 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50" />
                  </Slider.Root>
                  <div className="flex items-center gap-0.5">
                    <input
                      type="text"
                      inputMode="decimal"
                      value={toPersianDigits(String(val))}
                      onChange={(e) => handleParamChange('simulation', p.key, toWesternDigits(e.target.value))}
                      className="w-[80px] px-1.5 py-0.5 text-[13px] font-mono rounded border border-border bg-card text-text-h text-center focus:border-accent focus:outline-none"
                      dir="ltr"
                    />
                    <div className="flex flex-col gap-px">
                      <button
                        onClick={() => handleParamChange('simulation', p.key, String(Math.min(roundToStep(val + p.step, p.step), effectiveMax)))}
                        className="w-4 h-3.5 flex items-center justify-center text-[8px] text-text-dim bg-card border border-border rounded-t cursor-pointer hover:text-accent hover:border-accent-border transition-colors leading-none"
                      >▲</button>
                      <button
                        onClick={() => handleParamChange('simulation', p.key, String(Math.max(roundToStep(val - p.step, p.step), p.min)))}
                        className="w-4 h-3.5 flex items-center justify-center text-[8px] text-text-dim bg-card border border-border rounded-b cursor-pointer hover:text-accent hover:border-accent-border transition-colors leading-none"
                      >▼</button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </Tabs.Content>

        <Tabs.Content value="ctrl-params" className="p-3 flex flex-col gap-2 overflow-y-auto flex-1 focus:outline-none">
          {CTRL_PARAMS.map((p) => {
            const val = localOverrides[p.key] ?? params?.control?.[p.key] ?? p.min
            return (
              <div key={p.key} className="flex flex-col gap-0.5">
                <label className="text-[13px] text-text-dim">{p.label}</label>
                <div className="flex items-center gap-1.5">
                  <Slider.Root
                    value={[val]}
                    min={p.min}
                    max={p.max}
                    step={p.step}
                    onValueChange={([v]) => handleParamChange('control', p.key, String(v))}
                    dir="rtl"
                    className="relative flex items-center h-4 flex-1 select-none touch-none"
                  >
                    <Slider.Track className="relative h-[3px] flex-1 rounded-full bg-border">
                      <Slider.Range className="absolute h-full rounded-full bg-accent/60" />
                    </Slider.Track>
                    <Slider.Thumb className="w-3 h-3 rounded-full bg-accent cursor-pointer shadow-[0_0_8px_rgba(86,204,242,0.5)] transition-transform hover:scale-125 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50" />
                  </Slider.Root>
                  <div className="flex items-center gap-0.5">
                    <input
                      type="text"
                      inputMode="decimal"
                      value={toPersianDigits(String(val))}
                      onChange={(e) => handleParamChange('control', p.key, toWesternDigits(e.target.value))}
                      className="w-[80px] px-1.5 py-0.5 text-[13px] font-mono rounded border border-border bg-card text-text-h text-center focus:border-accent focus:outline-none"
                      dir="ltr"
                    />
                    <div className="flex flex-col gap-px">
                      <button
                        onClick={() => handleParamChange('control', p.key, String(Math.min(roundToStep(val + p.step, p.step), p.max)))}
                        className="w-4 h-3.5 flex items-center justify-center text-[8px] text-text-dim bg-card border border-border rounded-t cursor-pointer hover:text-accent hover:border-accent-border transition-colors leading-none"
                      >▲</button>
                      <button
                        onClick={() => handleParamChange('control', p.key, String(Math.max(roundToStep(val - p.step, p.step), p.min)))}
                        className="w-4 h-3.5 flex items-center justify-center text-[8px] text-text-dim bg-card border border-border rounded-b cursor-pointer hover:text-accent hover:border-accent-border transition-colors leading-none"
                      >▼</button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}