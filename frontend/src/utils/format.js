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
  return `${fmt(value, 3)} N·m`
}

/**
 * Format an angle in radians with degree equivalent.
 */
export function fmtAngle(rad) {
  const deg = (rad * 180) / Math.PI
  return `${fmt(rad, 4)} rad (${fmt(deg, 1)}°)`
}