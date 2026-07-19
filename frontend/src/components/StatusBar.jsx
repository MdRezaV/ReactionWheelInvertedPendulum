import { fmtTime } from '../utils/format'

const MODE_LABELS = {
  none: 'No Control',
  pid: 'PID Balance',
  lqr: 'LQR Balance',
  energy_swing_up: 'Energy Swing-Up',
  sliding_mode: 'Sliding Mode',
  manual: 'Manual Torque',
}

const STATUS_LABELS = {
  stopped: 'Stopped',
  running: 'Running',
  paused: 'Paused',
}

export default function StatusBar({ status, connected, warnings }) {
  const statusText = status ? STATUS_LABELS[status.status] || status.status : '—'
  const modeText = status ? MODE_LABELS[status.control_mode] || status.control_mode : '—'
  const timeText = status ? fmtTime(status.time) : '0:00.000'
  const clientCount = status ? status.client_count : 0

  return (
    <div className="status-bar">
      <div className="status-item">
        <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
        <span>{connected ? 'Connected' : 'Disconnected'}</span>
      </div>
      <div className="status-item">
        <span className="status-label">Sim:</span>
        <span className={`status-value status-${status?.status || 'stopped'}`}>{statusText}</span>
      </div>
      <div className="status-item">
        <span className="status-label">Time:</span>
        <span className="status-value mono">{timeText}</span>
      </div>
      <div className="status-item">
        <span className="status-label">Mode:</span>
        <span className="status-value">{modeText}</span>
      </div>
      <div className="status-item">
        <span className="status-label">Clients:</span>
        <span className="status-value">{clientCount}</span>
      </div>
      {status?.speed_multiplier && status.speed_multiplier !== 1.0 && (
        <div className="status-item">
          <span className="status-label">Speed:</span>
          <span className="status-value">{status.speed_multiplier.toFixed(1)}×</span>
        </div>
      )}
      {warnings && warnings.length > 0 && (
        <div className="status-item status-warning">
          <span>⚠ {warnings[0]}</span>
        </div>
      )}
    </div>
  )
}