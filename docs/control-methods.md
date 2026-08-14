# Control Methods — Mathematical Reference

This document presents the mathematical formulation of each balance/stabilization controller implemented in the reaction wheel inverted pendulum simulation. Swing-up strategies are covered separately and are **not** included here.

All controllers produce a **voltage command** $V$ applied to the DC motor armature. The voltage is always saturated:

$$
V_{\text{applied}} = \operatorname{clip}(V,\; -V_{\max},\; V_{\max})
$$

---

## System Model Recap

The plant is a 5-state coupled electro-mechanical system with state vector

$$
\mathbf{x} = \begin{bmatrix} \theta & \dot{\theta} & \varphi & \dot{\varphi} & i_a \end{bmatrix}^\top
$$

The mechanical dynamics are governed by the coupled 2×2 inertia matrix:

$$
\mathbf{M} \begin{bmatrix} \ddot{\theta} \\ \ddot{\varphi} \end{bmatrix}
= \begin{bmatrix} f_1 \\ f_2 \end{bmatrix}
$$

$$
f_1 = \Gamma \sin\theta - N K_t\, i_a - b\,\dot{\theta} + \tau_{\text{ext}}
$$

$$
f_2 = N K_t\, i_a - b_{w,\text{eff}}\,\dot{\varphi}
$$

where $\Gamma = (m_p \ell_c + m_w L)\,g$ is the gravity coefficient and $b_{w,\text{eff}} = b_w + N^2 b_m$.

The armature circuit dynamics are:

$$
L_a \frac{di_a}{dt} = V - R_a\, i_a - K_e N\, \dot{\varphi}
$$

The electromagnetic torque transmitted through the gearbox to the wheel is $\tau_w = N K_t\, i_a$.

For the complete derivation of the system dynamics, including parameter definitions, integration method, and energy expressions, see [System Description & Mathematical Model](./system-mathematics.md).

---

## 1. No Control

The simplest mode: zero voltage is applied, and the pendulum evolves under gravity and damping alone.

$$
V = 0
$$

This mode is useful for observing the open-loop (unstable) response of the system.

---

## 2. Manual Control

The operator specifies a constant voltage setpoint $V_{\text{set}}$, which is clamped to the actuator limit:

$$
V = \operatorname{clip}(V_{\text{set}},\; -V_{\max},\; V_{\max})
$$

No feedback is used. This mode is intended for open-loop experimentation and system identification.

---

## 3. PID Control

### 3.1 Control Law

The PID controller regulates the pendulum angle $\theta$ around the upright equilibrium ($\theta = 0$). The control signal is:

$$
V = K_p\, \theta + K_i \int_0^t \theta(\tau)\, d\tau + K_d\, \dot{\theta}
$$

| Gain | Role |
|------|------|
| $K_p$ | Proportional correction proportional to angle error |
| $K_i$ | Integral correction to eliminate steady-state offset |
| $K_d$ | Derivative damping proportional to angular velocity |

> **Sign convention.** A positive $\theta$ (pendulum tilted in the positive direction) requires a positive corrective voltage.

### 3.2 Anti-Windup (Clamping)

The integral term accumulates only when the output is **not** saturated, or when accumulation would **reduce** saturation. Formally, at each time step with integration step $\Delta t$:

$$
\text{Let } u_{\text{trial}} = K_p\,\theta + K_i\,I + K_d\,\dot{\theta}
$$

where $I$ is the current integral accumulator. The update rule is:

$$
I \leftarrow I + \theta\,\Delta t
\quad \text{if } |u_{\text{trial}}| < V_{\max}
$$

If $|u_{\text{trial}}| \ge V_{\max}$, integration proceeds **only** when it opposes the saturation:

$$
I \leftarrow I + \theta\,\Delta t
\quad \text{if } (u_{\text{trial}} > 0 \;\wedge\; \theta < 0) \;\;\vee\;\; (u_{\text{trial}} < 0 \;\wedge\; \theta > 0)
$$

Otherwise the integrator is frozen. This prevents wind-up during sustained saturation while still allowing recovery.

### 3.3 Final Output

$$
V = \operatorname{clip}\!\big(K_p\,\theta + K_i\,I + K_d\,\dot{\theta},\; -V_{\max},\; V_{\max}\big)
$$

---

## 4. LQR Control

### 4.1 Linearization

The full nonlinear dynamics are linearized around the upright equilibrium $\theta = 0$. The LQR uses a **4-state** model that includes the electrical (armature) dynamics:

$$
\mathbf{x} = \begin{bmatrix} \theta & \dot{\theta} & \dot{\varphi} & i_a \end{bmatrix}^\top,
\qquad
u = V
$$

The linearized continuous-time system is:

$$
\dot{\mathbf{x}} = \mathbf{A}\,\mathbf{x} + \mathbf{B}\,V
$$

### 4.2 System Matrices

Let $\Delta = M_{11} M_{22} - M_{12}^2$ (determinant of the inertia matrix). The $\mathbf{A}$ matrix is:

$$
\mathbf{A} = \begin{bmatrix}
0 & 1 & 0 & 0 \\[6pt]
\dfrac{M_{22}\,\Gamma}{\Delta}
& -\dfrac{M_{22}\,b}{\Delta}
& \dfrac{M_{12}\,b_{w,\text{eff}}}{\Delta}
& -\dfrac{(M_{22}+M_{12})\,N K_t}{\Delta} \\[10pt]
-\dfrac{M_{12}\,\Gamma}{\Delta}
& \dfrac{M_{12}\,b}{\Delta}
& -\dfrac{M_{11}\,b_{w,\text{eff}}}{\Delta}
& \dfrac{(M_{11}+M_{12})\,N K_t}{\Delta} \\[10pt]
0 & 0 & -\dfrac{K_e N}{L_a} & -\dfrac{R_a}{L_a}
\end{bmatrix}
$$

The $\mathbf{B}$ vector reflects that voltage enters only the electrical equation:

$$
\mathbf{B} = \begin{bmatrix} 0 \\ 0 \\ 0 \\ 1/L_a \end{bmatrix}
$$

### 4.3 Optimal Control Problem

The LQR minimizes the infinite-horizon quadratic cost:

$$
J = \int_0^\infty \!\big(\mathbf{x}^\top \mathbf{Q}\, \mathbf{x} + u^\top \mathbf{R}\, u\big)\, dt
$$

with weight matrices:

$$
\mathbf{Q} = \operatorname{diag}(q_\theta,\; q_{\dot{\theta}},\; q_{\dot{\varphi}},\; q_{i_a}),
\qquad
\mathbf{R} = r
$$

| Weight | Penalizes |
|--------|-----------|
| $q_\theta$ | Angle deviation from upright |
| $q_{\dot{\theta}}$ | Pendulum angular velocity |
| $q_{\dot{\varphi}}$ | Wheel angular velocity |
| $q_{i_a}$ | Armature current (electrical effort) |
| $r$ | Control voltage magnitude |

### 4.4 Riccati Equation and Gain

The optimal state-feedback gain is obtained from the **continuous algebraic Riccati equation** (CARE):

$$
\mathbf{A}^\top \mathbf{P} + \mathbf{P}\,\mathbf{A}
- \mathbf{P}\,\mathbf{B}\,\mathbf{R}^{-1}\,\mathbf{B}^\top\,\mathbf{P}
+ \mathbf{Q} = \mathbf{0}
$$

Solving for the symmetric positive-definite matrix $\mathbf{P}$, the optimal gain is:

$$
\mathbf{K} = \mathbf{R}^{-1}\,\mathbf{B}^\top\,\mathbf{P}
$$

### 4.5 Control Law

$$
V = -\mathbf{K}\,\mathbf{x}
= -\big(k_1\,\theta + k_2\,\dot{\theta} + k_3\,\dot{\varphi} + k_4\, i_a\big)
$$

The result is clamped to $[-V_{\max},\, V_{\max}]$.

### 4.6 Gain Recomputation and Fallback

- The gain $\mathbf{K}$ is **recomputed lazily** whenever the physical or control parameters change.
- If the Riccati solve fails (e.g., non-positive inertia determinant, non-finite gains), the controller **falls back to PID** behaviour and records a warning. The expensive Riccati solve is not retried at every physics step if the parameters have not changed.

---

## 5. Sliding Mode Control (SMC)

### 5.1 Sliding Surface

A scalar sliding surface is defined as a linear combination of the measurable states:

$$
s = c_1\,\theta + c_2\,\dot{\theta} + c_3\,\dot{\varphi}
$$

| Coefficient | Role |
|-------------|------|
| $c_1$ | Weight on angle error |
| $c_2$ | Weight on pendulum velocity |
| $c_3$ | Weight on wheel velocity |

The design objective is to drive $s \to 0$, which constrains the system to a desired dynamic manifold.

### 5.2 Boundary-Layer Saturation

To mitigate the high-frequency **chattering** inherent in pure sign-based SMC, a boundary-layer approximation replaces $\operatorname{sgn}(s)$ with a saturation function:

$$
\operatorname{sat}\!\left(\frac{s}{\Phi}\right) =
\begin{cases}
\dfrac{s}{\Phi} & \text{if } \left|\dfrac{s}{\Phi}\right| \le 1 \\[8pt]
\operatorname{sgn}(s) & \text{if } \left|\dfrac{s}{\Phi}\right| > 1
\end{cases}
$$

where $\Phi > 0$ is the **boundary-layer thickness**. Inside the layer the control is linear (smooth); outside it behaves like a conventional switching control.

### 5.3 Control Law

$$
V = -K\,\operatorname{sat}\!\left(\frac{s}{\Phi}\right) - \eta\, s
$$

| Parameter | Role |
|-----------|------|
| $K$ | Switching gain — drives the state toward the surface |
| $\eta$ | Proportional gain — adds continuous damping along the surface |
| $\Phi$ | Boundary thickness — trades chattering suppression against tracking precision |

The output is clamped to $[-V_{\max},\, V_{\max}]$.

### 5.4 Stability Sketch

On the sliding surface ($s = 0$), the equivalent dynamics satisfy $c_1\theta + c_2\dot\theta + c_3\dot\varphi = 0$. For appropriate positive gains, the Lyapunov candidate $\mathcal{V} = \tfrac{1}{2}s^2$ satisfies $\dot{\mathcal{V}} = s\,\dot{s} < 0$ outside the boundary layer, ensuring finite-time reachability of the layer and ultimate boundedness of the tracking error within $O(\Phi)$.

---

## 6. Summary

| Controller | States Used | Key Parameters | Output |
|------------|-------------|----------------|--------|
| No Control | — | — | $V = 0$ |
| Manual | — | $V_{\text{set}}$ | $V = V_{\text{set}}$ |
| PID | $\theta,\;\dot\theta$ | $K_p,\;K_i,\;K_d$ | $V = K_p\theta + K_i\!\int\theta + K_d\dot\theta$ |
| LQR | $\theta,\;\dot\theta,\;\dot\varphi,\;i_a$ | $\mathbf{Q},\;r$ | $V = -\mathbf{Kx}$ |
| Sliding Mode | $\theta,\;\dot\theta,\;\dot\varphi$ | $c_1,c_2,c_3,\;K,\;\eta,\;\Phi$ | $V = -K\,\text{sat}(s/\Phi) - \eta\,s$ |

All controllers operate on the **voltage** input to the armature circuit. The motor/gearbox physics (back-EMF, inductance, resistance, gear ratio) is handled internally by the simulation engine; controllers never compute torque directly.

---

## Related Documents

| Document | Content |
|----------|---------|
| [System Description & Mathematical Model](./system-mathematics.md) | Full system dynamics, integration method, energy expressions |
| [Gain Tuning Guide](./gain-tuning-guide.md) | Practical tuning procedures for all controller gains |
| [Swing-Up Algorithms](./swing-up-algorithms.md) | Energy-based, PFL, and impulse swing-up strategies |
| [Disturbance Model](./disturbance-model.md) | External perturbation injection channels and waveforms |
| [Physical Parameters Reference](./physical-parameters.md) | Parameter definitions, units, and measurement methods |