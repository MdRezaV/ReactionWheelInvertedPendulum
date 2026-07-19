# Reaction Wheel Inverted Pendulum

## Overview

**Reaction Wheel Inverted Pendulum** is a web-based physical system simulation project for modeling, controlling, and visualizing an inverted pendulum stabilized by a reaction wheel.

The project separates the computation-heavy simulation logic from the user interface:

- **Python** performs all physics calculations, numerical integration, control logic, and simulation state management.
- **React** provides a browser-based dashboard for charts, controls, and visual feedback.
- The system runs entirely as a local web application.
- **Electron is intentionally not used.**

The goal is to create an interactive simulation environment where users can adjust system parameters, start and stop simulations, observe real-time behavior, and analyze the dynamics of the reaction wheel inverted pendulum.

---

## Project Goals

- Simulate the dynamics of an inverted pendulum actuated by a reaction wheel.
- Implement control strategies such as:
  - PID control
  - LQR balancing
  - energy-based swing-up
  - manual tuning
- Stream simulation data from Python to the React frontend in real time.
- Visualize system behavior using:
  - time-series charts
  - phase-space plots
  - angular velocity indicators
  - 2D pendulum animation
- Provide a clean browser-based UI without requiring a desktop wrapper.
- Keep the architecture simple, modular, and easy to extend.

---

## System Architecture

The project uses a client-server architecture.

```text
React Frontend
Browser UI

|
| HTTP REST API for commands
| WebSocket for live telemetry
v

Python Backend
FastAPI Simulation Server

|
| Physics engine
| Numerical integration
| Control algorithms
v

Simulation State
NumPy / SciPy
```

The React frontend does not perform physics calculations. It only sends commands and renders simulation results.

The Python backend owns the simulation state and advances the model over time.

---

## Technology Stack

### Frontend

- React
- Vite
- JavaScript or TypeScript
- WebSocket API
- Charting library:
  - ECharts, Plotly, Chart.js, or Recharts
- Optional 2D visualization:
  - HTML Canvas
  - SVG
  - PixiJS

### Backend

- Python 3.11+
- FastAPI
- Uvicorn
- NumPy
- SciPy
- Pydantic
- WebSockets

### Communication

- REST API for simulation control
- WebSocket for real-time data streaming

---

## Core Features

### Simulation Control

The user can:

- start the simulation
- stop the simulation
- reset the simulation
- pause and resume
- step the simulation manually
- change simulation parameters
- select control mode

### Adjustable Parameters

Example parameters:

- pendulum mass
- pendulum length
- wheel mass
- wheel radius
- wheel inertia
- damping coefficient
- gravity
- simulation time step
- control gains
- initial angle
- initial angular velocity
- maximum motor torque

### Real-Time Visualization

The UI displays:

- pendulum angle over time
- pendulum angular velocity
- reaction wheel speed
- control torque
- energy plot
- phase portrait
- live 2D pendulum animation

### Control Modes

Possible control modes:

- no control
- PID balance
- LQR balance
- energy-based swing-up
- manual torque input

---

## Physical System Description

The system consists of an inverted pendulum with a rotating reaction wheel attached to its end or pivot.

The pendulum is underactuated. The motor applies torque to the reaction wheel, and the equal and opposite reaction torque influences the pendulum body.

The system state can be represented as:

```text
theta       = pendulum angle
theta_dot   = pendulum angular velocity
phi         = reaction wheel angle
phi_dot     = reaction wheel angular velocity
```

The control input is:

```text
u = motor torque applied to the reaction wheel
```

The objective is to drive the pendulum to the upright position and maintain balance by controlling the reaction wheel speed and acceleration.

---

## Simulation Model

The backend should implement the equations of motion for the reaction wheel inverted pendulum.

A general form can be written as:

```text
M(q) * q_ddot + C(q, q_dot) * q_dot = G(q) + B * u
```

Where:

```text
q     = generalized coordinates
q_dot = generalized velocities
M     = inertia matrix
C     = Coriolis and damping terms
G     = gravity terms
B     = input mapping matrix
u     = control torque
```

For implementation, the second-order system can be converted into a first-order system and integrated using a numerical solver such as:

- Euler integration
- semi-implicit Euler
- Runge-Kutta 4
- SciPy solve_ivp

Recommended default:

```text
Runge-Kutta 4
```

---

## Backend Responsibilities

The Python backend is responsible for:

- storing simulation state
- advancing the physics model
- applying control laws
- handling parameter updates
- exposing simulation controls
- streaming telemetry to the frontend
- ensuring stable time stepping
- decimating high-frequency simulation data for UI rendering

The backend should be able to simulate at a higher rate than the UI update rate.

Example:

```text
Physics simulation rate: 500 Hz or 1000 Hz
UI telemetry rate:       30 Hz to 60 Hz
```

---

## Frontend Responsibilities

The React frontend is responsible for:

- displaying simulation controls
- sending commands to the backend
- receiving live telemetry
- rendering charts
- rendering the pendulum animation
- showing current state values
- allowing parameter tuning
- displaying warnings or instability indicators

The frontend should not perform core physics calculations.

---

## API Design

### REST Endpoints

```text
GET  /api/simulation/status
GET  /api/simulation/params
POST /api/simulation/params
POST /api/simulation/start
POST /api/simulation/stop
POST /api/simulation/reset
POST /api/simulation/step
POST /api/simulation/control-mode
```

### WebSocket Endpoint

```text
/ws/telemetry
```

Example telemetry message:

```json
{
  "time": 1.24,
  "theta": 0.021,
  "theta_dot": -0.114,
  "phi_dot": 18.73,
  "torque": 0.42,
  "energy": 1.87,
  "mode": "lqr"
}
```

Example frontend command over WebSocket:

```json
{
  "type": "set_param",
  "name": "kp",
  "value": 12.5
}
```

---

## Suggested Project Structure

```text
reaction-wheel-inverted-pendulum/
├── backend/
│   ├── main.py
│   ├── simulation.py
│   ├── controller.py
│   ├── models.py
│   ├── websocket_manager.py
│   ├── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ControlPanel.jsx
│   │   │   ├── SimulationChart.jsx
│   │   │   ├── PhasePlot.jsx
│   │   │   ├── PendulumCanvas.jsx
│   │   │   ├── StatusBar.jsx
│   │   ├── hooks/
│   │   │   ├── useSimulationSocket.js
│   │   │   ├── useSimulationApi.js
│   │   ├── utils/
│   │   │   ├── math.js
│   │   │   ├── format.js
│
├── README.md
```

---

## Frontend Components

### ControlPanel

Provides controls for:

- start
- stop
- reset
- pause
- step
- control mode selection
- parameter sliders
- numeric inputs

### SimulationChart

Displays time-series data:

- pendulum angle
- pendulum angular velocity
- wheel angular velocity
- control torque

### PhasePlot

Displays:

```text
theta vs theta_dot
```

Useful for analyzing stability and swing-up behavior.

### PendulumCanvas

Renders a simple 2D animation of:

- pendulum arm
- pivot
- reaction wheel
- angular position
- direction of rotation

### StatusBar

Shows:

- simulation running state
- current time
- WebSocket connection state
- selected control mode
- warnings or errors

---

## Backend Modules

### main.py

FastAPI application entrypoint.

Handles:

- API routes
- WebSocket endpoint
- CORS configuration
- server startup and shutdown

### simulation.py

Contains the physics model.

Responsibilities:

- state representation
- numerical integration
- time stepping
- reset logic
- parameter updates

### controller.py

Contains control algorithms.

Possible controllers:

- PIDController
- LQRController
- EnergySwingUpController
- ManualController

### models.py

Pydantic models for:

- simulation parameters
- control parameters
- simulation state
- API request bodies
- API response bodies

### websocket_manager.py

Manages:

- connected WebSocket clients
- broadcasting telemetry
- handling client messages
- throttling update rate

---

## Simulation Loop Design

The backend simulation loop should separate physics stepping from UI broadcasting.

Example:

```text
Physics loop:
    advance simulation by dt
    compute control input
    update state

Broadcast loop:
    every N milliseconds
    send latest state to connected clients
```

This prevents the UI from overwhelming the browser with too many messages.

---

## Real-Time Data Handling

The frontend should keep a rolling buffer of recent data points.

Example:

```text
Keep last 300 to 1000 points
```

This avoids unbounded memory growth.

For high-frequency simulations, the backend should send only downsampled telemetry.

Example:

```text
Physics rate: 1000 Hz
Telemetry rate: 50 Hz
```

---

## Visualization Recommendations

### For scientific charts

Use one of:

- Plotly
- ECharts
- Chart.js

### For high-performance streaming

Recommended:

- ECharts
- uPlot

### For pendulum animation

Use:

- HTML Canvas
- SVG
- PixiJS

For most cases, Canvas is simple and efficient.

---

## Local Development Workflow

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install fastapi uvicorn numpy scipy
uvicorn main:app --reload --port 8000
```

Backend runs at:

```text
http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at:

```text
http://localhost:5173
```

The React app connects to the Python backend using:

```text
http://localhost:8000
ws://localhost:8000/ws/telemetry
```

---

## Production Deployment

The production version can be served as a local web app.

### Build frontend

```bash
cd frontend
npm run build
```

This generates static files in:

```text
frontend/dist
```

### Serve with FastAPI

FastAPI can serve the built React files.

Example behavior:

```text
/              -> React app
/api/*         -> backend API
/ws/telemetry  -> WebSocket endpoint
```

This keeps the entire project as a browser-based application without Electron.

---

## Non-Goals

This project intentionally does not include:

- Electron
- native desktop packaging
- system tray integration
- native OS menus
- bundled desktop executable
- Python execution inside the browser using WASM

The project is designed to run as a local web application with a Python backend and React frontend.

---

## Expected Outcome

At the end of the project, the system should provide:

- a Python simulation engine for a reaction wheel inverted pendulum
- a FastAPI backend exposing control and telemetry interfaces
- a React browser dashboard for live visualization
- real-time charts and animation
- adjustable simulation and control parameters
- a clean architecture that can be extended with new controllers and visualizations

---

## Summary

**Reaction Wheel Inverted Pendulum** is a Python-driven physics simulation with a React-based web interface.

The architecture is:

```text
React UI in browser
+
FastAPI Python backend
+
WebSocket live telemetry
+
NumPy/SciPy physics simulation
```

No Electron is used. The entire system runs as a local web application.