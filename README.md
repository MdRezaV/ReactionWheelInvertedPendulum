# Reaction Wheel Inverted Pendulum

A web-based physics simulation of an inverted pendulum stabilized by a reaction wheel driven through a DC motor and gearbox. Python backend owns all computation (5-state ODE, control laws, energy); React frontend is a real-time visualization layer over REST + WebSocket with binary MessagePack.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-009688)
![React](https://img.shields.io/badge/React-19-61DAFB)

## Features

- Full electro-mechanical simulation (5-state ODE: θ, θ̇, φ, φ̇, i_a) with RK5 integration
- Multiple controllers: PID, LQR, Energy Swing-Up, Sliding Mode, Manual, None
- Live binary MessagePack telemetry with delta encoding and adaptive rate control
- Configurable disturbance injection (constant, sinusoidal, pulse, sawtooth, Gaussian)
- PID auto-tuning via coordinate descent with ITAE cost
- Canvas-based visualization (pendulum, charts, energy, torque)

## Quick Start

### Backend

```bash
cd backend
uv venv && uv pip install -r requirements.txt
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Or with pip:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api` and `/ws` to the backend on port 8000.

### Production build

```bash
cd frontend && npm run build
```

The backend serves `frontend/dist` automatically.

## Running Tests

```bash
cd backend && python -m pytest tests/ -v
```

## Project Structure

- `backend/` — FastAPI app, physics engine, controllers, WebSocket manager, auto-tuner, tests
- `frontend/` — React app (Canvas 2D, Tailwind CSS 4, Radix UI, Persian RTL)
- `docs/` — Control methods, system mathematics, parameter references
- `scripts/` — Gain computation and figure generation
- `latex/` — Report source and generated results

## Contributing

Contributions welcome. Follow existing conventions (type hints, Pydantic v2, `match/case` dispatch, Canvas 2D rendering, Persian UI text). Add tests for new backend logic and run the full suite before submitting.