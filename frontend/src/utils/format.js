/**
 * Formatting utilities for display values.
 */

/**
 * Format a number to a fixed number of decimal places.
 */
export function fmt(value, decimals = 3) {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(decimals)
}

/**
 * Format simulation time as mm:ss.mmm
 */
export function fmtBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function fmtTime(seconds) {
  if (seconds == null) return '0:00.000'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toFixed(3).padStart(6, '0')}`
}

/**
 * Format a torque value with unit.
 */
export function fmtTorque(value) {
  return `${fmt(value, 3)} نیوتن·متر`
}

/**
 * Format an angle (radians input) as degrees.
 */
export function fmtAngle(rad) {
  const deg = (rad * 180) / Math.PI
  return `${fmt(deg, 2)}°`
}

/**
 * Format a voltage value with unit.
 */
export function fmtVoltage(value) {
  return `${fmt(value, 2)} ولت`
}

/**
 * Format a current value with unit.
 */
export function fmtCurrent(value) {
  return `${fmt(value, 3)} آمپر`
}