"""WebSocket connection manager for telemetry broadcasting and command parsing.

Responsibilities:
- Accept and track FastAPI WebSocket client connections.
- Safely remove disconnected clients.
- Broadcast binary (MessagePack) telemetry to all active clients.
- Parse and validate incoming command messages into typed objects.
- Provide a counter-based broadcast throttle so the runtime layer can
  decimate physics-rate updates to the configured telemetry rate.
- Batch multiple telemetry samples per frame to reduce overhead.
- Apply delta encoding to reduce payload size between full frames.
- Adapt telemetry rate based on connected client count.
- Push status events to clients on simulation state changes.

This module does NOT contain physics calculations, controller logic,
simulation state mutation, REST routes, or FastAPI application creation.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Union

import msgpack
from fastapi import WebSocket
from pydantic import ValidationError

from config import (
    ADAPTIVE_RATE_DEFAULT,
    ADAPTIVE_RATE_TABLE,
    DELTA_FULL_INTERVAL,
    TELEMETRY_BATCH_SIZE,
)
from models import (
    DEADBANDS,
    INT_TO_MODE,
    MODE_TO_INT,
    TELEMETRY_FIELD_ORDER,
    ControlMode,
    ControlParameters,
    SimulationParameters,
    StatusEvent,
    TelemetryMessage,
    WSCommand,
    WSStartCommand,
    WSStopCommand,
    WSPauseCommand,
    WSResumeCommand,
    WSResetCommand,
    WSStepCommand,
    WSSetParamCommand,
    WSSetSimulationParamsCommand,
    WSSetControlParamsCommand,
    WSSetControlModeCommand,
    WSSetManualVoltageCommand,
    WSSetSpeedCommand,
    WSSetDisturbanceCommand,
    WSClearDisturbanceCommand,
    WSAutoTunerStartCommand,
    WSAutoTunerStopCommand,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Command type registry
# ---------------------------------------------------------------------------

_COMMAND_REGISTRY: dict[str, type[WSCommand]] = {
    "start": WSStartCommand,
    "stop": WSStopCommand,
    "pause": WSPauseCommand,
    "resume": WSResumeCommand,
    "reset": WSResetCommand,
    "step": WSStepCommand,
    "set_param": WSSetParamCommand,
    "set_simulation_params": WSSetSimulationParamsCommand,
    "set_control_params": WSSetControlParamsCommand,
    "set_control_mode": WSSetControlModeCommand,
    "set_manual_voltage": WSSetManualVoltageCommand,
    "set_speed": WSSetSpeedCommand,
    "set_disturbance": WSSetDisturbanceCommand,
    "clear_disturbance": WSClearDisturbanceCommand,
    "auto_tuner_start": WSAutoTunerStartCommand,
    "auto_tuner_stop": WSAutoTunerStopCommand,
}

_VALID_COMMAND_TYPES: frozenset[str] = frozenset(_COMMAND_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Parse result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    """Successfully parsed and validated WebSocket command."""

    command: WSCommand


@dataclass(frozen=True, slots=True)
class CommandError:
    """Failed command parsing with an informative error message."""

    error: str
    raw_type: Optional[str] = None


ParseResult = Union[ParsedCommand, CommandError]


# ---------------------------------------------------------------------------
# Broadcast throttle
# ---------------------------------------------------------------------------


class BroadcastThrottle:
    """Counter-based throttle for decimating high-rate physics steps.

    The runtime layer calls :meth:`tick` on every physics step. The method
    returns ``True`` only when enough steps have accumulated to match the
    target telemetry rate, signalling that a broadcast should occur.

    Supports adaptive rate adjustment based on connected client count.

    Parameters
    ----------
    physics_rate_hz : int
        Physics simulation loop frequency.
    telemetry_rate_hz : int
        Desired telemetry broadcast frequency.
    """

    def __init__(self, physics_rate_hz: int, telemetry_rate_hz: int) -> None:
        if physics_rate_hz <= 0:
            raise ValueError(f"physics_rate_hz must be positive, got {physics_rate_hz}")
        if telemetry_rate_hz <= 0:
            raise ValueError(f"telemetry_rate_hz must be positive, got {telemetry_rate_hz}")
        if telemetry_rate_hz > physics_rate_hz:
            raise ValueError(
                f"telemetry_rate_hz ({telemetry_rate_hz}) cannot exceed "
                f"physics_rate_hz ({physics_rate_hz})"
            )
        self._physics_rate_hz = physics_rate_hz
        self._base_telemetry_rate_hz = telemetry_rate_hz
        self._interval: int = max(1, physics_rate_hz // telemetry_rate_hz)
        self._counter: int = 0

    @property
    def interval(self) -> int:
        """Number of physics steps between telemetry broadcasts."""
        return self._interval

    def tick(self) -> bool:
        """Advance the counter by one physics step.

        Returns
        -------
        bool
            ``True`` if a telemetry broadcast should be sent this step.
        """
        self._counter += 1
        if self._counter >= self._interval:
            self._counter = 0
            return True
        return False

    def reset(self) -> None:
        """Reset the internal counter (e.g. after simulation reset)."""
        self._counter = 0

    def update_rates(self, physics_rate_hz: int, telemetry_rate_hz: int) -> None:
        """Recompute the interval after rate changes."""
        if physics_rate_hz <= 0 or telemetry_rate_hz <= 0:
            raise ValueError("Rates must be positive")
        if telemetry_rate_hz > physics_rate_hz:
            raise ValueError("telemetry_rate_hz cannot exceed physics_rate_hz")
        self._physics_rate_hz = physics_rate_hz
        self._base_telemetry_rate_hz = telemetry_rate_hz
        self._interval = max(1, physics_rate_hz // telemetry_rate_hz)
        self._counter = 0

    def adapt_rate(self, client_count: int) -> None:
        """Adjust telemetry rate based on connected client count.

        Parameters
        ----------
        client_count : int
            Number of currently connected WebSocket clients.
        """
        effective_hz = ADAPTIVE_RATE_TABLE.get(client_count, ADAPTIVE_RATE_DEFAULT)
        effective_hz = min(effective_hz, self._base_telemetry_rate_hz)
        new_interval = max(1, self._physics_rate_hz // effective_hz)
        if new_interval != self._interval:
            self._interval = new_interval
            self._counter = 0


class TelemetryBatcher:
    """Accumulates telemetry samples and produces batched, delta-encoded frames.

    Collects individual telemetry snapshots into batches of configurable size.
    Every ``full_interval`` batches, a full frame is sent; intermediate batches
    use delta encoding (only fields exceeding deadband thresholds).

    Parameters
    ----------
    batch_size : int
        Number of telemetry samples per WebSocket frame.
    full_interval : int
        Send a full (non-delta) frame every N batches.
    """

    def __init__(
        self,
        batch_size: int = TELEMETRY_BATCH_SIZE,
        full_interval: int = DELTA_FULL_INTERVAL,
    ) -> None:
        self._batch_size = batch_size
        self._full_interval = full_interval
        self._buffer: list[list[float]] = []
        self._batch_count: int = 0
        self._last_sent: Optional[list[float]] = None

    @property
    def is_full(self) -> bool:
        """Whether the buffer has accumulated a full batch."""
        return len(self._buffer) >= self._batch_size

    def add(self, telemetry: TelemetryMessage) -> None:
        """Add a telemetry sample to the current batch buffer."""
        values = self._extract_values(telemetry)
        self._buffer.append(values)

    def add_values(self, values: list[float]) -> None:
        """Add a pre-built flat value list directly (zero Pydantic overhead).

        Parameters
        ----------
        values : list[float]
            17-element list matching TELEMETRY_FIELD_ORDER.
        """
        self._buffer.append(values)

    def flush(self) -> bytes:
        """Produce a msgpack-encoded batch frame and reset the buffer.

        Returns
        -------
        bytes
            MessagePack-encoded binary payload ready for WebSocket send.
        """
        self._batch_count += 1
        is_full_frame = (
            self._batch_count % self._full_interval == 0
            or self._last_sent is None
        )

        if is_full_frame:
            payload = {
                "t": 0,
                "full": True,
                "fields": TELEMETRY_FIELD_ORDER,
                "data": self._buffer,
            }
            self._last_sent = self._buffer[-1] if self._buffer else None
        else:
            delta_data = []
            for sample in self._buffer:
                delta = self._compute_delta(sample)
                delta_data.append(delta)
            payload = {
                "t": 0,
                "full": False,
                "data": delta_data,
            }
            self._last_sent = self._buffer[-1] if self._buffer else None

        self._buffer = []
        return msgpack.packb(payload, use_bin_type=True)

    def reset(self) -> None:
        """Clear buffer and force next flush to be a full frame."""
        self._buffer = []
        self._batch_count = 0
        self._last_sent = None

    def _extract_values(self, telemetry: TelemetryMessage) -> list[float]:
        """Convert a TelemetryMessage to a flat list of floats in field order."""
        mode_int = MODE_TO_INT.get(telemetry.mode.value, 0)
        return [
            telemetry.time,
            telemetry.theta,
            telemetry.theta_dot,
            telemetry.theta_ddot,
            telemetry.phi,
            telemetry.phi_dot,
            telemetry.phi_ddot,
            telemetry.voltage,
            telemetry.current,
            telemetry.back_emf,
            telemetry.motor_torque,
            telemetry.wheel_torque,
            telemetry.energy,
            telemetry.kinetic_energy,
            telemetry.potential_energy,
            telemetry.angular_momentum,
            float(mode_int),
        ]

    def _compute_delta(self, sample: list[float]) -> list[list]:
        """Compute delta pairs [field_index, value] for fields exceeding deadband.

        Time (index 0) is always included. Mode (index 16) is included
        only when changed.
        """
        if self._last_sent is None:
            return [[i, v] for i, v in enumerate(sample)]
        last = self._last_sent
        deadbands = DEADBANDS
        delta: list[list] = [[0, sample[0]]]
        for i in range(1, 17):
            if abs(sample[i] - last[i]) > deadbands[i]:
                delta.append([i, sample[i]])
        return delta


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------


class WebSocketManager:
    """Manages WebSocket client lifecycle, telemetry broadcasting, and command parsing.

    This class is intentionally free of simulation state, physics, or
    controller logic. The runtime layer (e.g. ``main.py``) owns the
    simulation and calls into this manager for I/O concerns only.

    Telemetry is sent as binary MessagePack frames with batching and
    delta encoding for minimal bandwidth and parse overhead.

    Parameters
    ----------
    physics_rate_hz : int
        Physics loop frequency, used to configure the broadcast throttle.
    telemetry_rate_hz : int
        Target telemetry broadcast frequency.
    """

    def __init__(
        self,
        physics_rate_hz: int = 1000,
        telemetry_rate_hz: int = 50,
    ) -> None:
        self._active_connections: list[WebSocket] = []
        self._throttle = BroadcastThrottle(physics_rate_hz, telemetry_rate_hz)
        self._batcher = TelemetryBatcher()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a WebSocket connection and register the client.

        Parameters
        ----------
        websocket : WebSocket
            The FastAPI WebSocket instance to accept and track.
        """
        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info(
            "WebSocket client connected. Active clients: %d", self.client_count
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a client from the active set.

        Safe to call multiple times or with an unregistered socket.

        Parameters
        ----------
        websocket : WebSocket
            The client connection to remove.
        """
        try:
            self._active_connections.remove(websocket)
            logger.info(
                "WebSocket client disconnected. Active clients: %d", self.client_count
            )
        except ValueError:
            pass

    @property
    def client_count(self) -> int:
        """Number of currently registered WebSocket clients."""
        return len(self._active_connections)

    @property
    def has_clients(self) -> bool:
        """Whether at least one client is connected."""
        return len(self._active_connections) > 0

        # ------------------------------------------------------------------
    # Telemetry broadcasting (binary MessagePack, batched, delta-encoded)
    # ------------------------------------------------------------------

    def add_telemetry_sample(self, telemetry: TelemetryMessage) -> None:
        """Add a telemetry sample to the batch buffer.

        Call this when the throttle signals a broadcast is due. The
        batcher accumulates samples until a full batch is ready.

        Parameters
        ----------
        telemetry : TelemetryMessage
            The telemetry snapshot to buffer.
        """
        self._batcher.add(telemetry)

    def add_telemetry_values(self, values: list[float]) -> None:
        """Add a pre-built telemetry value list (fast path, no Pydantic model).

        Parameters
        ----------
        values : list[float]
            17-element list matching TELEMETRY_FIELD_ORDER.
        """
        self._batcher.add_values(values)

    @property
    def batch_ready(self) -> bool:
        """Whether the batch buffer has accumulated enough samples to flush."""
        return self._batcher.is_full

    async def flush_batch(self) -> None:
        """Encode the current batch and send to all connected clients.

        Produces a binary MessagePack frame containing either a full
        or delta-encoded batch of telemetry samples.
        """
        if not self._active_connections:
            self._batcher.reset()
            return

        payload = self._batcher.flush()
        stale: list[WebSocket] = []
        for ws in self._active_connections:
            try:
                await ws.send_bytes(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    async def broadcast_telemetry(self, telemetry: TelemetryMessage) -> None:
        """Legacy single-sample broadcast (used by step endpoint).

        Sends an immediate full-frame binary message for a single sample.

        Parameters
        ----------
        telemetry : TelemetryMessage
            The telemetry snapshot to broadcast immediately.
        """
        if not self._active_connections:
            return

        values = self._batcher._extract_values(telemetry)
        payload = msgpack.packb(
            {"t": 0, "full": True, "fields": TELEMETRY_FIELD_ORDER, "data": [values]},
            use_bin_type=True,
        )
        stale: list[WebSocket] = []
        for ws in self._active_connections:
            try:
                await ws.send_bytes(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    async def broadcast_status(self, event: StatusEvent) -> None:
        """Push a status event to all connected clients as binary msgpack.

        Parameters
        ----------
        event : StatusEvent
            The status event to broadcast.
        """
        if not self._active_connections:
            return

        payload = msgpack.packb(
            {"t": 1, **event.model_dump(exclude={"type"})},
            use_bin_type=True,
        )
        stale: list[WebSocket] = []
        for ws in self._active_connections:
            try:
                await ws.send_bytes(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    async def broadcast_params(self, params_dict: dict) -> None:
        """Push current simulation/control parameters to all connected clients.

        Parameters
        ----------
        params_dict : dict
            Serialized parameters (from ParamsResponse.model_dump()).
        """
        if not self._active_connections:
            return

        payload = msgpack.packb({"t": 3, **params_dict}, use_bin_type=True)
        stale: list[WebSocket] = []
        for ws in self._active_connections:
            try:
                await ws.send_bytes(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    async def broadcast_tuning_progress(
        self,
        iteration: int,
        status: str,
        best_kp: float,
        best_ki: float,
        best_kd: float,
        best_cost: float,
        current_kp: float,
        current_ki: float,
        current_kd: float,
        current_cost: float,
    ) -> None:
        """Push auto-tuner progress to all connected clients as binary msgpack.

        Parameters
        ----------
        iteration : int
            Current coordinate-descent iteration number.
        status : str
            Tuner status string (idle, running, complete).
        best_kp, best_ki, best_kd : float
            Best PID gains found so far.
        best_cost : float
            ITAE cost of the best gains.
        current_kp, current_ki, current_kd : float
            PID gains currently under evaluation.
        current_cost : float
            ITAE cost of the current evaluation.
        """
        if not self._active_connections:
            return

        payload = msgpack.packb(
            {
                "t": 4,
                "iteration": iteration,
                "status": status,
                "best": {
                    "kp": best_kp,
                    "ki": best_ki,
                    "kd": best_kd,
                    "cost": best_cost,
                },
                "current": {
                    "kp": current_kp,
                    "ki": current_ki,
                    "kd": current_kd,
                    "cost": current_cost,
                },
            },
            use_bin_type=True,
        )
        stale: list[WebSocket] = []
        for ws in self._active_connections:
            try:
                await ws.send_bytes(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    async def broadcast_tuning_step_response(
        self,
        time: list[float],
        theta: list[float],
    ) -> None:
        """Push the best-run step response to all connected clients as binary msgpack.

        Parameters
        ----------
        time : list[float]
            Decimated time samples [s].
        theta : list[float]
            Decimated pendulum angle samples [rad].
        """
        if not self._active_connections:
            return

        payload = msgpack.packb(
            {"t": 5, "time": time, "theta": theta},
            use_bin_type=True,
        )
        stale: list[WebSocket] = []
        for ws in self._active_connections:
            try:
                await ws.send_bytes(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    def should_broadcast(self) -> bool:
        """Advance the throttle counter and indicate whether to sample.

        Call this once per physics step. When it returns ``True``, the
        runtime should call :meth:`add_telemetry_sample` with the latest
        telemetry snapshot, then check :attr:`batch_ready` and call
        :meth:`flush_batch` if true.

        Returns
        -------
        bool
            ``True`` if a telemetry sample should be collected this step.
        """
        return self._throttle.tick()

    def reset_throttle(self) -> None:
        """Reset the broadcast throttle counter and batch buffer."""
        self._throttle.reset()
        self._batcher.reset()

    def update_rates(self, physics_rate_hz: int, telemetry_rate_hz: int) -> None:
        """Update throttle rates (e.g. after parameter change).

        Parameters
        ----------
        physics_rate_hz : int
            New physics loop frequency.
        telemetry_rate_hz : int
            New telemetry broadcast frequency.
        """
        self._throttle.update_rates(physics_rate_hz, telemetry_rate_hz)

    def adapt_to_client_count(self) -> None:
        """Adjust telemetry rate based on current client count."""
        self._throttle.adapt_rate(self.client_count)

    # ------------------------------------------------------------------
    # Incoming message parsing
    # ------------------------------------------------------------------

    def parse_command(self, raw: dict) -> ParseResult:
        """Parse and validate a raw JSON dict into a typed command object.

        Parameters
        ----------
        raw : dict
            The decoded JSON payload from a WebSocket text message.

        Returns
        -------
        ParseResult
            Either a :class:`ParsedCommand` wrapping the validated command,
            or a :class:`CommandError` with an informative message.
        """
        if not isinstance(raw, dict):
            return CommandError(
                error="Message payload must be a JSON object.",
                raw_type=None,
            )

        cmd_type = raw.get("type")

        if cmd_type is None:
            return CommandError(
                error="Missing required field 'type' in command payload.",
                raw_type=None,
            )

        if not isinstance(cmd_type, str):
            return CommandError(
                error=f"Field 'type' must be a string, got {type(cmd_type).__name__}.",
                raw_type=str(cmd_type),
            )

        if cmd_type not in _VALID_COMMAND_TYPES:
            valid_list = ", ".join(sorted(_VALID_COMMAND_TYPES))
            return CommandError(
                error=(
                    f"Unknown command type '{cmd_type}'. "
                    f"Valid types: {valid_list}."
                ),
                raw_type=cmd_type,
            )

        command_cls = _COMMAND_REGISTRY[cmd_type]

        try:
            command = command_cls.model_validate(raw)
        except ValidationError as exc:
            field_errors = "; ".join(
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            )
            return CommandError(
                error=f"Validation failed for '{cmd_type}': {field_errors}",
                raw_type=cmd_type,
            )

        return ParsedCommand(command=command)

    async def receive_and_parse(self, websocket: WebSocket) -> Optional[ParseResult]:
        """Receive a single text message from a client and parse it.

        Convenience wrapper that handles JSON decoding errors and returns
        ``None`` if the connection is closed.

        Parameters
        ----------
        websocket : WebSocket
            The client connection to read from.

        Returns
        -------
        Optional[ParseResult]
            Parsed result, or ``None`` if the socket closed.
        """
        try:
            text = await websocket.receive_text()
        except Exception:
            return None

        try:
            raw = json.loads(text)
        except (json.JSONDecodeError, TypeError) as exc:
            return CommandError(
                error=f"Invalid JSON: {exc}",
                raw_type=None,
            )

        return self.parse_command(raw)