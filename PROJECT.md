# Reaction Wheel Inverted Pendulum

## Project Overview & Tech Stack

Web-based physics simulation of an inverted pendulum stabilized by a reaction wheel. Python backend owns all computation; React frontend is display-only. **No Electron. No physics in the browser.**

- **Backend**: Python 3.11+, FastAPI, Uvicorn, NumPy, SciPy, Pydantic v2, WebSockets
- **Frontend**: React 19, Vite 8, JavaScript (JSX — no TypeScript), Canvas 2D API
- **Communication**: REST (`/api/simulation/*`) + WebSocket (`/ws/telemetry`)
- **Testing**: pytest, pytest-asyncio, httpx (ASGI transport)
- **Linting**: oxlint (frontend)

## Architecture & Directory Structure

Client-server. Python advances physics via async background loop; React renders telemetry.

```
backend/
├── main.py              # FastAPI app, routes, WebSocket endpoint, SPA serving
├── simulation.py        # RK4 physics engine, state vector [θ, θ̇, φ, φ̇]
├── controller.py        # Controller ABC + PID, LQR, EnergySwingUp, Manual, None
├── simulation_manager.py # Background loop orchestration, lifecycle, param updates
├── websocket_manager.py  # Client tracking, broadcast throttle, command parsing
├── models.py            # Pydantic v2 schemas, enums, WS command types
├── config.py            # Default params, rates, CORS origins
├── pyproject.toml       # Project metadata + dependencies
├── requirements.txt     # Pinned deps
└── tests/               # pytest suite (conftest, test_api, test_simulation, test_models)

frontend/
├── src/
│   ├── main.jsx         # Entry point
│   ├── App.jsx          # Root component, wires hooks to components
│   ├── components/      # ControlPanel, SimulationChart, PhasePlot, PendulumCanvas, StatusBar
│   ├── hooks/           # useSimulationSocket (WS + buffer), useSimulationApi (REST)
│   └── utils/           # math.js, format.js
├── vite.config.js       # Dev proxy: /api→:8000, /ws→ws://:8000
├── package.json
└── .oxlintrc.json
```

**Key module responsibilities:**
- `simulation.py`: Coupled 2×2 inertia matrix dynamics, RK4 integration, energy computation, torque saturation, angle wrapping.
- `controller.py`: `Controller` ABC → `compute_torque(theta, theta_dot, phi_dot, energy, time, sim_params, ctrl_params)`. `ControllerManager` dispatches via `match/case`.
- `simulation_manager.py`: Owns `asyncio.Task` background loop, real-time pacing, catchup-step cap (20), delegates to `Simulation` + `ControllerManager` + `WebSocketManager`.
- `websocket_manager.py`: Zero physics logic. Connection lifecycle, `BroadcastThrottle` (counter-based decimation), command parsing via registry dict.

## Coding Conventions & Style

### Backend
- `from __future__ import annotations` in every module.
- Full type hints on all function signatures and return types.
- Pydantic **v2** API only: `model_copy()`, `model_validate()`, `model_dump()`, `model_dump_json()`, `Field(...)`, `model_validator`, `field_validator`. Never use v1 `.dict()`, `.copy()`, `.parse_obj()`.
- `match/case` for enum-based dispatch (not if/elif chains).
- Docstrings on all public classes and methods (NumPy-style parameter sections).
- `logging` module (not print). Logger per module: `logger = logging.getLogger(__name__)`.
- Torque always clamped via `np.clip(torque, -max_motor_torque, max_motor_torque)`.
- Angles wrapped to (-π, π] via `_wrap_angle()`.
- Physical fallbacks computed in `Simulation._compute_effective_quantities()` when nullable params are `None`.

### Frontend
- Functional components only. No class components.
- No TypeScript. Plain `.jsx` files.
- State via `useState`/`useRef`/`useCallback`. No external state library.
- All visualization via Canvas 2D API + `requestAnimationFrame`. No charting library.
- Rolling telemetry buffer: 600 points max (`MAX_BUFFER_SIZE` in `useSimulationSocket`).
- WebSocket reconnect: 2 s delay on close.
- REST calls through `useSimulationApi` hook (thin `fetch` wrapper).
- **All UI text in Persian (Farsi)**. All layouts RTL (`dir="rtl"`). No English labels in user-facing components. Use `toPersianDigits()` for numeric display.

### Testing
- `pytest-asyncio` with `asyncio_mode = "auto"`.
- `httpx.AsyncClient` with `ASGITransport` for API tests.
- `starlette.testclient.TestClient` for WebSocket tests.
- Deterministic: no wall-clock dependence; use `step` endpoint to advance physics.