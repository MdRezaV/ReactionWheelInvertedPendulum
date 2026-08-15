#!/usr/bin/env python3
"""Generate figures and compute numerical values for Section 1 (Mathematical Model).

Produces:
  1. Numerical values for all derived quantities (saved to text file).
  2. System schematic (pendulum + reaction wheel + motor).
  3. Potential energy landscape U(θ) with equilibrium points.
  4. Phase portrait (θ vs θ̇) for uncontrolled system.
  5. Energy conservation comparison: RK4 vs RK5 over long horizon.
  6. Coupling demonstration: response of θ and φ to initial displacement.

Usage (from project root):
    uv run --with numpy --with scipy --with matplotlib scripts/section1_figures.py
"""

from __future__ import annotations

import os

import numpy as np
from scipy.integrate import solve_ivp

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Circle, Rectangle, Arc
from matplotlib.lines import Line2D

# ── System parameters (defaults from backend/config.py) ─────────────

PENDULUM_MASS       = 0.4
PENDULUM_LENGTH     = 0.3
WHEEL_MASS          = 0.25
WHEEL_INNER_RADIUS  = 0.02
WHEEL_OUTER_RADIUS  = 0.07
DAMPING             = 0.001
WHEEL_DAMPING       = 0.0005
GRAVITY             = 9.81
TIME_STEP           = 0.001
MAX_VOLTAGE         = 12.0
MOTOR_RESISTANCE    = 1.2
MOTOR_INDUCTANCE    = 0.0005
MOTOR_CONSTANT      = 0.0876
MOTOR_ROTOR_INERTIA = 5e-5
MOTOR_VISCOUS_FRICTION = 0.001
GEAR_RATIO          = 1.0

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
N_GEAR = GEAR_RATIO
RA = MOTOR_RESISTANCE
LA = MOTOR_INDUCTANCE
B  = DAMPING


# ── Nonlinear dynamics (5-state) ────────────────────────────────────

def dynamics(state: np.ndarray, voltage: float = 0.0) -> np.ndarray:
    """Full 5-state dynamics: [θ, θ̇, φ, φ̇, i_a]."""
    theta, theta_dot, _phi, phi_dot, i_a = state
    V = np.clip(voltage, -MAX_VOLTAGE, MAX_VOLTAGE)

    tau_w = N_GEAR * KT * i_a

    f1 = GRAVITY_COEFF * np.sin(theta) - tau_w - B * theta_dot
    f2 = tau_w - B_W_EFF * phi_dot

    theta_ddot = (M22 * f1 - M12 * f2) / DET_M
    phi_ddot   = (M11 * f2 - M12 * f1) / DET_M
    di_a       = (V - RA * i_a - KE * N_GEAR * phi_dot) / LA

    return np.array([theta_dot, theta_ddot, phi_dot, phi_ddot, di_a])


def dynamics_no_elec(state: np.ndarray, voltage: float = 0.0) -> np.ndarray:
    """4-state dynamics for phase portrait (instantaneous current)."""
    theta, theta_dot, phi, phi_dot = state
    V = np.clip(voltage, -MAX_VOLTAGE, MAX_VOLTAGE)

    # Steady-state current (L_a → 0)
    i_a = (V - KE * N_GEAR * phi_dot) / RA
    tau_w = N_GEAR * KT * i_a

    f1 = GRAVITY_COEFF * np.sin(theta) - tau_w - B * theta_dot
    f2 = tau_w - B_W_EFF * phi_dot

    theta_ddot = (M22 * f1 - M12 * f2) / DET_M
    phi_ddot   = (M11 * f2 - M12 * f1) / DET_M

    return np.array([theta_dot, theta_ddot, phi_dot, phi_ddot])


# ── RK4 and RK5 integrators ────────────────────────────────────────

# Butcher tableau for RK5 (Butcher's 6-stage 5th-order)
A_RK5 = np.array([
    [0, 0, 0, 0, 0, 0],
    [1/4, 0, 0, 0, 0, 0],
    [1/8, 1/8, 0, 0, 0, 0],
    [0, -1/2, 1, 0, 0, 0],
    [3/16, 0, 0, 9/16, 0, 0],
    [-3/7, 2/7, 12/7, -12/7, 8/7, 0],
], dtype=np.float64)

B_RK5 = np.array([7/90, 0, 32/90, 12/90, 32/90, 7/90], dtype=np.float64)
C_RK5 = np.array([0, 1/4, 1/4, 1/2, 3/4, 1], dtype=np.float64)


def rk5_step(state: np.ndarray, voltage: float, dt: float) -> np.ndarray:
    """Single 6-stage 5th-order Runge-Kutta step."""
    k = np.zeros((6, len(state)))
    k[0] = dynamics(state, voltage)
    for i in range(1, 6):
        s_temp = state + dt * (A_RK5[i, :i] @ k[:i])
        k[i] = dynamics(s_temp, voltage)
    return state + dt * (B_RK5 @ k)


def rk4_step(state: np.ndarray, voltage: float, dt: float) -> np.ndarray:
    """Single classical RK4 step."""
    k1 = dynamics(state, voltage)
    k2 = dynamics(state + 0.5 * dt * k1, voltage)
    k3 = dynamics(state + 0.5 * dt * k2, voltage)
    k4 = dynamics(state + dt * k3, voltage)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def wrap_angle(a: float) -> float:
    return (a + np.pi) % (2.0 * np.pi) - np.pi


def compute_energy(state: np.ndarray) -> tuple[float, float, float]:
    """Compute kinetic, potential, total energy."""
    theta, theta_dot, _phi, phi_dot, _ia = state
    T = 0.5 * (M11 * theta_dot**2 + 2 * M12 * theta_dot * phi_dot + M22 * phi_dot**2)
    U = GRAVITY_COEFF * (np.cos(theta) - 1.0)
    return T, U, T + U


# ── Figure 1: System Schematic ──────────────────────────────────────

def plot_system_schematic(save_path: str) -> None:
    """Draw a simplified schematic of the reaction wheel inverted pendulum.

    Dimensions are proportional to physical parameters:
      beam length = 0.30 m, wheel outer radius = 0.07 m.
    Motor is drawn behind the wheel (coaxial, lower z-order).
    """
    SCALE = 4.0  # display units per metre

    beam_len = PENDULUM_LENGTH * SCALE        # 0.30 m → 1.2
    wheel_r  = WHEEL_OUTER_RADIUS * SCALE     # 0.07 m → 0.28
    hub_r    = WHEEL_INNER_RADIUS * SCALE     # 0.02 m → 0.08
    motor_w  = 0.10 * SCALE                   # motor housing width  ≈ 10 cm
    motor_h  = 0.06 * SCALE                   # motor housing height ≈  6 cm

    fig, ax = plt.subplots(1, 1, figsize=(7, 8))
    ax.set_xlim(-1.6, 1.6)
    ax.set_ylim(-0.6, 2.0)
    ax.set_aspect("equal")
    ax.axis("off")

    # Pivot point
    pivot = (0.0, 0.0)
    ax.plot(*pivot, "ko", markersize=10, zorder=6)
    ax.annotate("Pivot", xy=pivot, xytext=(0.35, -0.30),
                fontsize=9, ha="left",
                arrowprops=dict(arrowstyle="->", color="gray"))

    # Pendulum beam (slight tilt for visual interest)
    angle = 0.12
    tip_x = beam_len * np.sin(angle)
    tip_y = beam_len * np.cos(angle)
    tip = (tip_x, tip_y)

    ax.plot([pivot[0], tip[0]], [pivot[1], tip[1]],
            color="black", linewidth=5, solid_capstyle="round", zorder=3)

    # Centre-of-mass marker
    cm_x = 0.5 * beam_len * np.sin(angle)
    cm_y = 0.5 * beam_len * np.cos(angle)
    ax.plot(cm_x, cm_y, "bs", markersize=7, zorder=5)
    ax.annotate(r"$m_p,\;l_{cm}$", xy=(cm_x, cm_y), xytext=(0.55, 0.45),
                fontsize=10, color="blue",
                arrowprops=dict(arrowstyle="->", color="blue"))

    # ── Motor (drawn BEHIND the wheel) ──────────────────────────────
    motor_rect = Rectangle(
        (tip_x - motor_w / 2, tip_y - motor_h / 2),
        motor_w, motor_h,
        facecolor="lightyellow", edgecolor="orange", linewidth=2,
        zorder=3,
    )
    ax.add_patch(motor_rect)
    ax.text(tip_x, tip_y, "M", ha="center", va="center",
            fontsize=9, fontweight="bold", color="darkorange", zorder=3)
    ax.annotate("Motor (direct drive)", xy=(tip_x - motor_w / 2, tip_y),
                xytext=(-1.45, 0.85), fontsize=9, color="darkorange",
                arrowprops=dict(arrowstyle="->", color="orange"))

    # ── Reaction wheel (drawn ON TOP of motor) ──────────────────────
    wheel = Circle(tip, wheel_r, fill=False,
                   edgecolor="red", linewidth=2.5, zorder=5)
    ax.add_patch(wheel)
    # Hub
    hub = Circle(tip, hub_r, fill=True,
                 facecolor="mistyrose", edgecolor="red", linewidth=1.2, zorder=5)
    ax.add_patch(hub)
    # Spokes
    for a in range(0, 360, 60):
        rad = np.radians(a)
        ax.plot([tip[0] + hub_r * np.cos(rad), tip[0] + 0.92 * wheel_r * np.cos(rad)],
                [tip[1] + hub_r * np.sin(rad), tip[1] + 0.92 * wheel_r * np.sin(rad)],
                "r-", linewidth=1.0, zorder=5)
    ax.annotate(r"Reaction Wheel ($I_w$)", xy=(tip_x + wheel_r, tip_y),
                xytext=(0.85, 1.55), fontsize=10, color="red",
                arrowprops=dict(arrowstyle="->", color="red"))

    # ── Annotations & decorations ───────────────────────────────────

    # Gravity arrow
    ax.annotate("", xy=(1.35, 0.25), xytext=(1.35, 0.95),
                arrowprops=dict(arrowstyle="->", color="green", lw=2))
    ax.text(1.40, 0.55, r"$g$", fontsize=12, color="green")

    # Angle arc at pivot
    arc_r = 0.45
    theta_arc = np.linspace(np.pi / 2, np.pi / 2 - angle, 30)
    ax.plot(arc_r * np.cos(theta_arc), arc_r * np.sin(theta_arc),
            "g-", linewidth=1.5)
    ax.text(0.10, 0.50, r"$\theta$", fontsize=12, color="green")

    # Wheel rotation arrow (φ)
    ax.annotate("", xy=(tip[0] + wheel_r + 0.10, tip[1] + 0.08),
                xytext=(tip[0] + wheel_r + 0.10, tip[1] - 0.08),
                arrowprops=dict(arrowstyle="->", color="red", lw=1.5,
                                connectionstyle="arc3,rad=0.5"))
    ax.text(tip[0] + wheel_r + 0.16, tip[1], r"$\varphi$",
            fontsize=12, color="red")

    # Voltage input arrow (into motor, from the left)
    ax.annotate("", xy=(tip_x - motor_w / 2, tip_y),
                xytext=(tip_x - motor_w / 2 - 0.55, tip_y),
                arrowprops=dict(arrowstyle="->", color="purple", lw=2))
    ax.text(tip_x - motor_w / 2 - 0.60, tip_y + 0.08, r"$V$",
            fontsize=12, color="purple")

    # Dashed vertical reference
    ax.plot([0, 0], [0, beam_len + wheel_r + 0.15],
            "k--", linewidth=0.8, alpha=0.4)

    # Dimension annotation: beam length
    dim_x = -0.35
    ax.annotate("", xy=(dim_x, 0), xytext=(dim_x, beam_len),
                arrowprops=dict(arrowstyle="<->", color="gray", lw=1))
    ax.text(dim_x - 0.08, beam_len / 2, "0.30 m", fontsize=8,
            color="gray", ha="right", va="center", rotation=90)

    # Dimension annotation: wheel radius
    ax.annotate("", xy=(tip[0], tip[1]),
                xytext=(tip[0] + wheel_r, tip[1]),
                arrowprops=dict(arrowstyle="<->", color="gray", lw=1))
    ax.text(tip[0] + wheel_r / 2, tip[1] - 0.10, "0.07 m",
            fontsize=7, color="gray", ha="center")

    ax.set_title("Reaction Wheel Inverted Pendulum — System Schematic",
                 fontsize=11, pad=15)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Figure 2: Potential Energy Landscape ────────────────────────────

def plot_potential_energy(save_path: str) -> None:
    """Plot U(θ) showing equilibrium points."""
    theta = np.linspace(-np.pi, np.pi, 500)
    U = GRAVITY_COEFF * (np.cos(theta) - 1.0)

    fig, ax = plt.subplots(1, 1, figsize=(9, 5))

    ax.plot(np.degrees(theta), U, "b-", linewidth=2)
    ax.axhline(0, color="k", linewidth=0.5)

    # Mark equilibrium points
    ax.plot(0, 0, "ro", markersize=12, zorder=5, label=r"$\theta=0$ (unstable)")
    ax.plot(180, GRAVITY_COEFF * (np.cos(np.pi) - 1), "gs", markersize=12,
            zorder=5, label=r"$\theta=\pi$ (stable)")
    ax.plot(-180, GRAVITY_COEFF * (np.cos(-np.pi) - 1), "gs", markersize=12,
            zorder=5)

    # Annotations
    ax.annotate("Unstable\nequilibrium", xy=(0, 0), xytext=(30, -0.5),
                fontsize=10, color="red", ha="center",
                arrowprops=dict(arrowstyle="->", color="red"))
    ax.annotate("Stable\nequilibrium", xy=(180, -2 * GRAVITY_COEFF),
                xytext=(140, -2 * GRAVITY_COEFF + 0.3),
                fontsize=10, color="green", ha="center",
                arrowprops=dict(arrowstyle="->", color="green"))

    ax.set_xlabel(r"$\theta$ [degrees]", fontsize=12)
    ax.set_ylabel(r"$U(\theta) = G(\cos\theta - 1)$ [J]", fontsize=12)
    ax.set_title("Gravitational Potential Energy Landscape", fontsize=12)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-2 * GRAVITY_COEFF - 0.3, 0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Figure 3: Phase Portrait ────────────────────────────────────────

def plot_phase_portrait(save_path: str) -> None:
    """Phase portrait θ vs θ̇ for uncontrolled pendulum (V=0, no wheel)."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 7))

    # Vector field
    theta_grid = np.linspace(-np.pi, np.pi, 25)
    theta_dot_grid = np.linspace(-12, 12, 25)
    T, TD = np.meshgrid(theta_grid, theta_dot_grid)

    # For phase portrait, use simplified dynamics (no wheel coupling, V=0)
    U_dot = np.zeros_like(T)
    T_dot = TD
    for i in range(T.shape[0]):
        for j in range(T.shape[1]):
            th = T[i, j]
            td = TD[i, j]
            # Simplified: pendulum only
            theta_dd = (GRAVITY_COEFF * np.sin(th) - B * td) / M11
            T_dot[i, j] = td
            U_dot[i, j] = theta_dd

    speed = np.sqrt(T_dot**2 + U_dot**2)
    speed[speed == 0] = 1
    ax.quiver(np.degrees(T), TD, T_dot / speed, U_dot / speed,
              speed, alpha=0.4, cmap="coolwarm")

    # Trajectories from different initial conditions
    initial_conditions = [
        (0.1, 0.0),
        (0.3, 0.0),
        (0.6, 0.0),
        (1.0, 0.0),
        (2.0, 0.0),
        (2.8, 0.0),
        (0.0, 3.0),
        (0.0, 6.0),
        (0.0, 10.0),
    ]

    colors = plt.cm.viridis(np.linspace(0, 1, len(initial_conditions)))

    for idx, (th0, td0) in enumerate(initial_conditions):
        state = np.array([th0, td0, 0.0, 0.0, 0.0])
        dt = 0.001
        n_steps = 10000
        thetas = np.zeros(n_steps)
        theta_dots = np.zeros(n_steps)

        for i in range(n_steps):
            thetas[i] = state[0]
            theta_dots[i] = state[1]
            state = rk5_step(state, 0.0, dt)
            state[0] = wrap_angle(state[0])
            state[2] = wrap_angle(state[2])

        ax.plot(np.degrees(thetas), theta_dots, "-", color=colors[idx],
                linewidth=1.0, alpha=0.8)
        ax.plot(np.degrees(thetas[0]), theta_dots[0], "o", color=colors[idx],
                markersize=5)

    ax.set_xlabel(r"$\theta$ [degrees]", fontsize=12)
    ax.set_ylabel(r"$\dot{\theta}$ [rad/s]", fontsize=12)
    ax.set_title(r"Phase Portrait ($V=0$, uncontrolled)", fontsize=12)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-12, 12)
    ax.axhline(0, color="k", linewidth=0.5)
    ax.axvline(0, color="k", linewidth=0.5)
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Figure 4: Energy Conservation (RK4 vs RK5) ──────────────────────

def plot_energy_conservation(save_path: str) -> None:
    """Compare energy drift of RK4 vs RK5 over a long simulation."""
    theta0 = 0.5  # initial angle [rad]
    duration = 10.0
    dt = TIME_STEP
    steps = int(duration / dt)

    state0 = np.array([theta0, 0.0, 0.0, 0.0, 0.0])
    _, _, E0 = compute_energy(state0)

    # RK4
    state_rk4 = state0.copy()
    energy_rk4 = np.zeros(steps)
    for i in range(steps):
        _, _, E = compute_energy(state_rk4)
        energy_rk4[i] = E - E0
        state_rk4 = rk4_step(state_rk4, 0.0, dt)
        state_rk4[0] = wrap_angle(state_rk4[0])
        state_rk4[2] = wrap_angle(state_rk4[2])

    # RK5
    state_rk5 = state0.copy()
    energy_rk5 = np.zeros(steps)
    for i in range(steps):
        _, _, E = compute_energy(state_rk5)
        energy_rk5[i] = E - E0
        state_rk5 = rk5_step(state_rk5, 0.0, dt)
        state_rk5[0] = wrap_angle(state_rk5[0])
        state_rk5[2] = wrap_angle(state_rk5[2])

    t = np.arange(steps) * dt

    fig, ax = plt.subplots(1, 1, figsize=(9, 5))

    ax.plot(t, energy_rk4 * 1000, "r-", linewidth=1.2, label="RK4 (energy drift)")
    ax.plot(t, energy_rk5 * 1000, "b-", linewidth=1.2, label="RK5 (energy drift)")
    ax.axhline(0, color="k", linewidth=0.5)

    ax.set_xlabel("Time [s]", fontsize=12)
    ax.set_ylabel(r"$\Delta E$ [mJ]", fontsize=12)
    ax.set_title(
        f"Energy Conservation: RK4 vs RK5  "
        rf"($\theta_0 = {np.degrees(theta0):.1f}°$, $\Delta t = {dt}$ s)",
        fontsize=12,
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Figure 5: Coupling Demonstration ────────────────────────────────

def plot_coupling_demo(save_path: str) -> None:
    """Show coupled response of θ and φ from initial θ displacement."""
    theta0 = 0.2
    duration = 4.0
    dt = TIME_STEP
    steps = int(duration / dt)

    state = np.array([theta0, 0.0, 0.0, 0.0, 0.0])
    t = np.arange(steps) * dt
    thetas = np.zeros(steps)
    phis = np.zeros(steps)
    theta_dots = np.zeros(steps)
    phi_dots = np.zeros(steps)
    voltages = np.zeros(steps)

    for i in range(steps):
        thetas[i] = state[0]
        phis[i] = state[2]
        theta_dots[i] = state[1]
        phi_dots[i] = state[3]
        # Apply a brief voltage pulse to excite coupling
        V = 6.0 if (0.5 < t[i] < 0.6) else 0.0
        voltages[i] = V
        state = rk5_step(state, V, dt)
        state[0] = wrap_angle(state[0])
        state[2] = wrap_angle(state[2])

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    axes[0].plot(t, np.degrees(thetas), "b-", linewidth=1.2)
    axes[0].set_ylabel(r"$\theta$ [deg]", fontsize=11)
    axes[0].set_title("Coupling Demonstration: Voltage Pulse at t=0.5 s", fontsize=12)
    axes[0].grid(True, alpha=0.3)
    axes[0].axvspan(0.5, 0.6, alpha=0.2, color="orange", label="Voltage pulse")
    axes[0].legend(fontsize=10)

    axes[1].plot(t, np.degrees(phis), "r-", linewidth=1.2)
    axes[1].set_ylabel(r"$\varphi$ [deg]", fontsize=11)
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(t, voltages, "k-", linewidth=1.0)
    axes[2].set_ylabel("V [V]", fontsize=11)
    axes[2].set_xlabel("Time [s]", fontsize=12)
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Figure 6: Inertia Matrix Visualization ──────────────────────────

def plot_inertia_matrix(save_path: str) -> None:
    """Visualize the 2×2 inertia matrix structure."""
    M = np.array([[M11, M12], [M12, M22]])

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Heatmap
    im = axes[0].imshow(M, cmap="YlOrRd", aspect="auto")
    axes[0].set_xticks([0, 1])
    axes[0].set_yticks([0, 1])
    axes[0].set_xticklabels([r"$\theta$", r"$\varphi$"], fontsize=12)
    axes[0].set_yticklabels([r"$\theta$", r"$\varphi$"], fontsize=12)
    for i in range(2):
        for j in range(2):
            axes[0].text(j, i, f"{M[i, j]:.5f}", ha="center", va="center",
                        fontsize=10, fontweight="bold")
    axes[0].set_title("Inertia Matrix M", fontsize=12)
    plt.colorbar(im, ax=axes[0], fraction=0.046)

    # Bar comparison
    labels = [r"$M_{11}$", r"$M_{12}$", r"$M_{22}$", r"$\det(\mathbf{M})$"]
    values = [M11, M12, M22, DET_M]
    colors = ["steelblue", "orange", "steelblue", "green"]
    axes[1].bar(labels, values, color=colors, edgecolor="black", linewidth=0.5)
    axes[1].set_ylabel(r"kg·m²", fontsize=11)
    axes[1].set_title("Inertia Matrix Entries", fontsize=12)
    axes[1].grid(True, alpha=0.3, axis="y")
    for i, v in enumerate(values):
        axes[1].text(i, v + 0.001, f"{v:.5f}", ha="center", fontsize=9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ── Numerical values output ─────────────────────────────────────────

def compute_and_print_values() -> list[str]:
    """Compute all derived quantities and return formatted lines."""
    lines = [
        "=" * 65,
        "  Section 1 — Derived Numerical Values (Default Parameters)",
        "=" * 65,
        "",
        "  Pendulum:",
        f"    l_cm       = {L_COM:.4f} m",
        f"    I_p        = (1/3)·m_p·L_p² = {I_P:.6f} kg·m²",
        "",
        "  Reaction Wheel:",
        f"    I_w        = ½·m_w·(r_o² + r_i²) = {I_W:.7f} kg·m²",
        "",
        "  Effective (gearbox-reflected):",
        f"    I_w_eff    = I_w + J_r·N² = {I_W:.7f} + {MOTOR_ROTOR_INERTIA * GEAR_RATIO**2:.6f} = {I_W_EFF:.7f} kg·m²",
        f"    b_w_eff    = b_w + b_m·N² = {WHEEL_DAMPING:.5f} + {GEAR_RATIO**2 * MOTOR_VISCOUS_FRICTION:.4f} = {B_W_EFF:.5f} N·m·s/rad",
        "",
        "  Inertia Matrix:",
        f"    M₁₁ = I_p + m_w·L_p² + I_w_eff = {I_P:.6f} + {WHEEL_MASS * PENDULUM_LENGTH**2:.6f} + {I_W_EFF:.7f}",
        f"        = {M11:.7f} kg·m²",
        f"    M₁₂ = I_w_eff = {M12:.7f} kg·m²",
        f"    M₂₂ = I_w_eff = {M22:.7f} kg·m²",
        f"    det(M) = M₁₁·M₂₂ − M₁₂² = {DET_M:.9f} kg²·m⁴",
        f"    Coupling ratio M₁₂/M₁₁ = {M12/M11:.5f}",
        "",
        "  Gravitational Coefficient:",
        f"    G = (m_p·l_cm + m_w·L_p)·g = ({PENDULUM_MASS * L_COM:.4f} + {WHEEL_MASS * PENDULUM_LENGTH:.4f})·{GRAVITY}",
        f"    G = {GRAVITY_COEFF:.6f} N·m",
        "",
        "  Electrical:",
        f"    K_t·N = {KT * N_GEAR:.4f} N·m/A (effective torque constant)",
        f"    K_e·N = {KE * N_GEAR:.4f} V·s/rad (effective back-EMF constant)",
        f"    R_a = {RA} Ω,  L_a = {LA * 1000:.2f} mH",
        f"    Electrical time constant τ_e = L_a/R_a = {LA/RA * 1000:.3f} ms",
        "",
        "  Natural frequency (small-angle, linearized):",
        f"    ω_n = √(G / M₁₁) = √({GRAVITY_COEFF:.5f} / {M11:.6f})",
        f"    ω_n = {np.sqrt(GRAVITY_COEFF / M11):.4f} rad/s  ({np.sqrt(GRAVITY_COEFF / M11) / (2*np.pi):.3f} Hz)",
        f"    τ_instability ≈ 1/ω_n = {1.0/np.sqrt(GRAVITY_COEFF / M11):.4f} s",
        "",
        "=" * 65,
    ]
    return lines


# ── Main ────────────────────────────────────────────────────────────

def main() -> None:
    results_dir = os.path.join("latex", "results")
    os.makedirs(results_dir, exist_ok=True)

    print("Computing numerical values …")
    lines = compute_and_print_values()
    for line in lines:
        print(line)

    txt_path = os.path.join(results_dir, "section1_values.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nValues saved to {txt_path}\n")

    print("Generating figures …")

    figures = [
        ("section1_schematic", plot_system_schematic, "System schematic"),
        ("section1_potential_energy", plot_potential_energy, "Potential energy landscape"),
        ("section1_phase_portrait", plot_phase_portrait, "Phase portrait"),
        ("section1_energy_conservation", plot_energy_conservation, "Energy conservation RK4 vs RK5"),
        ("section1_coupling", plot_coupling_demo, "Coupling demonstration"),
        ("section1_inertia_matrix", plot_inertia_matrix, "Inertia matrix visualization"),
    ]

    for name, func, desc in figures:
        path = os.path.join(results_dir, f"{name}.png")
        print(f"  {desc} → {path}")
        func(path)

    print("\nAll done.")


if __name__ == "__main__":
    main()