/**
 * Formatting utilities for display values.
 */

const PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

/**
 * Convert all Western digits in a string to Persian digits.
 */
export function toPersianDigits(str) {
  return String(str).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[parseInt(d)])
}

/**
 * Format a number to a fixed number of decimal places (Persian digits).
 */
export function fmt(value, decimals = 3) {
  if (value == null || Number.isNaN(value)) return '—'
  return toPersianDigits(value.toFixed(decimals))
}

/**
 * Format simulation time as mm:ss.mmm
 */
export function fmtBytes(bytes) {
  if (bytes < 1024) return `${toPersianDigits(bytes)} بایت`
  if (bytes < 1024 * 1024) return `${toPersianDigits((bytes / 1024).toFixed(1))} کیلوبایت`
  return `${toPersianDigits((bytes / (1024 * 1024)).toFixed(2))} مگابایت`
}

export function fmtTime(seconds) {
  if (seconds == null) return '۰:۰۰.۰۰۰'
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return toPersianDigits(`${mins}:${secs.toFixed(3).padStart(6, '0')}`)
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