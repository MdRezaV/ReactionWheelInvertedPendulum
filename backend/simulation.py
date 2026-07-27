"""Core physics engine for the reaction wheel inverted pendulum.

Implements the coupled electro-mechanical equations of motion for an
inverted pendulum stabilized by a reaction wheel driven through a DC
motor and gearbox. The motor torque acts on the wheel relative to the
pendulum; the reaction on the pendulum body emerges naturally from
solving the coupled 2×2 inertia matrix. The armature current is an
explicit state, yielding a 5-state ODE system.

State vector: [theta, theta_dot, phi, phi_dot, i_a]
  theta     – pendulum angle from upright (0 = upright)
  theta_dot – pendulum angular velocity
  phi       – wheel angle relative to the pendulum arm
  phi_dot   – wheel angular velocity relative to the pendulum arm
  i_a       – motor armature current
"""

from __future__ import annotations

import numpy as np

from models import ControlMode, SimulationParameters, TelemetryMessage

_DEAD_ZONE: float = 1e-8


def _wrap_angle(angle: float) -> float:
    """Wrap an angle into the range (-pi, pi]."""
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


class Simulation:
    """Fixed-step RK4 simulation of a reaction wheel inverted pendulum.

    The system models a DC motor with gearbox driving a reaction wheel
    mounted on an inverted pendulum. The full 5-state ODE captures the
    coupled mechanical dynamics (pendulum + wheel) and the electrical
    dynamics (armature circuit with back-EMF).

    Parameters
    ----------
    params : SimulationParameters
        Physical and numerical parameters for the system.
    """

    def __init__(self, params: SimulationParameters) -> None:
        self._params = params.model_copy()
        self._time: float = 0.0
        self._last_voltage: float = 0.0
        self._last_current: float = 0.0
        self._last_theta_ddot: float = 0.0
        self._last_phi_ddot: float = 0.0
        self._last_energy: float = 0.0
        self._compute_effective_quantities()
        self._validate_physical_quantities()
        # State vector: [theta, theta_dot, phi, phi_dot, i_a]
        self._state: np.ndarray = np.zeros(5, dtype=np.float64)
        # Pre-allocated RK5 buffers (avoids 6 array allocations per step)
        self._k1: np.ndarray = np.zeros(5, dtype=np.float64)
        self._k2: np.ndarray = np.zeros(5, dtype=np.float64)
        self._k3: np.ndarray = np.zeros(5, dtype=np.float64)
        self._k4: np.ndarray = np.zeros(5, dtype=np.float64)
        self._k5: np.ndarray = np.zeros(5, dtype=np.float64)
        self._k6: np.ndarray = np.zeros(5, dtype=np.float64)
        self._tmp: np.ndarray = np.zeros(5, dtype=np.float64)
        self.reset()

    # ------------------------------------------------------------------
    # Effective physical quantities
    # ------------------------------------------------------------------

    def _compute_effective_quantities(self) -> None:
        """Derive effective inertias, damping, and electrical params from user parameters."""
        p = self._params

        # Center-of-mass distance
        self._l_com: float = (
            p.pendulum_com_length if p.pendulum_com_length is not None
            else p.pendulum_length / 2.0
        )

        # Pendulum moment of inertia about pivot (uniform rod fallback)
        self._I_p: float = (
            p.pendulum_inertia if p.pendulum_inertia is not None
            else (1.0 / 3.0) * p.pendulum_mass * p.pendulum_length ** 2
        )

        # Wheel moment of inertia (annular ring fallback)
        self._I_w: float = (
            p.wheel_inertia if p.wheel_inertia is not None
            else 0.5 * p.wheel_mass * (p.wheel_outer_radius ** 2 + p.wheel_inner_radius ** 2)
        )

        # Gearbox-reflected motor parameters to wheel side
        self._N: float = p.gear_ratio
        self._Kt: float = p.motor_constant
        self._Ke: float = p.motor_constant
        self._R: float = p.motor_resistance
        self._L: float = p.motor_inductance

        # Effective wheel-side inertia including reflected rotor
        self._I_w_eff: float = self._I_w + p.motor_rotor_inertia * self._N ** 2

        # Effective wheel-side damping including reflected motor viscous friction
        self._b_w_eff: float = p.wheel_damping + p.motor_viscous_friction * self._N ** 2

        # Coupled inertia matrix components
        # M = [[I_p + m_w * L² + I_w_eff,  I_w_eff],
        #      [I_w_eff,                   I_w_eff]]
        self._M11: float = self._I_p + p.wheel_mass * p.pendulum_length ** 2 + self._I_w_eff
        self._M12: float = self._I_w_eff
        self._M22: float = self._I_w_eff

        # Gravity coefficient: (m_p * l_com + m_w * L) * g
        self._gravity_coeff: float = (
            (p.pendulum_mass * self._l_com + p.wheel_mass * p.pendulum_length) * p.gravity
        )

    def _validate_physical_quantities(self) -> None:
        """Raise ValueError if derived physical quantities are invalid."""
        if self._I_p <= 0.0:
            raise ValueError(
                f"Pendulum inertia about pivot must be positive, got {self._I_p:.6e}"
            )
        if self._I_w <= 0.0:
            raise ValueError(
                f"Wheel inertia must be positive, got {self._I_w:.6e}"
            )
        if self._L <= 0.0:
            raise ValueError(
                f"Motor inductance must be positive, got {self._L:.6e}"
            )
        if self._R <= 0.0:
            raise ValueError(
                f"Motor resistance must be positive, got {self._R:.6e}"
            )

        det = self._M11 * self._M22 - self._M12 ** 2
        if det <= 0.0:
            raise ValueError(
                f"Inertia matrix determinant must be positive, got {det:.6e}. "
                f"M11={self._M11:.6e}, M12={self._M12:.6e}, M22={self._M22:.6e}"
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset state to initial conditions defined in parameters."""
        p = self._params
        self._state = np.array(
            [p.initial_theta, p.initial_theta_dot, p.initial_phi, p.initial_phi_dot, p.initial_current],
            dtype=np.float64,
        )
        self._time = 0.0
        self._last_voltage = 0.0
        self._last_current = 0.0
        self._last_theta_ddot = 0.0
        self._last_phi_ddot = 0.0

    def update_params(self, params: SimulationParameters) -> None:
        """Safely replace simulation parameters and recompute derived quantities.

        The current state is preserved; only the physical model changes.
        Raises ValueError if the new parameters produce invalid physics.
        """
        old_params = self._params
        self._params = params.model_copy()
        try:
            self._compute_effective_quantities()
            self._validate_physical_quantities()
        except ValueError:
            self._params = old_params
            self._compute_effective_quantities()
            raise

    def get_state(self) -> dict[str, float]:
        """Return the current state as a dictionary."""
        return {
            "time": self._time,
            "theta": float(self._state[0]),
            "theta_dot": float(self._state[1]),
            "phi": float(self._state[2]),
            "phi_dot": float(self._state[3]),
            "current": float(self._state[4]),
        }

    @property
    def state_array(self) -> np.ndarray:
        """Direct reference to the internal state array (no copy, read-only use)."""
        return self._state

    @property
    def cached_energy(self) -> float:
        """Energy computed during the last step() call (avoids recomputation)."""
        return self._last_energy

    def get_telemetry_values(self, mode_int: int) -> list[float]:
        """Return telemetry as a flat list matching TELEMETRY_FIELD_ORDER (zero Pydantic overhead).

        Parameters
        ----------
        mode_int : int
            Integer-encoded control mode.

        Returns
        -------
        list[float]
            17-element list: [time, theta, theta_dot, theta_ddot, phi, phi_dot,
            phi_ddot, voltage, current, back_emf, motor_torque, wheel_torque,
            energy, kinetic_energy, potential_energy, angular_momentum, mode].
        """
        s = self._state
        phi_dot = float(s[3])
        i_a = float(s[4])
        back_emf = self._Ke * self._N * phi_dot
        motor_torque = self._Kt * i_a
        wheel_torque = self._N * self._Kt * i_a
        ke = 0.5 * (
            self._M11 * s[1] ** 2
            + 2.0 * self._M12 * s[1] * phi_dot
            + self._M22 * phi_dot ** 2
        )
        pe = self._gravity_coeff * (np.cos(s[0]) - 1.0)
        return [
            self._time,
            float(s[0]),
            float(s[1]),
            self._last_theta_ddot,
            float(s[2]),
            phi_dot,
            self._last_phi_ddot,
            self._last_voltage,
            i_a,
            back_emf,
            motor_torque,
            wheel_torque,
            self._last_energy,
            float(ke),
            float(pe),
            float(self._M11 * s[1] + self._M12 * phi_dot),
            float(mode_int),
        ]

    def get_telemetry(self, mode: ControlMode) -> TelemetryMessage:
        """Return a telemetry-ready snapshot of the simulation."""
        ke, pe = self._compute_energy_components()
        phi_dot = float(self._state[3])
        i_a = float(self._state[4])
        back_emf = self._Ke * self._N * phi_dot
        motor_torque = self._Kt * i_a
        wheel_torque = self._N * self._Kt * i_a

        return TelemetryMessage(
            time=self._time,
            theta=float(self._state[0]),
            theta_dot=float(self._state[1]),
            theta_ddot=self._last_theta_ddot,
            phi=float(self._state[2]),
            phi_dot=phi_dot,
            phi_ddot=self._last_phi_ddot,
            voltage=self._last_voltage,
            current=i_a,
            back_emf=back_emf,
            motor_torque=motor_torque,
            wheel_torque=wheel_torque,
            energy=ke + pe,
            kinetic_energy=ke,
            potential_energy=pe,
            angular_momentum=self._compute_angular_momentum(),
            mode=mode,
        )

    def compute_energy(self) -> float:
        """Compute total mechanical energy (kinetic + potential).

        Returns the cached value from the last step() if available,
        avoiding redundant computation within the same physics tick.
        """
        return self._last_energy

    def _compute_energy_components(self) -> tuple[float, float]:
        """Compute kinetic and potential energy separately."""
        theta, theta_dot, _phi, phi_dot, _i_a = self._state

        # KE = 0.5 * [theta_dot, phi_dot] @ M @ [theta_dot, phi_dot]^T
        ke = 0.5 * (
            self._M11 * theta_dot ** 2
            + 2.0 * self._M12 * theta_dot * phi_dot
            + self._M22 * phi_dot ** 2
        )

        # PE referenced to upright: V = gravity_coeff * (cos(theta) - 1)
        pe = self._gravity_coeff * (np.cos(theta) - 1.0)

        return float(ke), float(pe)

    def _compute_angular_momentum(self) -> float:
        """Compute total angular momentum about the pivot.

        L = M11 * theta_dot + M12 * phi_dot
        """
        _theta, theta_dot, _phi, phi_dot, _i_a = self._state
        return float(self._M11 * theta_dot + self._M12 * phi_dot)

    def compute_dynamics(self, state: np.ndarray, voltage: float, external_torque: float = 0.0) -> np.ndarray:
        """Compute the state derivative for a given state and applied voltage.

        Parameters
        ----------
        state : np.ndarray
            State vector [theta, theta_dot, phi, phi_dot, i_a].
        voltage : float
            Armature voltage applied to the motor (saturated internally).
        external_torque : float
            External torque applied to the pendulum body [N·m].

        Returns
        -------
        np.ndarray
            Derivative vector [theta_dot, theta_ddot, phi_dot, phi_ddot, di_a/dt].
        """
        theta = state[0]
        theta_dot = state[1]
        phi_dot = state[3]
        i_a = state[4]

        # Saturate voltage
        v = float(np.clip(voltage, -self._params.max_voltage, self._params.max_voltage))

        # Electromagnetic torque transmitted through gearbox to wheel side
        torque_wheel = self._N * self._Kt * i_a

        # Right-hand side of M @ [theta_ddot, phi_ddot]^T = f
        # Pendulum equation: gravity - reaction torque - pivot damping + external
        f1 = (
            self._gravity_coeff * np.sin(theta)
            - torque_wheel
            - self._params.damping * theta_dot
            + external_torque
        )
        # Wheel equation: motor torque - effective wheel damping
        f2 = torque_wheel - self._b_w_eff * phi_dot

        # Solve 2x2 system: M @ q_ddot = f
        det = self._M11 * self._M22 - self._M12 ** 2
        theta_ddot = (self._M22 * f1 - self._M12 * f2) / det
        phi_ddot = (self._M11 * f2 - self._M12 * f1) / det

        # Electrical dynamics: L * di_a/dt = V - R * i_a - Ke * N * phi_dot
        back_emf = self._Ke * self._N * phi_dot
        di_a_dt = (v - self._R * i_a - back_emf) / self._L

        return np.array([theta_dot, theta_ddot, phi_dot, phi_ddot, di_a_dt], dtype=np.float64)

    def _compute_dynamics_into(self, state: np.ndarray, voltage: float, out: np.ndarray, external_torque: float = 0.0) -> None:
        """Compute state derivative into a pre-allocated output array (zero-alloc hot path).

        Parameters
        ----------
        state : np.ndarray
            State vector [theta, theta_dot, phi, phi_dot, i_a].
        voltage : float
            Armature voltage applied to the motor (saturated internally).
        out : np.ndarray
            Pre-allocated output array to write derivatives into.
        external_torque : float
            External torque applied to the pendulum body [N·m].
        """
        theta = state[0]
        theta_dot = state[1]
        phi_dot = state[3]
        i_a = state[4]

        v = float(np.clip(voltage, -self._params.max_voltage, self._params.max_voltage))
        torque_wheel = self._N * self._Kt * i_a

        f1 = (
            self._gravity_coeff * np.sin(theta)
            - torque_wheel
            - self._params.damping * theta_dot
            + external_torque
        )
        f2 = torque_wheel - self._b_w_eff * phi_dot

        det = self._M11 * self._M22 - self._M12 ** 2
        out[0] = theta_dot
        out[1] = (self._M22 * f1 - self._M12 * f2) / det
        out[2] = phi_dot
        out[3] = (self._M11 * f2 - self._M12 * f1) / det
        out[4] = (v - self._R * i_a - self._Ke * self._N * phi_dot) / self._L

    def step(self, voltage: float, external_torque: float = 0.0) -> None:
        """Advance the simulation by one fixed time step using 5th-order RK.

        Uses Butcher's 5th-order Runge-Kutta method for improved accuracy
        and better energy conservation over long durations. Pre-allocated
        buffers avoid per-step array allocations.

        Parameters
        ----------
        voltage : float
            Armature voltage command (will be saturated to max_voltage).
        external_torque : float
            External torque applied to the pendulum body [N·m].
        """
        dt = self._params.time_step
        v_clipped = float(np.clip(voltage, -self._params.max_voltage, self._params.max_voltage))
        self._last_voltage = v_clipped if abs(v_clipped) >= _DEAD_ZONE else 0.0

        s = self._state
        k1, k2, k3, k4, k5, k6, tmp = (
            self._k1, self._k2, self._k3, self._k4, self._k5, self._k6, self._tmp
        )

        self._compute_dynamics_into(s, voltage, k1, external_torque)

        # k2: tmp = s + 0.25*dt*k1
        tmp[0] = s[0] + 0.25 * dt * k1[0]
        tmp[1] = s[1] + 0.25 * dt * k1[1]
        tmp[2] = s[2] + 0.25 * dt * k1[2]
        tmp[3] = s[3] + 0.25 * dt * k1[3]
        tmp[4] = s[4] + 0.25 * dt * k1[4]
        self._compute_dynamics_into(tmp, voltage, k2, external_torque)

        # k3: tmp = s + (1/8)*dt*k1 + (1/8)*dt*k2
        tmp[0] = s[0] + 0.125 * dt * (k1[0] + k2[0])
        tmp[1] = s[1] + 0.125 * dt * (k1[1] + k2[1])
        tmp[2] = s[2] + 0.125 * dt * (k1[2] + k2[2])
        tmp[3] = s[3] + 0.125 * dt * (k1[3] + k2[3])
        tmp[4] = s[4] + 0.125 * dt * (k1[4] + k2[4])
        self._compute_dynamics_into(tmp, voltage, k3, external_torque)

        # k4: tmp = s - 0.5*dt*k2 + dt*k3
        tmp[0] = s[0] + dt * (-0.5 * k2[0] + k3[0])
        tmp[1] = s[1] + dt * (-0.5 * k2[1] + k3[1])
        tmp[2] = s[2] + dt * (-0.5 * k2[2] + k3[2])
        tmp[3] = s[3] + dt * (-0.5 * k2[3] + k3[3])
        tmp[4] = s[4] + dt * (-0.5 * k2[4] + k3[4])
        self._compute_dynamics_into(tmp, voltage, k4, external_torque)

        # k5: tmp = s + (3/16)*dt*k1 + (9/16)*dt*k4
        tmp[0] = s[0] + dt * (0.1875 * k1[0] + 0.5625 * k4[0])
        tmp[1] = s[1] + dt * (0.1875 * k1[1] + 0.5625 * k4[1])
        tmp[2] = s[2] + dt * (0.1875 * k1[2] + 0.5625 * k4[2])
        tmp[3] = s[3] + dt * (0.1875 * k1[3] + 0.5625 * k4[3])
        tmp[4] = s[4] + dt * (0.1875 * k1[4] + 0.5625 * k4[4])
        self._compute_dynamics_into(tmp, voltage, k5, external_torque)

        # k6: tmp = s + (-3/7)*dt*k1 + (2/7)*dt*k2 + (12/7)*dt*k3 - (12/7)*dt*k4 + (8/7)*dt*k5
        c1 = -3.0 / 7.0
        c2 = 2.0 / 7.0
        c3 = 12.0 / 7.0
        c4 = -12.0 / 7.0
        c5 = 8.0 / 7.0
        tmp[0] = s[0] + dt * (c1 * k1[0] + c2 * k2[0] + c3 * k3[0] + c4 * k4[0] + c5 * k5[0])
        tmp[1] = s[1] + dt * (c1 * k1[1] + c2 * k2[1] + c3 * k3[1] + c4 * k4[1] + c5 * k5[1])
        tmp[2] = s[2] + dt * (c1 * k1[2] + c2 * k2[2] + c3 * k3[2] + c4 * k4[2] + c5 * k5[2])
        tmp[3] = s[3] + dt * (c1 * k1[3] + c2 * k2[3] + c3 * k3[3] + c4 * k4[3] + c5 * k5[3])
        tmp[4] = s[4] + dt * (c1 * k1[4] + c2 * k2[4] + c3 * k3[4] + c4 * k4[4] + c5 * k5[4])
        self._compute_dynamics_into(tmp, voltage, k6, external_torque)

        # s += (dt/90)*(7*k1 + 32*k3 + 12*k4 + 32*k5 + 7*k6)
        coeff = dt / 90.0
        s[0] += coeff * (7.0 * k1[0] + 32.0 * k3[0] + 12.0 * k4[0] + 32.0 * k5[0] + 7.0 * k6[0])
        s[1] += coeff * (7.0 * k1[1] + 32.0 * k3[1] + 12.0 * k4[1] + 32.0 * k5[1] + 7.0 * k6[1])
        s[2] += coeff * (7.0 * k1[2] + 32.0 * k3[2] + 12.0 * k4[2] + 32.0 * k5[2] + 7.0 * k6[2])
        s[3] += coeff * (7.0 * k1[3] + 32.0 * k3[3] + 12.0 * k4[3] + 32.0 * k5[3] + 7.0 * k6[3])
        s[4] += coeff * (7.0 * k1[4] + 32.0 * k3[4] + 12.0 * k4[4] + 32.0 * k5[4] + 7.0 * k6[4])

        # Store quantities from the final RK5 evaluation for telemetry
        self._last_theta_ddot = float(k6[1])
        self._last_phi_ddot = float(k6[3])
        self._last_current = float(s[4])

        # Cache energy for this step (avoids recomputation in controller + telemetry)
        ke = 0.5 * (
            self._M11 * s[1] ** 2
            + 2.0 * self._M12 * s[1] * s[3]
            + self._M22 * s[3] ** 2
        )
        pe = self._gravity_coeff * (np.cos(s[0]) - 1.0)
        self._last_energy = float(ke + pe)

        # Normalize angles
        s[0] = _wrap_angle(s[0])
        s[2] = _wrap_angle(s[2])
        self._time += dt

    def apply_impulse(self, voltage: float, duration_steps: int) -> None:
        """Apply a constant disturbance voltage for a number of steps.

        Parameters
        ----------
        voltage : float
            Disturbance voltage [V] (will be saturated).
        duration_steps : int
            Number of physics steps to apply the disturbance.
        """
        for _ in range(max(1, duration_steps)):
            self.step(voltage)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def time(self) -> float:
        """Current simulation time [s]."""
        return self._time

    @property
    def time_step(self) -> float:
        """Current integration time step [s] (no copy overhead)."""
        return self._params.time_step

    @property
    def state_is_finite(self) -> bool:
        """Whether all state values are finite (no NaN or Inf)."""
        return bool(np.all(np.isfinite(self._state)))

    @property
    def params(self) -> SimulationParameters:
        """Current simulation parameters (copy)."""
        return self._params.model_copy()

    @property
    def inertia_matrix(self) -> np.ndarray:
        """The 2×2 coupled inertia matrix (wheel-side, includes reflected rotor)."""
        return np.array(
            [[self._M11, self._M12],
             [self._M12, self._M22]],
            dtype=np.float64,
        )