"""Tests for the 5-state DC motor reaction wheel inverted pendulum simulation.

Verifies numerical correctness of the RK4 integrator, energy conservation,
voltage saturation, parameter validation, qualitative dynamic response,
gearbox effects, and the electrical (armature current) state dynamics.

State vector: [theta, theta_dot, phi, phi_dot, i_a]
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from models import ControlMode, SimulationParameters
from simulation import Simulation


class TestUprightEquilibrium:
    """With zero voltage and zero initial current, upright is an equilibrium."""

    def test_stationary_at_upright(self):
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
        )
        sim = Simulation(params)

        for _ in range(1000):
            sim.step(0.0)

        state = sim.get_state()
        assert abs(state["theta"]) < 1e-10
        assert abs(state["theta_dot"]) < 1e-10
        assert abs(state["phi_dot"]) < 1e-10
        assert abs(state["current"]) < 1e-10

    def test_current_decays_with_zero_voltage(self):
        """With zero voltage and nonzero initial current, current decays ~exponentially.

        Uses weak electromechanical coupling (small gear_ratio and motor_constant)
        so that back-EMF feedback is negligible and the decay is approximately
        i(t) = i_0 * exp(-R t / L).
        """
        L = 0.01
        R = 1.0
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi=0.0,
            initial_phi_dot=0.0,
            initial_current=1.0,
            motor_inductance=L,
            motor_resistance=R,
            gear_ratio=1.0,
            motor_constant=0.01,
            damping=0.0,
            wheel_damping=0.0,
            motor_viscous_friction=0.0,
        )
        sim = Simulation(params)

        tau = L / R  # 0.01 s = 10 steps at dt=0.001
        steps_per_tau = int(tau / params.time_step)

        for _ in range(steps_per_tau):
            sim.step(0.0)

        state = sim.get_state()
        expected = math.exp(-1.0)  # i_0 * e^{-1}
        assert state["current"] == pytest.approx(expected, rel=0.10)


class TestEnergyConservation:
    """With zero damping and negligible resistance, mechanical energy is conserved."""

    def test_energy_conserved_undamped(self):
        """With R very small, I²R losses are negligible over the test horizon."""
        params = SimulationParameters(
            initial_theta=0.3,
            initial_theta_dot=0.5,
            initial_phi_dot=2.0,
            initial_current=0.0,
            damping=0.0,
            wheel_damping=0.0,
            motor_viscous_friction=0.0,
            motor_resistance=1e-4,
            motor_inductance=0.01,
        )
        sim = Simulation(params)

        e0 = sim.compute_energy()

        for _ in range(2000):
            sim.step(0.0)

        e_final = sim.compute_energy()
        assert abs(e_final - e0) < 1e-3 * max(abs(e0), 1.0)

    def test_energy_dissipates_with_damping(self):
        params = SimulationParameters(
            initial_theta=0.3,
            initial_theta_dot=1.0,
            initial_phi_dot=5.0,
            initial_current=0.0,
            damping=0.05,
            wheel_damping=0.01,
        )
        sim = Simulation(params)

        e0 = sim.compute_energy()

        for _ in range(2000):
            sim.step(0.0)

        e_final = sim.compute_energy()
        assert e_final < e0


class TestVoltageSaturation:
    """Commanded voltage must be clamped to [-max_voltage, max_voltage]."""

    def test_positive_saturation(self):
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            max_voltage=12.0,
        )
        sim = Simulation(params)

        sim.step(100.0)
        telemetry = sim.get_telemetry(ControlMode.manual)
        assert telemetry.voltage == pytest.approx(12.0)

    def test_negative_saturation(self):
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            max_voltage=12.0,
        )
        sim = Simulation(params)

        sim.step(-100.0)
        telemetry = sim.get_telemetry(ControlMode.manual)
        assert telemetry.voltage == pytest.approx(-12.0)

    def test_within_limits_unchanged(self):
        params = SimulationParameters(max_voltage=12.0)
        sim = Simulation(params)

        sim.step(5.0)
        telemetry = sim.get_telemetry(ControlMode.manual)
        assert telemetry.voltage == pytest.approx(5.0)


class TestQualitativeDynamics:
    """Verify the coupled electro-mechanical dynamics respond in expected directions."""

    def test_positive_voltage_spins_wheel_positive(self):
        """Positive voltage builds current, which torques the wheel in positive direction."""
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            damping=0.0,
            wheel_damping=0.0,
            motor_viscous_friction=0.0,
        )
        sim = Simulation(params)

        for _ in range(100):
            sim.step(5.0)

        state = sim.get_state()
        assert state["phi_dot"] > 0.0
        assert state["current"] > 0.0

    def test_positive_voltage_reacts_on_pendulum(self):
        """Positive wheel torque creates a negative reaction on the pendulum body.

        The reaction torque opposes wheel acceleration, so theta decreases
        (pendulum tips backward from upright).
        """
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            damping=0.0,
            wheel_damping=0.0,
            motor_viscous_friction=0.0,
        )
        sim = Simulation(params)

        for _ in range(100):
            sim.step(5.0)

        state = sim.get_state()
        assert state["theta"] < 0.0

    def test_gravity_tips_pendulum_from_upright(self):
        """With no voltage, a small positive theta should grow (inverted pendulum instability)."""
        params = SimulationParameters(
            initial_theta=0.1,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            damping=0.0,
            wheel_damping=0.0,
            motor_viscous_friction=0.0,
        )
        sim = Simulation(params)

        for _ in range(200):
            sim.step(0.0)

        state = sim.get_state()
        assert abs(state["theta"]) > 0.1

    def test_current_rises_with_voltage_step(self):
        """Current rises toward V/R with electrical time constant tau = L/R.

        Uses weak electromechanical coupling so back-EMF feedback is negligible.
        After 5*tau the current should reach ~99.3% of steady state V/R.
        """
        R = 2.0
        L = 0.01
        V = 4.0
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            motor_resistance=R,
            motor_inductance=L,
            gear_ratio=1.0,
            motor_constant=0.01,
            damping=0.0,
            wheel_damping=0.0,
            motor_viscous_friction=0.0,
            max_voltage=12.0,
        )
        sim = Simulation(params)

        tau = L / R  # 0.005 s = 5 steps
        total_steps = int(5 * tau / params.time_step)  # 25 steps

        for _ in range(total_steps):
            sim.step(V)

        state = sim.get_state()
        steady_state = V / R  # 2.0 A
        assert state["current"] == pytest.approx(steady_state, rel=0.05)


class TestSimulationReset:
    """Verify reset restores all 5 state variables to initial conditions."""

    def test_reset_restores_state(self):
        params = SimulationParameters(
            initial_theta=0.2,
            initial_theta_dot=1.0,
            initial_phi=0.5,
            initial_phi_dot=3.0,
            initial_current=0.7,
        )
        sim = Simulation(params)

        for _ in range(500):
            sim.step(2.0)

        sim.reset()
        state = sim.get_state()
        assert state["theta"] == pytest.approx(0.2)
        assert state["theta_dot"] == pytest.approx(1.0)
        assert state["phi"] == pytest.approx(0.5)
        assert state["phi_dot"] == pytest.approx(3.0)
        assert state["current"] == pytest.approx(0.7)
        assert state["time"] == pytest.approx(0.0)


class TestAngleWrapping:
    """Verify angles are wrapped to (-pi, pi]."""

    def test_theta_wraps(self):
        params = SimulationParameters(
            initial_theta=3.0,
            initial_theta_dot=2.0,
            initial_current=0.0,
            damping=0.0,
            wheel_damping=0.0,
        )
        sim = Simulation(params)

        for _ in range(2000):
            sim.step(0.0)

        state = sim.get_state()
        assert -math.pi < state["theta"] <= math.pi


class TestExtendedTelemetry:
    """Verify extended telemetry fields are populated correctly."""

    def test_telemetry_electrical_fields(self):
        """Verify voltage, current, back_emf, motor_torque, wheel_torque relationships."""
        Kt = 0.05
        N = 10.0
        params = SimulationParameters(
            initial_theta=0.1,
            initial_theta_dot=0.5,
            initial_phi_dot=2.0,
            initial_current=0.3,
            motor_constant=Kt,
            gear_ratio=N,
        )
        sim = Simulation(params)
        sim.step(3.0)
        telemetry = sim.get_telemetry(ControlMode.manual)

        assert telemetry.voltage == pytest.approx(3.0)
        assert telemetry.current != 0.0
        # back_emf = Ke * N * phi_dot
        assert telemetry.back_emf == pytest.approx(Kt * N * telemetry.phi_dot)
        # motor_torque = Kt * i_a
        assert telemetry.motor_torque == pytest.approx(Kt * telemetry.current)
        # wheel_torque = N * Kt * i_a
        assert telemetry.wheel_torque == pytest.approx(N * Kt * telemetry.current)

    def test_telemetry_has_accelerations(self):
        params = SimulationParameters(
            initial_theta=0.1,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
        )
        sim = Simulation(params)
        sim.step(0.0)
        telemetry = sim.get_telemetry(ControlMode.none)
        assert telemetry.theta_ddot != 0.0

    def test_telemetry_energy_components(self):
        params = SimulationParameters(
            initial_theta=0.3,
            initial_theta_dot=1.0,
            initial_phi_dot=2.0,
            initial_current=0.0,
        )
        sim = Simulation(params)
        sim.step(0.0)
        telemetry = sim.get_telemetry(ControlMode.none)
        assert telemetry.kinetic_energy > 0.0
        assert telemetry.potential_energy < 0.0
        assert telemetry.energy == pytest.approx(
            telemetry.kinetic_energy + telemetry.potential_energy
        )

    def test_telemetry_angular_momentum(self):
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=1.0,
            initial_phi_dot=5.0,
            initial_current=0.0,
        )
        sim = Simulation(params)
        sim.step(0.0)
        telemetry = sim.get_telemetry(ControlMode.none)
        assert telemetry.angular_momentum != 0.0

    def test_upright_zero_energy(self):
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
        )
        sim = Simulation(params)
        telemetry = sim.get_telemetry(ControlMode.none)
        assert telemetry.energy == pytest.approx(0.0, abs=1e-12)
        assert telemetry.kinetic_energy == pytest.approx(0.0, abs=1e-12)
        assert telemetry.potential_energy == pytest.approx(0.0, abs=1e-12)


class TestDisturbance:
    """Verify voltage disturbance application."""

    def test_voltage_disturbance_changes_state(self):
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            damping=0.0,
            wheel_damping=0.0,
        )
        sim = Simulation(params)
        sim.apply_impulse(5.0, 50)
        state = sim.get_state()
        assert state["phi_dot"] != 0.0
        assert state["current"] != 0.0
        assert state["time"] == pytest.approx(0.05)

    def test_disturbance_respects_voltage_saturation(self):
        params = SimulationParameters(
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=0.0,
            max_voltage=12.0,
        )
        sim = Simulation(params)
        sim.apply_impulse(100.0, 10)
        telemetry = sim.get_telemetry(ControlMode.manual)
        assert telemetry.voltage == pytest.approx(12.0)


class TestGearboxEffect:
    """Verify gearbox correctly reflects motor rotor inertia and scales torque."""

    def test_effective_wheel_inertia_includes_reflected_rotor(self):
        """With gear_ratio=N, effective wheel inertia = I_w + J_m * N²."""
        N = 10.0
        J_m = 1e-5
        wheel_mass = 0.5
        wheel_radius = 0.05
        params = SimulationParameters(
            gear_ratio=N,
            motor_rotor_inertia=J_m,
            wheel_mass=wheel_mass,
            wheel_radius=wheel_radius,
        )
        sim = Simulation(params)

        # Solid cylinder fallback: I_w = 0.5 * m * r²
        I_w = 0.5 * wheel_mass * wheel_radius ** 2
        expected_I_w_eff = I_w + J_m * N ** 2

        # M22 in the inertia matrix equals I_w_eff
        assert sim.inertia_matrix[1, 1] == pytest.approx(expected_I_w_eff)

    def test_wheel_torque_is_geared_motor_torque(self):
        """Wheel torque = N * Kt * i_a; motor torque = Kt * i_a."""
        N = 10.0
        Kt = 0.05
        i_a = 2.0
        params = SimulationParameters(
            gear_ratio=N,
            motor_constant=Kt,
            initial_theta=0.0,
            initial_theta_dot=0.0,
            initial_phi_dot=0.0,
            initial_current=i_a,
        )
        sim = Simulation(params)
        telemetry = sim.get_telemetry(ControlMode.none)

        assert telemetry.motor_torque == pytest.approx(Kt * i_a)
        assert telemetry.wheel_torque == pytest.approx(N * Kt * i_a)