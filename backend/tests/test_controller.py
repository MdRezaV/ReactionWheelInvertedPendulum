"""Deterministic tests for SwingUpBalanceController wheel-speed governor."""

from __future__ import annotations

import pytest

from controller import SwingUpBalanceController
from models import ControlParameters, SimulationParameters


@pytest.fixture
def sim_params() -> SimulationParameters:
    return SimulationParameters()


@pytest.fixture
def ctrl_params() -> ControlParameters:
    return ControlParameters()


class TestSwingUpWheelSpeedGovernor:
    """Verify voltage cutoff at and above the configured max wheel speed."""

    def test_zero_voltage_at_exact_max_wheel_speed(self, sim_params, ctrl_params):
        """Voltage is zero when |phi_dot| equals swing_up_max_wheel_speed."""
        controller = SwingUpBalanceController(balance_mode=None)
        max_speed = ctrl_params.swing_up_max_wheel_speed

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=max_speed,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage == 0.0

    def test_zero_voltage_above_max_wheel_speed(self, sim_params, ctrl_params):
        """Voltage is zero when |phi_dot| exceeds swing_up_max_wheel_speed."""
        controller = SwingUpBalanceController(balance_mode=None)
        max_speed = ctrl_params.swing_up_max_wheel_speed

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=max_speed + 1.0,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage == 0.0

    def test_zero_voltage_at_negative_max_wheel_speed(self, sim_params, ctrl_params):
        """Voltage is zero when phi_dot equals -swing_up_max_wheel_speed."""
        controller = SwingUpBalanceController(balance_mode=None)
        max_speed = ctrl_params.swing_up_max_wheel_speed

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=-max_speed,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage == 0.0


class TestSwingUpHardSafetyGuard:
    """Verify the hard safety guard at 1.5x max wheel speed."""

    def test_zero_voltage_above_hard_guard(self, sim_params, ctrl_params):
        """Voltage is zero when |phi_dot| exceeds 1.5 * max_wheel_speed."""
        controller = SwingUpBalanceController(balance_mode=None)
        hard_limit = 1.5 * ctrl_params.swing_up_max_wheel_speed

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=hard_limit + 1.0,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage == 0.0

    def test_zero_voltage_at_negative_hard_guard(self, sim_params, ctrl_params):
        """Voltage is zero when phi_dot is below -1.5 * max_wheel_speed."""
        controller = SwingUpBalanceController(balance_mode=None)
        hard_limit = 1.5 * ctrl_params.swing_up_max_wheel_speed

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=-(hard_limit + 1.0),
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage == 0.0

    def test_hard_guard_overrides_balance_mode(self, sim_params, ctrl_params):
        """Hard safety guard applies even when balance_mode is configured."""
        controller = SwingUpBalanceController(balance_mode="pid")
        hard_limit = 1.5 * ctrl_params.swing_up_max_wheel_speed

        voltage = controller.compute_voltage(
            theta=0.1,
            theta_dot=0.0,
            phi_dot=hard_limit + 1.0,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage == 0.0


class TestSwingUpNonzeroVoltage:
    """Verify nonzero swing-up voltage when safely below the wheel-speed limit."""

    def test_nonzero_voltage_below_limit(self, sim_params, ctrl_params):
        """Voltage is nonzero when |phi_dot| is well below max_wheel_speed."""
        controller = SwingUpBalanceController(balance_mode=None)

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=5.0,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage != 0.0

    def test_nonzero_voltage_negative_phi_dot(self, sim_params, ctrl_params):
        """Voltage is nonzero for negative phi_dot below the limit."""
        controller = SwingUpBalanceController(balance_mode=None)

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=-5.0,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage != 0.0

    def test_voltage_sign_follows_energy_pumping_convention(self, sim_params, ctrl_params):
        """With energy below target and positive phi_dot, voltage is positive."""
        controller = SwingUpBalanceController(balance_mode=None)

        voltage = controller.compute_voltage(
            theta=2.0,
            theta_dot=0.0,
            phi_dot=5.0,
            current=0.0,
            energy=-1.0,
            time=0.0,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
        )
        assert voltage > 0.0