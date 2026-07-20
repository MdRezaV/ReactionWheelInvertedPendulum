import { fmtTime, fmtBytes } from '../utils/format'

const MODE_LABELS = {
  none: 'بدون کنترل',
  pid: 'تعادل PID',
  lqr: 'تعادل LQR',
  energy_swing_up: 'نوسان انرژی',
  sliding_mode: 'مد لغزشی',
  manual: 'گشتاور دستی',
}

const STATUS_LABELS = {
  stopped: 'متوقف',
  running: 'در حال اجرا',
  paused: 'مکث',
}

const STATUS_COLORS = {
  running: 'text-success',
  paused: 'text-warning',
  stopped: 'text-text-dim',
}

export default function StatusBar({ status, connected, warnings, fps, bytesPerSec, msgsPerSec }) {
  const statusText = status ? STATUS_LABELS[status.status] || status.status : '—'
  const modeText = status ? MODE_LABELS[status.control_mode] || status.control_mode : '—'
  const timeText = status ? fmtTime(status.time) : '0:00.000'
  const clientCount = status ? status.client_count : 0
  const statusColor = STATUS_COLORS[status?.status] || 'text-text-dim'

  return (
    <div className="flex items-center gap-5 px-6 py-2 border-b border-border text-[13px] flex-shrink-0 flex-wrap bg-surface/60 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-success shadow-[0_0_6px_#4caf50]' : 'bg-danger shadow-[0_0_6px_#f44336]'}`} />
        <span className={connected ? 'text-success' : 'text-danger'}>
          {connected ? 'متصل' : 'قطع'}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-text-dim">شبیه‌سازی:</span>
        <span className={`font-medium ${statusColor}`}>{statusText}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-text-dim">زمان:</span>
        <span className="font-mono text-text-h">{timeText}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-text-dim">حالت:</span>
        <span className="text-text-h font-medium">{modeText}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-text-dim">کلاینت:</span>
        <span className="text-text-h">{clientCount}</span>
      </div>
      {status?.speed_multiplier && status.speed_multiplier !== 1.0 && (
        <div className="flex items-center gap-1.5">
          <span className="text-text-dim">سرعت:</span>
          <span className="text-text-h">{status.speed_multiplier.toFixed(1)}×</span>
        </div>
      )}
      <div className="flex items-center gap-1.5">
        <span className="text-text-dim">فریم:</span>
        <span className={`font-mono ${fps < 30 ? 'text-warning' : 'text-text-h'}`}>{fps}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-text-dim">شبکه:</span>
        <span className="font-mono text-text-h">{fmtBytes(bytesPerSec)}/s</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-text-dim">پیام:</span>
        <span className="font-mono text-text-h">{msgsPerSec}/s</span>
      </div>
      {warnings && warnings.length > 0 && (
        <div className="flex items-center gap-1.5 text-warning text-xs">
          <span>⚠ {warnings[0]}</span>
        </div>
      )}
    </div>
  )
}