/**
 * Math utilities for the pendulum simulation frontend.
 */

/**
 * Clamp a value between min and max.
 */
export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

/**
 * Linear interpolation between a and b by factor t.
 */
export function lerp(a, b, t) {
  return a + (b - a) * t
}

/**
 * Map a value from one range to another.
 */
export function mapRange(value, inMin, inMax, outMin, outMax) {
  return outMin + ((value - inMin) / (inMax - inMin)) * (outMax - outMin)
}

/**
 * Convert radians to degrees.
 */
export function radToDeg(rad) {
  return (rad * 180) / Math.PI
}

/**
 * Convert degrees to radians.
 */
export function degToRad(deg) {
  return (deg * Math.PI) / 180
}