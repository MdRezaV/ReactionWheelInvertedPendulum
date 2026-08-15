#!/usr/bin/env python3
"""Section 2 figures and numerical results for the reaction wheel inverted pendulum.

Generates:
  1. Numerical inertia matrix values (M11, M12, M22, Δ).
  2. Numerical LQR linearized A (4×4) and B (4×1) matrices.
  3. Sliding Mode Controller step response (full 5-state nonlinear plant).
  4. Open-loop (no control) response showing pendulum divergence.
  5. Three-way comparison plot: LQR vs PID vs SMC.
  6. Individual SMC and open-loop plots.

Saves plots to ``latex/results/`` and numerical results to
``latex/results/section2_results.txt``.

Usage (from the project root):
    uv run --with numpy --with scipy --with matplotlib scripts/section2_figures.py
"""

from __future__ import annotations

import os

import numpy as np
from scipy.linalg import solve_continuous_are

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── System parameters (defaults from backend/config.py) ─────────────

PENDULUM_MASS          = 1.0        # kg
PENDULUM_LENGTH        = 0.3        # m
WHEEL_MASS             = 0.25       # kg
WHEEL_INNER_RADIUS     = 0.02       # m
WHEEL_OUTER_RADIUS     = 0.07       # m
DAMPING                = 0.001      # N·m·s/rad
WHEEL_DAMPING          = 0.0005     # N·m·s/rad
GRAVITY                = 9.81       # m/s²
TIME_STEP              = 0.001      # s
MAX_VOLTAGE            = 12.0       # V
MOTOR_RESISTANCE       = 1.2        # Ω
MOTOR_INDUCTANCE       = 0.0005     # H
MOTOR_CONSTANT         = 0.0876     # N·m/A  (= V·s/rad)
MOTOR_ROTOR_INERTIA    = 5e-5       # kg·m²
MOTOR_VISCOUS_FRICTION = 0.001      # N·m·s/rad
GEAR_RATIO             = 1.0        # –

# SMC default parameters (from backend/config.py)
SMC_C1       = 10.0
SMC_C2       = 5.0
SMC_C3       = 1.0
SMC_K        = 2.0
SMC_ETA      = 0.5
SMC_BOUNDARY = 0.05

# Optimized PID gains (from optimal_gains.py results)
PID_KP = 145.23
PID_KI = 8e-6
PID_KD = 0.97

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


# ── LQR matrices ────────────────────────────────────────────────────

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


# ── Simulation helpers ──────────────────────────────────────────────

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


def simulate_smc(
    theta0: float, duration: float, dt: float,
    c1: float = SMC_C1, c2: float = SMC_C2, c3: float = SMC_C3,
    k: float = SMC_K, eta: float = SMC_ETA, boundary: float = SMC_BOUNDARY,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate the nonlinear plant under Sliding Mode Control."""
    steps = int(duration / dt)
    t = np.arange(steps) * dt
    states = np.zeros((steps, 5))
    voltages = np.zeros(steps)

    state = np.array([theta0, 0.0, 0.0, 0.0, 0.0])

    for i in range(steps):
        theta, theta_dot, _, phi_dot, _ = state

        # Sliding surface
        s = c1 * theta + c2 * theta_dot + c3 * phi_dot

        # Boundary-layer saturation
        s_normalized = s / boundary
        if abs(s_normalized) <= 1.0:
            sat_val = s_normalized
        else:
            sat_val = 1.0 if s_normalized > 0 else -1.0

        # Control law
        V = -k * sat_val - eta * s
        V = float(np.clip(V, -MAX_VOLTAGE, MAX_VOLTAGE))

        states[i] = state
        voltages[i] = V

        state = rk4_step(state, V, dt)
        state[0] = wrap_angle(state[0])
        state[2] = wrap_angle(state[2])

    return t, states, voltages


def simulate_open_loop(
    theta0: float, duration: float, dt: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate the nonlinear plant with V=0 (no control)."""
    steps = int(duration / dt)
    t = np.arange(steps) * dt
    states = np.zeros((steps, 5))

    state = np.array([theta0, 0.0, 0.0, 0.0, 0.0])

    for i in range(steps):
        states[i] = state
        state = rk4_step(state, 0.0, dt)
        state[0] = wrap_angle(state[0])
        state[2] = wrap_angle(state[2])

    return t, states


# ── Plotting ────────────────────────────────────────────────────────

def plot_smc_response(
    t: np.ndarray, states: np.ndarray, voltages: np.ndarray,
    save_path: str,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(t, np.degrees(states[:, 0]), "m-", linewidth=1.2)
    axes[0].set_ylabel(r"$\theta$ [deg]")
    axes[0].set_title(
        f"SMC Step Response   "
        rf"$c_1\!=\!{SMC_C1},\;c_2\!=\!{SMC_C2},\;c_3\!=\!{SMC_C3},\;"
        rf"K\!=\!{SMC_K},\;\eta\!=\!{SMC_ETA},\;\Phi\!=\!{SMC_BOUNDARY}$"
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


def plot_open_loop_response(
    t: np.ndarray, states: np.ndarray, save_path: str,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(t, np.degrees(states[:, 0]), "k-", linewidth=1.2)
    ax.set_ylabel(r"$\theta$ [deg]")
    ax.set_xlabel("Time [s]")
    ax.set_title(r"Open-Loop Response ($V=0$, $\theta_0 = 0.1$ rad)")
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="gray", linewidth=0.5)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_three_comparison(
    t_lqr: np.ndarray, states_lqr: np.ndarray,
    t_pid: np.ndarray, states_pid: np.ndarray,
    t_smc: np.ndarray, states_smc: np.ndarray,
    save_path: str,
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(t_lqr, np.degrees(states_lqr[:, 0]), "b-",
                 label="LQR", linewidth=1.2)
    axes[0].plot(t_pid, np.degrees(states_pid[:, 0]), "g--",
                 label="PID (optimized)", linewidth=1.2)
    axes[0].plot(t_smc, np.degrees(states_smc[:, 0]), "m-.",
                 label="SMC", linewidth=1.2)
    axes[0].set_ylabel(r"$\theta$ [deg]")
    axes[0].set_title("LQR vs. PID vs. SMC — Pendulum Angle")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].axhline(0, color="k", linewidth=0.5)

    axes[1].plot(t_lqr, np.degrees(states_lqr[:, 3]), "b-",
                 label="LQR", linewidth=1.0)
    axes[1].plot(t_pid, np.degrees(states_pid[:, 3]), "g--",
                 label="PID (optimized)", linewidth=1.0)
    axes[1].plot(t_smc, np.degrees(states_smc[:, 3]), "m-.",
                 label="SMC", linewidth=1.0)
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

    theta0   = 0.1       # initial displacement [rad]
    duration = 5.0       # simulation horizon [s]
    dt       = TIME_STEP

    lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    # ── 1. Inertia matrix values ──
    log("=" * 60)
    log("  Inertia Matrix Numerical Values")
    log("=" * 60)
    log(f"  I_p       = {I_P:.8e}  kg·m²")
    log(f"  I_w       = {I_W:.8e}  kg·m²")
    log(f"  I_w_eff   = {I_W_EFF:.8e}  kg·m²")
    log(f"  M11       = {M11:.8e}  kg·m²")
    log(f"  M12       = {M12:.8e}  kg·m²")
    log(f"  M22       = {M22:.8e}  kg·m²")
    log(f"  Δ (det)   = {DET_M:.8e}  kg²·m⁴")
    log()

    # ── 2. LQR A and B matrices ──
    log("=" * 60)
    log("  LQR Linearized Matrices")
    log("=" * 60)

    A_mat, B_mat = build_lqr_matrices()

    log("  A matrix (4×4):")
    for row_idx in range(4):
        row_str = "    ["
        for col_idx in range(4):
            row_str += f"  {A_mat[row_idx, col_idx]:+14.8f}"
        row_str += " ]"
        log(row_str)
    log()
    log("  B matrix (4×1):")
    for row_idx in range(4):
        log(f"    [  {B_mat[row_idx, 0]:+14.8f} ]")
    log()

    # ── LQR gains and closed-loop poles ──
    q_diag = [100.0, 1.0, 10.0, 0.01]
    r_lqr  = 1.0

    K, A_full, B_full, P = compute_lqr_gains(q_diag, r_lqr)
    A_cl = A_full - B_full @ K.reshape(1, -1)
    poles = np.linalg.eigvals(A_cl)

    log(f"  Q  = diag({q_diag})")
    log(f"  R  = {r_lqr}")
    log(f"  K  = [{K[0]:.6f},  {K[1]:.6f},  {K[2]:.6f},  {K[3]:.6f}]")
    log("  Closed-loop poles:")
    for p in poles:
        log(f"    {p.real:+.4f} {p.imag:+.4f}j")
    log()

    # ── 3. SMC parameters ──
    log("=" * 60)
    log("  Sliding Mode Controller Parameters")
    log("=" * 60)
    log(f"  c1       = {SMC_C1}")
    log(f"  c2       = {SMC_C2}")
    log(f"  c3       = {SMC_C3}")
    log(f"  K        = {SMC_K}")
    log(f"  η        = {SMC_ETA}")
    log(f"  Φ        = {SMC_BOUNDARY}")
    log()

    # ── Simulations ──
    log("Running simulations …")

    t_lqr, states_lqr, voltages_lqr = simulate_lqr(K, theta0, duration, dt)
    log("  LQR done.")

    t_pid, states_pid, voltages_pid = simulate_pid(
        PID_KP, PID_KI, PID_KD, theta0, duration, dt,
    )
    log("  PID done.")

    t_smc, states_smc, voltages_smc = simulate_smc(theta0, duration, dt)
    log("  SMC done.")

    t_ol, states_ol = simulate_open_loop(theta0, duration=3.0, dt=dt)
    log("  Open-loop done.")
    log()

    # ── Plots ──
    log("Generating plots …")

    p1 = os.path.join(results_dir, "smc_step_response.png")
    plot_smc_response(t_smc, states_smc, voltages_smc, p1)
    log(f"  {p1}")

    p2 = os.path.join(results_dir, "open_loop_response.png")
    plot_open_loop_response(t_ol, states_ol, p2)
    log(f"  {p2}")

    p3 = os.path.join(results_dir, "three_controller_comparison.png")
    plot_three_comparison(t_lqr, states_lqr, t_pid, states_pid,
                          t_smc, states_smc, p3)
    log(f"  {p3}")

    log()
    log("Done.")

    # ── Save text output ──
    txt_path = os.path.join(results_dir, "section2_results.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nText output saved to {txt_path}")


if __name__ == "__main__":
    main()