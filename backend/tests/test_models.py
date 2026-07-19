"""Tests for Pydantic model validation and construction."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import (
    ControlMode,
    ControlParameters,
    SimulationParameters,
    SimulationStatus,
    TelemetryMessage,
)


class TestSimulationParametersDefaults:
    """Verify default parameter construction produces valid physical values."""

    def test_default_construction(self):
        params = SimulationParameters()
        assert params.pendulum_mass == 1.0
        assert params.pendulum_length == 0.5
        assert params.wheel_mass == 0.5
        assert params.wheel_radius == 0.05
        assert params.gravity == 9.81
        assert params.time_step == 0.001
        assert params.max_motor_torque == 1.0
        assert params.damping == 0.01
        assert params.wheel_damping == 0.001

    def test_default_initial_conditions(self):
        params = SimulationParameters()
        assert params.initial_theta == 0.05
        assert params.initial_theta_dot == 0.0
        assert params.initial_phi == 0.0
        assert params.initial_phi_dot == 0.0

    def test_nullable_inertia_defaults_to_none(self):
        params = SimulationParameters()
        assert params.pendulum_com_length is None
        assert params.pendulum_inertia is None
        assert params.wheel_inertia is None

    def test_explicit_inertia_values_accepted(self):
        params = SimulationParameters(
            pendulum_com_length=0.25,
            pendulum_inertia=0.1,
            wheel_inertia=0.001,
        )
        assert params.pendulum_com_length == 0.25
        assert params.pendulum_inertia == 0.1
        assert params.wheel_inertia == 0.001


class TestSimulationParametersValidation:
    """Verify rejection of physically invalid parameter values."""

    @pytest.mark.parametrize("field,value", [
        ("pendulum_mass", 0.0),
        ("pendulum_mass", -1.0),
        ("pendulum_length", 0.0),
        ("pendulum_length", -0.5),
        ("wheel_mass", 0.0),
        ("wheel_mass", -2.0),
        ("wheel_radius", 0.0),
        ("wheel_radius", -0.01),
        ("time_step", 0.0),
        ("time_step", -0.001),
        ("max_motor_torque", 0.0),
        ("max_motor_torque", -1.0),
        ("gravity", 0.0),
        ("gravity", -9.81),
    ])
    def test_rejects_non_positive_required_fields(self, field: str, value: float):
        with pytest.raises(ValidationError):
            SimulationParameters(**{field: value})

    def test_rejects_negative_damping(self):
        with pytest.raises(ValidationError):
            SimulationParameters(damping=-0.01)

    def test_rejects_negative_wheel_damping(self):
        with pytest.raises(ValidationError):
            SimulationParameters(wheel_damping=-0.001)

    def test_rejects_com_exceeding_length(self):
        with pytest.raises(ValidationError, match="pendulum_com_length cannot exceed"):
            SimulationParameters(pendulum_com_length=1.0, pendulum_length=0.5)

    def test_accepts_com_equal_to_length(self):
        params = SimulationParameters(pendulum_com_length=0.5, pendulum_length=0.5)
        assert params.pendulum_com_length == 0.5

    def test_rejects_negative_inertia(self):
        with pytest.raises(ValidationError):
            SimulationParameters(pendulum_inertia=-0.1)

    def test_rejects_negative_wheel_inertia(self):
        with pytest.raises(ValidationError):
            SimulationParameters(wheel_inertia=-0.001)


class TestControlParametersDefaults:
    """Verify default control parameter construction."""

    def test_default_construction(self):
        params = ControlParameters()
        assert params.pid_kp == 50.0
        assert params.pid_ki == 0.1
        assert params.pid_kd == 10.0
        assert params.lqr_q_theta == 100.0
        assert params.lqr_r == 1.0
        assert params.energy_swing_up_gain == 1.0
        assert params.upright_angle_threshold == 0.3
        assert params.manual_torque == 0.0

    def test_rejects_negative_gains(self):
        with pytest.raises(ValidationError):
            ControlParameters(pid_kp=-1.0)

    def test_rejects_zero_lqr_r(self):
        with pytest.raises(ValidationError):
            ControlParameters(lqr_r=0.0)


class TestEnums:
    """Verify enum values."""

    def test_simulation_status_values(self):
        assert SimulationStatus.stopped == "stopped"
        assert SimulationStatus.running == "running"
        assert SimulationStatus.paused == "paused"

    def test_control_mode_values(self):
        assert ControlMode.none == "none"
        assert ControlMode.pid == "pid"
        assert ControlMode.lqr == "lqr"
        assert ControlMode.energy_swing_up == "energy_swing_up"
        assert ControlMode.manual == "manual"


class TestTelemetryMessage:
    """Verify telemetry message construction."""

    def test_construction(self):
        msg = TelemetryMessage(
            time=1.0,
            theta=0.01,
            theta_dot=-0.1,
            phi=0.5,
            phi_dot=10.0,
            torque=0.3,
            energy=1.5,
            mode=ControlMode.lqr,
        )
        assert msg.time == 1.0
        assert msg.theta == 0.01
        assert msg.mode == ControlMode.lqr

    def test_extended_fields_default(self):
        msg = TelemetryMessage(
            time=0.0,
            theta=0.0,
            theta_dot=0.0,
            phi=0.0,
            phi_dot=0.0,
            torque=0.0,
            energy=0.0,
            mode=ControlMode.none,
        )
        assert msg.theta_ddot == 0.0
        assert msg.phi_ddot == 0.0
        assert msg.kinetic_energy == 0.0
        assert msg.potential_energy == 0.0
        assert msg.angular_momentum == 0.0

    def test_extended_fields_populated(self):
        msg = TelemetryMessage(
            time=2.0,
            theta=0.1,
            theta_dot=0.5,
            theta_ddot=-1.2,
            phi=1.0,
            phi_dot=8.0,
            phi_ddot=3.5,
            torque=0.4,
            energy=2.1,
            kinetic_energy=1.8,
            potential_energy=0.3,
            angular_momentum=0.7,
            mode=ControlMode.sliding_mode,
        )
        assert msg.theta_ddot == -1.2
        assert msg.phi_ddot == 3.5
        assert msg.kinetic_energy == 1.8
        assert msg.potential_energy == 0.3
        assert msg.angular_momentum == 0.7
        assert msg.mode == ControlMode.sliding_mode


class TestControlModeEnum:
    """Verify all control modes including SMC."""

    def test_sliding_mode_exists(self):
        assert ControlMode.sliding_mode == "sliding_mode"

    def test_all_modes(self):
        modes = [m.value for m in ControlMode]
        assert "none" in modes
        assert "pid" in modes
        assert "lqr" in modes
        assert "energy_swing_up" in modes
        assert "sliding_mode" in modes
        assert "manual" in modes


class TestControlParametersSMC:
    """Verify SMC parameter defaults and validation."""

    def test_smc_defaults(self):
        params = ControlParameters()
        assert params.smc_c1 == 10.0
        assert params.smc_c2 == 5.0
        assert params.smc_c3 == 1.0
        assert params.smc_k == 2.0
        assert params.smc_eta == 0.5
        assert params.smc_boundary == 0.05

    def test_rejects_negative_smc_k(self):
        with pytest.raises(ValidationError):
            ControlParameters(smc_k=-1.0)

    def test_rejects_zero_smc_boundary(self):
        with pytest.raises(ValidationError):
            ControlParameters(smc_boundary=0.0)