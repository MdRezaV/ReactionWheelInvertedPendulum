# Disturbance Model

## Overview

The simulation supports external disturbances injected into the electro-mechanical system to test controller robustness. Disturbances enter through two independent **channels** and are shaped by five selectable **waveforms**. Multiple disturbances may be active simultaneously.

---

## Injection Channels

### 1. Torque Channel (τ_ext)

An external torque is applied directly to the pendulum body. It enters the pendulum equation of motion:

$$
M_{11}\,\ddot{\theta} + M_{12}\,\ddot{\varphi} = m_{\text{eff}}\,g\,\sin\theta - N\,K_t\,i_a - b\,\dot{\theta} + \tau_{\text{ext}}(t)
$$

where $m_{\text{eff}} = m_p\,l_{\text{cm}} + m_w\,L$ is the effective gravitational mass arm.

### 2. Voltage Channel (V_dist)

A voltage offset is added to the controller's voltage command before it reaches the armature circuit:

$$
V_{\text{total}} = V_{\text{controller}} + V_{\text{dist}}(t)
$$

The combined voltage then drives the electrical dynamics:

$$
L\,\frac{di_a}{dt} = V_{\text{total}} - R\,i_a - K_e\,N\,\dot{\varphi}
$$

Both channels respect the actuator voltage saturation $|V_{\text{total}}| \leq V_{\max}$.

---

## Waveform Definitions

Each waveform is parameterized by an **amplitude** $A$ and, where applicable, a **frequency** $f$ (in Hz), **duty cycle** $D$, **mean** $\mu$, and **standard deviation** $\sigma$.

### 1. Constant

A steady offset:

$$
d(t) = A
$$

**Use case:** Models a persistent bias (e.g., a stuck mass, constant wind load, or sensor offset).

---

### 2. Sinusoidal

A harmonic oscillation:

$$
d(t) = A\,\sin(2\pi f\, t)
$$

**Use case:** Models periodic excitations such as rotating imbalance or vibratory base motion.

---

### 3. Pulse (Rectangular)

A periodic square wave with duty cycle $D \in [0, 1]$:

$$
d(t) = \begin{cases} A & \text{if } (t \cdot f) \mod 1 < D \\ 0 & \text{otherwise} \end{cases}
$$

**Use case:** Models intermittent impacts or on–off disturbances (e.g., a periodic push).

---

### 4. Sawtooth

A linear ramp that resets each period:

$$
d(t) = A \cdot \left(\frac{t \cdot f \mod 1}{1}\right) = A \cdot (t \cdot f \mod 1)
$$

The signal rises linearly from $0$ to $A$ over each period $T = 1/f$, then drops instantaneously back to zero.

**Use case:** Models progressively building disturbances (e.g., slowly accumulating load that is suddenly released).

---

### 5. Gaussian Noise

A stochastic signal drawn at each physics step:

$$
d(t) \sim \mathcal{N}(\mu,\;\sigma^2)
$$

Each sample is independent (white noise). The parameters are:
- $\mu$: mean offset
- $\sigma$: standard deviation (controls noise intensity)

**Use case:** Models sensor noise, turbulent aerodynamic forces, or unmodeled stochastic friction.

---

## Duration

Every disturbance has a configurable duration measured in physics steps:

| Duration value | Behaviour |
|---|---|
| $N > 0$ | Disturbance is active for exactly $N$ integration steps, then removed |
| $0$ | Disturbance persists indefinitely until manually cleared |

Given the physics step size $\Delta t$, a finite duration of $N$ steps corresponds to a real-time span of $N \cdot \Delta t$ seconds.

---

## Superposition

Multiple disturbances may be active simultaneously. Their contributions are **summed** per channel before entering the dynamics:

$$
\tau_{\text{ext}}(t) = \sum_{k} d_k(t) \quad \text{(torque channel)}
$$

$$
V_{\text{dist}}(t) = \sum_{k} d_k(t) \quad \text{(voltage channel)}
$$

---

## Effect on the Coupled System

The full disturbed system of equations is:

$$
\begin{bmatrix} M_{11} & M_{12} \\ M_{12} & M_{22} \end{bmatrix}
\begin{bmatrix} \ddot{\theta} \\ \ddot{\varphi} \end{bmatrix}
=
\begin{bmatrix}
m_{\text{eff}}\,g\,\sin\theta - N K_t i_a - b\,\dot{\theta} + \tau_{\text{ext}}(t) \\
N K_t i_a - b_w^{\text{eff}}\,\dot{\varphi}
\end{bmatrix}
$$

$$
L\,\frac{di_a}{dt} = \bigl[V_{\text{ctrl}} + V_{\text{dist}}(t)\bigr] - R\,i_a - K_e\,N\,\dot{\varphi}
$$

where:

| Symbol | Meaning |
|---|---|
| $M_{11} = I_p + m_w L^2 + I_w^{\text{eff}}$ | Pendulum-axis inertia |
| $M_{12} = M_{22} = I_w^{\text{eff}}$ | Coupling / wheel inertia |
| $I_w^{\text{eff}} = I_w + J_r N^2$ | Wheel inertia + reflected rotor |
| $b_w^{\text{eff}} = b_w + b_m N^2$ | Wheel damping + reflected motor friction |
| $m_{\text{eff}}\,g$ | Gravitational coefficient |
| $N$ | Gear ratio |
| $K_t,\, K_e$ | Motor torque / back-EMF constants |

For the complete derivation of the system dynamics and parameter definitions, see [System Description & Mathematical Model](./system-mathematics.md).

---

## Related Documents

| Document | Content |
|----------|---------|
| [System Description & Mathematical Model](./system-mathematics.md) | Full system dynamics, inertia matrix, armature circuit |
| [Control Methods](./control-methods.md) | Balance controllers (PID, LQR, SMC) that disturbances test |
| [Gain Tuning Guide](./gain-tuning-guide.md) | Tuning procedures including disturbance robustness testing |
| [Physical Parameters Reference](./physical-parameters.md) | Parameter definitions, units, and measurement methods |

---

## Summary

The disturbance framework provides a mathematically clean separation between **where** a perturbation enters (torque vs. voltage) and **what shape** it takes (constant, sinusoidal, pulse, sawtooth, Gaussian). This allows systematic robustness testing of any controller (PID, LQR, SMC, swing-up) against both deterministic and stochastic perturbations without modifying the underlying physics or control laws.