#!/usr/bin/env python3
"""Optimal LQR and PID gain computation for the reaction wheel inverted pendulum.

Computes:
  1. LQR optimal gains via the continuous algebraic Riccati equation (CARE).
  2. PID gains optimized by minimizing the ITAE cost over a full nonlinear
     5-state simulation (Nelder–Mead).

Generates step-response plots and saves them to ``latex/results/``.

Usage (from the project root):
    uv run --with numpy --with scipy --with matplotlib scripts/optimal_gains.py
"""

from __future__ import annotations

import os

import numpy as np
from scipy.linalg import solve_continuous_are
from scipy.optimize import minimize

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── System parameters (defaults from backend/config.py) ─────────────

PENDULUM_MASS       = 0.4        # kg
PENDULUM_LENGTH     = 0.3        # m
WHEEL_MASS          = 0.25       # kg
WHEEL_INNER_RADIUS  = 0.02       # m
WHEEL_OUTER_RADIUS  = 0.07       # m
DAMPING             = 0.001      # N·m·s/rad
WHEEL_DAMPING       = 0.0005     # N·m·s/rad
GRAVITY             = 9.81       # m/s²
TIME_STEP           = 0.001      # s
MAX_VOLTAGE         = 12.0       # V
MOTOR_RESISTANCE    = 1.2        # Ω
MOTOR_INDUCTANCE    = 0.0005     # H
MOTOR_CONSTANT      = 0.0876     # N·m/A  (= V·s/rad)
MOTOR_ROTOR_INERTIA = 5e-5       # kg·m²
MOTOR_VISCOUS_FRICTION = 0.001   # N·m·s/rad
GEAR_RATIO          = 4.0        # –

# ── Derived quantities ──────────────────────────────────────────────

L_COM   = PENDULUM_LENGTH / 2.0
I_P     = (1.0 / 3.0) * PENDULUM_MASS * PENDULUM_LENGTH ** 2
I_W     = 0.5 * WHEEL_MASS * (WHEEL_OUTER_RADIUS ** 2 + WHEEL_INNER_RADIUS ** 2)
I_W_EFF = I_W + MOTOR_ROTOR_INERTIA * GEAR_RATIO ** 2
B_W_EFF = WHEEL_DAMPING + GEAR_RATIO ** 2 * MOTOR_VISCOUS_FRICTION

M11   = I_P + WHEEL_MASS * PENDULUM_LENGTH ** 2 + I_W_EFF
M12   = I_W_EFF
M22   = I_W_EFF
DET_M = M11 * M22 - M12 ** 2

GRAVITY_COEFF = (PENDULUM_MASS * L_COM + WHEEL_MASS * PENDULUM_LENGTH) * GRAVITY

KT = MOTOR_CONSTANT
KE = MOTOR_CONSTANT
N  = GEAR_RATIO
RA = MOTOR_RESISTANCE
LA = MOTOR_INDUCTANCE
B  = DAMPING


# ── Nonlinear dynamics ──────────────────────────────────────────────

def nonlinear_dynamics(state: np.ndarray, voltage: float) -> np.ndarray:
    """Full 5-state dynamics: [θ, θ̇, φ, φ̇, i_a]."""
    theta, theta_dot, _phi, phi_dot, i_a = state
    V = np.clip(voltage, -MAX_VOLTAGE, MAX_VOLTAGE)

    tau_w = N * KT * i_a

    f1 = GRAVITY_COEFF * np.sin(theta) - tau_w - B * theta_dot
    f2 = tau_w - B_W_EFF * phi_dot

    theta_ddot = (M22 * f1 - M12 * f2) / DET_M
    phi_ddot   = (M11 * f2 - M12 * f1) / DET_M
    di_a       = (V - RA * i_a - KE * N * phi_dot) / LA

    return np.array([theta_dot, theta_ddot, phi_dot, phi_ddot, di_a])


def rk4_step(state: np.ndarray, voltage: float, dt: float) -> np.ndarray:
    """Single classical RK4 step."""
    k1 = nonlinear_dynamics(state, voltage)
    k2 = nonlinear_dynamics(state + 0.5 * dt * k1, voltage)
    k3 = nonlinear_dynamics(state + 0.5 * dt * k2, voltage)
    k4 = nonlinear_dynamics(state + dt * k3, voltage)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def wrap_angle(a: float) -> float:
    return (a + np.pi) % (2.0 * np.pi) - np.pi


# ── LQR ─────────────────────────────────────────────────────────────

def build_lqr_matrices() -> tuple[np.ndarray, np.ndarray]:
    """Linearized (A, B) for state [θ, θ̇, φ̇, i_a], input V."""
    A = np.array([
        [0.0, 1.0, 0.0, 0.0],
        [
            M22 * GRAVITY_COEFF / DET_M,
            -M22 * B / DET_M,
            M12 * B_W_EFF / DET_M,
            -(M22 + M12) * N * KT / DET_M,
        ],
        [
            -M12 * GRAVITY_COEFF / DET_M,
            M12 * B / DET_M,
            -M11 * B_W_EFF / DET_M,
            (M11 + M12) * N * KT / DET_M,
        ],
        [0.0, 0.0, -KE * N / LA, -RA / LA],
    ], dtype=np.float64)

    B_mat = np.array([[0.0], [0.0], [0.0], [1.0 / LA]], dtype=np.float64)
    return A, B_mat


def compute_lqr_gains(
    q_diag: list[float], r: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Solve CARE and return (K, A, B, P)."""
    A, B_mat = build_lqr_matrices()
    Q = np.diag(q_diag).astype(np.float64)
    R = np.array([[r]], dtype=np.float64)

    P = solve_continuous_are(A, B_mat, Q, R)
    K = np.linalg.solve(R, B_mat.T @ P).flatten()
    return K, A, B_mat, P


def simulate_lqr(
    K: np.ndarray, theta0: float, duration: float, dt: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate the nonlinear plant under LQR state feedback."""
    steps = int(duration / dt)
    t = np.arange(steps) * dt
    states = np.zeros((steps, 5))
    voltages = np.zeros(steps)

    state = np.array([theta0, 0.0, 0.0, 0.0, 0.0])

    for i in range(steps):
        x_lqr = np.array([state[0], state[1], state[3], state[4]])
        V = float(np.clip(-K @ x_lqr, -MAX_VOLTAGE, MAX_VOLTAGE))

        states[i] = state
        voltages[i] = V

        state = rk4_step(state, V, dt)
        state[0] = wrap_angle(state[0])
        state[2] = wrap_angle(state[2])

    return t, states, voltages


# ── PID ─────────────────────────────────────────────────────────────

def simulate_pid(
    kp: float, ki: float, kd: float,
    theta0: float, duration: float, dt: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate the nonlinear plant under PID with clamping anti-windup."""
    steps = int(duration / dt)
    t = np.arange(steps) * dt
    states = np.zeros((steps, 5))
    voltages = np.zeros(steps)

    state = np.array([theta0, 0.0, 0.0, 0.0, 0.0])
    integral = 0.0

    for i in range(steps):
        theta, theta_dot = state[0], state[1]

        output = kp * theta + ki * integral + kd * theta_dot

        if abs(output) < MAX_VOLTAGE:
            integral += theta * dt
        elif (output > 0 and theta < 0) or (output < 0 and theta > 0):
            integral += theta * dt

        V = float(np.clip(kp * theta + ki * integral + kd * theta_dot,
                          -MAX_VOLTAGE, MAX_VOLTAGE))

        states[i] = state
        voltages[i] = V

        state = rk4_step(state, V, dt)
        state[0] = wrap_angle(state[0])
        state[2] = wrap_angle(state[2])

    return t, states, voltages


def itae_cost(params: np.ndarray, theta0: float, duration: float, dt: float) -> float:
    """ITAE cost for a PID candidate: ∫ t·|θ(t)| dt."""
    kp, ki, kd = params
    if kp < 0.0 or ki < 0.0 or kd < 0.0:
        return 1e10
    try:
        t, states, _ = simulate_pid(kp, ki, kd, theta0, duration, dt)
        theta = states[:, 0]
        cost = float(np.sum(t * np.abs(theta)) * dt)
        return cost if np.isfinite(cost) else 1e10
    except Exception:
        return 1e10


def optimize_pid(
    theta0: float = 0.1,
    duration: float = 5.0,
    dt: float = 0.001,
) -> tuple[np.ndarray, float]:
    """Nelder–Mead optimization of (Kp, Ki, Kd) minimizing ITAE."""
    x0 = np.array([50.0, 0.1, 10.0])
    result = minimize(
        itae_cost, x0,
        args=(theta0, duration, dt),
        method="Nelder-Mead",
        options={"maxiter": 300, "xatol": 0.05, "fatol": 1e-5},
    )
    return result.x, result.fun


# ── Plotting ────────────────────────────────────────────────────────

def plot_lqr_response(
    t: np.ndarray, states: np.ndarray, voltages: np.ndarray,
    K: np.ndarray, save_path: str,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(t, np.degrees(states[:, 0]), "b-", linewidth=1.2)
    axes[0].set_ylabel(r"$\theta$ [deg]")
    axes[0].set_title(
        f"LQR Step Response   "
        rf"$K=[{K[0]:.2f},\;{K[1]:.2f},\;{K[2]:.2f},\;{K[3]:.2f}]$"
    )
    axes[0].grid(True, alpha=0.3)
    axes[0].axhline(0, color="k", linewidth=0.5)

    axes[1].plot(t, voltages, "r-", linewidth=1.0)
    axes[1].set_ylabel("Voltage [V]")
    axes[1].set_xlabel("Time [s]")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_pid_response(
    t: np.ndarray, states: np.ndarray, voltages: np.ndarray,
    gains: np.ndarray, cost: float, save_path: str,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(t, np.degrees(states[:, 0]), "g-", linewidth=1.2)
    axes[0].set_ylabel(r"$\theta$ [deg]")
    axes[0].set_title(
        f"Optimized PID Step Response   "
        rf"$K_p\!=\!{gains[0]:.2f},\;K_i\!=\!{gains[1]:.4f},\;K_d\!=\!{gains[2]:.2f}$"
        f"   (ITAE = {cost:.4f})"
    )
    axes[0].grid(True, alpha=0.3)
    axes[0].axhline(0, color="k", linewidth=0.5)

    axes[1].plot(t, voltages, "r-", linewidth=1.0)
    axes[1].set_ylabel("Voltage [V]")
    axes[1].set_xlabel("Time [s]")
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_comparison(
    t_lqr: np.ndarray, states_lqr: np.ndarray,
    t_pid: np.ndarray, states_pid: np.ndarray,
    save_path: str,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(t_lqr, np.degrees(states_lqr[:, 0]), "b-",
                 label="LQR", linewidth=1.2)
    axes[0].plot(t_pid, np.degrees(states_pid[:, 0]), "g--",
                 label="PID (optimized)", linewidth=1.2)
    axes[0].set_ylabel(r"$\theta$ [deg]")
    axes[0].set_title("LQR vs. Optimized PID — Pendulum Angle")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(t_lqr, np.degrees(states_lqr[:, 3]), "b-",
                 label="LQR", linewidth=1.0)
    axes[1].plot(t_pid, np.degrees(states_pid[:, 3]), "g--",
                 label="PID (optimized)", linewidth=1.0)
    axes[1].set_ylabel(r"$\dot{\varphi}$ [deg/s]")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_title("Wheel Angular Velocity")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Main ────────────────────────────────────────────────────────────

def main() -> None:
    results_dir = os.path.join("latex", "results")
    os.makedirs(results_dir, exist_ok=True)

    theta0   = 0.1       # initial displacement [rad] ≈ 5.7°
    duration = 5.0       # simulation horizon [s]
    dt       = TIME_STEP

    lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    # ── LQR ──
    log("=" * 60)
    log("  LQR Optimal Gain Computation")
    log("=" * 60)

    q_diag = [100.0, 1.0, 10.0, 0.01]
    r_lqr  = 1.0

    K, A, B_mat, P = compute_lqr_gains(q_diag, r_lqr)
    A_cl = A - B_mat @ K.reshape(1, -1)
    poles = np.linalg.eigvals(A_cl)

    log(f"  Q  = diag({q_diag})")
    log(f"  R  = {r_lqr}")
    log(f"  K  = [{K[0]:.6f},  {K[1]:.6f},  {K[2]:.6f},  {K[3]:.6f}]")
    log("  Closed-loop poles:")
    for p in poles:
        log(f"    {p.real:+.4f} {p.imag:+.4f}j")
    log()

    t_lqr, states_lqr, voltages_lqr = simulate_lqr(K, theta0, duration, dt)

    # ── PID optimisation ──
    log("=" * 60)
    log("  PID Gain Optimization  (ITAE, Nelder–Mead)")
    log("=" * 60)
    log(f"  Initial guess : Kp=50, Ki=0.1, Kd=10")
    log(f"  θ₀ = {theta0} rad, T = {duration} s, dt = {dt} s")
    log("  Optimizing …")

    pid_gains, pid_cost = optimize_pid(theta0=theta0, duration=duration, dt=dt)

    log(f"  Optimal Kp = {pid_gains[0]:.4f}")
    log(f"  Optimal Ki = {pid_gains[1]:.6f}")
    log(f"  Optimal Kd = {pid_gains[2]:.4f}")
    log(f"  ITAE cost  = {pid_cost:.6f}")
    log()

    t_pid, states_pid, voltages_pid = simulate_pid(
        pid_gains[0], pid_gains[1], pid_gains[2], theta0, duration, dt,
    )

    # ── Plots ──
    log("Generating plots …")

    p1 = os.path.join(results_dir, "lqr_step_response.png")
    plot_lqr_response(t_lqr, states_lqr, voltages_lqr, K, p1)
    log(f"  {p1}")

    p2 = os.path.join(results_dir, "pid_step_response.png")
    plot_pid_response(t_pid, states_pid, voltages_pid, pid_gains, pid_cost, p2)
    log(f"  {p2}")

    p3 = os.path.join(results_dir, "lqr_vs_pid_comparison.png")
    plot_comparison(t_lqr, states_lqr, t_pid, states_pid, p3)
    log(f"  {p3}")

    log()
    log("Done.")

    # ── Save text output ──
    txt_path = os.path.join(results_dir, "gain_results.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nText output saved to {txt_path}")


if __name__ == "__main__":
    main()