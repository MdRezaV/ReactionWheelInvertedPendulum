# Reaction Wheel Inverted Pendulum

## Project Overview & Tech Stack

Web-based physics simulation of an inverted pendulum stabilized by a reaction wheel driven through a DC motor and gearbox. Python backend owns all computation; React frontend is display-only. **No Electron. No physics in the browser.**

The simulation models the full coupled electro-mechanical system: a 2×2 inertia matrix (pendulum + wheel) and armature circuit dynamics (5-state ODE: θ, θ̇, φ, φ̇, i_a). Controllers output voltage commands; the motor/gearbox physics translates them into wheel torque internally.

- **Backend**: Python 3.11+, FastAPI, Uvicorn, NumPy, SciPy, Pydantic v2, WebSockets, MessagePack
- **Frontend**: React 19, Vite 8, JavaScript (JSX — no TypeScript), Canvas 2D API, Tailwind CSS 4, Radix UI primitives, vazirmatn font
- **Communication**: REST (`/api/simulation/*`) + WebSocket (`/ws/telemetry`), binary MessagePack with delta encoding
- **Testing**: pytest, pytest-asyncio, httpx (ASGI transport)
- **Linting**: oxlint (frontend)
- **Package management**: uv (backend, `uv.lock`), npm (frontend, `package-lock.json`)

## Architecture & Directory Structure

Client-server. Python advances physics via async background loop; React renders telemetry. All WebSocket data is binary MessagePack with batching, delta encoding, and adaptive rate control.

```
backend/
├── main.py               # FastAPI app, REST routes, WebSocket endpoint, SPA serving, MsgpackResponse
├── simulation.py         # 5-state RK5 physics engine: [θ, θ̇, φ, φ̇, i_a], electro-mechanical coupling
├── controller.py         # Controller ABC + No, Manual, PID, LQR, EnergySwingUp, SlidingMode
├── simulation_manager.py # Background loop orchestration, lifecycle, param updates, disturbance handling
├── websocket_manager.py  # Client tracking, batched delta-encoded broadcast, adaptive rate, command parsing
├── auto_tuner.py         # Coordinate-descent PID auto-tuner (ITAE cost, multi-scenario robustness)
├── models.py             # Pydantic v2 schemas, enums, WS command types, telemetry field constants
├── config.py             # Default params, rates, adaptive table, CORS origins, batching constants
├── pyproject.toml        # Project metadata + dependencies
├── requirements.txt      # Pinned deps
├── uv.lock               # uv lockfile
└── tests/                # pytest suite (conftest, test_api, test_simulation, test_models)

frontend/
├── src/
│   ├── main.jsx          # Entry point
│   ├── App.jsx           # Root component, tab layout (simulation / tuning), wires hooks to components
│   ├── components/
│   │   ├── ControlPanel.jsx    # Simulation controls, parameter editing, disturbance config
│   │   ├── PendulumCanvas.jsx  # Animated pendulum + wheel visualization
│   │   ├── SimulationChart.jsx # Time-series angle/velocity chart
│   │   ├── EnergyChart.jsx     # Kinetic/potential/total energy chart
│   │   ├── TorqueChart.jsx     # Motor/wheel torque and voltage chart
│   │   ├── NumericReadout.jsx  # Live numeric state display
│   │   ├── StatusBar.jsx       # Connection status, FPS, bandwidth metrics
│   │   ├── ErrorLog.jsx        # Runtime error display
│   │   ├── TuningTab.jsx       # Auto-tuner UI: progress, gains, step response canvas
│   │   └── TuningChart.jsx     # (Helper for tuning visualization)
│   ├── hooks/
│   │   ├── useSimulationSocket.js   # WS binary decode, delta reconstruction, rolling buffer, tuning state
│   │   ├── useSimulationApi.js      # REST fetch wrapper
│   │   └── usePerformanceMetrics.js # FPS, bytes/sec, msgs/sec from socket metrics ref
│   ├── utils/            # math.js, format.js (toPersianDigits)
│   └── index.css         # Tailwind CSS 4 theme, custom properties, global styles
├── vite.config.js        # Vite plugins (react, tailwindcss), dev proxy: /api→:8000, /ws→ws://:8000
├── package.json
└── .oxlintrc.json
```

**Key module responsibilities:**

- `simulation.py`: Coupled 2×2 inertia matrix dynamics with armature circuit. 5th-order Runge-Kutta (Butcher, 6-stage) integration with pre-allocated buffers. Voltage saturation, angle wrapping, energy computation. `compute_dynamics()` and zero-alloc `_compute_dynamics_into()` for hot path.
- `controller.py`: `Controller` ABC → `compute_voltage(theta, theta_dot, phi_dot, current, energy, time, sim_params, ctrl_params)`. Modes: none, manual, PID (anti-windup), LQR (4-state linearization incl. electrical dynamics, Riccati solve, PID fallback), EnergySwingUp (energy pumping + LQR balance near upright), SlidingMode (boundary-layer SMC). `ControllerManager` dispatches via `match/case`.
- `auto_tuner.py`: `AutoTunerManager` — background asyncio task running coordinate descent over (kp, ki, kd). Evaluates candidates via local `Simulation` + `PIDController` instances across multiple initial-condition scenarios. ITAE + effort + oscillation + settling cost. Broadcasts progress (t=4) and step response (t=5) over WebSocket.
- `simulation_manager.py`: Owns `asyncio.Task` background loop, real-time pacing, catchup-step cap, disturbance application, delegates to `Simulation` + `ControllerManager` + `WebSocketManager` + `AutoTunerManager`.
- `websocket_manager.py`: Zero physics logic. Connection lifecycle, `BroadcastThrottle` (counter-based decimation with adaptive rate table), `TelemetryBatcher` (batch accumulation + delta encoding with deadbands), command parsing via registry dict. Broadcasts typed binary frames: telemetry (t=0), status (t=1), params (t=3), tuning progress (t=4), tuning step response (t=5).

**WebSocket binary protocol (MessagePack):**

| Frame type | `t` value | Direction | Content |
|---|---|---|---|
| Telemetry (full) | 0 | Server→Client | `fields` + batched `data` arrays |
| Telemetry (delta) | 0 | Server→Client | Delta-encoded `[field_idx, value]` pairs |
| Status | 1 | Server→Client | Simulation state, warnings, disturbances |
| Error | 2 | Server→Client | Error message string |
| Params | 3 | Server→Client | Full simulation + control parameters |
| Tuning progress | 4 | Server→Client | Iteration, best/current gains + cost |
| Tuning step response | 5 | Server→Client | Decimated time/theta arrays |
| Command | — | Client→Server | JSON text, parsed via `_COMMAND_REGISTRY` |

## Coding Conventions & Style

### Backend

- `from __future__ import annotations` in every module.
- Full type hints on all function signatures and return types.
- Pydantic **v2** API only: `model_copy()`, `model_validate()`, `model_dump()`, `model_dump_json()`, `Field(...)`, `model_validator`, `field_validator`. Never use v1 `.dict()`, `.copy()`, `.parse_obj()`.
- `match/case` for enum-based dispatch (not if/elif chains).
- Docstrings on all public classes and methods (NumPy-style parameter sections).
- `logging` module (not print). Logger per module: `logger = logging.getLogger(__name__)`.
- Controllers output **voltage** (not torque). Voltage always clamped via `Controller._clamp_voltage(v, max_voltage)` → `np.clip(v, -max_voltage, max_voltage)`.
- Angles wrapped to (-π, π] via `_wrap_angle()`.
- Physical fallbacks computed in `Simulation._compute_effective_quantities()` when nullable params are `None`.
- Pre-allocated NumPy buffers for RK stages (`_k1`–`_k6`, `_tmp`) to avoid per-step allocation.
- Hot-path telemetry via `Simulation.get_telemetry_values()` returning flat `list[float]` (bypasses Pydantic model construction).
- `MsgpackResponse` as default FastAPI response class for REST endpoints.
- WebSocket telemetry is binary MessagePack with batching (`TELEMETRY_BATCH_SIZE=5`) and delta encoding (`DEADBANDS` per field, full frame every `DELTA_FULL_INTERVAL=5` batches).
- Disturbance system: `DisturbanceConfig` with channel (voltage/torque) × waveform (constant/sinusoidal/pulse/sawtooth/gaussian_noise). Applied as external torque or voltage offset in the physics loop.

### Frontend

- Functional components only. No class components.
- No TypeScript. Plain `.jsx` files.
- State via `useState`/`useRef`/`useCallback`. No external state library.
- All visualization via Canvas 2D API + `requestAnimationFrame`. No charting library.
- Rolling telemetry buffer: 600 points max (`MAX_BUFFER_SIZE` in `useSimulationSocket`).
- WebSocket: binary `arraybuffer` frames decoded via `@msgpack/msgpack`. Delta reconstruction from last full frame. Reconnect: 2 s delay on close.
- REST calls through `useSimulationApi` hook (thin `fetch` wrapper).
- Styling: Tailwind CSS 4 via `@tailwindcss/vite` plugin. Custom theme tokens in `index.css` `@theme` block. No external CSS files beyond `index.css`.
- UI primitives: Radix UI (`@radix-ui/react-tabs`, `react-select`, `react-slider`, `react-collapsible`, `react-tooltip`).
- Font: `vazirmatn` (Persian). Set as `--font-sans` and `--font-mono` in theme.
- **All UI text in Persian (Farsi)**. All layouts RTL (`dir="rtl"`). No English labels in user-facing components. Use `toPersianDigits()` for numeric display.
- Tab-based navigation: "شبیه‌سازی" (simulation) and "تنظیم خودکار" (auto-tuning) via Radix Tabs.

### Testing

- `pytest-asyncio` with `asyncio_mode = "auto"`.
- `httpx.AsyncClient` with `ASGITransport` for API tests.
- `starlette.testclient.TestClient` for WebSocket tests.
- Deterministic: no wall-clock dependence; use `step` endpoint to advance physics.