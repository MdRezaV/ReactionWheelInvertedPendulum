import { fmtTime, fmtBytes, toPersianDigits } from '../utils/format'

const MODE_LABELS = {
  none: 'بدون کنترل',
  pid: 'تعادل PID',
  lqr: 'تعادل LQR',
  energy_swing_up: 'نوسان انرژی',
  sliding_mode: 'مد لغزشی',
  manual: 'ورودی دستی',
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
  const timeText = status ? fmtTime(status.time) : '۰:۰۰'
  const clientCount = status ? status.client_count : 0
  const statusColor = STATUS_COLORS[status?.status] || 'text-text-dim'

  return (
    <header className="flex items-center gap-4 px-4 py-2 border-b border-border flex-shrink-0 bg-surface/70 backdrop-blur-md text-[14px]">
      <h1 className="text-[15px] font-bold text-text-h tracking-tight whitespace-nowrap">
        پاندول معکوس چرخ عکس‌العملی
      </h1>

      <div className="w-px h-4 bg-border" />

      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-success shadow-[0_0_5px_#6fcf97]' : 'bg-danger shadow-[0_0_5px_#eb5757]'}`} />
        <span className={connected ? 'text-success' : 'text-danger'}>
          {connected ? 'متصل' : 'قطع'}
        </span>
      </div>

      <div className="w-px h-4 bg-border" />

      <span className={`font-semibold ${statusColor}`}>{statusText}</span>
      <span className="font-mono text-text-h">{timeText}</span>
      <span className="text-accent font-medium">{modeText}</span>

      {status?.speed_multiplier && status.speed_multiplier !== 1.0 && (
        <span className="text-warning font-mono">{toPersianDigits(status.speed_multiplier < 0.01 ? status.speed_multiplier.toFixed(3) : status.speed_multiplier < 0.1 ? status.speed_multiplier.toFixed(2) : status.speed_multiplier.toFixed(1))} برابر</span>
      )}

      <div className="flex-1" />

      <div className="flex items-center gap-3 text-text-dim text-[13px]">
        <span>{toPersianDigits(fps)} فریم</span>
        <span>{fmtBytes(bytesPerSec)}/ثانیه</span>
        <span>{toPersianDigits(msgsPerSec)} پیام/ثانیه</span>
        <span>{toPersianDigits(clientCount)} کلاینت</span>
      </div>

      {warnings && warnings.length > 0 && (
        <span className="text-warning text-[13px]">هشدار: {warnings[0]}</span>
      )}
    </header>
  )
}