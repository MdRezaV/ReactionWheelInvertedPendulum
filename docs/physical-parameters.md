# Physical Parameters Reference — Reaction Wheel Inverted Pendulum

This document describes every physical parameter in the simulation, its role in the governing equations, its units, and practical guidance for measurement or estimation. The presentation is purely mathematical and physical; no implementation details are discussed.

---

## 1. System Overview

The system consists of a rigid pendulum arm pivoted at one end, with a reaction wheel mounted at the tip. The wheel is driven by a DC motor through a gearbox. The pendulum is stabilized in the inverted (upright) position by controlling the motor voltage, which produces a reaction torque on the pendulum body.

**Generalized coordinates:**

| Symbol | Name | Definition |
|--------|------|------------|
| $\theta$ | Pendulum angle | Angle of the pendulum arm from the upright vertical. $\theta = 0$ is upright. |
| $\phi$ | Wheel angle | Angle of the reaction wheel *relative to the pendulum arm*. |
| $i_a$ | Armature current | Electrical current through the motor winding. |

The full state is $(\theta,\;\dot\theta,\;\phi,\;\dot\phi,\;i_a)$ — a fifth-order system.

For the complete derivation of the system dynamics, including the coupled inertia matrix, equations of motion, and numerical integration method, see [System Description & Mathematical Model](./system-mathematics.md).

---

## 2. Pendulum Body Parameters

### 2.1 Pendulum Mass — $m_p$ [kg]

The total mass of the pendulum arm (excluding the wheel and motor rotor).

**Role in dynamics:** Enters the gravitational torque coefficient and the effective inertia about the pivot.

**Measurement:** Weigh the pendulum arm on a scale, excluding the wheel assembly and motor rotor. If the arm is a composite structure, weigh the complete arm minus the wheel/motor.

### 2.2 Pendulum Length — $L_p$ [m]

The distance from the pivot axis to the tip of the pendulum arm (where the wheel axle is located).

**Role in dynamics:**
- Determines the gravitational torque lever arm for the wheel mass: $m_w \cdot L_p \cdot g$.
- Contributes to the pendulum inertia about the pivot: $m_w \cdot L_p^2$.

**Measurement:** Measure from the pivot shaft center to the wheel axle center using calipers or a ruler.

### 2.3 Center-of-Mass Distance — $l_{\text{com}}$ [m]

Distance from the pivot to the center of mass of the pendulum arm alone (not including the wheel).

**Role in dynamics:** Determines the gravitational restoring torque:

$$\tau_g = \bigl(m_p \, l_{\text{com}} + m_w \, L_p\bigr)\, g \, \sin\theta$$

**Measurement:**
- **Balance method:** Support the arm horizontally on a knife edge; the balance point is the center of mass. Measure from the pivot hole to this point.
- **Composite calculation:** For a uniform rod of length $L_p$, $l_{\text{com}} = L_p / 2$. For non-uniform arms (e.g., tapered or with attached electronics), use the balance method.
- **Default fallback:** If not specified, the simulation assumes $l_{\text{com}} = L_p / 2$ (uniform rod).

### 2.4 Pendulum Moment of Inertia — $I_p$ [kg·m²]

Moment of inertia of the pendulum arm about the pivot axis.

**Role in dynamics:** Dominant term in the diagonal inertia matrix entry:

$$M_{11} = I_p + m_w L_p^2 + I_{w,\text{eff}}$$

**Measurement:**
- **Compound pendulum (swing) test:** Suspend the arm from the pivot, displace by a small angle, and measure the oscillation period $T$. Then:
$$I_p = \frac{m_p \, l_{\text{com}} \, g \, T^2}{4\pi^2} - m_p \, l_{\text{com}}^2$$
  (This gives the inertia about the pivot directly.)
- **CAD / analytical:** For a uniform slender rod: $I_p = \tfrac{1}{3} m_p L_p^2$. For a compound shape, sum contributions using the parallel-axis theorem.
- **Default fallback:** $I_p = \tfrac{1}{3} m_p L_p^2$ (uniform rod).

### 2.5 Pivot Damping — $b$ [N·m·s/rad]

Viscous friction coefficient at the pendulum pivot bearing.

**Role in dynamics:** Produces a dissipative torque opposing pendulum rotation:

$$\tau_{\text{damp}} = -b\,\dot\theta$$

**Measurement:**
- **Free-decay test:** With no motor drive, displace the pendulum and record the angular velocity decay. Fit $\dot\theta(t) \approx \dot\theta_0 \, e^{-(b/I_{\text{total}})\,t}$ to extract $b$.
- **Torque sensor:** Rotate the pivot slowly at constant angular velocity $\omega$ and measure the resisting torque $\tau$. Then $b = \tau / \omega$.
- Typical values for ball bearings: $10^{-5}$ to $10^{-3}$ N·m·s/rad. For bushings or dry contact, values up to $0.1$ or higher.

---

## 3. Reaction Wheel Parameters

### 3.1 Wheel Mass — $m_w$ [kg]

Mass of the reaction wheel (the disc or ring that spins relative to the arm).

**Measurement:** Remove the wheel from the axle and weigh it.

### 3.2 Wheel Inner Radius — $r_i$ [m]

Inner radius of the wheel (bore radius). For a solid disc, $r_i = 0$.

### 3.3 Wheel Outer Radius — $r_o$ [m]

Outer radius of the wheel.

**Measurement:** Measure diameter with calipers; divide by 2.

### 3.4 Wheel Moment of Inertia — $I_w$ [kg·m²]

Moment of inertia of the wheel about its spin axis (the axle).

**Role in dynamics:** Combined with reflected rotor inertia to form the effective wheel inertia:

$$I_{w,\text{eff}} = I_w + J_r \, N^2$$

This effective inertia appears in all three entries of the inertia matrix.

**Measurement:**
- **Analytical (annular ring):** $I_w = \tfrac{1}{2}\,m_w\,(r_o^2 + r_i^2)$
- **Analytical (solid disc):** $I_w = \tfrac{1}{2}\,m_w\,r_o^2$
- **Trifilar pendulum test:** Suspend the wheel from three equal-length wires, twist slightly, and measure the oscillation period $T$:
$$I_w = \frac{m_w \, g \, R_{\text{susp}}^2 \, T^2}{4\pi^2 \, \ell_{\text{wire}}}$$
  where $R_{\text{susp}}$ is the suspension radius and $\ell_{\text{wire}}$ is the wire length.
- **Spin-down test:** Spin the wheel at known angular velocity $\omega_0$, cut power, and measure deceleration $\alpha$. Then $I_w = \tau_{\text{friction}} / \alpha$.

### 3.5 Wheel Damping — $b_w$ [N·m·s/rad]

Viscous friction at the wheel bearing (relative to the arm).

**Role in dynamics:** Dissipative torque on the wheel:

$$\tau_{w,\text{damp}} = -b_{w,\text{eff}}\,\dot\phi$$

where $b_{w,\text{eff}} = b_w + b_m N^2$ (includes reflected motor friction).

**Measurement:** Same free-decay or spin-down methods as pivot damping, but applied to the wheel spinning on its axle with the pendulum arm held fixed.

---

## 4. Motor and Electrical Parameters

> **This section receives extended treatment because motor parameters are the most critical and most frequently mis-specified in reaction-wheel designs.**

### 4.1 Gear Ratio — $N$ [dimensionless]

The reduction ratio of the gearbox between the motor rotor and the reaction wheel. Defined as:

$$N = \frac{\omega_{\text{motor}}}{\omega_{\text{wheel}}} = \frac{\tau_{\text{wheel}}}{\tau_{\text{motor}}}$$

A value $N > 1$ means the motor spins faster than the wheel (speed reduction, torque multiplication).

**Role in dynamics:** The gear ratio transforms all motor-side quantities to the wheel side:

- Reflected rotor inertia: $J_r \to J_r N^2$
- Reflected viscous friction: $b_m \to b_m N^2$
- Torque at wheel: $\tau_w = N \, K_t \, i_a$
- Back-EMF at wheel speed: $V_{\text{emf}} = K_e \, N \, \dot\phi$

**Measurement:**
- Read the gearbox datasheet (e.g., "50:1" means $N = 50$).
- **Experimental:** Mark the rotor shaft and the output shaft. Rotate the output by exactly one revolution and count rotor revolutions. That count is $N$.
- **Note:** If the motor is direct-drive (no gearbox), set $N = 1$.

### 4.2 Motor Torque Constant — $K_t$ [N·m/A]

Relates armature current to electromagnetic torque produced by the motor:

$$\tau_{\text{motor}} = K_t \, i_a$$

The torque delivered to the wheel through the gearbox is:

$$\tau_{\text{wheel}} = N \, K_t \, i_a$$

**Measurement:**
- **Datasheet:** Usually listed as "torque constant" in N·m/A or mN·m/A.
- **Stall test:** Lock the rotor, apply a known current $i_a$, and measure the output torque $\tau$ with a torque sensor or lever-arm + force gauge. Then $K_t = \tau / i_a$.
- **Relationship to $K_e$:** In SI units, $K_t = K_e$ numerically (both in N·m/A and V·s/rad respectively). The simulation uses a single `motor_constant` for both.

### 4.3 Motor Back-EMF Constant — $K_e$ [V·s/rad]

The voltage generated by the motor due to rotation (back-electromotive force):

$$V_{\text{emf}} = K_e \, \omega_{\text{motor}} = K_e \, N \, \dot\phi$$

This opposes the applied voltage and limits the maximum achievable current at high speeds.

**Measurement:**
- **Back-drive test:** Disconnect the motor from any drive. Spin the shaft at a known angular velocity $\omega$ using a drill or another motor. Measure the open-circuit terminal voltage $V_{\text{oc}}$. Then:
$$K_e = \frac{V_{\text{oc}}}{\omega}$$
- **Equivalence:** For an ideal DC motor, $K_e = K_t$ in SI units. If the datasheet gives $K_e$ in V/(krpm), convert: $K_e\,[\text{V·s/rad}] = K_e\,[\text{V/krpm}] \times \frac{60}{2\pi \times 1000}$.

### 4.4 Armature Resistance — $R$ [Ω]

The DC resistance of the motor winding (both terminals).

**Role in dynamics:** Determines the steady-state current for a given voltage and speed:

$$i_a = \frac{V - K_e N \dot\phi}{R}$$

and the electrical time constant:

$$\tau_e = \frac{L}{R}$$

Higher $R$ means more resistive power loss ($P = i_a^2 R$) and lower maximum current.

**Measurement:**
- **Multimeter:** Measure resistance across the two motor terminals with a digital multimeter. For low-resistance motors (< 1 Ω), use a four-wire (Kelvin) measurement to eliminate lead resistance.
- **Locked-rotor test:** Apply a small DC voltage $V$ to the locked motor, measure current $i_a$. Then $R = V / i_a$ (valid at low speed where back-EMF ≈ 0).
- **Datasheet:** Usually listed directly.
- **Temperature note:** Copper resistance increases ~0.4%/°C. A motor rated at 25 °C will have ~15–20% higher resistance at operating temperature (~100 °C).

### 4.5 Armature Inductance — $L$ [H]

The electrical inductance of the motor winding.

**Role in dynamics:** Governs the rate of change of armature current:

$$L \,\frac{di_a}{dt} = V - R\,i_a - K_e\,N\,\dot\phi$$

This creates a first-order electrical lag with time constant $\tau_e = L/R$. For small DC motors, $\tau_e$ is typically 0.1–5 ms, much faster than the mechanical dynamics.

**Measurement:**
- **LCR meter:** Measure inductance at the motor terminals at ~1 kHz. Note that inductance may vary slightly with rotor position in non-ideal motors.
- **Datasheet:** Listed as "terminal inductance" or "winding inductance."
- **Step-response test:** Apply a voltage step to the locked rotor and measure the current rise with an oscilloscope. The current follows $i(t) = (V/R)(1 - e^{-t/\tau_e})$; extract $\tau_e$ and compute $L = \tau_e \cdot R$.
- **Typical values:** Small coreless motors: 0.01–0.5 mH. Larger brushed motors: 0.5–10 mH. Brushless (if modeled as DC equivalent): similar range.

### 4.6 Motor Rotor Inertia — $J_r$ [kg·m²]

Moment of inertia of the motor rotor (the spinning part of the motor itself) about its own axis.

**Role in dynamics:** Reflected through the gearbox to the wheel side:

$$I_{w,\text{eff}} = I_w + J_r \, N^2$$

For high gear ratios, $J_r N^2$ can dominate $I_w$, significantly increasing the effective wheel inertia and slowing the system's response.

**Measurement:**
- **Datasheet:** Usually listed as "rotor inertia" in g·cm² or kg·m².
- **Conversion:** $1\;\text{g·cm}^2 = 10^{-7}\;\text{kg·m}^2$.
- **Experimental (acceleration test):** Apply a known torque $\tau$ to the unloaded motor and measure angular acceleration $\alpha$: $J_r = \tau / \alpha$.
- **Experimental (energy method):** Spin the motor to known speed $\omega$, cut power, and measure deceleration due to known friction: $J_r = b_m / (\dot\omega/\omega)$.
- **Typical values:** Small motors (13 mm diameter): $10^{-7}$ to $10^{-6}$ kg·m². Medium motors (25–40 mm): $10^{-6}$ to $10^{-5}$ kg·m².

### 4.7 Motor Viscous Friction — $b_m$ [N·m·s/rad]

Viscous friction coefficient of the motor rotor bearings (Coulomb friction is not modeled; only the linear viscous term).

**Role in dynamics:** Reflected to the wheel side:

$$b_{w,\text{eff}} = b_w + b_m \, N^2$$

This contributes to the damping torque opposing wheel rotation.

**Measurement:**
- **No-load speed test:** Run the motor at no load with known voltage $V$. At steady state:
$$V = R\,i_a + K_e\,N\,\dot\phi$$
$$\tau_{\text{friction}} = K_t\,i_a = b_m\,N\,\dot\phi$$
  Measure $i_a$ and $\dot\phi$; solve for $b_m$:
$$b_m = \frac{K_t \, i_a}{N \, \dot\phi}$$
- **Spin-down test:** Spin the motor freely, record $\omega(t)$, fit exponential decay: $b_m = J_r / \tau_{\text{decay}}$.
- **Typical values:** $10^{-6}$ to $10^{-4}$ N·m·s/rad for small motors with ball bearings.

### 4.8 Maximum Voltage — $V_{\max}$ [V]

The saturation limit on the motor drive voltage. The controller output is clamped:

$$V_{\text{applied}} = \text{clip}(V_{\text{command}},\;-V_{\max},\;+V_{\max})$$

**Role in dynamics:** Limits the maximum achievable current and torque:

$$i_{a,\max} \approx \frac{V_{\max}}{R} \quad \text{(at stall, } \dot\phi = 0\text{)}$$

$$\tau_{\text{wheel},\max} \approx N \, K_t \, \frac{V_{\max}}{R}$$

**Measurement / Selection:**
- This is set by the motor driver (H-bridge, ESC, or amplifier) supply voltage.
- Must not exceed the motor's rated maximum voltage (datasheet).
- Common values: 6 V, 12 V, 24 V, 48 V depending on motor class.

---

## 5. Gravitational Parameter

### 5.1 Gravity — $g$ [m/s²]

Standard gravitational acceleration. Default: $g = 9.81$ m/s².

**Role in dynamics:** Sets the gravitational torque coefficient:

$$C_g = \bigl(m_p\,l_{\text{com}} + m_w\,L_p\bigr)\,g$$

The pendulum equation includes $C_g \sin\theta$ as the destabilizing (or restoring) torque.

---

## 6. Coupled Equations of Motion

The complete dynamics are expressed via the coupled 2×2 inertia matrix:

$$\mathbf{M} \begin{bmatrix} \ddot\theta \\ \ddot\phi \end{bmatrix} = \begin{bmatrix} f_1 \\ f_2 \end{bmatrix}$$

where

$$\mathbf{M} = \begin{bmatrix} M_{11} & M_{12} \\ M_{12} & M_{22} \end{bmatrix}$$

with

$$M_{11} = I_p + m_w L_p^2 + I_{w,\text{eff}}$$
$$M_{12} = I_{w,\text{eff}}$$
$$M_{22} = I_{w,\text{eff}}$$
$$I_{w,\text{eff}} = I_w + J_r N^2$$

The right-hand-side forces are:

$$f_1 = C_g \sin\theta \;-\; N K_t i_a \;-\; b\,\dot\theta \;+\; \tau_{\text{ext}}$$

$$f_2 = N K_t i_a \;-\; b_{w,\text{eff}}\,\dot\phi$$

Solving for the accelerations (Cramer's rule on the 2×2 system):

$$\ddot\theta = \frac{M_{22}\,f_1 - M_{12}\,f_2}{\det(\mathbf{M})}$$

$$\ddot\phi = \frac{M_{11}\,f_2 - M_{12}\,f_1}{\det(\mathbf{M})}$$

where $\det(\mathbf{M}) = M_{11} M_{22} - M_{12}^2 > 0$ (always positive for physical parameters).

The electrical dynamics complete the system:

$$L\,\frac{di_a}{dt} = V - R\,i_a - K_e\,N\,\dot\phi$$

---

## 7. Energy Expressions

### 7.1 Kinetic Energy

$$T = \frac{1}{2}\begin{bmatrix}\dot\theta & \dot\phi\end{bmatrix} \mathbf{M} \begin{bmatrix}\dot\theta \\ \dot\phi\end{bmatrix} = \frac{1}{2}\Bigl(M_{11}\dot\theta^2 + 2M_{12}\dot\theta\dot\phi + M_{22}\dot\phi^2\Bigr)$$

### 7.2 Potential Energy (upright-referenced)

$$V_{\text{grav}} = C_g\,(\cos\theta - 1)$$

At upright ($\theta = 0$): $V_{\text{grav}} = 0$. At hanging ($\theta = \pi$): $V_{\text{grav}} = -2C_g$.

### 7.3 Total Mechanical Energy

$$E = T + V_{\text{grav}}$$

The energy-based swing-up controller drives $E \to 0$ (the upright rest energy level).

### 7.4 Angular Momentum (about pivot)

$$H = M_{11}\,\dot\theta + M_{12}\,\dot\phi$$

---

## 8. Derived Quantities and Their Physical Meaning

| Derived quantity | Formula | Physical meaning |
|---|---|---|
| $I_{w,\text{eff}}$ | $I_w + J_r N^2$ | Total spinning inertia at the wheel shaft, including reflected rotor |
| $b_{w,\text{eff}}$ | $b_w + b_m N^2$ | Total viscous damping at the wheel shaft |
| $\tau_{\text{wheel}}$ | $N K_t i_a$ | Electromagnetic torque delivered to the wheel |
| $V_{\text{emf}}$ | $K_e N \dot\phi$ | Back-EMF opposing the applied voltage |
| $C_g$ | $(m_p l_{\text{com}} + m_w L_p)\,g$ | Gravitational torque coefficient |
| $\det(\mathbf{M})$ | $M_{11}M_{22} - M_{12}^2$ | Must be positive for well-posed dynamics |
| $\tau_e = L/R$ | — | Electrical time constant (current rise time) |
| $\tau_m = I_{w,\text{eff}} R / (K_t K_e N^2)$ | — | Mechanical time constant (speed response) |

---

## 9. Practical Motor Parameter Identification Guide

When selecting or characterizing a DC motor for a reaction wheel application, the following procedure gives all required parameters:

### Step 1: Read the Datasheet
Extract: $K_t$ (or $K_e$), $R$, $L$, $J_r$, rated voltage, rated current, no-load speed, stall torque.

### Step 2: Verify Resistance
Measure terminal resistance with a four-wire ohmmeter. Compare to datasheet. Account for temperature rise during operation.

### Step 3: Verify Torque Constant
If a torque sensor is available, run a stall test at several currents and confirm linearity: $\tau = K_t \, i_a$.

### Step 4: Measure Back-EMF Constant
Back-drive the motor at a measured speed and record open-circuit voltage. Confirm $K_e \approx K_t$.

### Step 5: Measure Inductance
Use an LCR meter at 1 kHz, or observe the current step response. Confirm $L/R$ gives the expected electrical bandwidth.

### Step 6: Measure Rotor Inertia
Use the datasheet value, or perform an acceleration test with known torque. This is critical for high gear ratios because of the $N^2$ amplification.

### Step 7: Measure Viscous Friction
Run the motor at no load, measure steady-state current at a known speed. Compute $b_m = K_t i_a / (N \dot\phi)$.

### Step 8: Account for the Gearbox
Multiply rotor inertia and viscous friction by $N^2$. Check that the gearbox backlash is acceptable for the control bandwidth required.

---

## 10. Parameter Sensitivity Summary

| Parameter | Effect on dynamics | Sensitivity |
|---|---|---|
| $m_p$, $l_{\text{com}}$ | Gravitational torque; larger → faster fall, harder to stabilize | High |
| $I_p$ | Slows pendulum angular acceleration; larger → easier to balance but slower response | Medium |
| $I_w$, $J_r$, $N$ | Effective wheel inertia; larger → more stored angular momentum but slower torque response | High |
| $K_t$ | Torque per amp; larger → more control authority | High |
| $R$ | Limits maximum current and torque; larger → weaker control | High |
| $L$ | Electrical lag; larger → slower current response | Low (usually $\tau_e \ll$ mechanical time) |
| $b$, $b_w$, $b_m$ | Damping; larger → more passive stability but more energy loss | Low–Medium |
| $g$ | Gravitational torque; larger → faster instability | High |
| $V_{\max}$ | Actuator saturation; limits maximum torque | High |

---

## 11. Units Quick Reference

| Parameter | SI Unit | Common alternative |
|---|---|---|
| Mass | kg | g |
| Length / radius | m | mm, cm |
| Moment of inertia | kg·m² | g·cm² ($\times 10^{-7}$) |
| Damping / friction | N·m·s/rad | — |
| Torque constant $K_t$ | N·m/A | mN·m/A ($\times 10^{-3}$) |
| Back-EMF constant $K_e$ | V·s/rad | V/krpm ($\times 9.549 \times 10^{-3}$) |
| Resistance $R$ | Ω | mΩ |
| Inductance $L$ | H | mH ($\times 10^{-3}$) |
| Voltage | V | — |
| Current | A | mA |
| Angular velocity | rad/s | rpm ($\times \pi/30$) |
| Gravity $g$ | m/s² | — |

---

## Related Documents

| Document | Content |
|----------|---------|
| [System Description & Mathematical Model](./system-mathematics.md) | Full system dynamics, integration method, energy expressions |
| [Control Methods](./control-methods.md) | Mathematical formulation of balance controllers |
| [Gain Tuning Guide](./gain-tuning-guide.md) | Practical tuning procedures for all controller gains |
| [Swing-Up Algorithms](./swing-up-algorithms.md) | Energy-based, PFL, and impulse swing-up strategies |
| [Disturbance Model](./disturbance-model.md) | External perturbation injection channels and waveforms |