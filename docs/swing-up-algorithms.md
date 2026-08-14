# Swing-Up Algorithms

## 1. System Model

The reaction wheel inverted pendulum is described by five coupled states: the pendulum angle θ, its angular velocity θ̇, the wheel angle φ, its relative angular velocity φ̇, and the armature current i_a. The swing-up controllers operate on the mechanical subsystem and issue voltage commands V that the motor–gearbox translates into wheel torque.

For the complete derivation of the system dynamics, including parameter definitions, integration method, and energy expressions, see [System Description & Mathematical Model](./system-mathematics.md).

### Coupled Inertia Matrix

The pendulum and wheel form a two-body rotational system. Defining the effective wheel inertia (including the reflected rotor through the gearbox of ratio N):

$$I_w^{\text{eff}} = I_w + I_{\text{rotor}} \, N^2$$

the coupled equations of motion take the matrix form:

$$\begin{bmatrix} M_{11} & M_{12} \\ M_{12} & M_{22} \end{bmatrix} \begin{bmatrix} \ddot{\theta} \\ \ddot{\varphi} \end{bmatrix} = \begin{bmatrix} G \sin\theta - b\,\dot\theta \\ N\,K_t\, i_a - b_w^{\text{eff}}\,\dot\varphi \end{bmatrix}$$

where the inertia terms are:

$$M_{11} = I_p + m_w L^2 + I_w^{\text{eff}}$$

$$M_{12} = M_{22} = I_w^{\text{eff}}$$

and the gravitational coefficient aggregates the pendulum and wheel weight acting at their respective moment arms:

$$G = \left(m_p \, \ell_{\text{com}} + m_w \, L\right) g$$

Here $I_p$ is the pendulum moment of inertia about the pivot, $m_p$ and $m_w$ are the pendulum and wheel masses, $\ell_{\text{com}}$ is the pendulum center-of-mass distance, $L$ is the pendulum length, and $g$ is gravitational acceleration.

### Armature Circuit

The DC motor electrical dynamics couple back into the mechanical system through the back-EMF:

$$L_a \frac{di_a}{dt} = V - R_a\, i_a - K_e\, N\, \dot\varphi$$

where $L_a$ is armature inductance, $R_a$ is armature resistance, and $K_e = K_t$ is the motor constant (torque constant equals back-EMF constant by convention).

### Energy Reference

The pendulum mechanical energy is referenced to the upright rest configuration (θ = 0, θ̇ = 0), so that:

$$E_p(\theta, \dot\theta) = \tfrac{1}{2}\, I_p\, \dot\theta^2 + G\,(\cos\theta - 1)$$

At upright rest, $E_p = 0$. Below upright, $E_p < 0$. The swing-up goal is to drive $E_p \to 0$ with $\dot\theta \to 0$ simultaneously.

---

## 2. Energy-Based Swing-Up (Åström–Furuta Method)

### Physical Intuition

The pendulum is a nonlinear oscillator. By applying wheel torque in the correct phase with the pendulum's swing, energy is pumped into the system on each half-cycle—exactly as a child pumps a playground swing by shifting their center of mass at the right moments. The key insight of the Åström–Furuta approach is to track only the **pendulum's** energy, not the total system energy, so that energy does not accumulate uselessly in the spinning wheel.

### Control Law

The voltage command is proportional to the product of the energy deficit and the wheel velocity:

$$V = -k_e \;\bigl(E_{\text{target}} - E_p\bigr)\; \dot\varphi$$

where:

- $k_e > 0$ is the energy gain (parameter `energy_swing_up_gain`, default 1.0),
- $E_{\text{target}} = 0$ J (the upright rest energy),
- $E_p = \tfrac{1}{2} I_p \dot\theta^2 + G(\cos\theta - 1)$ is the instantaneous pendulum energy,
- $\dot\varphi$ is the relative wheel angular velocity.

The negative sign ensures that when energy is below target ($E_{\text{target}} - E_p > 0$), the voltage drives the wheel in the direction that increases pendulum energy on the current half-swing.

### Over-Energy Damping

If the pendulum overshoots the target ($E_p > 0$), continued pumping would drive the pendulum into continuous rotation. The controller switches to dissipative wheel damping:

$$V = -\tfrac{1}{2}\, k_e\, \dot\varphi$$

This bleeds kinetic energy from the wheel through the motor's resistive losses.

### Phase-Based Excitation

Near the swing extremes the wheel velocity $\dot\varphi$ approaches zero, and the pumping signal $-k_e (E_{\text{target}} - E_p) \dot\varphi$ vanishes. The pendulum stalls. To escape this deadlock, an excitation voltage is injected whenever $|\dot\varphi| < \varphi_{\text{exc}}$, where $\varphi_{\text{exc}} = 0.5$ rad/s:

$$V_{\text{exc}} = \alpha\, V_{\max}\, \operatorname{sign}(\sin\theta)$$

with excitation fraction $\alpha = 0.3$. The direction $\operatorname{sign}(\sin\theta)$ ensures the wheel kicks in the direction that will raise the pendulum on the subsequent swing.

### Wheel-Speed Tapering

To prevent the wheel from accelerating beyond safe limits, the voltage is linearly attenuated when $|\dot\varphi|$ exceeds 60 % of the maximum allowed wheel speed $\omega_{\max}$:

$$\text{scale} = \max\!\left(0,\; \frac{\omega_{\max} - |\dot\varphi|}{\omega_{\max} - 0.6\,\omega_{\max}}\right), \qquad V \leftarrow V \cdot \text{scale}$$

This creates a smooth linear ramp from full voltage at $|\dot\varphi| = 0.6\,\omega_{\max}$ down to zero at $|\dot\varphi| = \omega_{\max}$.

---

## 3. Partial Feedback Linearization (PFL)

### Physical Intuition

Rather than indirectly pumping energy, PFL directly commands the pendulum's angular acceleration by inverting the nonlinear coupled dynamics. The controller specifies where it wants $\ddot\theta$ to go, computes what wheel acceleration $\ddot\varphi$ is required to achieve it through the inertia coupling, and translates that into a voltage. This is a model-based approach: it requires accurate knowledge of the inertia matrix and gravitational term.

### Desired Pendulum Acceleration

The controller defines a virtual PD target for the pendulum:

$$\ddot\theta_{\text{des}} = -k_p \sin\theta - k_d\, \dot\theta$$

The $\sin\theta$ term provides a position-dependent restoring acceleration (strong near horizontal, weak near upright), while the $-k_d \dot\theta$ term provides velocity damping. Together they shape a stable trajectory toward θ = 0.

### Dynamic Inversion

From the first row of the coupled dynamics:

$$M_{11}\,\ddot\theta + M_{12}\,\ddot\varphi = G\sin\theta - b\,\dot\theta$$

Substituting $\ddot\theta = \ddot\theta_{\text{des}}$ and solving for the required wheel acceleration:

$$\ddot\varphi_{\text{req}} = \frac{G\sin\theta - M_{11}\,\ddot\theta_{\text{des}}}{M_{12}}$$

This is the wheel acceleration that, through the off-diagonal inertia coupling $M_{12}$, will produce the desired pendulum acceleration.

### Torque and Voltage Mapping

From the second row of the coupled dynamics, the motor torque needed to produce $\ddot\varphi_{\text{req}}$ while maintaining $\ddot\theta_{\text{des}}$ is:

$$\tau_m = \frac{M_{12}\,\ddot\theta_{\text{des}} + M_{22}\,\ddot\varphi_{\text{req}}}{N}$$

Under the quasi-static electrical assumption (armature inductance negligible at the mechanical timescale), the current is $i_a = \tau_m / K_t$, and the required voltage is:

$$V = R_a \frac{\tau_m}{K_t} + K_e\, N\, \dot\varphi$$

The first term is the resistive voltage needed to drive the required current; the second compensates for the back-EMF generated by the spinning wheel.

### Energy-Aware Saturation

If the pendulum energy has already reached or exceeded the upright target ($E_p > 0$), further acceleration would cause overshoot. The controller switches to back-EMF braking:

$$V = -K_e\, N\, \dot\varphi$$

This short-circuits the motor electrically (zero external voltage), causing the back-EMF to drive a braking current through the armature resistance, dissipating wheel kinetic energy.

---

## 4. Zero-Velocity Impulse Swing-Up

### Physical Intuition

This is the most direct strategy: wait until the pendulum reaches a swing extreme (where it momentarily stops), then deliver a sharp torque impulse to the wheel. By conservation of angular momentum, the pendulum receives an equal and opposite angular impulse, launching it back with more energy than before. Repeating this at each successive extreme gradually raises the swing amplitude.

### Zero-Crossing Detection

The pendulum is at a swing extreme when its angular velocity changes sign:

$$(\dot\theta_{\text{prev}} > 0 \;\wedge\; \dot\theta \leq 0) \quad \lor \quad (\dot\theta_{\text{prev}} < 0 \;\wedge\; \dot\theta \geq 0)$$

An impulse is triggered only if $|\theta| > \theta_{\min} = 0.05$ rad (to avoid spurious triggers near the upright equilibrium) and the pendulum energy is still below target ($E_p < 0$).

### Impulse Law

At a detected zero-crossing, a constant voltage is applied for a fixed duration $\Delta t_{\text{imp}}$:

$$V = \operatorname{sign}(\theta) \cdot V_{\max}, \qquad t \in [0,\; \Delta t_{\text{imp}}]$$

The number of integration steps is $\lceil \Delta t_{\text{imp}} / h \rceil$, where $h$ is the physics time step.

The sign convention $\operatorname{sign}(\theta)$ ensures the wheel reaction torque pushes the pendulum **toward** upright on the return swing. When $\theta > 0$ (pendulum tilted right), a positive voltage accelerates the wheel positively; the reaction decelerates the pendulum, pulling it back through vertical.

### Energy Scaling

The impulse magnitude is implicitly scaled by the energy deficit: impulses are only triggered when $E_p < 0$. As the pendulum approaches upright, the energy deficit shrinks, and the zero-crossings occur closer to θ = 0, eventually falling below the trigger threshold $\theta_{\min}$.

### Safety Cutoff

If during an active impulse the wheel speed exceeds $0.9\,\omega_{\max}$, the impulse is immediately terminated and voltage returns to zero. This prevents wheel overspeed from consecutive impulses.

---

## 5. Balance Handoff

The swing-up controllers are only effective far from upright. Near the equilibrium, a stabilizing balance controller takes over. The handoff condition requires both angle and velocity to be within thresholds:

$$|\theta| < \theta_{\text{up}} \quad \wedge \quad |\dot\theta| < \dot\theta_{\text{up}}$$

where $\theta_{\text{up}} = 0.3$ rad and $\dot\theta_{\text{up}} = 1.0$ rad/s by default.

### LQR Balance

The balance controller linearizes the full 4-state electro-mechanical system $[\theta,\; \dot\theta,\; \dot\varphi,\; i_a]$ around the upright equilibrium. The linearized system $\dot{\mathbf{x}} = A\mathbf{x} + B\,V$ yields the optimal state-feedback gain via the continuous algebraic Riccati equation:

$$A^\top P + P A - P B R^{-1} B^\top P + Q = 0$$

The control law is:

$$V = -K\,\mathbf{x} = -R^{-1} B^\top P\;\mathbf{x}$$

where $Q = \operatorname{diag}(q_\theta,\; q_{\dot\theta},\; q_{\dot\varphi},\; q_{i_a})$ penalizes state deviations and $R$ penalizes control effort.

For the complete LQR derivation including the linearized system matrices, see [Control Methods — LQR Control](./control-methods.md#4-lqr-control).

### PID Balance

A classical PID on the angle error with anti-windup:

$$V = k_p\,\theta + k_i \int_0^t \theta\, d\tau + k_d\, \dot\theta$$

The integral accumulator is frozen when the output is saturated and the integrator would grow further in the saturating direction (clamping anti-windup).

For the complete PID formulation including anti-windup details, see [Control Methods — PID Control](./control-methods.md#3-pid-control).

---

## 6. Global Safety Constraints

All swing-up methods are wrapped in a layered protection scheme that operates regardless of the selected algorithm:

| Layer | Condition | Effect |
|---|---|---|
| Hard speed guard | $\lvert\dot\varphi\rvert > 1.5\,\omega_{\max}$ | $V = 0$ (immediate shutoff) |
| Speed governor | $\lvert\dot\varphi\rvert \geq \omega_{\max}$ | $V = 0$ |
| Upper-band taper | $\lvert\dot\varphi\rvert > 0.8\,\omega_{\max}$ | $V \leftarrow V \cdot \dfrac{\omega_{\max} - \lvert\dot\varphi\rvert}{0.2\,\omega_{\max}}$ |
| Voltage saturation | Always | $V \leftarrow \operatorname{clip}(V,\; -V_{\max},\; +V_{\max})$ |

These ensure the wheel never exceeds mechanical limits regardless of controller aggressiveness or parameter misconfiguration.

---

## 7. Parameter Summary

| Symbol | Parameter name | Default | Unit | Role |
|---|---|---|---|---|
| $k_e$ | `energy_swing_up_gain` | 1.0 | — | Energy pumping gain |
| $k_p^{\text{PFL}}$ | `pfl_kp` | 5.0 | rad⁻¹s⁻² | PFL proportional gain |
| $k_d^{\text{PFL}}$ | `pfl_kd` | 2.0 | rad⁻¹s⁻¹ | PFL derivative gain |
| $\omega_{\max}$ | `swing_up_max_wheel_speed` | 50.0 | rad/s | Wheel speed ceiling |
| $\Delta t_{\text{imp}}$ | `zero_velocity_impulse_duration` | 0.05 | s | Impulse duration |
| $\varphi_{\text{exc}}$ | (class constant) | 0.5 | rad/s | Excitation threshold |
| $\alpha$ | (class constant) | 0.3 | — | Excitation fraction of $V_{\max}$ |
| $\theta_{\text{up}}$ | `upright_angle_threshold` | 0.3 | rad | Balance handoff angle |
| $\dot\theta_{\text{up}}$ | `upright_velocity_threshold` | 1.0 | rad/s | Balance handoff velocity |
| $\theta_{\min}$ | (class constant) | 0.05 | rad | Zero-crossing trigger guard |

---

## 8. Mode Selection

The control mode determines whether balance handoff is active:

| Mode | Swing-up | Balance |
|---|---|---|
| `swing_up` / `energy_swing_up` | ✓ | — |
| `swing_up_lqr` | ✓ | LQR |
| `swing_up_pid` | ✓ | PID |

The swing-up method is chosen independently via `swing_up_method ∈ {energy, pfl, zero_velocity}`. Any method can be paired with any balance mode.

---

## Related Documents

| Document | Content |
|----------|---------|
| [System Description & Mathematical Model](./system-mathematics.md) | Full system dynamics, integration method, energy expressions |
| [Control Methods](./control-methods.md) | Mathematical formulation of balance controllers (PID, LQR, SMC) |
| [Gain Tuning Guide](./gain-tuning-guide.md) | Practical tuning procedures for all controller gains |
| [Disturbance Model](./disturbance-model.md) | External perturbation injection channels and waveforms |
| [Physical Parameters Reference](./physical-parameters.md) | Parameter definitions, units, and measurement methods |