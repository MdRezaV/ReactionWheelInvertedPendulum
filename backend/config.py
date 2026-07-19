"""Centralized non-UI backend settings for the reaction wheel inverted pendulum."""

# Simulation loop rates
DEFAULT_PHYSICS_RATE_HZ: int = 1000
DEFAULT_TELEMETRY_RATE_HZ: int = 50

# CORS origins for local Vite development
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Default simulation parameters (upright-near-balance demo)
DEFAULT_SIMULATION_PARAMS: dict = {
    "pendulum_mass": 1.0,
    "pendulum_length": 0.5,
    "pendulum_com_length": None,
    "pendulum_inertia": None,
    "wheel_mass": 0.5,
    "wheel_radius": 0.05,
    "wheel_inertia": None,
    "damping": 0.01,
    "wheel_damping": 0.001,
    "gravity": 9.81,
    "time_step": 0.001,
    "max_motor_torque": 1.0,
    "initial_theta": 0.05,
    "initial_theta_dot": 0.0,
    "initial_phi": 0.0,
    "initial_phi_dot": 0.0,
}

# Default control parameters
DEFAULT_CONTROL_PARAMS: dict = {
    "pid_kp": 50.0,
    "pid_ki": 0.1,
    "pid_kd": 10.0,
    "lqr_q_theta": 100.0,
    "lqr_q_theta_dot": 1.0,
    "lqr_q_phi_dot": 10.0,
    "lqr_q_phi": 0.1,
    "lqr_r": 1.0,
    "energy_swing_up_gain": 1.0,
    "smc_c1": 10.0,
    "smc_c2": 5.0,
    "smc_c3": 1.0,
    "smc_k": 2.0,
    "smc_eta": 0.5,
    "smc_boundary": 0.05,
    "upright_angle_threshold": 0.3,
    "upright_velocity_threshold": 1.0,
    "manual_torque": 0.0,
}