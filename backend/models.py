"""Shared Pydantic schemas and enums for the reaction wheel inverted pendulum backend."""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


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
    manual = "manual"


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
    wheel_radius: float = Field(default=0.05, gt=0, description="Reaction wheel radius [m]")
    wheel_inertia: Optional[float] = Field(
        default=None, gt=0, description="Wheel moment of inertia [kg·m²]; computed if None"
    )
    damping: float = Field(default=0.01, ge=0, description="Pendulum joint damping [N·m·s/rad]")
    wheel_damping: float = Field(default=0.001, ge=0, description="Wheel bearing damping [N·m·s/rad]")
    gravity: float = Field(default=9.81, gt=0, description="Gravitational acceleration [m/s²]")
    time_step: float = Field(default=0.001, gt=0, description="Integration time step [s]")
    max_motor_torque: float = Field(default=1.0, gt=0, description="Maximum motor torque [N·m]")
    initial_theta: float = Field(default=0.05, description="Initial pendulum angle [rad]")
    initial_theta_dot: float = Field(default=0.0, description="Initial pendulum angular velocity [rad/s]")
    initial_phi: float = Field(default=0.0, description="Initial wheel angle [rad]")
    initial_phi_dot: float = Field(default=0.0, description="Initial wheel angular velocity [rad/s]")

    @model_validator(mode="after")
    def _validate_com_within_length(self) -> "SimulationParameters":
        if self.pendulum_com_length is not None and self.pendulum_com_length > self.pendulum_length:
            raise ValueError("pendulum_com_length cannot exceed pendulum_length")
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

    upright_angle_threshold: float = Field(
        default=0.3, gt=0, description="Angle threshold to consider upright [rad]"
    )
    upright_velocity_threshold: float = Field(
        default=1.0, gt=0, description="Velocity threshold for upright switch [rad/s]"
    )

    manual_torque: float = Field(default=0.0, description="Manual torque command [N·m]")


# ---------------------------------------------------------------------------
# API Response Schemas
# ---------------------------------------------------------------------------


class StatusResponse(BaseModel):
    status: SimulationStatus
    time: float = 0.0
    control_mode: ControlMode = ControlMode.none
    client_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class ParamsResponse(BaseModel):
    simulation: SimulationParameters
    control: ControlParameters


class TelemetryMessage(BaseModel):
    time: float
    theta: float
    theta_dot: float
    phi: float
    phi_dot: float
    torque: float
    energy: float
    mode: ControlMode


# ---------------------------------------------------------------------------
# API Request Schemas
# ---------------------------------------------------------------------------


class ParamsUpdateRequest(BaseModel):
    simulation: Optional[SimulationParameters] = None
    control: Optional[ControlParameters] = None


class ControlModeRequest(BaseModel):
    mode: ControlMode


class ManualTorqueRequest(BaseModel):
    torque: float = Field(description="Torque command [N·m]")


class StepRequest(BaseModel):
    steps: int = Field(default=1, ge=1, description="Number of physics steps to advance")


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


class WSSetManualTorqueCommand(WSCommandBase):
    type: Literal["set_manual_torque"] = "set_manual_torque"
    torque: float


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
    | WSSetManualTorqueCommand
)