# Reaction Wheel Inverted Pendulum

A web-based physics simulation of an inverted pendulum stabilized by a reaction wheel driven through a DC motor and gearbox. The Python backend owns all computation (5-state ODE integration, control laws, energy calculations); the React frontend is a real-time visualization layer communicating over REST and WebSocket with binary MessagePack encoding.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)
![React](https://img.shields.io/badge/React-19-61DAFB)
![Vite](https://img.shields.io/badge/Vite-8-646CFF)

## Features

- **Full electro-mechanical simulation** — Coupled 2×2 inertia matrix dynamics with armature circuit (5-state ODE: θ, θ̇, φ, φ̇, i_a) integrated via 5th-order Runge-Kutta (Butcher, 6-stage) at a configurable physics rate.
- **Multiple control strategies** — PID, LQR, Energy-Based Swing-Up, Sliding Mode, Manual voltage input, and uncontrolled (None) modes. Controllers output voltage commands; motor/gearbox physics translates them into wheel torque internally.
- **Live telemetry streaming** — Binary MessagePack WebSocket broadcast with batching, delta encoding, adaptive rate control, and counter-based decimation so physics rate and display rate stay decoupled.
- **Interactive controls** — Adjust physical parameters (masses, lengths, inertia, damping, motor limits) and controller gains on the fly.
- **Disturbance injection** — Configurable disturbances (constant, sinusoidal, pulse, sawtooth, Gaussian noise) applied as external torque or voltage offset.
- **PID auto-tuning** — Coordinate-descent auto-tuner with ITAE cost, multi-scenario robustness evaluation, and live progress streaming over WebSocket.
- **Canvas-based visualization** — Pendulum animation, time-series charts, energy plot, and torque history rendered with the Canvas 2D API. No charting libraries.
- **Deterministic stepping** — A `/api/simulation/step` endpoint advances physics by a fixed number of steps for reproducible testing and debugging.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                   React Frontend                       │
│  (Vite 8 · JSX · Canvas 2D · WebSocket client)        │
└──────────────────────┬─────────────────────────────────┘
                       │  REST /api/simulation/*
                       │  WS   /ws/telemetry (binary MsgPack)
┌──────────────────────▼─────────────────────────────────┐
│                  FastAPI Backend                        │
│                                                        │
│  simulation.py          RK5 integrator, 5-state ODE    │
│  controller.py          PID / LQR / SwingUp / SMC /    │
│                         Manual / None                  │
│  simulation_manager.py  Async background loop          │
│  websocket_manager.py   Batched delta-encoded broadcast│
│  auto_tuner.py          Coordinate-descent PID tuner   │
│  models.py              Pydantic v2 schemas            │
│  config.py              Defaults & constants           │
└────────────────────────────────────────────────────────┘
```

The backend advances physics in an `asyncio` background task. Telemetry is broadcast to all connected WebSocket clients as binary MessagePack frames with batching (5 samples per frame), delta encoding with per-field deadbands, and adaptive rate control via a `BroadcastThrottle`.

## Tech Stack

| Layer      | Technology                                      |
|------------|-------------------------------------------------|
| Backend    | Python 3.11+, FastAPI, Uvicorn, NumPy, SciPy    |
| Validation | Pydantic v2                                     |
| Frontend   | React 19, Vite 8, JavaScript (JSX)              |
| Rendering  | Canvas 2D API, `requestAnimationFrame`          |
| Transport  | REST (MessagePack) + WebSocket (binary MsgPack) |
| UI Kit     | Tailwind CSS 4, Radix UI primitives             |
| Testing    | pytest, pytest-asyncio, httpx (ASGI transport)  |
| Linting    | oxlint (frontend)                               |
| Packages   | uv (backend), npm (frontend)                    |

## Prerequisites

- **Python** 3.11 or later
- **Node.js** 20+ and npm
- (Optional) `uv` for fast Python dependency management

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/MdRezaV/ReactionWheelInvertedPendulum.git
cd ReactionWheelInvertedPendulum
```

### 2. Backend setup

**With pip:**

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**With uv (faster):**

```bash
cd backend

# Create a virtual environment and install dependencies in one step
uv venv
uv pip install -r requirements.txt

# Activate the environment
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

Or skip activation entirely and run directly through `uv`:

```bash
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Start the backend server (if using pip or an activated venv):

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 3. Frontend setup

```bash
cd frontend

npm install
```

Start the Vite dev server:

```bash
npm run dev
```

The dev server proxies `/api` and `/ws` requests to the backend on port 8000 (configured in `vite.config.js`). Open the printed URL (typically `http://localhost:5173`) in your browser.

### 4. Production build

```bash
cd frontend
npm run build
```

The backend serves the built assets from `frontend/dist` automatically — no separate static file server is needed.

## Project Structure

```
backend/
├── main.py                 # FastAPI app, routes, WebSocket endpoint, SPA serving, MsgpackResponse
├── simulation.py           # 5-state RK5 physics engine: [θ, θ̇, φ, φ̇, i_a]
├── controller.py           # Controller ABC + PID, LQR, EnergySwingUp, SlidingMode, Manual, None
├── simulation_manager.py   # Background loop orchestration, lifecycle, param updates, disturbances
├── websocket_manager.py    # Client tracking, batched delta-encoded broadcast, command parsing
├── auto_tuner.py           # Coordinate-descent PID auto-tuner (ITAE, multi-scenario)
├── models.py               # Pydantic v2 schemas, enums, WS command types, telemetry constants
├── config.py               # Default params, rates, adaptive table, CORS, batching constants
├── requirements.txt        # Pinned dependencies
└── tests/                  # pytest suite

scripts/
├── optimal_gains.py        # LQR / PID optimal gain computation + plots
├── section1_figures.py     # Report figures (section 1)
└── section2_figures.py     # Report figures (section 2)

frontend/
├── src/
│   ├── App.jsx             # Root component, tab layout (simulation / tuning)
│   ├── components/         # ControlPanel, PendulumCanvas, SimulationChart, EnergyChart,
│   │                       # TorqueChart, NumericReadout, StatusBar, ErrorLog, TuningTab, TuningChart
│   ├── hooks/              # useSimulationSocket, useSimulationApi, usePerformanceMetrics
│   └── utils/              # math.js, format.js (toPersianDigits)
├── vite.config.js          # Dev proxy configuration
└── package.json
```

## WebSocket Protocol

All WebSocket telemetry is binary MessagePack. Frame types:

| Frame type             | `t` value | Direction     | Content                                        |
|------------------------|-----------|---------------|------------------------------------------------|
| Telemetry (full)       | 0         | Server→Client | Field names + batched data arrays              |
| Telemetry (delta)      | 0         | Server→Client | Delta-encoded `[field_idx, value]` pairs       |
| Status                 | 1         | Server→Client | Simulation state, warnings, disturbances       |
| Error                  | 2         | Server→Client | Error message string                           |
| Params                 | 3         | Server→Client | Full simulation + control parameters           |
| Tuning progress        | 4         | Server→Client | Iteration, best/current gains + cost           |
| Tuning step response   | 5         | Server→Client | Decimated time/theta arrays                    |
| Command                | —         | Client→Server | JSON text, parsed via command registry         |

## API Overview

| Method | Endpoint                        | Description                          |
|--------|---------------------------------|--------------------------------------|
| GET    | `/api/simulation/state`         | Current simulation state             |
| GET    | `/api/simulation/params`        | Physical & controller parameters     |
| POST   | `/api/simulation/params`        | Update parameters                    |
| POST   | `/api/simulation/start`         | Start the background physics loop    |
| POST   | `/api/simulation/stop`          | Stop the background physics loop     |
| POST   | `/api/simulation/reset`         | Reset state to initial conditions    |
| POST   | `/api/simulation/step`          | Advance physics by N steps (manual)  |
| POST   | `/api/simulation/controller`    | Switch active control mode           |
| WS     | `/ws/telemetry`                 | Real-time binary telemetry stream    |

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

Tests use `pytest-asyncio` in auto mode and `httpx.AsyncClient` with ASGI transport. No wall-clock dependence — physics is advanced deterministically via the `step` endpoint.

## Optimal Gain Computation

A standalone script in `scripts/` computes optimal LQR gains (via the continuous algebraic Riccati equation) and optimizes PID gains (minimizing ITAE over a full nonlinear 5-state simulation), then saves step-response plots to `latex/results/`.

Run from the project root:

```bash
uv run --with numpy --with scipy --with matplotlib scripts/optimal_gains.py
```

Generated files:

| File | Content |
|------|---------|
| `latex/results/lqr_step_response.png` | LQR angle + voltage step response |
| `latex/results/pid_step_response.png` | Optimized PID angle + voltage step response |
| `latex/results/lqr_vs_pid_comparison.png` | Side-by-side angle and wheel-speed comparison |

## Contributing

Contributions are welcome. To get started:

1. **Fork** the repository and create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Follow the existing conventions:**
   - Backend: full type hints, `from __future__ import annotations`, Pydantic v2 API only, `match/case` for enum dispatch, NumPy-style docstrings, `logging` (not `print`).
   - Frontend: functional components, plain JSX (no TypeScript), Canvas 2D for all visualization, no external charting or state libraries. All UI text in Persian (Farsi), RTL layout.
   - Clamp all voltage outputs to `[-max_voltage, max_voltage]`.
   - Wrap angles to (-π, π] after integration.

3. **Add tests** for any new backend logic. Place them in `backend/tests/` and ensure the full suite passes:
   ```bash
   cd backend && python -m pytest tests/ -v
   ```

4. **Lint the frontend** before committing:
   ```bash
   cd frontend && npx oxlint src/
   ```

5. **Open a Pull Request** against `main` with a clear description of what changed and why. Reference any related issues.

### Adding a New Controller

- Subclass the `Controller` ABC in `controller.py`.
- Implement `reset()` and `compute_voltage(theta, theta_dot, phi_dot, current, energy, time, sim_params, ctrl_params)`.
- Clamp output via `Controller._clamp_voltage(v, max_voltage)`.
- Register the new mode in the `ControlMode` enum (`models.py`) and the `match/case` dispatch in `ControllerManager`.

### Adding a New WebSocket Command

- Define the command schema in `models.py` and add it to the `WSCommand` union.
- Register a handler in `_COMMAND_REGISTRY` in `websocket_manager.py`.
- Keep all physics logic out of `websocket_manager.py`.

## Acknowledgments

Built as an educational tool for exploring nonlinear dynamics, underactuated control, and real-time web visualization.