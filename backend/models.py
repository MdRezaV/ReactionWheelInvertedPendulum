"""Shared Pydantic schemas and enums for the reaction wheel inverted pendulum backend."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SimulationStatus(str, Enum):
    stopped = "stopped"
    running = "running"
    paused = "paused"


class ControlMode(str, Enum):
    none = "none"
    pid = "pid"
    lqr = "lqr"
    energy_swing_up = "energy_swing_up"
    sliding_mode = "sliding_mode"
    manual = "manual"


class AutoTunerStatus(str, Enum):
    idle = "idle"
    running = "running"
    complete = "complete"


# ---------------------------------------------------------------------------
# Simulation Parameters
# ---------------------------------------------------------------------------


class SimulationParameters(BaseModel):
    """Physical and numerical parameters for the pendulum simulation.

    Nullable fields (pendulum_com_length, pendulum_inertia, wheel_inertia)
    allow the simulation layer to compute physical fallbacks when not
    explicitly provided.
    """

    pendulum_mass: float = Field(default=1.0, gt=0, description="Pendulum mass [kg]")
    pendulum_length: float = Field(default=0.5, gt=0, description="Pendulum length [m]")
    pendulum_com_length: Optional[float] = Field(
        default=None, gt=0, description="Center-of-mass distance from pivot [m]; computed if None"
    )
    pendulum_inertia: Optional[float] = Field(
        default=None, gt=0, description="Pendulum moment of inertia [kg·m²]; computed if None"
    )
    wheel_mass: float = Field(default=0.5, gt=0, description="Reaction wheel mass [kg]")
    wheel_inner_radius: float = Field(default=0.04, gt=0, description="Reaction wheel inner radius [m]")
    wheel_outer_radius: float = Field(default=0.05, gt=0, description="Reaction wheel outer radius [m]")
    wheel_inertia: Optional[float] = Field(
        default=None, gt=0, description="Wheel moment of inertia [kg·m²]; computed if None"
    )
    damping: float = Field(default=0.01, ge=0, description="Pendulum joint damping [N·m·s/rad]")
    wheel_damping: float = Field(default=0.001, ge=0, description="Wheel bearing damping [N·m·s/rad]")
    gravity: float = Field(default=9.81, gt=0, description="Gravitational acceleration [m/s²]")
    time_step: float = Field(default=0.001, gt=0, description="Integration time step [s]")
    max_voltage: float = Field(default=12.0, gt=0, description="Maximum applied voltage [V]")
    motor_resistance: float = Field(default=1.0, gt=0, description="Armature resistance [Ω]")
    motor_inductance: float = Field(
        default=0.001, gt=0,
        description="Armature inductance [H]; L/R must be >= time_step/10 (stiffness guard)",
    )
    motor_constant: float = Field(
        default=0.05, gt=0, description="Motor torque/back-EMF constant Kt=Ke [N·m/A = V·s/rad]"
    )
    motor_rotor_inertia: float = Field(default=1e-5, gt=0, description="Motor rotor inertia [kg·m²]")
    motor_viscous_friction: float = Field(
        default=1e-5, ge=0, description="Motor viscous friction [N·m·s/rad]"
    )
    gear_ratio: float = Field(default=10.0, gt=0, description="Gearbox ratio N (motor_speed = N * wheel_speed)")
    initial_theta: float = Field(default=0.05, description="Initial pendulum angle [rad]")
    initial_theta_dot: float = Field(default=0.0, description="Initial pendulum angular velocity [rad/s]")
    initial_phi: float = Field(default=0.0, description="Initial wheel angle [rad]")
    initial_phi_dot: float = Field(default=0.0, description="Initial wheel angular velocity [rad/s]")
    initial_current: float = Field(default=0.0, description="Initial armature current [A]")

    @model_validator(mode="after")
    def _validate_com_within_length(self) -> "SimulationParameters":
        if self.pendulum_com_length is not None and self.pendulum_com_length > self.pendulum_length:
            raise ValueError("pendulum_com_length cannot exceed pendulum_length")
        return self

    @model_validator(mode="after")
    def _validate_wheel_radii(self) -> "SimulationParameters":
        if self.wheel_inner_radius >= self.wheel_outer_radius:
            raise ValueError("wheel_inner_radius must be strictly less than wheel_outer_radius")
        return self

    @model_validator(mode="after")
    def _validate_electrical_stiffness(self) -> "SimulationParameters":
        """Reject inductance values that make the electrical time constant too small.

        The electrical time constant tau_e = L / R must satisfy
        tau_e >= time_step / 10 to avoid numerical stiffness in the
        coupled electro-mechanical ODE system.
        """
        tau_e = self.motor_inductance / self.motor_resistance
        min_tau = self.time_step / 10.0
        if tau_e < min_tau:
            logger.warning(
                "Electrical time constant L/R=%.6f s is below minimum %.6f s "
                "(time_step/10). Increase motor_inductance or decrease time_step.",
                tau_e,
                min_tau,
            )
            raise ValueError(
                f"motor_inductance/motor_resistance ({tau_e:.6e} s) must be >= "
                f"time_step/10 ({min_tau:.6e} s) to avoid numerical stiffness"
            )
        return self


# ---------------------------------------------------------------------------
# Control Parameters
# ---------------------------------------------------------------------------


class ControlParameters(BaseModel):
    """Tunable gains and thresholds for all control modes."""

    pid_kp: float = Field(default=50.0, ge=0, description="PID proportional gain")
    pid_ki: float = Field(default=0.1, ge=0, description="PID integral gain")
    pid_kd: float = Field(default=10.0, ge=0, description="PID derivative gain")

    lqr_q_theta: float = Field(default=100.0, ge=0, description="LQR weight on theta")
    lqr_q_theta_dot: float = Field(default=1.0, ge=0, description="LQR weight on theta_dot")
    lqr_q_phi_dot: float = Field(default=10.0, ge=0, description="LQR weight on phi_dot")
    lqr_q_phi: float = Field(default=0.1, ge=0, description="LQR weight on phi")
    lqr_r: float = Field(default=1.0, gt=0, description="LQR control effort weight")

    energy_swing_up_gain: float = Field(default=1.0, gt=0, description="Energy swing-up gain")

    smc_c1: float = Field(default=10.0, gt=0, description="SMC sliding surface coeff on theta")
    smc_c2: float = Field(default=5.0, gt=0, description="SMC sliding surface coeff on theta_dot")
    smc_c3: float = Field(default=1.0, ge=0, description="SMC sliding surface coeff on phi_dot")
    smc_k: float = Field(default=2.0, gt=0, description="SMC switching gain")
    smc_eta: float = Field(default=0.5, ge=0, description="SMC reaching law coeff")
    smc_boundary: float = Field(default=0.05, gt=0, description="SMC boundary layer thickness")

    upright_angle_threshold: float = Field(
        default=0.3, gt=0, description="Angle threshold to consider upright [rad]"
    )
    upright_velocity_threshold: float = Field(
        default=1.0, gt=0, description="Velocity threshold for upright switch [rad/s]"
    )

    lqr_q_current: float = Field(default=0.01, ge=0, description="LQR weight on armature current")

    manual_voltage: float = Field(default=0.0, description="Manual voltage command [V]")


# ---------------------------------------------------------------------------
# API Response Schemas
# ---------------------------------------------------------------------------


class StatusResponse(BaseModel):
    status: SimulationStatus
    time: float = 0.0
    control_mode: ControlMode = ControlMode.none
    client_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    speed_multiplier: float = 1.0


class ParamsResponse(BaseModel):
    simulation: SimulationParameters
    control: ControlParameters


class TelemetryMessage(BaseModel):
    time: float
    theta: float
    theta_dot: float
    theta_ddot: float = 0.0
    phi: float
    phi_dot: float
    phi_ddot: float = 0.0
    voltage: float
    current: float = 0.0
    back_emf: float = 0.0
    motor_torque: float = 0.0
    wheel_torque: float = 0.0
    energy: float
    kinetic_energy: float = 0.0
    potential_energy: float = 0.0
    angular_momentum: float = 0.0
    mode: ControlMode


# ---------------------------------------------------------------------------
# Binary telemetry encoding constants
# ---------------------------------------------------------------------------

TELEMETRY_FIELD_ORDER: list[str] = [
    "time", "theta", "theta_dot", "theta_ddot",
    "phi", "phi_dot", "phi_ddot",
    "voltage", "current", "back_emf",
    "motor_torque", "wheel_torque",
    "energy", "kinetic_energy", "potential_energy", "angular_momentum",
    "mode",
]

MODE_TO_INT: dict[str, int] = {
    "none": 0, "pid": 1, "lqr": 2,
    "energy_swing_up": 3, "sliding_mode": 4, "manual": 5,
}
INT_TO_MODE: dict[int, str] = {v: k for k, v in MODE_TO_INT.items()}

DEADBANDS: list[float] = [
    0.0,      # time: always send
    0.0005,   # theta
    0.005,    # theta_dot
    0.01,     # theta_ddot
    0.001,    # phi
    0.01,     # phi_dot
    0.05,     # phi_ddot
    0.005,    # voltage
    0.001,    # current
    0.005,    # back_emf
    0.0001,   # motor_torque
    0.001,    # wheel_torque
    0.0005,   # energy
    0.0005,   # kinetic_energy
    0.0005,   # potential_energy
    0.001,    # angular_momentum
    0.0,      # mode: always send if changed
]


class StatusEvent(BaseModel):
    """Lightweight status push sent over WebSocket on state changes."""
    type: str = "status"
    status: SimulationStatus
    time: float = 0.0
    control_mode: ControlMode = ControlMode.none
    client_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    speed_multiplier: float = 1.0


# ---------------------------------------------------------------------------
# API Request Schemas
# ---------------------------------------------------------------------------


class ParamsUpdateRequest(BaseModel):
    simulation: Optional[SimulationParameters] = None
    control: Optional[ControlParameters] = None


class ControlModeRequest(BaseModel):
    mode: ControlMode


class ManualVoltageRequest(BaseModel):
    voltage: float = Field(description="Voltage command [V]")


class StepRequest(BaseModel):
    steps: int = Field(default=1, ge=1, description="Number of physics steps to advance")


class DisturbanceRequest(BaseModel):
    voltage: float = Field(description="Disturbance voltage magnitude [V]")
    duration_steps: int = Field(default=10, ge=1, le=1000, description="Duration in physics steps")


class SpeedRequest(BaseModel):
    multiplier: float = Field(default=1.0, ge=0.1, le=10.0, description="Simulation speed multiplier")


# ---------------------------------------------------------------------------
# WebSocket Command Schemas
# ---------------------------------------------------------------------------


class WSCommandBase(BaseModel):
    type: str


class WSStartCommand(WSCommandBase):
    type: Literal["start"] = "start"


class WSStopCommand(WSCommandBase):
    type: Literal["stop"] = "stop"


class WSPauseCommand(WSCommandBase):
    type: Literal["pause"] = "pause"


class WSResumeCommand(WSCommandBase):
    type: Literal["resume"] = "resume"


class WSResetCommand(WSCommandBase):
    type: Literal["reset"] = "reset"


class WSStepCommand(WSCommandBase):
    type: Literal["step"] = "step"
    steps: int = Field(default=1, ge=1)


class WSSetParamCommand(WSCommandBase):
    type: Literal["set_param"] = "set_param"
    name: str
    value: float
    scope: Optional[Literal["simulation", "control"]] = None


class WSSetSimulationParamsCommand(WSCommandBase):
    type: Literal["set_simulation_params"] = "set_simulation_params"
    params: SimulationParameters


class WSSetControlParamsCommand(WSCommandBase):
    type: Literal["set_control_params"] = "set_control_params"
    params: ControlParameters


class WSSetControlModeCommand(WSCommandBase):
    type: Literal["set_control_mode"] = "set_control_mode"
    mode: ControlMode


class WSSetManualVoltageCommand(WSCommandBase):
    type: Literal["set_manual_voltage"] = "set_manual_voltage"
    voltage: float


class WSDisturbanceCommand(WSCommandBase):
    type: Literal["apply_disturbance"] = "apply_disturbance"
    voltage: float
    duration_steps: int = Field(default=10, ge=1, le=1000)


class WSSetSpeedCommand(WSCommandBase):
    type: Literal["set_speed"] = "set_speed"
    multiplier: float = Field(default=1.0, ge=0.1, le=10.0)


class WSAutoTunerStartCommand(WSCommandBase):
    type: Literal["auto_tuner_start"] = "auto_tuner_start"
    initial_angle: float = Field(
        default=0.087, description="Initial pendulum angle for tuning [rad] (~5 deg)"
    )


class WSAutoTunerStopCommand(WSCommandBase):
    type: Literal["auto_tuner_stop"] = "auto_tuner_stop"


WSCommand = (
    WSStartCommand
    | WSStopCommand
    | WSPauseCommand
    | WSResumeCommand
    | WSResetCommand
    | WSStepCommand
    | WSSetParamCommand
    | WSSetSimulationParamsCommand
    | WSSetControlParamsCommand
    | WSSetControlModeCommand
    | WSSetManualVoltageCommand
    | WSDisturbanceCommand
    | WSSetSpeedCommand
    | WSAutoTunerStartCommand
    | WSAutoTunerStopCommand
)