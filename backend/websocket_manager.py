"""WebSocket connection manager for telemetry broadcasting and command parsing.

Responsibilities:
- Accept and track FastAPI WebSocket client connections.
- Safely remove disconnected clients.
- Broadcast JSON telemetry to all active clients.
- Parse and validate incoming command messages into typed objects.
- Provide a counter-based broadcast throttle so the runtime layer can
  decimate physics-rate updates to the configured telemetry rate.

This module does NOT contain physics calculations, controller logic,
simulation state mutation, REST routes, or FastAPI application creation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Union

from fastapi import WebSocket
from pydantic import ValidationError

from models import (
    ControlMode,
    ControlParameters,
    SimulationParameters,
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
    WSSetManualTorqueCommand,
    WSDisturbanceCommand,
    WSSetSpeedCommand,
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
    "set_manual_torque": WSSetManualTorqueCommand,
    "apply_disturbance": WSDisturbanceCommand,
    "set_speed": WSSetSpeedCommand,
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
        self._interval = max(1, physics_rate_hz // telemetry_rate_hz)
        self._counter = 0


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------


class WebSocketManager:
    """Manages WebSocket client lifecycle, telemetry broadcasting, and command parsing.

    This class is intentionally free of simulation state, physics, or
    controller logic. The runtime layer (e.g. ``main.py``) owns the
    simulation and calls into this manager for I/O concerns only.

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
    # Telemetry broadcasting
    # ------------------------------------------------------------------

    async def broadcast_telemetry(self, telemetry: TelemetryMessage) -> None:
        """Serialize and send a telemetry message to all connected clients.

        Clients that fail to receive (e.g. broken pipe) are removed
        silently. This method is intended to be called only when the
        broadcast throttle signals it is time to send.

        Parameters
        ----------
        telemetry : TelemetryMessage
            The telemetry snapshot to broadcast.
        """
        if not self._active_connections:
            return

        payload = telemetry.model_dump_json()
        stale: list[WebSocket] = []

        for ws in self._active_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    def should_broadcast(self) -> bool:
        """Advance the throttle counter and indicate whether to broadcast.

        Call this once per physics step. When it returns ``True``, the
        runtime should call :meth:`broadcast_telemetry` with the latest
        telemetry snapshot.

        Returns
        -------
        bool
            ``True`` if telemetry should be sent this physics step.
        """
        return self._throttle.tick()

    def reset_throttle(self) -> None:
        """Reset the broadcast throttle counter."""
        self._throttle.reset()

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