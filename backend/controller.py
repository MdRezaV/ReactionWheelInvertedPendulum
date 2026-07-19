"""Control algorithms for the reaction wheel inverted pendulum.

Implements PID, LQR, energy-based swing-up, manual, and no-control
strategies. All controllers share a common interface and clamp output
torque to the actuator limit.

State conventions (from simulation.py):
  theta     – pendulum angle from upright (0 = upright), wrapped to (-pi, pi]
  theta_dot – pendulum angular velocity [rad/s]
  phi_dot   – wheel angular velocity relative to the pendulum arm [rad/s]
  energy    – total mechanical energy referenced to upright (0 at upright rest)
"""

from __future__ import annotations

import abc
import math
from typing import Optional

import numpy as np
from scipy.linalg import solve_continuous_are

from models import ControlMode, ControlParameters, SimulationParameters

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract controller interface
# ---------------------------------------------------------------------------


class Controller(abc.ABC):
    """Base class for all pendulum controllers."""

    @abc.abstractmethod
    def reset(self) -> None:
        """Reset internal controller state (integrators, flags, etc.)."""

    @abc.abstractmethod
    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        """Compute the motor torque command.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        energy : float
            Total mechanical energy (upright-referenced) [J].
        time : float
            Current simulation time [s].
        sim_params : SimulationParameters
            Physical simulation parameters.
        ctrl_params : ControlParameters
            Tunable control gains and thresholds.

        Returns
        -------
        float
            Motor torque command, clamped to [-max_motor_torque, max_motor_torque].
        """

    @staticmethod
    def _clamp(torque: float, max_torque: float) -> float:
        """Clamp torque to actuator limits."""
        return float(np.clip(torque, -max_torque, max_torque))


# ---------------------------------------------------------------------------
# NoController
# ---------------------------------------------------------------------------


class NoController(Controller):
    """Returns zero torque (free-fall / uncontrolled)."""

    def reset(self) -> None:
        pass

    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# ManualController
# ---------------------------------------------------------------------------


class ManualController(Controller):
    """Returns a user-specified torque, saturated to the actuator limit."""

    def __init__(self) -> None:
        self._torque: float = 0.0

    def set_torque(self, torque: float) -> None:
        """Set the manual torque command [N·m]."""
        self._torque = torque

    def reset(self) -> None:
        self._torque = 0.0

    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        return self._clamp(self._torque, sim_params.max_motor_torque)


# ---------------------------------------------------------------------------
# PIDController
# ---------------------------------------------------------------------------


class PIDController(Controller):
    """PID balance controller for the upright equilibrium.

    Sign convention: positive torque for positive theta (pendulum tilted
    in the positive direction requires positive corrective torque).

    u = Kp * theta + Ki * integral(theta) + Kd * theta_dot

    The integral term uses clamping anti-windup: integration stops when
    the output is saturated and the integrator would grow further.
    """

    def __init__(self) -> None:
        self._integral: float = 0.0

    def reset(self) -> None:
        """Reset the integral accumulator."""
        self._integral = 0.0

    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        kp = ctrl_params.pid_kp
        ki = ctrl_params.pid_ki
        kd = ctrl_params.pid_kd
        dt = sim_params.time_step
        max_torque = sim_params.max_motor_torque

        # Proportional + derivative
        p_term = kp * theta
        d_term = kd * theta_dot

        # Tentative output without integral
        output_no_i = p_term + d_term

        # Anti-windup: only integrate if not saturated in the same direction
        i_term = ki * self._integral
        output = output_no_i + i_term

        if abs(output) < max_torque:
            # Not saturated – accumulate normally
            self._integral += theta * dt
        else:
            # Saturated – only accumulate if it would reduce saturation
            if (output > 0 and theta < 0) or (output < 0 and theta > 0):
                self._integral += theta * dt

        # Recompute with updated integral
        i_term = ki * self._integral
        output = output_no_i + i_term

        return self._clamp(output, max_torque)


# ---------------------------------------------------------------------------
# LQRController
# ---------------------------------------------------------------------------


class LQRController(Controller):
    """LQR balance controller using the continuous-time linearization.

    Linearizes the coupled pendulum-wheel dynamics around the upright
    equilibrium (theta = 0) for the reduced state [theta, theta_dot, phi_dot].

    The linear model:
        x_dot = A x + B u

    is derived from the full nonlinear equations:
        M @ [theta_ddot, phi_ddot]^T = f(theta, theta_dot, phi_dot, u)

    where M is the 2x2 coupled inertia matrix and f contains gravity,
    damping, and control input terms.

    If the Riccati equation fails or produces non-finite gains, the
    controller falls back to PID behavior and sets a warning flag.
    """

    def __init__(self) -> None:
        self._gain: Optional[np.ndarray] = None  # shape (1, 3)
        self._warning: Optional[str] = None
        self._pid_fallback: PIDController = PIDController()
        self._last_sim_params: Optional[SimulationParameters] = None
        self._last_ctrl_params: Optional[ControlParameters] = None

    @property
    def warning(self) -> Optional[str]:
        """Warning message if LQR gain computation failed."""
        return self._warning

    @property
    def gain(self) -> Optional[np.ndarray]:
        """Current LQR gain vector K (shape (3,)) or None if unavailable."""
        if self._gain is not None:
            return self._gain.flatten()
        return None

    def reset(self) -> None:
        """Reset fallback PID integrator and clear warning."""
        self._pid_fallback.reset()
        self._warning = None

    def _compute_gain(
        self,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> None:
        """Compute the LQR gain from the linearized model.

        Sets self._gain on success or self._warning on failure.
        """
        try:
            # Effective physical quantities (mirror simulation.py logic)
            l_com = (
                sim_params.pendulum_com_length
                if sim_params.pendulum_com_length is not None
                else sim_params.pendulum_length / 2.0
            )
            I_p = (
                sim_params.pendulum_inertia
                if sim_params.pendulum_inertia is not None
                else (1.0 / 3.0) * sim_params.pendulum_mass * sim_params.pendulum_length ** 2
            )
            I_w = (
                sim_params.wheel_inertia
                if sim_params.wheel_inertia is not None
                else 0.5 * sim_params.wheel_mass * sim_params.wheel_radius ** 2
            )

            M11 = I_p + sim_params.wheel_mass * sim_params.pendulum_length ** 2 + I_w
            M12 = I_w
            M22 = I_w
            det = M11 * M22 - M12 ** 2

            if det <= 0.0:
                raise ValueError(f"Non-positive inertia determinant: {det:.6e}")

            gravity_coeff = (
                (sim_params.pendulum_mass * l_com + sim_params.wheel_mass * sim_params.pendulum_length)
                * sim_params.gravity
            )
            damping = sim_params.damping
            wheel_damping = sim_params.wheel_damping

            # Linearized A matrix for state [theta, theta_dot, phi_dot]
            # Row 0: theta_dot = theta_dot
            # Row 1: theta_ddot = (M22*f1 - M12*f2) / det
            # Row 2: phi_ddot   = (M11*f2 - M12*f1) / det
            #
            # f1 = gravity_coeff*theta - u - damping*theta_dot
            # f2 = u - wheel_damping*phi_dot
            #
            # Linearized (sin(theta) ≈ theta):
            A = np.array([
                [0.0, 1.0, 0.0],
                [
                    M22 * gravity_coeff / det,
                    -M22 * damping / det,
                    M12 * wheel_damping / det,
                ],
                [
                    -M12 * gravity_coeff / det,
                    M12 * damping / det,
                    -M11 * wheel_damping / det,
                ],
            ], dtype=np.float64)

            # Linearized B matrix
            # Coefficient of u in theta_ddot: (-M22 - M12) / det
            # Coefficient of u in phi_ddot:   ( M11 + M12) / det
            B = np.array([
                [0.0],
                [-(M22 + M12) / det],
                [(M11 + M12) / det],
            ], dtype=np.float64)

            # Weight matrices
            Q = np.diag([
                ctrl_params.lqr_q_theta,
                ctrl_params.lqr_q_theta_dot,
                ctrl_params.lqr_q_phi_dot,
            ]).astype(np.float64)
            R = np.array([[ctrl_params.lqr_r]], dtype=np.float64)

            # Solve continuous algebraic Riccati equation
            P = solve_continuous_are(A, B, Q, R)

            # Optimal gain: K = R^{-1} B^T P
            K = np.linalg.solve(R, B.T @ P)

            if not np.all(np.isfinite(K)):
                raise ValueError(f"Non-finite LQR gains: {K}")

            self._gain = K
            self._warning = None

        except Exception as exc:
            self._gain = None
            self._warning = f"LQR gain computation failed: {exc}"

    def _ensure_gain(
        self,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> None:
        """Recompute gain if physical or control parameters changed."""
        if (
            self._gain is None
            or self._last_sim_params != sim_params
            or self._last_ctrl_params != ctrl_params
        ):
            self._compute_gain(sim_params, ctrl_params)
            self._last_sim_params = sim_params.model_copy()
            self._last_ctrl_params = ctrl_params.model_copy()

    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        self._ensure_gain(sim_params, ctrl_params)

        if self._gain is None:
            # Fallback to PID
            return self._pid_fallback.compute_torque(
                theta, theta_dot, phi_dot, energy, time, sim_params, ctrl_params
            )

        # State feedback: u = -K @ x
        x = np.array([theta, theta_dot, phi_dot], dtype=np.float64)
        u = float(-self._gain @ x)

        return self._clamp(u, sim_params.max_motor_torque)


# ---------------------------------------------------------------------------
# EnergySwingUpController
# ---------------------------------------------------------------------------


class EnergySwingUpController(Controller):
    """Energy-based swing-up with LQR/PID balance near upright.

    Away from upright, commands torque to pump mechanical energy toward
    the upright energy level (E_target = 0). The control law is:

        u = gain * (E_target - E) * phi_dot

    which ensures motor power (u * phi_dot) is positive when energy is
    below target, driving the system toward upright.

    When |phi_dot| is too small to transfer meaningful power, a bounded
    phase-based excitation torque is added to spin the wheel.

    Near upright (within configurable angle and velocity thresholds),
    the controller switches to LQR (preferred) or PID for fine balance.
    """

    # Minimum |phi_dot| below which excitation is applied [rad/s]
    _PHI_DOT_EXCITATION_THRESHOLD: float = 0.5
    # Maximum excitation torque as fraction of max_motor_torque
    _EXCITATION_FRACTION: float = 0.3

    def __init__(self) -> None:
        self._lqr: LQRController = LQRController()
        self._pid: PIDController = PIDController()

    def reset(self) -> None:
        """Reset internal LQR and PID controllers."""
        self._lqr.reset()
        self._pid.reset()

    @property
    def lqr_warning(self) -> Optional[str]:
        """Expose LQR warning if swing-up falls back to PID near upright."""
        return self._lqr.warning

    def _is_near_upright(
        self,
        theta: float,
        theta_dot: float,
        ctrl_params: ControlParameters,
    ) -> bool:
        """Check if the pendulum is close enough to upright for balance control."""
        return (
            abs(theta) < ctrl_params.upright_angle_threshold
            and abs(theta_dot) < ctrl_params.upright_velocity_threshold
        )

    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        max_torque = sim_params.max_motor_torque

        # Near upright: switch to balance controller
        if self._is_near_upright(theta, theta_dot, ctrl_params):
            if self._lqr.gain is not None or self._lqr.warning is None:
                # Attempt LQR; it will fall back to PID internally if needed
                return self._lqr.compute_torque(
                    theta, theta_dot, phi_dot, energy, time, sim_params, ctrl_params
                )
            return self._pid.compute_torque(
                theta, theta_dot, phi_dot, energy, time, sim_params, ctrl_params
            )

        # Energy swing-up region
        # Target energy at upright rest = 0 (by convention in simulation.py)
        e_target = 0.0
        e_error = e_target - energy  # positive when below target

        gain = ctrl_params.energy_swing_up_gain

        # Primary energy-pumping law: u = gain * e_error * phi_dot
        u_energy = gain * e_error * phi_dot

        # Phase-based excitation when wheel speed is too low
        if abs(phi_dot) < self._PHI_DOT_EXCITATION_THRESHOLD:
            # Use pendulum angle to determine excitation direction.
            # sin(theta) > 0 means pendulum is on the positive side;
            # excite the wheel to build angular momentum in a direction
            # that will pump energy on the next swing.
            excitation_amplitude = self._EXCITATION_FRACTION * max_torque
            # Direction: push wheel to create reaction that aids swing-up
            excitation_dir = math.copysign(1.0, math.sin(theta)) if abs(math.sin(theta)) > 1e-6 else 1.0
            u_excitation = excitation_amplitude * excitation_dir
            u_energy += u_excitation

        return self._clamp(u_energy, max_torque)


# ---------------------------------------------------------------------------
# SlidingModeController
# ---------------------------------------------------------------------------


class SlidingModeController(Controller):
    """Sliding mode controller for robust pendulum stabilization.

    Defines a sliding surface:
        s = c1 * theta + c2 * theta_dot + c3 * phi_dot

    The control law uses a boundary-layer approximation to reduce chattering:
        u = -K * sat(s / boundary) - eta * s

    where sat() is the saturation function (linear within the boundary layer,
    sign outside). This provides robustness to parameter uncertainty while
    avoiding the high-frequency chattering of pure sign-based SMC.
    """

    def reset(self) -> None:
        pass

    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        c1 = ctrl_params.smc_c1
        c2 = ctrl_params.smc_c2
        c3 = ctrl_params.smc_c3
        k = ctrl_params.smc_k
        eta = ctrl_params.smc_eta
        boundary = ctrl_params.smc_boundary
        max_torque = sim_params.max_motor_torque

        # Sliding surface
        s = c1 * theta + c2 * theta_dot + c3 * phi_dot

        # Boundary-layer saturation: sat(s/boundary)
        s_normalized = s / boundary
        if abs(s_normalized) <= 1.0:
            sat_val = s_normalized
        else:
            sat_val = 1.0 if s_normalized > 0 else -1.0

        # Control law
        u = -k * sat_val - eta * s

        return self._clamp(u, max_torque)


# ---------------------------------------------------------------------------
# ControllerManager
# ---------------------------------------------------------------------------


class ControllerManager:
    """Manages the active control mode and delegates torque computation.

    Stores controller instances, current parameters, and handles live
    gain updates and LQR recomputation when physical parameters change.
    """

    def __init__(
        self,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> None:
        self._sim_params: SimulationParameters = sim_params.model_copy()
        self._ctrl_params: ControlParameters = ctrl_params.model_copy()
        self._mode: ControlMode = ControlMode.none
        self._manual_torque: float = 0.0

        # Instantiate all controllers
        self._no_controller: NoController = NoController()
        self._manual_controller: ManualController = ManualController()
        self._pid_controller: PIDController = PIDController()
        self._lqr_controller: LQRController = LQRController()
        self._energy_controller: EnergySwingUpController = EnergySwingUpController()
        self._smc_controller: SlidingModeController = SlidingModeController()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def mode(self) -> ControlMode:
        """Active control mode."""
        return self._mode

    @property
    def control_params(self) -> ControlParameters:
        """Current control parameters (copy)."""
        return self._ctrl_params.model_copy()

    @property
    def lqr_warning(self) -> Optional[str]:
        """Warning from LQR controller if gain computation failed."""
        return self._lqr_controller.warning

    # ------------------------------------------------------------------
    # Mode and parameter management
    # ------------------------------------------------------------------

    def set_mode(self, mode: ControlMode) -> None:
        """Switch control mode, resetting the newly active controller."""
        if mode != self._mode:
            self._mode = mode
            self._get_active_controller().reset()

    def set_manual_torque(self, torque: float) -> None:
        """Update the manual torque setpoint."""
        self._manual_torque = torque
        self._manual_controller.set_torque(torque)

    def update_control_params(self, ctrl_params: ControlParameters) -> None:
        """Live-update control gains without resetting integrators.

        LQR gains are recomputed lazily on the next torque computation
        when parameters differ from the cached values.
        """
        self._ctrl_params = ctrl_params.model_copy()

    def update_sim_params(self, sim_params: SimulationParameters) -> None:
        """Update physical parameters, triggering LQR recomputation.

        The LQR controller detects parameter changes and recomputes
        the gain matrix on the next compute_torque call.
        """
        self._sim_params = sim_params.model_copy()

    def reset(self) -> None:
        """Reset all controllers and clear warnings."""
        self._no_controller.reset()
        self._manual_controller.reset()
        self._pid_controller.reset()
        self._lqr_controller.reset()
        self._energy_controller.reset()
        self._smc_controller.reset()
        self._manual_torque = 0.0

    def reset_active(self) -> None:
        """Reset only the currently active controller."""
        self._get_active_controller().reset()

    # ------------------------------------------------------------------
    # Torque computation
    # ------------------------------------------------------------------

    def compute_torque(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        energy: float,
        time: float,
    ) -> float:
        """Delegate torque computation to the active controller.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        energy : float
            Total mechanical energy (upright-referenced) [J].
        time : float
            Current simulation time [s].

        Returns
        -------
        float
            Motor torque command clamped to actuator limits.
        """
        controller = self._get_active_controller()
        return controller.compute_torque(
            theta, theta_dot, phi_dot, energy, time,
            self._sim_params, self._ctrl_params,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_active_controller(self) -> Controller:
        """Return the controller instance for the current mode."""
        match self._mode:
            case ControlMode.none:
                return self._no_controller
            case ControlMode.manual:
                return self._manual_controller
            case ControlMode.pid:
                return self._pid_controller
            case ControlMode.lqr:
                return self._lqr_controller
            case ControlMode.energy_swing_up:
                return self._energy_controller
            case ControlMode.sliding_mode:
                return self._smc_controller
            case _:
                return self._no_controller