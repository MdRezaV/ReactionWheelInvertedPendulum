"""Core physics engine for the reaction wheel inverted pendulum.

Implements the coupled equations of motion for an inverted pendulum
stabilized by a reaction wheel. The motor torque acts on the wheel
relative to the pendulum; the reaction on the pendulum body emerges
naturally from solving the coupled 2×2 inertia matrix.

State vector: [theta, theta_dot, phi, phi_dot]
  theta     – pendulum angle from upright (0 = upright)
  theta_dot – pendulum angular velocity
  phi       – wheel angle relative to the pendulum arm
  phi_dot   – wheel angular velocity relative to the pendulum arm
"""

from __future__ import annotations

import numpy as np

from models import ControlMode, SimulationParameters, TelemetryMessage


def _wrap_angle(angle: float) -> float:
    """Wrap an angle into the range (-pi, pi]."""
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


class Simulation:
    """Fixed-step RK4 simulation of a reaction wheel inverted pendulum.

    Parameters
    ----------
    params : SimulationParameters
        Physical and numerical parameters for the system.
    """

    def __init__(self, params: SimulationParameters) -> None:
        self._params = params.model_copy()
        self._time: float = 0.0
        self._last_torque: float = 0.0
        self._last_theta_ddot: float = 0.0
        self._last_phi_ddot: float = 0.0

        self._compute_effective_quantities()
        self._validate_physical_quantities()

        # State vector: [theta, theta_dot, phi, phi_dot]
        self._state: np.ndarray = np.zeros(4, dtype=np.float64)
        self.reset()

    # ------------------------------------------------------------------
    # Effective physical quantities
    # ------------------------------------------------------------------

    def _compute_effective_quantities(self) -> None:
        """Derive effective inertias and geometry from user parameters."""
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

        # Wheel moment of inertia (solid cylinder fallback)
        self._I_w: float = (
            p.wheel_inertia if p.wheel_inertia is not None
            else 0.5 * p.wheel_mass * p.wheel_radius ** 2
        )

        # Coupled inertia matrix components
        # M = [[I_p + m_w * L^2 + I_w,  I_w],
        #      [I_w,                    I_w]]
        self._M11: float = self._I_p + p.wheel_mass * p.pendulum_length ** 2 + self._I_w
        self._M12: float = self._I_w
        self._M22: float = self._I_w

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
            [p.initial_theta, p.initial_theta_dot, p.initial_phi, p.initial_phi_dot],
            dtype=np.float64,
        )
        self._time = 0.0
        self._last_torque = 0.0
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
            # Roll back on failure
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
        }

    def get_telemetry(self, mode: ControlMode) -> TelemetryMessage:
        """Return a telemetry-ready snapshot of the simulation."""
        ke, pe = self._compute_energy_components()
        return TelemetryMessage(
            time=self._time,
            theta=float(self._state[0]),
            theta_dot=float(self._state[1]),
            theta_ddot=self._last_theta_ddot,
            phi=float(self._state[2]),
            phi_dot=float(self._state[3]),
            phi_ddot=self._last_phi_ddot,
            torque=self._last_torque,
            energy=ke + pe,
            kinetic_energy=ke,
            potential_energy=pe,
            angular_momentum=self._compute_angular_momentum(),
            mode=mode,
        )

    def compute_energy(self) -> float:
        """Compute total mechanical energy (kinetic + potential).

        Kinetic energy uses the full coupled inertia matrix.
        Potential energy is referenced so that the upright position
        (theta = 0) has zero potential energy.
        """
        ke, pe = self._compute_energy_components()
        return ke + pe

    def _compute_energy_components(self) -> tuple[float, float]:
        """Compute kinetic and potential energy separately."""
        theta, theta_dot, _phi, phi_dot = self._state

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
        _theta, theta_dot, _phi, phi_dot = self._state
        return float(self._M11 * theta_dot + self._M12 * phi_dot)

    def compute_dynamics(self, state: np.ndarray, torque: float) -> np.ndarray:
        """Compute the state derivative for a given state and applied torque.

        Parameters
        ----------
        state : np.ndarray
            State vector [theta, theta_dot, phi, phi_dot].
        torque : float
            Motor torque applied to the wheel (saturated internally).

        Returns
        -------
        np.ndarray
            Derivative vector [theta_dot, theta_ddot, phi_dot, phi_ddot].
        """
        theta = state[0]
        theta_dot = state[1]
        phi_dot = state[3]

        # Saturate torque
        u = float(np.clip(torque, -self._params.max_motor_torque, self._params.max_motor_torque))

        # Right-hand side of M @ [theta_ddot, phi_ddot]^T = f
        # Pendulum equation: gravity - reaction torque - pivot damping
        f1 = (
            self._gravity_coeff * np.sin(theta)
            - u
            - self._params.damping * theta_dot
        )
        # Wheel equation: motor torque - relative wheel damping
        f2 = u - self._params.wheel_damping * phi_dot

        # Solve 2x2 system: M @ q_ddot = f
        det = self._M11 * self._M22 - self._M12 ** 2
        theta_ddot = (self._M22 * f1 - self._M12 * f2) / det
        phi_ddot = (self._M11 * f2 - self._M12 * f1) / det

        return np.array([theta_dot, theta_ddot, phi_dot, phi_ddot], dtype=np.float64)

    def step(self, torque: float) -> None:
        """Advance the simulation by one fixed time step using RK4.

        Parameters
        ----------
        torque : float
            Motor torque command (will be saturated to max_motor_torque).
        """
        dt = self._params.time_step
        self._last_torque = float(
            np.clip(torque, -self._params.max_motor_torque, self._params.max_motor_torque)
        )

        s = self._state
        k1 = self.compute_dynamics(s, torque)
        k2 = self.compute_dynamics(s + 0.5 * dt * k1, torque)
        k3 = self.compute_dynamics(s + 0.5 * dt * k2, torque)
        k4 = self.compute_dynamics(s + dt * k3, torque)

        self._state = s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        # Store accelerations from the final RK4 evaluation for telemetry
        self._last_theta_ddot = float(k4[1])
        self._last_phi_ddot = float(k4[3])

        # Normalize angles
        self._state[0] = _wrap_angle(self._state[0])
        self._state[2] = _wrap_angle(self._state[2])

        self._time += dt

    def apply_impulse(self, torque: float, duration_steps: int) -> None:
        """Apply a constant disturbance torque for a number of steps.

        Parameters
        ----------
        torque : float
            Disturbance torque [N·m] (will be saturated).
        duration_steps : int
            Number of physics steps to apply the disturbance.
        """
        for _ in range(max(1, duration_steps)):
            self.step(torque)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def time(self) -> float:
        """Current simulation time [s]."""
        return self._time

    @property
    def params(self) -> SimulationParameters:
        """Current simulation parameters (copy)."""
        return self._params.model_copy()

    @property
    def inertia_matrix(self) -> np.ndarray:
        """The 2×2 coupled inertia matrix."""
        return np.array(
            [[self._M11, self._M12],
             [self._M12, self._M22]],
            dtype=np.float64,
        )