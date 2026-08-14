"""Centralized non-UI backend settings for the reaction wheel inverted pendulum."""

# Simulation loop rates
DEFAULT_PHYSICS_RATE_HZ: int = 1000
DEFAULT_TELEMETRY_RATE_HZ: int = 50

# Telemetry batching: number of samples per WebSocket frame
TELEMETRY_BATCH_SIZE: int = 5

# Delta encoding: send a full frame every N batches
DELTA_FULL_INTERVAL: int = 5

# Adaptive telemetry rate thresholds (client_count -> effective Hz)
ADAPTIVE_RATE_TABLE: dict[int, int] = {
    1: 50,
    2: 40,
    3: 40,
    4: 25,
}
ADAPTIVE_RATE_DEFAULT: int = 25

# WebSocket compression: permessage-deflate is negotiated automatically
# by the `websockets` library (uvicorn[standard]). Ensure startup uses:
#   uvicorn main:app --ws-per-message-deflate
WS_PER_MESSAGE_DEFLATE: bool = True

# CORS origins for local Vite development
CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Default simulation parameters (upright-near-balance demo)
# Motor: 12V DC, 330 rpm no-load, 34W, 2.8A, 2.5 kg·cm torque
DEFAULT_SIMULATION_PARAMS: dict = {
    "pendulum_mass": 0.4,
    "pendulum_length": 0.3,
    "pendulum_com_length": None,
    "pendulum_inertia": None,
    "wheel_mass": 0.25,
    "wheel_inner_radius": 0.02,
    "wheel_outer_radius": 0.07,
    "wheel_inertia": None,
    "damping": 0.001,
    "wheel_damping": 0.0005,
    "gravity": 9.81,
    "time_step": 0.001,
    "max_voltage": 12.0,
    "motor_resistance": 1.2,
    "motor_inductance": 0.0005,
    "motor_constant": 0.0876,
    "motor_rotor_inertia": 5e-5,
    "motor_viscous_friction": 0.001,
    "gear_ratio": 4.0,
    "initial_theta": 0.05,
    "initial_theta_dot": 0.0,
    "initial_phi": 0.0,
    "initial_phi_dot": 0.0,
    "initial_current": 0.0,
}

# Default control parameters
DEFAULT_CONTROL_PARAMS: dict = {
    "pid_kp": 50.0,
    "pid_ki": 0.1,
    "pid_kd": 10.0,
    "lqr_q_theta": 100.0,
    "lqr_q_theta_dot": 1.0,
    "lqr_q_phi_dot": 10.0,
    "lqr_q_current": 0.01,
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
    "manual_voltage": 0.0,
    "swing_up_method": "energy",
    "pfl_kp": 5.0,
    "pfl_kd": 2.0,
    "swing_up_max_wheel_speed": 50.0,
    "zero_velocity_swing_gain": 8.0,
    "zero_velocity_impulse_duration": 0.05,
}