"""Tests for Pydantic model validation and construction."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import (
    ControlMode,
    ControlParameters,
    ManualVoltageRequest,
    SimulationParameters,
    SimulationStatus,
    TelemetryMessage,
    TuningTarget,
    WSAutoTunerStartCommand,
    WSSetManualVoltageCommand,
)


class TestSimulationParametersDefaults:
    """Verify default parameter construction produces valid physical values."""

    def test_default_construction(self):
        params = SimulationParameters()
        assert params.pendulum_mass == 1.0
        assert params.pendulum_length == 0.5
        assert params.wheel_mass == 0.5
        assert params.wheel_inner_radius == 0.04
        assert params.wheel_outer_radius == 0.05
        assert params.gravity == 9.81
        assert params.time_step == 0.001
        assert params.damping == 0.01
        assert params.wheel_damping == 0.001

    def test_default_motor_parameters(self):
        params = SimulationParameters()
        assert params.max_voltage == 12.0
        assert params.motor_resistance == 1.0
        assert params.motor_inductance == 0.001
        assert params.motor_constant == 0.05
        assert params.motor_rotor_inertia == 1e-5
        assert params.motor_viscous_friction == 1e-5
        assert params.gear_ratio == 10.0
        assert params.initial_current == 0.0

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
        ("wheel_inner_radius", 0.0),
        ("wheel_inner_radius", -0.01),
        ("wheel_outer_radius", 0.0),
        ("wheel_outer_radius", -0.01),
        ("time_step", 0.0),
        ("time_step", -0.001),
        ("gravity", 0.0),
        ("gravity", -9.81),
        ("motor_resistance", 0.0),
        ("motor_resistance", -1.0),
        ("motor_inductance", 0.0),
        ("motor_inductance", -0.001),
        ("motor_constant", 0.0),
        ("motor_constant", -0.05),
        ("motor_rotor_inertia", 0.0),
        ("motor_rotor_inertia", -1e-5),
        ("gear_ratio", 0.0),
        ("gear_ratio", -10.0),
        ("max_voltage", 0.0),
        ("max_voltage", -12.0),
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

    def test_motor_viscous_friction_accepts_zero(self):
        params = SimulationParameters(motor_viscous_friction=0.0)
        assert params.motor_viscous_friction == 0.0

    def test_rejects_negative_motor_viscous_friction(self):
        with pytest.raises(ValidationError):
            SimulationParameters(motor_viscous_friction=-1e-5)

    def test_rejects_inner_radius_not_less_than_outer(self):
        with pytest.raises(ValidationError, match="wheel_inner_radius must be strictly less than wheel_outer_radius"):
            SimulationParameters(wheel_inner_radius=0.05, wheel_outer_radius=0.05)
        with pytest.raises(ValidationError, match="wheel_inner_radius must be strictly less than wheel_outer_radius"):
            SimulationParameters(wheel_inner_radius=0.06, wheel_outer_radius=0.05)

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
        assert params.manual_voltage == 0.0
        assert params.lqr_q_current == 0.01

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
            voltage=6.0,
            energy=1.5,
            mode=ControlMode.lqr,
        )
        assert msg.time == 1.0
        assert msg.theta == 0.01
        assert msg.voltage == 6.0
        assert msg.mode == ControlMode.lqr

    def test_extended_fields_default(self):
        msg = TelemetryMessage(
            time=0.0,
            theta=0.0,
            theta_dot=0.0,
            phi=0.0,
            phi_dot=0.0,
            voltage=0.0,
            energy=0.0,
            mode=ControlMode.none,
        )
        assert msg.theta_ddot == 0.0
        assert msg.phi_ddot == 0.0
        assert msg.current == 0.0
        assert msg.back_emf == 0.0
        assert msg.motor_torque == 0.0
        assert msg.wheel_torque == 0.0
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
            voltage=9.5,
            current=2.3,
            back_emf=4.1,
            motor_torque=0.12,
            wheel_torque=1.2,
            energy=2.1,
            kinetic_energy=1.8,
            potential_energy=0.3,
            angular_momentum=0.7,
            mode=ControlMode.sliding_mode,
        )
        assert msg.theta_ddot == -1.2
        assert msg.phi_ddot == 3.5
        assert msg.voltage == 9.5
        assert msg.current == 2.3
        assert msg.back_emf == 4.1
        assert msg.motor_torque == 0.12
        assert msg.wheel_torque == 1.2
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


class TestManualVoltageRequest:
    """Verify ManualVoltageRequest schema."""

    def test_construction(self):
        req = ManualVoltageRequest(voltage=5.5)
        assert req.voltage == 5.5

    def test_negative_voltage_accepted(self):
        req = ManualVoltageRequest(voltage=-3.0)
        assert req.voltage == -3.0


class TestWSSetManualVoltageCommand:
    """Verify WSSetManualVoltageCommand schema."""

    def test_type_literal(self):
        cmd = WSSetManualVoltageCommand(voltage=7.2)
        assert cmd.type == "set_manual_voltage"

    def test_voltage_field(self):
        cmd = WSSetManualVoltageCommand(voltage=-1.5)
        assert cmd.voltage == -1.5


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


class TestTuningTarget:
    """Verify TuningTarget enum values."""

    def test_swing_up_pid_value(self):
        assert TuningTarget.swing_up_pid == "swing_up_pid"

    def test_swing_up_lqr_value(self):
        assert TuningTarget.swing_up_lqr == "swing_up_lqr"

    def test_all_targets_present(self):
        targets = [t.value for t in TuningTarget]
        assert "pid" in targets
        assert "lqr" in targets
        assert "swing_up_pid" in targets
        assert "swing_up_lqr" in targets


class TestWSAutoTunerStartCommandTarget:
    """Verify WSAutoTunerStartCommand validates new tuning targets."""

    def test_accepts_swing_up_pid(self):
        cmd = WSAutoTunerStartCommand(target="swing_up_pid")
        assert cmd.target == TuningTarget.swing_up_pid

    def test_accepts_swing_up_lqr(self):
        cmd = WSAutoTunerStartCommand(target="swing_up_lqr")
        assert cmd.target == TuningTarget.swing_up_lqr

    def test_accepts_pid(self):
        cmd = WSAutoTunerStartCommand(target="pid")
        assert cmd.target == TuningTarget.pid

    def test_accepts_lqr(self):
        cmd = WSAutoTunerStartCommand(target="lqr")
        assert cmd.target == TuningTarget.lqr

    def test_rejects_invalid_target(self):
        with pytest.raises(ValidationError):
            WSAutoTunerStartCommand(target="invalid_target")


class TestControlParametersSwingUpMaxWheelSpeed:
    """Verify swing_up_max_wheel_speed default and validation."""

    def test_default_value(self):
        params = ControlParameters()
        assert params.swing_up_max_wheel_speed == 50.0

    def test_rejects_zero(self):
        with pytest.raises(ValidationError):
            ControlParameters(swing_up_max_wheel_speed=0.0)

    def test_rejects_negative(self):
        with pytest.raises(ValidationError):
            ControlParameters(swing_up_max_wheel_speed=-10.0)