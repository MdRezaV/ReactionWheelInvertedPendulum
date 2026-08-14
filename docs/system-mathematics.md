# Reaction Wheel Inverted Pendulum — System Description & Mathematical Model

## 1. System Overview

This project simulates an **inverted pendulum stabilized by a reaction wheel**. A DC motor, connected through a gearbox, drives a flywheel (reaction wheel) mounted at the tip of a pendulum arm. By accelerating or decelerating the wheel, a reaction torque is exerted on the pendulum body, enabling it to balance in the upright (unstable) equilibrium or be swung up from a hanging position.

The simulation models the **full coupled electro-mechanical system**:

- **Mechanical subsystem**: A rigid pendulum arm with a reaction wheel, described by a coupled 2×2 inertia matrix.
- **Electrical subsystem**: A DC motor armature circuit with resistance, inductance, and back-EMF.

The resulting model is a **5-state ordinary differential equation (ODE)**:

$$
\mathbf{x} = \begin{bmatrix} \theta & \dot{\theta} & \varphi & \dot{\varphi} & i_a \end{bmatrix}^T
$$

| State | Symbol | Description |
|-------|--------|-------------|
| Pendulum angle | $\theta$ | Angle from upright (0 = upright) |
| Pendulum angular velocity | $\dot{\theta}$ | Rate of change of $\theta$ |
| Wheel angle | $\varphi$ | Wheel angle relative to pendulum arm |
| Wheel angular velocity | $\dot{\varphi}$ | Rate of change of $\varphi$ (relative) |
| Armature current | $i_a$ | Motor armature current |

---

## 2. Physical Parameters

For complete parameter definitions, units, and measurement methods, see [Physical Parameters Reference](./physical-parameters.md).

### 2.1 Pendulum

| Parameter | Symbol | Default | Unit |
|-----------|--------|---------|------|
| Pendulum mass | $m_p$ | 0.4 | kg |
| Pendulum length | $L_p$ | 0.3 | m |
| Center-of-mass distance | $l_{cm}$ | $L_p / 2$ (fallback) | m |
| Moment of inertia about pivot | $I_p$ | $\frac{1}{3} m_p L_p^2$ (fallback) | kg·m² |
| Pivot damping coefficient | $b$ | 0.001 | N·m·s/rad |

### 2.2 Reaction Wheel

| Parameter | Symbol | Default | Unit |
|-----------|--------|---------|------|
| Wheel mass | $m_w$ | 0.25 | kg |
| Wheel inner radius | $r_i$ | 0.02 | m |
| Wheel outer radius | $r_o$ | 0.07 | m |
| Wheel moment of inertia | $I_w$ | $\frac{1}{2} m_w(r_o^2 + r_i^2)$ (fallback) | kg·m² |
| Wheel damping | $b_w$ | 0.0005 | N·m·s/rad |

### 2.3 Motor & Gearbox

| Parameter | Symbol | Default | Unit |
|-----------|--------|---------|------|
| Gear ratio | $N$ | 4.0 | — |
| Motor torque/back-EMF constant | $K_t = K_e$ | 0.0876 | N·m/A = V·s/rad |
| Armature resistance | $R$ | 1.2 | Ω |
| Armature inductance | $L$ | 0.0005 | H |
| Rotor inertia | $J_r$ | 5×10⁻⁵ | kg·m² |
| Motor viscous friction | $b_m$ | 0.001 | N·m·s/rad |
| Maximum voltage | $V_{max}$ | 12.0 | V |

### 2.4 Environment & Numerics

| Parameter | Symbol | Default | Unit |
|-----------|--------|---------|------|
| Gravitational acceleration | $g$ | 9.81 | m/s² |
| Integration time step | $\Delta t$ | 0.001 | s |

---

## 3. Derived Quantities

### 3.1 Effective Wheel-Side Inertia

The motor rotor inertia is reflected to the wheel side through the gearbox:

$$
I_{w,\text{eff}} = I_w + J_r \, N^2
$$

### 3.2 Effective Wheel-Side Damping

Motor viscous friction is similarly reflected:

$$
b_{w,\text{eff}} = b_w + b_m \, N^2
$$

### 3.3 Coupled Inertia Matrix

The 2×2 mass/inertia matrix for the generalized coordinates $(\theta, \varphi)$ is:

$$
\mathbf{M} = \begin{bmatrix} M_{11} & M_{12} \\ M_{12} & M_{22} \end{bmatrix}
$$

where:

$$
M_{11} = I_p + m_w L_p^2 + I_{w,\text{eff}}
$$

$$
M_{12} = I_{w,\text{eff}}
$$

$$
M_{22} = I_{w,\text{eff}}
$$

The determinant is:

$$
\det(\mathbf{M}) = M_{11} M_{22} - M_{12}^2 > 0
$$

This must be strictly positive for the system to be physically valid.

### 3.4 Gravity Coefficient

The combined gravitational torque coefficient:

$$
G = (m_p \, l_{cm} + m_w \, L_p) \, g
$$

---

## 4. Equations of Motion

### 4.1 Mechanical Dynamics (Coupled 2×2 System)

The coupled equations arise from Lagrangian mechanics. The motor produces electromagnetic torque $\tau_m = K_t \, i_a$, which is transmitted to the wheel through the gearbox as $\tau_w = N \, K_t \, i_a$.

The system is:

$$
\mathbf{M} \begin{bmatrix} \ddot{\theta} \\ \ddot{\varphi} \end{bmatrix} = \begin{bmatrix} f_1 \\ f_2 \end{bmatrix}
$$

where the right-hand-side forces are:

$$
f_1 = G \sin\theta - \tau_w - b\,\dot{\theta} + \tau_{\text{ext}}
$$

$$
f_2 = \tau_w - b_{w,\text{eff}} \, \dot{\varphi}
$$

Here $\tau_{\text{ext}}$ is an optional external disturbance torque applied to the pendulum body.

**Solving the 2×2 system** (Cramer's rule):

$$
\ddot{\theta} = \frac{M_{22}\, f_1 - M_{12}\, f_2}{\det(\mathbf{M})}
$$

$$
\ddot{\varphi} = \frac{M_{11}\, f_2 - M_{12}\, f_1}{\det(\mathbf{M})}
$$

### 4.2 Electrical Dynamics (Armature Circuit)

The DC motor armature circuit obeys Kirchhoff's voltage law:

$$
L \frac{di_a}{dt} = V - R\, i_a - K_e \, N \, \dot{\varphi}
$$

where:
- $V$ is the applied armature voltage (saturated to $[-V_{max}, V_{max}]$),
- $R\, i_a$ is the resistive voltage drop,
- $K_e \, N \, \dot{\varphi}$ is the back-EMF (proportional to wheel speed through the gearbox).

Thus:

$$
\frac{di_a}{dt} = \frac{V - R\, i_a - K_e \, N \, \dot{\varphi}}{L}
$$

### 4.3 Complete State-Space ODE

The full 5-state derivative is:

$$
\dot{\mathbf{x}} = \begin{bmatrix} \dot{\theta} \\ \ddot{\theta} \\ \dot{\varphi} \\ \ddot{\varphi} \\ \dot{i}_a \end{bmatrix} = \begin{bmatrix} x_2 \\ \frac{M_{22}\, f_1 - M_{12}\, f_2}{\det(\mathbf{M})} \\ x_4 \\ \frac{M_{11}\, f_2 - M_{12}\, f_1}{\det(\mathbf{M})} \\ \frac{V - R\, x_5 - K_e N\, x_4}{L} \end{bmatrix}
$$

with:
- $f_1 = G \sin(x_1) - N K_t\, x_5 - b\, x_2 + \tau_{\text{ext}}$
- $f_2 = N K_t\, x_5 - b_{w,\text{eff}}\, x_4$

---

## 5. Numerical Integration — 5th-Order Runge-Kutta (Butcher)

The ODE is integrated using a **6-stage, 5th-order Runge-Kutta method** (Butcher tableau). This provides higher accuracy and better long-term energy conservation compared to classic RK4.

### 5.1 Butcher Tableau

$$
\begin{array}{c|cccccc}
0 & & & & & & \\
\frac{1}{4} & \frac{1}{4} & & & & & \\
\frac{1}{4} & \frac{1}{8} & \frac{1}{8} & & & & \\
\frac{1}{2} & 0 & -\frac{1}{2} & 1 & & & \\
\frac{3}{4} & \frac{3}{16} & 0 & 0 & \frac{9}{16} & & \\
1 & -\frac{3}{7} & \frac{2}{7} & \frac{12}{7} & -\frac{12}{7} & \frac{8}{7} & \\
\hline
& \frac{7}{90} & 0 & \frac{32}{90} & \frac{12}{90} & \frac{32}{90} & \frac{7}{90}
\end{array}
$$

### 5.2 Step Algorithm

Given state $\mathbf{x}_n$ at time $t_n$ with step size $h = \Delta t$:

1. $\mathbf{k}_1 = f(\mathbf{x}_n,\; V)$
2. $\mathbf{k}_2 = f\!\left(\mathbf{x}_n + \tfrac{h}{4}\mathbf{k}_1,\; V\right)$
3. $\mathbf{k}_3 = f\!\left(\mathbf{x}_n + \tfrac{h}{8}(\mathbf{k}_1 + \mathbf{k}_2),\; V\right)$
4. $\mathbf{k}_4 = f\!\left(\mathbf{x}_n + h(-\tfrac{1}{2}\mathbf{k}_2 + \mathbf{k}_3),\; V\right)$
5. $\mathbf{k}_5 = f\!\left(\mathbf{x}_n + h(\tfrac{3}{16}\mathbf{k}_1 + \tfrac{9}{16}\mathbf{k}_4),\; V\right)$
6. $\mathbf{k}_6 = f\!\left(\mathbf{x}_n + h(-\tfrac{3}{7}\mathbf{k}_1 + \tfrac{2}{7}\mathbf{k}_2 + \tfrac{12}{7}\mathbf{k}_3 - \tfrac{12}{7}\mathbf{k}_4 + \tfrac{8}{7}\mathbf{k}_5),\; V\right)$

Update:

$$
\mathbf{x}_{n+1} = \mathbf{x}_n + \frac{h}{90}\left(7\mathbf{k}_1 + 32\mathbf{k}_3 + 12\mathbf{k}_4 + 32\mathbf{k}_5 + 7\mathbf{k}_6\right)
$$

After each step, angles $\theta$ and $\varphi$ are wrapped to $(-\pi, \pi]$.

### 5.3 Implementation Notes

- All six stage buffers ($\mathbf{k}_1$–$\mathbf{k}_6$) and a temporary buffer are **pre-allocated** at initialization to avoid per-step heap allocations.
- The dynamics function writes into a pre-allocated output array (`_compute_dynamics_into`) for zero-allocation hot-path execution.
- Voltage is clamped to $[-V_{max}, V_{max}]$ before entering the integrator.

---

## 6. Energy Computation

### 6.1 Kinetic Energy

$$
T = \frac{1}{2} \begin{bmatrix} \dot{\theta} & \dot{\varphi} \end{bmatrix} \mathbf{M} \begin{bmatrix} \dot{\theta} \\ \dot{\varphi} \end{bmatrix} = \frac{1}{2}\left(M_{11}\dot{\theta}^2 + 2M_{12}\dot{\theta}\dot{\varphi} + M_{22}\dot{\varphi}^2\right)
$$

### 6.2 Potential Energy

Referenced to the upright position ($\theta = 0$):

$$
U = G(\cos\theta - 1)
$$

At upright: $U = 0$. Below upright: $U < 0$.

### 6.3 Total Mechanical Energy

$$
E = T + U
$$

### 6.4 Angular Momentum

Total angular momentum about the pivot:

$$
\mathcal{L} = M_{11}\dot{\theta} + M_{12}\dot{\varphi}
$$

---

## 7. Controllers

All controllers output a **voltage command** $V \in [-V_{max}, V_{max}]$. The motor/gearbox physics internally translates voltage into wheel torque through the armature dynamics.

For the complete mathematical formulation of all balance controllers, see [Control Methods](./control-methods.md). For swing-up strategies, see [Swing-Up Algorithms](./swing-up-algorithms.md). For practical tuning guidance, see [Gain Tuning Guide](./gain-tuning-guide.md).

### 7.1 No Control

$$
V = 0
$$

The pendulum evolves freely under gravity.

### 7.2 Manual Control

$$
V = \text{clamp}(V_{\text{user}},\; -V_{max},\; V_{max})
$$

A user-specified constant voltage.

### 7.3 PID Controller

A classical PID balance controller operating on the pendulum angle error from upright:

$$
V = K_p\, \theta + K_i \int_0^t \theta(\tau)\, d\tau + K_d\, \dot{\theta}
$$

**Anti-windup**: Integration is halted when the output is saturated and the integrator would grow further in the saturating direction. Specifically, the integral accumulates only when:
- The output is not saturated, OR
- The output is saturated but the error sign would reduce saturation.

Default gains: $K_p = 50$, $K_i = 0.1$, $K_d = 10$.

### 7.4 LQR Controller (Linear-Quadratic Regulator)

#### 7.4.1 Linearization

The full nonlinear system is linearized around the upright equilibrium ($\theta = 0$, $\dot{\theta} = 0$, $\dot{\varphi} = 0$, $i_a = 0$) with the 4-state vector:

$$
\mathbf{x} = \begin{bmatrix} \theta & \dot{\theta} & \dot{\varphi} & i_a \end{bmatrix}^T
$$

The linearized continuous-time system $\dot{\mathbf{x}} = \mathbf{A}\mathbf{x} + \mathbf{B}V$:

$$
\mathbf{A} = \begin{bmatrix}
0 & 1 & 0 & 0 \\
\frac{M_{22}\, G}{\Delta} & \frac{-M_{22}\, b}{\Delta} & \frac{M_{12}\, b_{w,\text{eff}}}{\Delta} & \frac{-(M_{22}+M_{12})\, N K_t}{\Delta} \\
\frac{-M_{12}\, G}{\Delta} & \frac{M_{12}\, b}{\Delta} & \frac{-M_{11}\, b_{w,\text{eff}}}{\Delta} & \frac{(M_{11}+M_{12})\, N K_t}{\Delta} \\
0 & 0 & \frac{-K_e N}{L} & \frac{-R}{L}
\end{bmatrix}
$$

$$
\mathbf{B} = \begin{bmatrix} 0 \\ 0 \\ 0 \\ 1/L \end{bmatrix}
$$

where $\Delta = \det(\mathbf{M}) = M_{11}M_{22} - M_{12}^2$.

#### 7.4.2 Optimal Control Law

The LQR minimizes the quadratic cost:

$$
J = \int_0^\infty \left(\mathbf{x}^T \mathbf{Q} \mathbf{x} + V^T \mathbf{R}_{\text{lqr}} V\right) dt
$$

The optimal gain is obtained by solving the **continuous algebraic Riccati equation** (CARE):

$$
\mathbf{A}^T \mathbf{P} + \mathbf{P} \mathbf{A} - \mathbf{P} \mathbf{B} \mathbf{R}_{\text{lqr}}^{-1} \mathbf{B}^T \mathbf{P} + \mathbf{Q} = 0
$$

The state-feedback gain:

$$
\mathbf{K} = \mathbf{R}_{\text{lqr}}^{-1} \mathbf{B}^T \mathbf{P}
$$

Control law:

$$
V = -\mathbf{K} \mathbf{x} = -(K_1\,\theta + K_2\,\dot{\theta} + K_3\,\dot{\varphi} + K_4\, i_a)
$$

#### 7.4.3 Weight Matrices (Defaults)

$$
\mathbf{Q} = \text{diag}(100,\; 1,\; 10,\; 0.01), \quad \mathbf{R}_{\text{lqr}} = 1
$$

#### 7.4.4 Fallback

If the Riccati solve fails or produces non-finite gains, the controller falls back to PID behavior and sets a warning flag.

### 7.5 Energy-Based Swing-Up Controller

Implements the **Åström–Furuta energy pumping** strategy to swing the pendulum from hanging to upright.

#### 7.5.1 Pendulum Energy

The pendulum-only energy (excluding the wheel) referenced to upright rest:

$$
E_p = \frac{1}{2} I_p \dot{\theta}^2 + G(\cos\theta - 1)
$$

At upright rest: $E_p = 0$. The target energy is $E_{\text{target}} = 0$.

#### 7.5.2 Energy Pumping Law

$$
V = -k_e \cdot (E_{\text{target}} - E_p) \cdot \dot{\varphi}
$$

where $k_e$ is the energy swing-up gain (default: 1.0).

The sign convention ensures energy flows into the pendulum: when $E_p < 0$ (below upright), the error is positive, and the voltage drives the wheel in the direction that pumps energy upward.

#### 7.5.3 Over-Energy Damping

If $E_p > E_{\text{target}}$ (pendulum has excess energy):

$$
V = -\frac{k_e}{2} \cdot \dot{\varphi}
$$

This bleeds energy from the wheel to prevent continuous rotation.

#### 7.5.4 Low-Speed Excitation

When $|\dot{\varphi}| < 0.5$ rad/s, a phase-based excitation is added:

$$
V_{\text{exc}} = 0.3 \cdot V_{max} \cdot \text{sign}(\sin\theta)
$$

This ensures the wheel starts spinning when nearly stationary.

#### 7.5.5 Wheel Speed Governor

- **Tapering**: For $|\dot{\varphi}| > 0.6 \cdot \dot{\varphi}_{max}$, voltage is linearly scaled down:

$$
V \leftarrow V \cdot \max\!\left(0,\; \frac{\dot{\varphi}_{max} - |\dot{\varphi}|}{\dot{\varphi}_{max} - 0.6\,\dot{\varphi}_{max}}\right)
$$

- **Hard cutoff**: $V = 0$ if $|\dot{\varphi}| \geq \dot{\varphi}_{max}$ (default: 50 rad/s).
- **Safety cutoff**: $V = 0$ if $|\dot{\varphi}| > 1.5 \cdot \dot{\varphi}_{max}$.

#### 7.5.6 Balance Handoff

When the pendulum enters the upright region:

$$
|\theta| < \theta_{\text{th}} \quad \text{and} \quad |\dot{\theta}| < \dot{\theta}_{\text{th}}
$$

(defaults: $\theta_{\text{th}} = 0.3$ rad, $\dot{\theta}_{\text{th}} = 1.0$ rad/s), control switches to LQR or PID balance.

### 7.6 Partial Feedback Linearization (PFL) Swing-Up

An alternative swing-up method that shapes the pendulum acceleration via feedback linearization.

#### 7.6.1 Desired Acceleration

$$
\ddot{\theta}_{\text{des}} = -K_p^{\text{pfl}} \sin\theta - K_d^{\text{pfl}} \dot{\theta}
$$

(defaults: $K_p^{\text{pfl}} = 5$, $K_d^{\text{pfl}} = 2$)

#### 7.6.2 Required Wheel Acceleration

From the first row of the coupled dynamics:

$$
M_{11}\ddot{\theta} + M_{12}\ddot{\varphi} = G\sin\theta
$$

Solving for the required wheel acceleration:

$$
\ddot{\varphi}_{\text{req}} = \frac{G\sin\theta - M_{11}\ddot{\theta}_{\text{des}}}{M_{12}}
$$

#### 7.6.3 Required Motor Torque

From the second row:

$$
M_{12}\ddot{\theta} + M_{22}\ddot{\varphi} = N K_t\, i_a
$$

$$
\tau_m = K_t\, i_a = \frac{M_{12}\ddot{\theta}_{\text{des}} + M_{22}\ddot{\varphi}_{\text{req}}}{N}
$$

#### 7.6.4 Quasi-Static Voltage

Using the steady-state motor model (neglecting inductance):

$$
V = R \cdot \frac{\tau_m}{K_t} + K_e\, N\, \dot{\varphi}
$$

#### 7.6.5 Over-Energy Guard

If pendulum energy exceeds the upright target ($E_p > 0$), the controller switches to wheel damping:

$$
V = -K_e\, N\, \dot{\varphi}
$$

### 7.7 Zero-Velocity Impulse Swing-Up

A third swing-up strategy that applies voltage pulses at pendulum swing extremes.

#### 7.7.1 Detection

Zero-crossings of $\dot{\theta}$ are detected (sign changes), indicating the pendulum is at a swing extreme.

#### 7.7.2 Impulse

At a zero-crossing with $|\theta| > 0.05$ rad and $E_p < 0$:

$$
V = \text{sign}(\theta) \cdot V_{max}
$$

applied for a fixed duration (default: 0.05 s).

The impulse is aborted if $|\dot{\varphi}| > 0.9 \cdot \dot{\varphi}_{max}$.

### 7.8 Sliding Mode Controller (SMC)

A robust nonlinear controller using boundary-layer smoothing.

#### 7.8.1 Sliding Surface

$$
s = c_1\,\theta + c_2\,\dot{\theta} + c_3\,\dot{\varphi}
$$

(defaults: $c_1 = 10$, $c_2 = 5$, $c_3 = 1$)

#### 7.8.2 Boundary-Layer Saturation

$$
\text{sat}\!\left(\frac{s}{\Phi}\right) = \begin{cases}
\frac{s}{\Phi} & \text{if } |s| \leq \Phi \\
\text{sign}(s) & \text{if } |s| > \Phi
\end{cases}
$$

where $\Phi$ is the boundary layer thickness (default: 0.05).

#### 7.8.3 Control Law

$$
V = -K \cdot \text{sat}\!\left(\frac{s}{\Phi}\right) - \eta \cdot s
$$

(defaults: $K = 2$, $\eta = 0.5$)

The boundary layer replaces the discontinuous $\text{sign}(s)$ to reduce chattering while maintaining robustness to model uncertainty.

---

## 8. Disturbance Model

External disturbances can be applied as:

- **Torque channel**: An additive torque $\tau_{\text{ext}}$ on the pendulum body (enters $f_1$).
- **Voltage channel**: An additive voltage offset on the motor command.

Supported waveforms: constant, sinusoidal, pulse, sawtooth, Gaussian noise.

For the complete disturbance model including injection channels, waveform definitions, and superposition, see [Disturbance Model](./disturbance-model.md).

---

## 9. Telemetry Outputs

At each physics step, the following quantities are computed for telemetry:

| Quantity | Formula |
|----------|---------|
| Back-EMF | $K_e \, N \, \dot{\varphi}$ |
| Motor torque | $K_t \, i_a$ |
| Wheel torque | $N \, K_t \, i_a$ |
| Kinetic energy | $\frac{1}{2}(M_{11}\dot{\theta}^2 + 2M_{12}\dot{\theta}\dot{\varphi} + M_{22}\dot{\varphi}^2)$ |
| Potential energy | $G(\cos\theta - 1)$ |
| Angular momentum | $M_{11}\dot{\theta} + M_{12}\dot{\varphi}$ |

---

## 10. Angle Wrapping

Both $\theta$ and $\varphi$ are wrapped to $(-\pi, \pi]$ after each integration step:

$$
\alpha_{\text{wrapped}} = \left((\alpha + \pi) \mod 2\pi\right) - \pi
$$

This prevents unbounded angle growth while preserving the physical state.

---

## 11. Summary

The reaction wheel inverted pendulum is a 5-state electro-mechanical system combining:

1. **Coupled rigid-body mechanics** (2×2 inertia matrix for pendulum + wheel),
2. **DC motor electrical dynamics** (armature circuit with back-EMF),
3. **Gearbox transmission** (reflecting rotor inertia and friction to wheel side),
4. **Multiple control strategies** (PID, LQR, energy swing-up, PFL, sliding mode).

The system is integrated with a 5th-order Runge-Kutta method at 1 kHz, providing accurate long-term energy conservation and stable numerical behavior for real-time interactive simulation.

---

## Related Documents

| Document | Content |
|----------|---------|
| [Control Methods](./control-methods.md) | Mathematical formulation of balance controllers (PID, LQR, SMC) |
| [Gain Tuning Guide](./gain-tuning-guide.md) | Practical tuning procedures for all controller gains |
| [Swing-Up Algorithms](./swing-up-algorithms.md) | Energy-based, PFL, and impulse swing-up strategies |
| [Disturbance Model](./disturbance-model.md) | External perturbation injection channels and waveforms |
| [Physical Parameters Reference](./physical-parameters.md) | Parameter definitions, units, and measurement methods |