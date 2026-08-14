# Gain Tuning Guide — Mathematical Reference

This document describes every tunable gain in the reaction wheel inverted pendulum system from a **mathematical and control-theoretic** perspective. It covers how each parameter shapes the closed-loop dynamics and provides practical tuning guidance.

---

## 1. System Dynamics (Equations of Motion)

The plant is a 5-state coupled electro-mechanical system:

$$\mathbf{x} = [\theta,\;\dot\theta,\;\varphi,\;\dot\varphi,\;i_a]^\top$$

where $\theta$ is the pendulum angle from upright, $\varphi$ is the wheel angle relative to the pendulum arm, and $i_a$ is the armature current.

For the complete derivation of the system dynamics, including parameter definitions, integration method, and energy expressions, see [System Description & Mathematical Model](./system-mathematics.md).

### 1.1 Mechanical Subsystem

The coupled 2×2 inertia matrix governs the mechanical dynamics:

$$\mathbf{M}\begin{bmatrix}\ddot\theta\\\ddot\varphi\end{bmatrix} = \mathbf{f}$$

$$\mathbf{M} = \begin{bmatrix} M_{11} & M_{12} \\ M_{12} & M_{22}\end{bmatrix}$$

where:

| Symbol | Definition |
|--------|-----------|
| $M_{11}$ | $I_p + m_w L^2 + I_{w,\text{eff}}$ |
| $M_{12} = M_{21}$ | $I_{w,\text{eff}}$ |
| $M_{22}$ | $I_{w,\text{eff}}$ |
| $I_{w,\text{eff}}$ | $I_w + J_r N^2$ (wheel + reflected rotor inertia) |

The forcing vector:

$$f_1 = (m_p \ell_c + m_w L)\,g\sin\theta - N K_t i_a - b\,\dot\theta + \tau_{\text{ext}}$$

$$f_2 = N K_t i_a - b_{w,\text{eff}}\,\dot\varphi$$

where $b_{w,\text{eff}} = b_w + N^2 b_{\text{visc}}$.

Solving via Cramer's rule ($\det M = M_{11}M_{22} - M_{12}^2$):

$$\ddot\theta = \frac{M_{22}\,f_1 - M_{12}\,f_2}{\det M}, \qquad \ddot\varphi = \frac{M_{11}\,f_2 - M_{12}\,f_1}{\det M}$$

### 1.2 Electrical Subsystem

$$L\,\frac{di_a}{dt} = V - R\,i_a - K_e N\,\dot\varphi$$

The back-EMF term $K_e N \dot\varphi$ couples the electrical and mechanical domains.

### 1.3 Key Physical Parameters

For complete parameter definitions, units, and measurement methods, see [Physical Parameters Reference](./physical-parameters.md).

| Parameter | Symbol | Effect on Dynamics |
|-----------|--------|-------------------|
| Pendulum mass | $m_p$ | Increases gravitational torque $\propto m_p \ell_c g$; makes the system harder to balance |
| Pendulum length | $L$ | Increases both gravitational torque and inertia; longer → slower natural frequency |
| Wheel inertia | $I_w$ | Larger $I_w$ → more angular momentum storage; smoother but slower response |
| Gear ratio | $N$ | Multiplies torque to wheel by $N$; increases reflected inertia by $N^2$; trades speed for torque |
| Motor constant | $K_t = K_e$ | Torque per amp; higher → more authority per unit current |
| Motor resistance | $R$ | Limits steady-state current: $i_{ss} = V/R$; higher $R$ → weaker actuator |
| Motor inductance | $L_a$ | Electrical time constant $\tau_e = L_a/R$; higher → slower current response |
| Damping | $b$ | Pendulum pivot friction; stabilizes open-loop but slows response |
| Wheel damping | $b_w$ | Wheel bearing friction; dissipates energy from the wheel |
| Max voltage | $V_{\max}$ | Actuator saturation limit; bounds maximum achievable torque |
| Gravity | $g$ | Sets the instability growth rate; higher $g$ → faster toppling |

---

## 2. PID Balance Controller

### 2.1 Control Law

$$V(t) = K_p\,\theta + K_i\int_0^t \theta\,d\tau + K_d\,\dot\theta$$

Output is clamped: $V \in [-V_{\max},\; V_{\max}]$.

### 2.2 Gain Effects

| Gain | Symbol | Mathematical Role | Effect of Increasing |
|------|--------|-------------------|---------------------|
| Proportional | $K_p$ | Stiffness: $K_p\theta$ | Faster response, reduced steady-state error; too high → oscillation |
| Integral | $K_i$ | Eliminates steady-state offset: $K_i\int\theta\,d\tau$ | Removes DC error; too high → windup, slow oscillation |
| Derivative | $K_d$ | Damping: $K_d\dot\theta$ | Suppresses overshoot, adds phase lead; too high → noise sensitivity |

### 2.3 Anti-Windup Mechanism

The integrator uses **clamping**: integration pauses when $|V| = V_{\max}$ and the integrator would grow further in the saturating direction. Formally:

$$\frac{d}{dt}\!\left(\int\theta\,d\tau\right) = \begin{cases} \theta & \text{if } |V| < V_{\max} \\ \theta & \text{if } |V| = V_{\max} \text{ and } \theta \cdot V < 0 \\ 0 & \text{otherwise} \end{cases}$$

### 2.4 Tuning Procedure

1. Set $K_i = 0$, $K_d = 0$. Increase $K_p$ until the pendulum oscillates around upright with acceptable frequency.
2. Add $K_d$ to damp the oscillation. Rule of thumb: $K_d \approx 2\sqrt{K_p \cdot I_{\text{eff}}} / V_{\max}$ where $I_{\text{eff}}$ is the effective inertia seen at the pivot.
3. Add small $K_i$ (typically $K_i \ll K_p$) to remove any residual offset. Keep $K_i < 0.1\,K_p$ to avoid windup.

**Typical starting point:** $K_p = 50$, $K_i = 0.1$, $K_d = 10$ (for the default physical parameters).

---

## 3. LQR Balance Controller

### 3.1 Linearization

Around the upright equilibrium ($\theta = 0$, $\dot\theta = 0$, $\dot\varphi = 0$, $i_a = 0$), the nonlinear system is linearized to:

$$\dot{\mathbf{x}} = A\mathbf{x} + B\,V$$

with state $\mathbf{x} = [\theta,\;\dot\theta,\;\dot\varphi,\;i_a]^\top$ and:

$$A = \begin{bmatrix} 0 & 1 & 0 & 0 \\ \frac{M_{22}\,\Gamma}{\Delta} & -\frac{M_{22}\,b}{\Delta} & \frac{M_{12}\,b_{w,\text{eff}}}{\Delta} & -\frac{(M_{22}+M_{12})\,N K_t}{\Delta} \\ -\frac{M_{12}\,\Gamma}{\Delta} & \frac{M_{12}\,b}{\Delta} & -\frac{M_{11}\,b_{w,\text{eff}}}{\Delta} & \frac{(M_{11}+M_{12})\,N K_t}{\Delta} \\ 0 & 0 & -\frac{K_e N}{L_a} & -\frac{R}{L_a} \end{bmatrix}$$

$$B = \begin{bmatrix} 0 \\ 0 \\ 0 \\ 1/L_a \end{bmatrix}$$

where $\Gamma = (m_p \ell_c + m_w L)\,g$ and $\Delta = M_{11}M_{22} - M_{12}^2$.

### 3.2 Optimal Control Law

The LQR minimizes the quadratic cost:

$$J = \int_0^\infty \left(\mathbf{x}^\top Q\,\mathbf{x} + V^\top R_{\text{lqr}}\,V\right) dt$$

The optimal feedback is:

$$V = -K\mathbf{x} = -R_{\text{lqr}}^{-1} B^\top P\,\mathbf{x}$$

where $P$ solves the continuous algebraic Riccati equation:

$$A^\top P + PA - PBR_{\text{lqr}}^{-1}B^\top P + Q = 0$$

### 3.3 Weight Matrix Interpretation

$$Q = \text{diag}(q_\theta,\; q_{\dot\theta},\; q_{\dot\varphi},\; q_{i_a})$$

| Weight | Symbol | Penalizes | Effect of Increasing |
|--------|--------|-----------|---------------------|
| $q_\theta$ | `lqr_q_theta` | Angle deviation from upright | Tighter angle regulation; more aggressive correction |
| $q_{\dot\theta}$ | `lqr_q_theta_dot` | Pendulum angular velocity | More damping of pendulum swings |
| $q_{\dot\varphi}$ | `lqr_q_phi_dot` | Wheel speed | Limits wheel spin; trades balance quality for wheel energy |
| $q_{i_a}$ | `lqr_q_current` | Armature current | Limits electrical effort; reduces actuator stress |
| $R_{\text{lqr}}$ | `lqr_r` | Control effort (voltage) | Higher → more conservative, less aggressive control |

### 3.4 Tuning Procedure

1. Start with $R_{\text{lqr}} = 1$. Set all $Q$ weights to 1.
2. Increase $q_\theta$ to tighten angle regulation (try 100–500).
3. Increase $q_{\dot\theta}$ if oscillations persist (try 1–10).
4. Increase $q_{\dot\varphi}$ if the wheel spins excessively (try 10–50).
5. Increase $q_{i_a}$ if current spikes are problematic (try 0.01–1).
6. Increase $R_{\text{lqr}}$ to globally reduce aggressiveness.

**Trade-off:** Larger $Q/R_{\text{lqr}}$ ratio → more aggressive control, higher voltage demands, faster settling. Smaller ratio → gentler, slower, but less actuator stress.

**Typical starting point:** $q_\theta = 100$, $q_{\dot\theta} = 1$, $q_{\dot\varphi} = 10$, $q_{i_a} = 0.01$, $R_{\text{lqr}} = 1$.

---

## 4. Energy-Based Swing-Up Controller

### 4.1 Pendulum Energy

The pendulum-only mechanical energy referenced to upright rest:

$$E_p = \frac{1}{2}I_p\,\dot\theta^2 + (m_p\ell_c + m_w L)\,g\,(\cos\theta - 1)$$

At upright rest: $E_p = 0$. Below upright: $E_p < 0$.

### 4.2 Pumping Law (Åström–Furuta)

$$V = -k_e\,(E_{\text{target}} - E_p)\,\dot\varphi$$

where $E_{\text{target}} = 0$ (upright energy level) and $k_e$ is the energy swing-up gain.

**Sign logic:** When $E_p < 0$ (below target), $e = E_{\text{target}} - E_p > 0$. The voltage is proportional to $-\dot\varphi$, ensuring energy flows into the pendulum regardless of wheel direction.

### 4.3 Gain Effect

| Parameter | Symbol | Effect |
|-----------|--------|--------|
| $k_e$ | `energy_swing_up_gain` | Pumping aggressiveness. Higher → faster energy injection, but risks overshooting $E_{\text{target}}$ and destabilizing near upright |
| $\dot\varphi_{\max}$ | `swing_up_max_wheel_speed` | Wheel speed governor. Voltage is zeroed when $|\dot\varphi| \geq \dot\varphi_{\max}$ and linearly tapered above $0.8\,\dot\varphi_{\max}$ |

### 4.4 Safety Mechanisms

- **Wheel speed governor:** $V = 0$ when $|\dot\varphi| \geq \dot\varphi_{\max}$.
- **Linear taper:** For $0.8\,\dot\varphi_{\max} < |\dot\varphi| < \dot\varphi_{\max}$:
  $$V \leftarrow V \cdot \frac{\dot\varphi_{\max} - |\dot\varphi|}{0.2\,\dot\varphi_{\max}}$$
- **Hard cutoff:** $V = 0$ when $|\dot\varphi| > 1.5\,\dot\varphi_{\max}$.
- **Energy overshoot damping:** When $E_p > 0$ (above target), $V = -0.5\,k_e\,\dot\varphi$ to bleed excess wheel energy.
- **Low-speed excitation:** When $|\dot\varphi| < 0.5$ rad/s, a phase-based excitation of amplitude $0.3\,V_{\max}$ is added in the direction of $\text{sign}(\sin\theta)$ to prevent stalling.

### 4.5 Tuning Procedure

1. Start with $k_e = 1$. Observe the energy trajectory.
2. Increase $k_e$ (up to ~5) if swing-up is too slow.
3. Decrease $k_e$ if the pendulum overshoots upright or the wheel saturates frequently.
4. Set $\dot\varphi_{\max}$ based on mechanical limits of the wheel/motor (default 50 rad/s).

---

## 5. Partial Feedback Linearization (PFL) Swing-Up

### 5.1 Desired Acceleration

$$\ddot\theta_{\text{des}} = -k_{\text{pfl},p}\,\sin\theta - k_{\text{pfl},d}\,\dot\theta$$

This shapes the pendulum dynamics as a damped nonlinear oscillator driving $\theta \to 0$.

### 5.2 Feedback Linearization

From the coupled dynamics, solve for the required wheel acceleration:

$$\ddot\varphi_{\text{req}} = \frac{\Gamma\sin\theta - M_{11}\,\ddot\theta_{\text{des}}}{M_{12}}$$

Then compute the required motor torque from the wheel equation:

$$\tau_m = \frac{M_{12}\,\ddot\theta_{\text{des}} + M_{22}\,\ddot\varphi_{\text{req}}}{N}$$

### 5.3 Quasi-Static Voltage Mapping

$$V = R\,\frac{\tau_m}{K_t} + K_e N\,\dot\varphi$$

The first term drives the required current; the second compensates back-EMF.

### 5.4 Gain Effects

| Gain | Symbol | Role | Effect of Increasing |
|------|--------|------|---------------------|
| $k_{\text{pfl},p}$ | `pfl_kp` | Proportional shaping: $-k_p\sin\theta$ | Faster convergence toward upright; too high → aggressive wheel demands |
| $k_{\text{pfl},d}$ | `pfl_kd` | Damping: $-k_d\dot\theta$ | Suppresses overshoot near upright; too high → sluggish swing-up |

### 5.5 Energy-Aware Saturation

When $E_p > 0$ (pendulum energy exceeds upright target), the controller switches to pure wheel damping:

$$V = -K_e N\,\dot\varphi$$

This prevents continuous rotation and allows the balance handoff to engage.

### 5.6 Tuning Procedure

1. Start with $k_{\text{pfl},p} = 5$, $k_{\text{pfl},d} = 2$.
2. Increase $k_{\text{pfl},p}$ for faster swing-up (creates larger $\ddot\theta_{\text{des}}$).
3. Increase $k_{\text{pfl},d}$ if the pendulum overshoots near upright.
4. Monitor wheel speed: if $\dot\varphi$ saturates frequently, reduce $k_{\text{pfl},p}$.

---

## 6. Zero-Velocity Impulse Swing-Up

### 6.1 Mechanism

Detects zero-crossings of $\dot\theta$ (pendulum at swing extremes) and applies a full-voltage pulse to the wheel:

$$V = \text{sign}(\theta) \cdot V_{\max} \quad \text{for duration } T_{\text{impulse}}$$

The direction is chosen so the reaction torque pushes the pendulum toward upright on the return swing.

### 6.2 Parameters

| Parameter | Symbol | Effect |
|-----------|--------|--------|
| $T_{\text{impulse}}$ | `zero_velocity_impulse_duration` | Pulse width [s]. Longer → more energy per impulse, but risks over-spinning the wheel |
| $k_{zv}$ | `zero_velocity_swing_gain` | (Reserved for proportional scaling; current implementation uses full $V_{\max}$) |

### 6.3 Safety

- Impulse is aborted if $|\dot\varphi| > 0.9\,\dot\varphi_{\max}$.
- No impulse is applied if $|\theta| < 0.05$ rad (near upright — let balance controller handle it).
- Only fires when $E_p < 0$ (energy deficit exists).

### 6.4 Tuning

- Increase $T_{\text{impulse}}$ for faster energy buildup (default 0.05 s = 50 ms).
- This method works best for systems with high gear ratio where a short voltage burst produces significant wheel momentum.

---

## 7. Sliding Mode Controller (SMC)

### 7.1 Sliding Surface

$$s = c_1\,\theta + c_2\,\dot\theta + c_3\,\dot\varphi$$

The surface $s = 0$ defines the desired dynamic relationship between pendulum angle, velocity, and wheel speed.

### 7.2 Control Law (Boundary Layer)

$$V = -K\,\text{sat}\!\left(\frac{s}{\Phi}\right) - \eta\,s$$

where the saturation function provides chattering-free operation:

$$\text{sat}(z) = \begin{cases} z & |z| \leq 1 \\ \text{sign}(z) & |z| > 1 \end{cases}$$

### 7.3 Gain Effects

| Gain | Symbol | Mathematical Role | Effect of Increasing |
|------|--------|-------------------|---------------------|
| $c_1$ | `smc_c1` | Angle weight in sliding surface | Stronger correction for angle error; dominates the surface shape |
| $c_2$ | `smc_c2` | Velocity weight in sliding surface | Adds damping to the surface dynamics |
| $c_3$ | `smc_c3` | Wheel speed weight in surface | Couples wheel dynamics into the sliding condition; helps coordinate wheel and pendulum |
| $K$ | `smc_k` | Reaching law gain | Faster convergence to $s=0$; too high → chattering at boundary edge |
| $\eta$ | `smc_eta` | Proportional damping on $s$ | Smooths the approach; adds continuous feedback within boundary |
| $\Phi$ | `smc_boundary` | Boundary layer thickness | Wider → smoother but less precise; narrower → more aggressive, approaches pure sign-based SMC |

### 7.4 Sliding Surface Dynamics

On the surface ($s = 0$):

$$c_1\,\theta + c_2\,\dot\theta + c_3\,\dot\varphi = 0$$

This constrains the system to a first-order manifold. The eigenvalue of the reduced dynamics is approximately $-c_1/c_2$ for the pendulum subsystem (when $c_3$ is small).

### 7.5 Tuning Procedure

1. Set $c_3 = 0$ initially. Choose $c_1/c_2$ to set the desired closed-loop time constant: $\tau \approx c_2/c_1$.
2. Add $c_3$ (small, e.g., 0.5–2) to incorporate wheel speed feedback.
3. Set $\Phi$ to limit chattering (start with 0.05). Increase if actuator chatter is observed.
4. Increase $K$ for faster reaching (start with 2).
5. Add $\eta$ (start with 0.5) for additional damping on the surface.

**Typical starting point:** $c_1 = 10$, $c_2 = 5$, $c_3 = 1$, $K = 2$, $\eta = 0.5$, $\Phi = 0.05$.

---

## 8. Balance Handoff Thresholds (Swing-Up → Balance Transition)

### 8.1 Switching Condition

The swing-up controller hands off to the balance controller (LQR or PID) when:

$$|\theta| < \theta_{\text{th}} \quad \text{AND} \quad |\dot\theta| < \dot\theta_{\text{th}}$$

### 8.2 Parameters

| Parameter | Symbol | Effect |
|-----------|--------|--------|
| $\theta_{\text{th}}$ | `upright_angle_threshold` | Angle window for handoff [rad]. Larger → earlier switch, but balance controller must handle larger initial errors. Smaller → swing-up must bring pendulum closer to upright before switching |
| $\dot\theta_{\text{th}}$ | `upright_velocity_threshold` | Velocity window [rad/s]. Larger → allows handoff at higher speeds. Smaller → requires near-zero velocity |

### 8.3 Tuning

- The balance controller (LQR or PID) must be stable for the initial condition $(\theta_{\text{th}}, \dot\theta_{\text{th}})$.
- Rule of thumb: $\theta_{\text{th}} \in [0.15, 0.5]$ rad (≈ 9°–29°), $\dot\theta_{\text{th}} \in [0.5, 2.0]$ rad/s.
- If the pendulum "falls out" after handoff, increase the balance controller's domain of attraction (increase $K_p$ or LQR $q_\theta$) or decrease $\theta_{\text{th}}$.

---

## 9. Disturbance Parameters

For the complete disturbance model including injection channels, waveform definitions, and superposition, see [Disturbance Model](./disturbance-model.md).

### 9.1 Channels

| Channel | Injection Point | Mathematical Effect |
|---------|----------------|-------------------|
| Voltage | Added to $V$ before motor: $V_{\text{actual}} = V_{\text{ctrl}} + V_{\text{dist}}$ | Simulates actuator noise, supply ripple |
| Torque | Added to $f_1$: $f_1 \mathrel{+}= \tau_{\text{dist}}$ | Simulates external push on pendulum body |

### 9.2 Waveforms

| Waveform | Equation | Parameters |
|----------|----------|-----------|
| Constant | $d(t) = A$ | Amplitude $A$ |
| Sinusoidal | $d(t) = A\sin(2\pi f t)$ | Amplitude $A$, frequency $f$ |
| Pulse | $d(t) = A$ if $(t \mod 1/f) < D/f$, else 0 | Amplitude $A$, frequency $f$, duty cycle $D$ |
| Sawtooth | $d(t) = A \cdot (2(t \mod 1/f) \cdot f - 1)$ | Amplitude $A$, frequency $f$ |
| Gaussian noise | $d(t) \sim \mathcal{N}(\mu, \sigma^2)$ | Mean $\mu$, std $\sigma$ |

---

## 10. Interaction Between Gains

### 10.1 Voltage Saturation Coupling

All controllers output voltage clamped to $[-V_{\max}, V_{\max}]$. The effective torque limit is:

$$\tau_{\max} = N \cdot K_t \cdot \frac{V_{\max}}{R}$$

If gains demand more torque than $\tau_{\max}$, the system saturates and performance degrades. **Always verify:**

$$K_p \cdot \theta_{\max} + K_d \cdot \dot\theta_{\max} < V_{\max}$$

for the expected operating range.

### 10.2 Gear Ratio Scaling

The gear ratio $N$ appears in multiple places:
- Torque to wheel: $\tau_w = N K_t i_a$ (torque multiplied by $N$)
- Reflected inertia: $J_r N^2$ (inertia multiplied by $N^2$)
- Back-EMF: $K_e N \dot\varphi$ (speed multiplied by $N$)

Increasing $N$ gives more torque authority but reduces maximum wheel speed and increases effective inertia. Gains tuned for one $N$ will not transfer directly to another.

### 10.3 Electrical Time Constant

The armature circuit bandwidth is:

$$\omega_e = \frac{R}{L_a}$$

If the control loop demands current changes faster than $\omega_e$, the electrical dynamics become the bottleneck. For the default parameters ($R = 1.2\,\Omega$, $L_a = 0.5\,\text{mH}$), $\omega_e = 2400$ rad/s, which is well above the mechanical bandwidth.

---

## 11. Summary Table

| Controller | Key Gains | Primary Tuning Goal |
|-----------|-----------|-------------------|
| PID | $K_p$, $K_i$, $K_d$ | Balance near upright; $K_p$ for stiffness, $K_d$ for damping, $K_i$ for offset |
| LQR | $Q$ diagonal, $R_{\text{lqr}}$ | Optimal trade-off between state regulation and control effort |
| Energy Swing-Up | $k_e$, $\dot\varphi_{\max}$ | Pump energy to upright without over-spinning wheel |
| PFL Swing-Up | $k_{\text{pfl},p}$, $k_{\text{pfl},d}$ | Shape pendulum acceleration toward upright |
| Zero-Velocity | $T_{\text{impulse}}$ | Impulse timing and magnitude at swing extremes |
| SMC | $c_1,c_2,c_3,K,\eta,\Phi$ | Robust stabilization with bounded chattering |
| Handoff | $\theta_{\text{th}}$, $\dot\theta_{\text{th}}$ | Smooth transition from swing-up to balance |

---

## 12. Recommended Tuning Workflow

1. **Start with physical parameters** — set mass, length, inertia, motor constants to match the real system.
2. **Verify open-loop stability** — run with no controller; observe natural toppling time.
3. **Tune PID first** — simplest to debug. Get stable balance within ±10° of upright.
4. **Switch to LQR** — tune $Q/R$ for performance. Compare with PID.
5. **Tune swing-up** — start with energy method, adjust $k_e$. Then try PFL for faster convergence.
6. **Set handoff thresholds** — ensure smooth transition without transient overshoot.
7. **Add disturbances** — test robustness with torque pulses and noise.
8. **Try SMC** — if robustness to parameter uncertainty is needed.

---

## Related Documents

| Document | Content |
|----------|---------|
| [System Description & Mathematical Model](./system-mathematics.md) | Full system dynamics, integration method, energy expressions |
| [Control Methods](./control-methods.md) | Mathematical formulation of balance controllers |
| [Swing-Up Algorithms](./swing-up-algorithms.md) | Detailed swing-up strategy derivations |
| [Disturbance Model](./disturbance-model.md) | Disturbance injection channels and waveforms |
| [Physical Parameters Reference](./physical-parameters.md) | Parameter definitions, units, and measurement methods |