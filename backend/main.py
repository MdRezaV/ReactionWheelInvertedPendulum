"""FastAPI application for the reaction wheel inverted pendulum simulation.

Exposes REST endpoints under /api/simulation for simulation control and a
WebSocket endpoint at /ws/telemetry for real-time data streaming. Optionally
serves the React production build from frontend/dist as a single-page app.

No Electron. No physics in the frontend. All computation stays in Python.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import msgpack
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from config import (
    CORS_ORIGINS,
    DEFAULT_CONTROL_PARAMS,
    DEFAULT_PHYSICS_RATE_HZ,
    DEFAULT_SIMULATION_PARAMS,
    DEFAULT_TELEMETRY_RATE_HZ,
)


# ---------------------------------------------------------------------------
# MessagePack response class (replaces default JSON serialization)
# ---------------------------------------------------------------------------
class MsgpackResponse(Response):
    """Serializes response content as binary MessagePack instead of JSON."""

    media_type = "application/x-msgpack"

    def render(self, content: Any) -> bytes:
        return msgpack.packb(content, use_bin_type=True)
from models import (
    ControlModeRequest,
    ControlParameters,
    DisturbanceConfig,
    ManualVoltageRequest,
    ParamsResponse,
    ParamsUpdateRequest,
    SimulationParameters,
    SpeedRequest,
    StatusResponse,
    StepRequest,
    TelemetryMessage,
)
from simulation_manager import SimulationManager
from websocket_manager import CommandError, ParsedCommand, WebSocketManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application-level singletons
# ---------------------------------------------------------------------------

_sim_params = SimulationParameters(**DEFAULT_SIMULATION_PARAMS)
_ctrl_params = ControlParameters(**DEFAULT_CONTROL_PARAMS)
_ws_manager = WebSocketManager(
    physics_rate_hz=DEFAULT_PHYSICS_RATE_HZ,
    telemetry_rate_hz=DEFAULT_TELEMETRY_RATE_HZ,
)
_sim_manager = SimulationManager(
    sim_params=_sim_params,
    ctrl_params=_ctrl_params,
    ws_manager=_ws_manager,
    physics_rate_hz=DEFAULT_PHYSICS_RATE_HZ,
    telemetry_rate_hz=DEFAULT_TELEMETRY_RATE_HZ,
)


# ---------------------------------------------------------------------------
# Lifespan: start/stop the background simulation loop
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _sim_manager.startup()
    yield
    await _sim_manager.shutdown()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Reaction Wheel Inverted Pendulum",
    version="0.1.0",
    lifespan=lifespan,
    default_response_class=MsgpackResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST API: /api/simulation
# ---------------------------------------------------------------------------


@app.get("/api/simulation/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    base = _sim_manager.get_status()
    return StatusResponse(
        status=base.status,
        time=base.time,
        control_mode=base.control_mode,
        client_count=_ws_manager.client_count,
        warnings=_sim_manager.warnings,
    )


@app.get("/api/simulation/params", response_model=ParamsResponse)
async def get_params() -> ParamsResponse:
    return _sim_manager.get_params()


@app.post("/api/simulation/params", response_model=ParamsResponse)
async def update_params(request: ParamsUpdateRequest) -> ParamsResponse:
    if request.simulation is not None:
        current = _sim_manager.simulation.params
        update_data = request.simulation.model_dump(exclude_unset=True)
        merged = SimulationParameters.model_validate(
            {**current.model_dump(), **update_data}
        )
        _sim_manager.update_sim_params(merged)

    if request.control is not None:
        current = _sim_manager.controller_manager.control_params
        update_data = request.control.model_dump(exclude_unset=True)
        merged = ControlParameters.model_validate(
            {**current.model_dump(), **update_data}
        )
        _sim_manager.update_ctrl_params(merged)

    result = _sim_manager.get_params()
    await _ws_manager.broadcast_params(result.model_dump())
    return result


@app.post("/api/simulation/start", response_model=StatusResponse)
async def start_simulation() -> StatusResponse:
    await _sim_manager.start()
    return await get_status()


@app.post("/api/simulation/stop", response_model=StatusResponse)
async def stop_simulation() -> StatusResponse:
    await _sim_manager.stop()
    return await get_status()


@app.post("/api/simulation/pause", response_model=StatusResponse)
async def pause_simulation() -> StatusResponse:
    await _sim_manager.pause()
    return await get_status()


@app.post("/api/simulation/resume", response_model=StatusResponse)
async def resume_simulation() -> StatusResponse:
    await _sim_manager.resume()
    return await get_status()


@app.post("/api/simulation/reset", response_model=StatusResponse)
async def reset_simulation() -> StatusResponse:
    await _sim_manager.reset()
    return await get_status()


@app.post("/api/simulation/step", response_model=TelemetryMessage)
async def step_simulation(request: StepRequest = StepRequest()) -> TelemetryMessage:
    return await _sim_manager.step(request.steps)


@app.post("/api/simulation/control-mode", response_model=StatusResponse)
async def set_control_mode(request: ControlModeRequest) -> StatusResponse:
    _sim_manager.set_control_mode(request.mode)
    return await get_status()


@app.post("/api/simulation/manual-voltage")
async def set_manual_voltage(request: ManualVoltageRequest) -> dict:
    _sim_manager.set_manual_voltage(request.voltage)
    return {"voltage": request.voltage}


@app.post("/api/simulation/disturbance", response_model=StatusResponse)
async def apply_disturbance(config: DisturbanceConfig) -> StatusResponse:
    await _sim_manager.apply_disturbance(config)
    return await get_status()

@app.post("/api/simulation/clear-disturbance", response_model=StatusResponse)
async def clear_disturbance(id: Optional[str] = None) -> StatusResponse:
    await _sim_manager.clear_disturbance(id)
    return await get_status()


@app.post("/api/simulation/speed", response_model=StatusResponse)
async def set_speed(request: SpeedRequest) -> StatusResponse:
    _sim_manager.set_speed_multiplier(request.multiplier)
    return await get_status()


# ---------------------------------------------------------------------------
# WebSocket: /ws/telemetry
# ---------------------------------------------------------------------------


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket) -> None:
    await _ws_manager.connect(websocket)
    _ws_manager.adapt_to_client_count()
    try:
        # Send an immediate binary snapshot so the client has initial state.
        from models import TELEMETRY_FIELD_ORDER

        telemetry = _sim_manager.last_telemetry
        if telemetry is not None:
            values = telemetry.to_flat_values()
            snapshot = msgpack.packb(
                {"t": 0, "full": True, "fields": TELEMETRY_FIELD_ORDER, "data": [values]},
                use_bin_type=True,
            )
            await websocket.send_bytes(snapshot)
        else:
            status = _sim_manager.get_status()
            status_payload = msgpack.packb(
                {
                    "t": 1,
                    "status": status.status.value,
                    "time": status.time,
                    "control_mode": status.control_mode.value,
                    "client_count": _ws_manager.client_count,
                    "warnings": _sim_manager.warnings,
                    "speed_multiplier": status.speed_multiplier,
                },
                use_bin_type=True,
            )
            await websocket.send_bytes(status_payload)

        # Send current parameters so the client has them without polling.
        params_resp = _sim_manager.get_params()
        params_payload = msgpack.packb(
            {"t": 3, **params_resp.model_dump()},
            use_bin_type=True,
        )
        await websocket.send_bytes(params_payload)

        # Command receive loop. Telemetry streaming is handled by the
        # SimulationManager background loop broadcasting to all clients.
        while True:
            result = await _ws_manager.receive_and_parse(websocket)
            if result is None:
                break
            if isinstance(result, CommandError):
                await websocket.send_bytes(
                    msgpack.packb({"t": 2, "error": result.error}, use_bin_type=True)
                )
            elif isinstance(result, ParsedCommand):
                try:
                    await _sim_manager.handle_ws_command(result.command)
                    cmd_type = result.command.type
                    if cmd_type in (
                        "set_param",
                        "set_simulation_params",
                        "set_control_params",
                        "set_control_mode",
                        "set_speed",
                        "set_disturbance",
                        "clear_disturbance",
                    ):
                        params_resp = _sim_manager.get_params()
                        await _ws_manager.broadcast_params(params_resp.model_dump())
                except (ValueError, KeyError) as exc:
                    await websocket.send_bytes(
                        msgpack.packb({"t": 2, "error": str(exc)}, use_bin_type=True)
                    )
    except WebSocketDisconnect:
        pass
    finally:
        _ws_manager.disconnect(websocket)
        _ws_manager.adapt_to_client_count()


# ---------------------------------------------------------------------------
# Static file serving: React production build (SPA fallback)
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        file_path = (_FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and file_path.is_file()
            and file_path.is_relative_to(_FRONTEND_DIST.resolve())
        ):
            return FileResponse(file_path)
        return FileResponse(_FRONTEND_DIST / "index.html")