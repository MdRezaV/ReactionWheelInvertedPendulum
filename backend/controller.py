"""Control algorithms for the reaction wheel inverted pendulum.

Implements PID, LQR, energy-based swing-up, manual, and no-control
strategies. All controllers share a common interface and clamp output
voltage to the actuator limit.

State conventions (from simulation.py):
  theta     – pendulum angle from upright (0 = upright), wrapped to (-pi, pi]
  theta_dot – pendulum angular velocity [rad/s]
  phi_dot   – wheel angular velocity relative to the pendulum arm [rad/s]
  current   – armature current [A]
  energy    – total mechanical energy referenced to upright (0 at upright rest)
"""

from __future__ import annotations

import abc
import math
from typing import Optional

import numpy as np
from scipy.linalg import solve_continuous_are

from models import ControlMode, ControlParameters, SimulationParameters, SwingUpMethod

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
    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        """Compute the motor voltage command.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        current : float
            Armature current [A].
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
            Voltage command [V], clamped to [-max_voltage, max_voltage].
        """

    @staticmethod
    def _clamp_voltage(voltage: float, max_voltage: float) -> float:
        """Clamp voltage to actuator limits."""
        return max(-max_voltage, min(max_voltage, voltage))


# ---------------------------------------------------------------------------
# NoController
# ---------------------------------------------------------------------------


class NoController(Controller):
    """Returns zero voltage (free-fall / uncontrolled)."""

    def reset(self) -> None:
        pass

    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
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
    """Returns a user-specified voltage, saturated to the actuator limit."""

    def __init__(self) -> None:
        self._voltage: Optional[float] = None

    def set_voltage(self, voltage: float) -> None:
        """Set the manual voltage command [V]."""
        self._voltage = voltage

    def reset(self) -> None:
        self._voltage = None

    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        voltage = self._voltage if self._voltage is not None else ctrl_params.manual_voltage
        return self._clamp_voltage(voltage, sim_params.max_voltage)


# ---------------------------------------------------------------------------
# PIDController
# ---------------------------------------------------------------------------


class PIDController(Controller):
    """PID balance controller for the upright equilibrium.

    Sign convention: positive voltage for positive theta (pendulum tilted
    in the positive direction requires positive corrective voltage).

    u = Kp * theta + Ki * integral(theta) + Kd * theta_dot

    The integral term uses clamping anti-windup: integration stops when
    the output is saturated and the integrator would grow further.
    """

    def __init__(self) -> None:
        self._integral: float = 0.0

    def reset(self) -> None:
        """Reset the integral accumulator."""
        self._integral = 0.0

    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        kp = ctrl_params.pid_kp
        ki = ctrl_params.pid_ki
        kd = ctrl_params.pid_kd
        dt = sim_params.time_step
        max_voltage = sim_params.max_voltage

        # Proportional + derivative
        p_term = kp * theta
        d_term = kd * theta_dot

        # Tentative output without integral
        output_no_i = p_term + d_term

        # Anti-windup: only integrate if not saturated in the same direction
        i_term = ki * self._integral
        output = output_no_i + i_term

        if abs(output) < max_voltage:
            # Not saturated – accumulate normally
            self._integral += theta * dt
        else:
            # Saturated – only accumulate if it would reduce saturation
            if (output > 0 and theta < 0) or (output < 0 and theta > 0):
                self._integral += theta * dt

        # Recompute with updated integral
        i_term = ki * self._integral
        output = output_no_i + i_term

        return self._clamp_voltage(output, max_voltage)


# ---------------------------------------------------------------------------
# LQRController
# ---------------------------------------------------------------------------


class LQRController(Controller):
    """LQR balance controller using the continuous-time linearization.

    Linearizes the coupled electro-mechanical pendulum-wheel dynamics
    around the upright equilibrium (theta = 0) for the state
    [theta, theta_dot, phi_dot, i_a] with voltage input V.

    The linear model:
        x_dot = A x + B V

    is derived from the full nonlinear equations including the armature
    circuit: L di/dt = V - R i - Ke*N*phi_dot.

    If the Riccati equation fails or produces non-finite gains, the
    controller falls back to PID behavior and sets a warning flag.
    """

    def __init__(self) -> None:
        self._gain: Optional[np.ndarray] = None  # shape (1, 4)
        self._warning: Optional[str] = None
        self._pid_fallback: PIDController = PIDController()
        self._last_sim_params: Optional[SimulationParameters] = None
        self._last_ctrl_params: Optional[ControlParameters] = None
        self._state_buf: np.ndarray = np.zeros(4, dtype=np.float64)

    @property
    def warning(self) -> Optional[str]:
        """Warning message if LQR gain computation failed."""
        return self._warning

    @property
    def gain(self) -> Optional[np.ndarray]:
        """Current LQR gain vector K (shape (4,)) or None if unavailable."""
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
        """Compute the LQR gain from the linearized electro-mechanical model.

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
                else 0.5 * sim_params.wheel_mass * (
                    sim_params.wheel_outer_radius ** 2 + sim_params.wheel_inner_radius ** 2
                )
            )

            # Extract electro-mechanical parameters (needed for reflected inertia)
            N = sim_params.gear_ratio

            # Effective wheel-side inertia including reflected rotor (matches simulation.py)
            I_w_eff = I_w + sim_params.motor_rotor_inertia * N ** 2

            M11 = I_p + sim_params.wheel_mass * sim_params.pendulum_length ** 2 + I_w_eff
            M12 = I_w_eff
            M22 = I_w_eff
            det = M11 * M22 - M12 ** 2

            if det <= 0.0:
                raise ValueError(f"Non-positive inertia determinant: {det:.6e}")

            gravity_coeff = (
                (sim_params.pendulum_mass * l_com + sim_params.wheel_mass * sim_params.pendulum_length)
                * sim_params.gravity
            )
            Kt = sim_params.motor_constant
            Ke = sim_params.motor_constant  # Kt = Ke by convention
            R = sim_params.motor_resistance
            L = sim_params.motor_inductance
            b = sim_params.damping
            b_w_eff = sim_params.wheel_damping + N ** 2 * sim_params.motor_viscous_friction


            # Linearized A matrix for state [theta, theta_dot, phi_dot, i_a]
            # Mechanical rows derived from M @ [theta_ddot, phi_ddot] = f
            # with motor torque tau_m = Kt * i_a, wheel torque = N * Kt * i_a.
            # Electrical row: di/dt = V/L - R*i/L - Ke*N*phi_dot/L
            A = np.array([
                [0.0, 1.0, 0.0, 0.0],
                [
                    M22 * gravity_coeff / det,
                    -M22 * b / det,
                    M12 * b_w_eff / det,
                    -(M22 + M12) * N * Kt / det,
                ],
                [
                    -M12 * gravity_coeff / det,
                    M12 * b / det,
                    -M11 * b_w_eff / det,
                    (M11 + M12) * N * Kt / det,
                ],
                [0.0, 0.0, -Ke * N / L, -R / L],
            ], dtype=np.float64)

            # Linearized B matrix (voltage input enters only the electrical equation)
            B = np.array([
                [0.0],
                [0.0],
                [0.0],
                [1.0 / L],
            ], dtype=np.float64)

            # Weight matrices
            Q = np.diag([
                ctrl_params.lqr_q_theta,
                ctrl_params.lqr_q_theta_dot,
                ctrl_params.lqr_q_phi_dot,
                ctrl_params.lqr_q_current,
            ]).astype(np.float64)
            R_lqr = np.array([[ctrl_params.lqr_r]], dtype=np.float64)

            # Solve continuous algebraic Riccati equation
            P = solve_continuous_are(A, B, Q, R_lqr)

            # Optimal gain: K = R_lqr^{-1} B^T P
            K = np.linalg.solve(R_lqr, B.T @ P)

            if not np.all(np.isfinite(K)):
                raise ValueError(f"Non-finite LQR gains: {K}")

            self._gain = K.flatten()
            self._warning = None

        except Exception as exc:
            self._gain = None
            self._warning = f"LQR gain computation failed: {exc}"

    def _ensure_gain(
        self,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> None:
        """Recompute gain if physical or control parameters changed.

        If the previous computation failed and parameters have not changed,
        the expensive Riccati solve is skipped to avoid retrying at physics
        rate with identical inputs.
        """
        params_changed = (
            self._last_sim_params != sim_params
            or self._last_ctrl_params != ctrl_params
        )
        if self._gain is None and self._warning is not None and not params_changed:
            return
        if self._gain is None or params_changed:
            self._compute_gain(sim_params, ctrl_params)
            self._last_sim_params = sim_params.model_copy()
            self._last_ctrl_params = ctrl_params.model_copy()

    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        self._ensure_gain(sim_params, ctrl_params)

        if self._gain is None:
            # Fallback to PID
            return self._pid_fallback.compute_voltage(
                theta, theta_dot, phi_dot, current, energy, time, sim_params, ctrl_params
            )

        # State feedback: V = -K @ [theta, theta_dot, phi_dot, i_a]
        self._state_buf[0] = theta
        self._state_buf[1] = theta_dot
        self._state_buf[2] = phi_dot
        self._state_buf[3] = current
        v = float(-self._gain @ self._state_buf)

        return self._clamp_voltage(v, sim_params.max_voltage)


# ---------------------------------------------------------------------------
# EnergySwingUpController
# ---------------------------------------------------------------------------


class SwingUpBalanceController(Controller):
    """Generalized swing-up controller with configurable balance handoff.

    Supports two swing-up methods selected at runtime via
    ``ctrl_params.swing_up_method``:

    * **energy** – Energy-based pumping: V = gain * (E_target - E) * phi_dot,
      with phase-based excitation when wheel speed is too low.
    * **pfl** – Partial Feedback Linearization: shapes theta_ddot via
      feedback linearization of the coupled dynamics, then maps the
      required wheel acceleration to a voltage command.

    The ``balance_mode`` constructor argument determines the handoff
    behaviour near upright:

    * ``"lqr"`` – switch to LQRController within angle/velocity thresholds.
    * ``"pid"`` – switch to PIDController within angle/velocity thresholds.
    * ``None``  – pure swing-up; never switch to a balance controller.
    """

    # Minimum |phi_dot| below which excitation is applied [rad/s]
    _PHI_DOT_EXCITATION_THRESHOLD: float = 0.5
    # Maximum excitation voltage as fraction of max_voltage
    _EXCITATION_FRACTION: float = 0.3

    def __init__(self, balance_mode: Optional[str] = None) -> None:
        """Initialize the swing-up/balance controller.

        Parameters
        ----------
        balance_mode : str or None
            ``"lqr"``, ``"pid"``, or ``None`` for pure swing-up.
        """
        self._balance_mode: Optional[str] = balance_mode
        self._lqr: Optional[LQRController] = (
            LQRController() if balance_mode == "lqr" else None
        )
        self._pid: Optional[PIDController] = (
            PIDController() if balance_mode == "pid" else None
        )
        self._prev_theta_dot: float = 0.0
        self._impulse_steps_remaining: int = 0
        self._impulse_voltage: float = 0.0

        # Cached derived physical quantities (recomputed only when sim_params changes)
        self._cached_sim_params: Optional[SimulationParameters] = None
        self._cached_l_com: Optional[float] = None
        self._cached_I_p: Optional[float] = None
        self._cached_I_w: Optional[float] = None
        self._cached_N: Optional[float] = None
        self._cached_I_w_eff: Optional[float] = None
        self._cached_M11: Optional[float] = None
        self._cached_M12: Optional[float] = None
        self._cached_M22: Optional[float] = None
        self._cached_gravity_coeff: Optional[float] = None
        self._cached_Kt: Optional[float] = None
        self._cached_Ke: Optional[float] = None
        self._cached_R: Optional[float] = None

    def reset(self) -> None:
        """Reset internal balance controllers and zero-velocity impulse state."""
        if self._lqr is not None:
            self._lqr.reset()
        if self._pid is not None:
            self._pid.reset()
        self._prev_theta_dot = 0.0
        self._impulse_steps_remaining = 0
        self._impulse_voltage = 0.0
        self._cached_sim_params = None
        self._cached_l_com = None
        self._cached_I_p = None
        self._cached_I_w = None
        self._cached_N = None
        self._cached_I_w_eff = None
        self._cached_M11 = None
        self._cached_M12 = None
        self._cached_M22 = None
        self._cached_gravity_coeff = None
        self._cached_Kt = None
        self._cached_Ke = None
        self._cached_R = None

    def _ensure_derived(self, sim_params: SimulationParameters) -> None:
        """Recompute and cache derived physical quantities if sim_params changed.

        Uses an identity check as a fast-path so that repeated calls within
        the same physics step (where the same object is passed) skip all work.

        Parameters
        ----------
        sim_params : SimulationParameters
            Current physical simulation parameters.
        """
        if self._cached_sim_params is sim_params:
            return

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
            else 0.5 * sim_params.wheel_mass * (
                sim_params.wheel_outer_radius ** 2 + sim_params.wheel_inner_radius ** 2
            )
        )

        N = sim_params.gear_ratio
        I_w_eff = I_w + sim_params.motor_rotor_inertia * N ** 2

        M11 = I_p + sim_params.wheel_mass * sim_params.pendulum_length ** 2 + I_w_eff
        M12 = I_w_eff
        M22 = I_w_eff

        gravity_coeff = (
            (sim_params.pendulum_mass * l_com + sim_params.wheel_mass * sim_params.pendulum_length)
            * sim_params.gravity
        )

        self._cached_sim_params = sim_params
        self._cached_l_com = l_com
        self._cached_I_p = I_p
        self._cached_I_w = I_w
        self._cached_N = N
        self._cached_I_w_eff = I_w_eff
        self._cached_M11 = M11
        self._cached_M12 = M12
        self._cached_M22 = M22
        self._cached_gravity_coeff = gravity_coeff
        self._cached_Kt = sim_params.motor_constant
        self._cached_Ke = sim_params.motor_constant
        self._cached_R = sim_params.motor_resistance

    @property
    def lqr_warning(self) -> Optional[str]:
        """Expose LQR warning if swing-up falls back to PID near upright."""
        if self._lqr is not None:
            return self._lqr.warning
        return None

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

    # ------------------------------------------------------------------
    # PFL swing-up helper
    # ------------------------------------------------------------------

    def _compute_pfl_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        """Compute voltage via Partial Feedback Linearization with energy-aware saturation.

        Desired angular acceleration:
            theta_ddot_des = -pfl_kp * sin(theta) - pfl_kd * theta_dot

        From the coupled dynamics M11*theta_ddot + M12*phi_ddot = gravity_term,
        solve for the required phi_ddot, then convert to voltage using a
        quasi-static motor model: V ≈ R * (tau_m / Kt) + Ke * N * phi_dot.

        When pendulum energy exceeds the upright target, the controller
        switches to wheel damping to prevent continuous rotation.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        sim_params : SimulationParameters
            Physical simulation parameters.
        ctrl_params : ControlParameters
            Control gains including pfl_kp, pfl_kd.

        Returns
        -------
        float
            Voltage command [V], clamped to [-max_voltage, max_voltage].
        """
        self._ensure_derived(sim_params)
        max_voltage = sim_params.max_voltage

        N = self._cached_N
        M11 = self._cached_M11
        M12 = self._cached_M12
        M22 = self._cached_M22
        gravity_coeff = self._cached_gravity_coeff
        Kt = self._cached_Kt
        Ke = self._cached_Ke
        R = self._cached_R

        # Energy-aware saturation: if pendulum energy exceeds upright target,
        # actively brake the pendulum by commanding wheel torque proportional
        # to theta_dot.  Through the M12 coupling this produces a reaction
        # torque that decelerates the pendulum (unlike wheel braking which
        # accelerates it).
        e_pendulum = self._compute_pendulum_energy(theta, theta_dot, sim_params)
        if e_pendulum > 0.0:
            excess_scale = min(
                1.0 + e_pendulum / max(abs(gravity_coeff), 1e-6), 3.0
            )
            brake_gain = ctrl_params.pfl_kd * excess_scale
            tau_wheel_des = brake_gain * theta_dot
            i_a_des = tau_wheel_des / (N * Kt)
            voltage = R * i_a_des + Ke * N * phi_dot
            return self._clamp_voltage(voltage, max_voltage)

        # Near the downward equilibrium (|theta| ≈ π), sin(theta) ≈ 0 creates
        # a control singularity where the PFL law produces zero voltage.
        # Inject a small excitation to break the deadlock.
        sin_theta = math.sin(theta)
        if abs(sin_theta) < 0.05 and abs(theta) > math.pi * 0.5 and abs(theta_dot) < 0.5:
            excitation_dir = math.copysign(1.0, theta) if abs(theta) > 1e-6 else 1.0
            v_exc = excitation_dir * self._EXCITATION_FRACTION * max_voltage
            return self._clamp_voltage(v_exc, max_voltage)

        # Desired pendulum angular acceleration
        theta_ddot_des = (
            -ctrl_params.pfl_kp * sin_theta
            - ctrl_params.pfl_kd * theta_dot
        )

        # Required wheel acceleration from coupled dynamics:
        # M11*theta_ddot + M12*phi_ddot = gravity_coeff * sin(theta)
        # => phi_ddot = (gravity_coeff*sin(theta) - M11*theta_ddot_des) / M12
        if abs(M12) < 1e-12:
            return 0.0
        phi_ddot_req = (gravity_coeff * math.sin(theta) - M11 * theta_ddot_des) / M12

        # Required motor torque from the wheel equation:
        # M12*theta_ddot + M22*phi_ddot = N * Kt * i_a
        # => tau_m = Kt * i_a = (M12*theta_ddot_des + M22*phi_ddot_req) / N
        tau_m = (M12 * theta_ddot_des + M22 * phi_ddot_req) / N

        # Quasi-static voltage: V = R * i_a + Ke * N * phi_dot
        # where i_a = tau_m / Kt
        voltage = R * (tau_m / Kt) + Ke * N * phi_dot

        return self._clamp_voltage(voltage, max_voltage)

    # ------------------------------------------------------------------
    # Energy-based swing-up helper
    # ------------------------------------------------------------------

    def _compute_pendulum_energy(
        self,
        theta: float,
        theta_dot: float,
        sim_params: SimulationParameters,
    ) -> float:
        """Compute pendulum-only mechanical energy referenced to upright rest.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        sim_params : SimulationParameters
            Physical simulation parameters.

        Returns
        -------
        float
            Pendulum energy [J]; 0 at upright rest, negative below upright.
        """
        self._ensure_derived(sim_params)
        I_p = self._cached_I_p
        l_com = self._cached_l_com
        ke = 0.5 * I_p * theta_dot ** 2
        pe = (
            (sim_params.pendulum_mass * l_com + sim_params.wheel_mass * sim_params.pendulum_length)
            * sim_params.gravity
            * (math.cos(theta) - 1.0)
        )
        return ke + pe

    def _compute_energy_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        """Compute voltage via energy-based swing-up using pendulum-only energy.

        Uses the standard Åström–Furuta pumping law:
            V = -k * (E_target - E_pendulum) * phi_dot

        This prevents energy from being trapped in the wheel by tracking
        only the pendulum's kinetic + potential energy.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        sim_params : SimulationParameters
            Physical simulation parameters.
        ctrl_params : ControlParameters
            Control gains.

        Returns
        -------
        float
            Voltage command [V], clamped to [-max_voltage, max_voltage].
        """
        self._ensure_derived(sim_params)
        max_voltage = sim_params.max_voltage
        max_wheel_speed = ctrl_params.swing_up_max_wheel_speed

        # Pendulum-only energy referenced to upright rest (0 at upright)
        e_pendulum = self._compute_pendulum_energy(theta, theta_dot, sim_params)
        e_target = 0.0
        e_error = e_target - e_pendulum  # positive when below target

        gain = ctrl_params.energy_swing_up_gain

        # If pendulum energy exceeds target, brake the pendulum by commanding
        # wheel torque proportional to theta_dot (correct coupling direction).
        if e_error < 0.0:
            self._ensure_derived(sim_params)
            N = self._cached_N
            Kt = self._cached_Kt
            Ke = self._cached_Ke
            R = self._cached_R
            excess_scale = min(1.0 + abs(e_error) / max(abs(self._cached_gravity_coeff), 1e-6), 3.0)
            brake_gain = gain * 0.5 * excess_scale
            tau_wheel_des = brake_gain * theta_dot
            i_a_des = tau_wheel_des / (N * Kt)
            voltage = R * i_a_des + Ke * N * phi_dot
            return self._clamp_voltage(voltage, max_voltage)

        # Energy-pumping law: V = -gain * e_error * phi_dot
        # (negative sign ensures energy flows into the pendulum)
        v_energy = -gain * e_error * phi_dot

        # Phase-based excitation when wheel speed is too low
        if abs(phi_dot) < self._PHI_DOT_EXCITATION_THRESHOLD:
            excitation_amplitude = self._EXCITATION_FRACTION * max_voltage
            excitation_dir = math.copysign(1.0, math.sin(theta)) if abs(math.sin(theta)) > 1e-6 else 1.0
            v_energy += excitation_amplitude * excitation_dir

        # Aggressive wheel-speed tapering: linearly reduce voltage above 60% of max
        abs_phi_dot = abs(phi_dot)
        taper_start = 0.6 * max_wheel_speed
        if abs_phi_dot > taper_start:
            scale = max(0.0, (max_wheel_speed - abs_phi_dot) / (max_wheel_speed - taper_start))
            v_energy *= scale

        return self._clamp_voltage(v_energy, max_voltage)

    # ------------------------------------------------------------------
    # Zero-velocity swing-up helper
    # ------------------------------------------------------------------

    def _compute_zero_velocity_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        """Compute voltage via zero-velocity impulse swing-up.

        Detects zero-crossings of theta_dot (pendulum at swing extremes)
        and applies a proportional voltage pulse to the wheel in the
        direction that pumps energy into the pendulum on the return swing.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        sim_params : SimulationParameters
            Physical simulation parameters.
        ctrl_params : ControlParameters
            Control gains.

        Returns
        -------
        float
            Voltage command [V], clamped to [-max_voltage, max_voltage].
        """
        max_voltage = sim_params.max_voltage
        max_wheel_speed = ctrl_params.swing_up_max_wheel_speed

        # Detect zero-crossing of theta_dot (sign change)
        prev = self._prev_theta_dot
        self._prev_theta_dot = theta_dot

        crossed = (prev > 0.0 and theta_dot <= 0.0) or (prev < 0.0 and theta_dot >= 0.0)

        if crossed and abs(theta) > 0.05:
            # Compute pendulum energy to scale the impulse
            e_pendulum = self._compute_pendulum_energy(theta, theta_dot, sim_params)
            e_error = -e_pendulum  # positive when below target

            if e_error > 0.0:
                # Direction: push pendulum toward upright on the return swing.
                # Positive voltage → positive wheel torque → negative reaction on pendulum.
                # When theta > 0, we want to push pendulum negative (toward upright).
                impulse_dir = math.copysign(1.0, theta)

                duration = ctrl_params.zero_velocity_impulse_duration

                self._impulse_steps_remaining = max(1, int(duration / sim_params.time_step))
                self._impulse_voltage = impulse_dir * max_voltage
            else:
                self._impulse_steps_remaining = 0
                self._impulse_voltage = 0.0

        if self._impulse_steps_remaining > 0:
            self._impulse_steps_remaining -= 1
            # Wheel-speed safety: abort impulse if wheel is too fast
            if abs(phi_dot) > 0.9 * max_wheel_speed:
                self._impulse_steps_remaining = 0
                return 0.0
            return self._clamp_voltage(self._impulse_voltage, max_voltage)

        return 0.0

    # ------------------------------------------------------------------
    # Main control law
    # ------------------------------------------------------------------

    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
        energy: float,
        time: float,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> float:
        """Compute the motor voltage command for swing-up (and balance if configured).

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        current : float
            Armature current [A].
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
            Voltage command [V], clamped to [-max_voltage, max_voltage].
        """
        max_wheel_speed = ctrl_params.swing_up_max_wheel_speed
        abs_phi_dot = abs(phi_dot)

        # Hard safety guard: cut voltage if wheel speed is dangerously high.
        if abs_phi_dot > 1.5 * max_wheel_speed:
            return 0.0

        # Near upright: switch to balance controller if configured.
        if self._balance_mode is not None and self._is_near_upright(theta, theta_dot, ctrl_params):
            if self._balance_mode == "lqr" and self._lqr is not None:
                return self._lqr.compute_voltage(
                    theta, theta_dot, phi_dot, current, energy, time, sim_params, ctrl_params
                )
            if self._balance_mode == "pid" and self._pid is not None:
                return self._pid.compute_voltage(
                    theta, theta_dot, phi_dot, current, energy, time, sim_params, ctrl_params
                )

        # Swing-up region: enforce wheel-speed governor.
        if abs_phi_dot >= max_wheel_speed:
            return 0.0

        match ctrl_params.swing_up_method:
            case SwingUpMethod.pfl:
                voltage = self._compute_pfl_voltage(
                    theta, theta_dot, phi_dot, sim_params, ctrl_params
                )
            case SwingUpMethod.zero_velocity:
                voltage = self._compute_zero_velocity_voltage(
                    theta, theta_dot, phi_dot, sim_params, ctrl_params
                )
            case _:
                voltage = self._compute_energy_voltage(
                    theta, theta_dot, phi_dot, sim_params, ctrl_params
                )

        # Near-upright voltage reduction: the balance handoff above requires
        # both angle AND velocity within thresholds, so a fast pass-through
        # at upright bypasses it and the swing-up law keeps pumping energy,
        # causing continuous rotation.  Linearly taper the swing-up voltage
        # to zero as |theta| -> 0 to prevent this.
        upright_thresh = ctrl_params.upright_angle_threshold
        if abs(theta) < upright_thresh:
            voltage *= abs(theta) / max(upright_thresh, 1e-9)

        # Linearly taper voltage toward zero in the upper 20 % of the speed band.
        taper_threshold = 0.8 * max_wheel_speed
        if abs_phi_dot > taper_threshold:
            scale = (max_wheel_speed - abs_phi_dot) / (max_wheel_speed - taper_threshold)
            voltage *= scale

        return voltage


# Backward-compatible alias
EnergySwingUpController = SwingUpBalanceController


# ---------------------------------------------------------------------------
# SlidingModeController
# ---------------------------------------------------------------------------


class SlidingModeController(Controller):
    """Sliding mode controller for robust pendulum stabilization.

    Defines a sliding surface:
        s = c1 * theta + c2 * theta_dot + c3 * phi_dot

    The control law uses a boundary-layer approximation to reduce chattering:
        V = -K * sat(s / boundary) - eta * s

    where sat() is the saturation function (linear within the boundary layer,
    sign outside). This provides robustness to parameter uncertainty while
    avoiding the high-frequency chattering of pure sign-based SMC.
    """

    def reset(self) -> None:
        pass

    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
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
        max_voltage = sim_params.max_voltage

        # Sliding surface
        s = c1 * theta + c2 * theta_dot + c3 * phi_dot

        # Boundary-layer saturation: sat(s/boundary)
        s_normalized = s / boundary
        if abs(s_normalized) <= 1.0:
            sat_val = s_normalized
        else:
            sat_val = 1.0 if s_normalized > 0 else -1.0

        # Control law
        v = -k * sat_val - eta * s

        return self._clamp_voltage(v, max_voltage)


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
        self._manual_voltage: float = 0.0

        # Instantiate all controllers
        self._no_controller: NoController = NoController()
        self._manual_controller: ManualController = ManualController()
        self._pid_controller: PIDController = PIDController()
        self._lqr_controller: LQRController = LQRController()
        self._swing_up_controller: SwingUpBalanceController = SwingUpBalanceController(balance_mode=None)
        self._swing_up_lqr_controller: SwingUpBalanceController = SwingUpBalanceController(balance_mode="lqr")
        self._swing_up_pid_controller: SwingUpBalanceController = SwingUpBalanceController(balance_mode="pid")
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
        warning = self._lqr_controller.warning
        if warning is None:
            warning = self._swing_up_lqr_controller.lqr_warning
        return warning

    # ------------------------------------------------------------------
    # Mode and parameter management
    # ------------------------------------------------------------------

    def set_mode(self, mode: ControlMode) -> None:
        """Switch control mode, resetting the newly active controller."""
        if mode != self._mode:
            self._mode = mode
            self._get_active_controller().reset()

    def set_manual_voltage(self, voltage: float) -> None:
        """Update the manual voltage setpoint."""
        self._manual_voltage = voltage
        self._manual_controller.set_voltage(voltage)

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
        self._swing_up_controller.reset()
        self._swing_up_lqr_controller.reset()
        self._swing_up_pid_controller.reset()
        self._smc_controller.reset()
        self._manual_voltage = 0.0

    def reset_active(self) -> None:
        """Reset only the currently active controller."""
        self._get_active_controller().reset()

    # ------------------------------------------------------------------
    # Torque computation
    # ------------------------------------------------------------------

    def compute_voltage(
        self,
        theta: float,
        theta_dot: float,
        phi_dot: float,
        current: float,
        energy: float,
        time: float,
    ) -> float:
        """Delegate voltage computation to the active controller.

        Parameters
        ----------
        theta : float
            Pendulum angle from upright [rad].
        theta_dot : float
            Pendulum angular velocity [rad/s].
        phi_dot : float
            Relative wheel angular velocity [rad/s].
        current : float
            Armature current [A].
        energy : float
            Total mechanical energy (upright-referenced) [J].
        time : float
            Current simulation time [s].

        Returns
        -------
        float
            Voltage command [V] clamped to [-max_voltage, max_voltage].
        """
        controller = self._get_active_controller()
        return controller.compute_voltage(
            theta, theta_dot, phi_dot, current, energy, time,
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
                return self._swing_up_controller
            case ControlMode.swing_up:
                return self._swing_up_controller
            case ControlMode.swing_up_lqr:
                return self._swing_up_lqr_controller
            case ControlMode.swing_up_pid:
                return self._swing_up_pid_controller
            case ControlMode.sliding_mode:
                return self._smc_controller
            case _:
                return self._no_controller