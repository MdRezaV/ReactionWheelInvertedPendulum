"""Runtime simulation manager for the reaction wheel inverted pendulum.

Owns the authoritative simulation lifecycle: background physics loop,
telemetry broadcasting, parameter updates, and control mode switching.
Designed to be started/stopped by the FastAPI application lifespan hooks.

This module does NOT implement HTTP route handlers or WebSocket endpoint
registration. Those belong in main.py, which delegates to this manager.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import numpy as np

from auto_tuner import AutoTunerManager
from config import DEFAULT_PHYSICS_RATE_HZ, DEFAULT_TELEMETRY_RATE_HZ
from controller import ControllerManager
from models import (
    ControlMode,
    ControlParameters,
    DisturbanceChannel,
    DisturbanceConfig,
    DisturbanceWaveform,
    MODE_TO_INT,
    ParamsResponse,
    SimulationParameters,
    SimulationStatus,
    StatusEvent,
    StatusResponse,
    TelemetryMessage,
    TuningTarget,
    WSAutoTunerStartCommand,
    WSAutoTunerStopCommand,
    WSClearDisturbanceCommand,
    WSPauseCommand,
    WSResetCommand,
    WSResumeCommand,
    WSSetControlModeCommand,
    WSSetControlParamsCommand,
    WSSetDisturbanceCommand,
    WSSetManualVoltageCommand,
    WSSetParamCommand,
    WSSetSimulationParamsCommand,
    WSSetSpeedCommand,
    WSStartCommand,
    WSStepCommand,
    WSStopCommand,
)
from simulation import Simulation
from websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Maximum physics steps allowed per loop iteration to prevent a death
# spiral when the machine falls behind real-time pacing.
_MAX_CATCHUP_STEPS: int = 20


class SimulationManager:
    """Orchestrates the simulation runtime: physics loop, telemetry, and state.

    Parameters
    ----------
    sim_params : SimulationParameters
        Initial physical and numerical parameters.
    ctrl_params : ControlParameters
        Initial control gains and thresholds.
    ws_manager : WebSocketManager, optional
        Pre-configured WebSocket manager. Created internally if not provided.
    physics_rate_hz : int
        Physics loop target frequency (should equal 1 / time_step).
    telemetry_rate_hz : int
        Telemetry broadcast frequency.
    """

    def __init__(
        self,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
        ws_manager: Optional[WebSocketManager] = None,
        physics_rate_hz: int = DEFAULT_PHYSICS_RATE_HZ,
        telemetry_rate_hz: int = DEFAULT_TELEMETRY_RATE_HZ,
    ) -> None:
        self._sim = Simulation(sim_params)
        self._ctrl_manager = ControllerManager(sim_params, ctrl_params)
        self._ws_manager = ws_manager or WebSocketManager(physics_rate_hz, telemetry_rate_hz)

        self._physics_rate_hz = physics_rate_hz
        self._telemetry_rate_hz = telemetry_rate_hz

        # Authoritative runtime state
        self._status: SimulationStatus = SimulationStatus.stopped
        self._last_voltage: float = 0.0
        self._last_telemetry: Optional[TelemetryMessage] = None
        self._warnings: list[str] = []
        self._speed_multiplier: float = 1.0

        # Disturbance state
        self._active_disturbances: dict[str, DisturbanceConfig] = {}
        self._disturbance_step_counts: dict[str, int] = {}

        # Auto-tuner
        self._auto_tuner = AutoTunerManager(
            ws_manager=self._ws_manager,
            sim_params=sim_params,
            ctrl_params=ctrl_params,
            on_complete=self._on_tuning_complete,
        )

        # Background task management
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        self._last_iteration_time: float = 0.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> SimulationStatus:
        return self._status

    @property
    def simulation(self) -> Simulation:
        """Direct access to the physics simulation (read-only use recommended)."""
        return self._sim

    @property
    def controller_manager(self) -> ControllerManager:
        """Direct access to the controller manager."""
        return self._ctrl_manager

    @property
    def ws_manager(self) -> WebSocketManager:
        """The WebSocket manager used for telemetry broadcasting."""
        return self._ws_manager

    @property
    def last_telemetry(self) -> Optional[TelemetryMessage]:
        """Most recent telemetry snapshot, reconstructed on demand if needed."""
        if self._last_telemetry is None and self._sim.time > 0.0:
            self._last_telemetry = self._sim.get_telemetry(self._ctrl_manager.mode)
        return self._last_telemetry

    @property
    def warnings(self) -> list[str]:
        """Current non-fatal warnings (e.g. LQR gain failures)."""
        return list(self._warnings)

    @property
    def speed_multiplier(self) -> float:
        """Current simulation speed multiplier."""
        return self._speed_multiplier

    @property
    def auto_tuner(self) -> AutoTunerManager:
        """The auto-tuner manager for PID gain optimization."""
        return self._auto_tuner

    # ------------------------------------------------------------------
    # Lifecycle hooks (called by FastAPI lifespan)
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Start the background simulation loop.

        Call this during FastAPI application startup. The loop begins
        in the stopped state; call :meth:`start` to begin advancing physics.
        """
        if self._task is not None and not self._task.done():
            logger.warning("SimulationManager.startup called but task already running.")
            return

        self._shutdown_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="sim-loop")
        logger.info("SimulationManager background loop started.")

    async def shutdown(self) -> None:
        """Cancel the background loop and await clean termination.

        Call this during FastAPI application shutdown.
        """
        self._shutdown_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._auto_tuner.stop()
        self._status = SimulationStatus.stopped
        logger.info("SimulationManager background loop stopped.")

    # ------------------------------------------------------------------
    # Simulation control operations
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Begin advancing the physics simulation in real time."""
        if self._status == SimulationStatus.running:
            return
        self._status = SimulationStatus.running
        self._last_iteration_time = asyncio.get_event_loop().time()
        await self._push_status()
        logger.info("Simulation started.")

    async def stop(self) -> None:
        """Stop the simulation. Physics no longer advances."""
        if self._status == SimulationStatus.stopped:
            return
        self._status = SimulationStatus.stopped
        await self._push_status()
        logger.info("Simulation stopped at t=%.4f s.", self._sim.time)

    async def pause(self) -> None:
        """Pause the simulation. Physics halts but state is preserved."""
        if self._status != SimulationStatus.running:
            return
        self._status = SimulationStatus.paused
        await self._push_status()
        logger.info("Simulation paused at t=%.4f s.", self._sim.time)

    async def resume(self) -> None:
        """Resume a paused simulation."""
        if self._status != SimulationStatus.paused:
            return
        self._status = SimulationStatus.running
        self._last_iteration_time = asyncio.get_event_loop().time()
        await self._push_status()
        logger.info("Simulation resumed at t=%.4f s.", self._sim.time)

    async def reset(self) -> None:
        """Reset simulation state to initial conditions.

        Stops the simulation, resets physics and controllers, and clears
        telemetry history. Does not change parameters or control mode.
        """
        self._status = SimulationStatus.stopped
        self._sim.reset()
        self._ctrl_manager.reset()
        self._ws_manager.reset_throttle()
        self._last_voltage = 0.0
        self._last_telemetry = None
        self._warnings.clear()
        self._active_disturbances.clear()
        self._disturbance_step_counts.clear()
        await self._push_status()
        logger.info("Simulation reset.")

    async def step(self, steps: int = 1) -> TelemetryMessage:
        """Manually advance the simulation by a fixed number of physics steps.

        Works regardless of simulation status (stopped, paused, or running).
        Produces and broadcasts an immediate telemetry snapshot.

        Parameters
        ----------
        steps : int
            Number of fixed time-step physics steps to advance (>= 1).

        Returns
        -------
        TelemetryMessage
            The telemetry snapshot after the final step.
        """
        steps = max(1, steps)
        for _ in range(steps):
            self._physics_step()

        telemetry = self._sim.get_telemetry(self._ctrl_manager.mode)
        self._last_telemetry = telemetry
        await self._ws_manager.broadcast_telemetry(telemetry)
        return telemetry

    # ------------------------------------------------------------------
    # Status and parameter queries
    # ------------------------------------------------------------------

    def get_status(self) -> StatusResponse:
        """Return the current simulation status summary."""
        return StatusResponse(
            status=self._status,
            time=self._sim.time,
            control_mode=self._ctrl_manager.mode,
            speed_multiplier=self._speed_multiplier,
            active_disturbances=list(self._active_disturbances.values()),
        )

    def get_params(self) -> ParamsResponse:
        """Return current simulation and control parameters."""
        return ParamsResponse(
            simulation=self._sim.params,
            control=self._ctrl_manager.control_params,
        )

    # ------------------------------------------------------------------
    # Parameter and mode updates
    # ------------------------------------------------------------------

    def update_sim_params(self, params: SimulationParameters) -> None:
        """Replace simulation parameters with validation.

        Updates the physics model and notifies the controller manager so
        LQR gains are recomputed on the next torque evaluation. If the
        time step changes, the broadcast throttle is reconfigured.

        Raises
        ------
        ValueError
            If the new parameters produce invalid physical quantities.
        """
        old_time_step = self._sim.params.time_step
        self._sim.update_params(params)
        self._ctrl_manager.update_sim_params(params)

        new_time_step = params.time_step
        if new_time_step != old_time_step:
            new_physics_rate = max(1, round(1.0 / new_time_step))
            self._physics_rate_hz = new_physics_rate
            self._ws_manager.update_rates(new_physics_rate, self._telemetry_rate_hz)
            logger.info(
                "Time step changed to %.6f s; physics rate now %d Hz.",
                new_time_step,
                new_physics_rate,
            )

        self._collect_warnings()

    def update_ctrl_params(self, params: ControlParameters) -> None:
        """Replace control parameters with validation.

        LQR gains are recomputed lazily on the next torque computation.
        PID integrators are preserved across gain changes.
        """
        self._ctrl_manager.update_control_params(params)
        self._collect_warnings()

    def set_control_mode(self, mode: ControlMode) -> None:
        """Switch the active control mode, resetting the new controller."""
        self._ctrl_manager.set_mode(mode)
        self._collect_warnings()
        logger.info("Control mode set to '%s'.", mode.value)

    async def _push_status(self) -> None:
        """Broadcast a status event to all connected WebSocket clients."""
        event = StatusEvent(
            status=self._status,
            time=self._sim.time,
            control_mode=self._ctrl_manager.mode,
            client_count=self._ws_manager.client_count,
            warnings=self._warnings,
            speed_multiplier=self._speed_multiplier,
            active_disturbances=list(self._active_disturbances.values()),
        )
        await self._ws_manager.broadcast_status(event)

    def set_manual_voltage(self, voltage: float) -> None:
        """Set the manual voltage command (used when mode is 'manual')."""
        self._ctrl_manager.set_manual_voltage(voltage)

    def set_speed_multiplier(self, multiplier: float) -> None:
        """Set the simulation speed multiplier (0.1 to 10.0)."""
        self._speed_multiplier = max(0.1, min(10.0, multiplier))
        logger.info("Speed multiplier set to %.2f.", self._speed_multiplier)

    async def apply_disturbance(self, config: DisturbanceConfig) -> None:
        """Add a new disturbance to the active set.

        Parameters
        ----------
        config : DisturbanceConfig
            Configuration of the disturbance to apply.
        """
        self._active_disturbances[config.id] = config
        self._disturbance_step_counts[config.id] = 0
        await self._push_status()
        logger.info("Disturbance applied: %s", config.id)

    async def clear_disturbance(self, id: Optional[str] = None) -> None:
        """Clear a specific disturbance by ID, or all if ID is None.

        Parameters
        ----------
        id : Optional[str]
            ID of the disturbance to clear. If None, clears all.
        """
        if id is None:
            self._active_disturbances.clear()
            self._disturbance_step_counts.clear()
        else:
            self._active_disturbances.pop(id, None)
            self._disturbance_step_counts.pop(id, None)
        await self._push_status()
        logger.info("Disturbance cleared: %s", id or "all")

    # ------------------------------------------------------------------
    # WebSocket command dispatch (called from endpoint handler)
    # ------------------------------------------------------------------

    async def handle_ws_command(self, command) -> Optional[TelemetryMessage]:
        """Dispatch a parsed WebSocket command to the appropriate operation.

        Parameters
        ----------
        command : WSCommand
            A validated command object from WebSocketManager.parse_command.

        Returns
        -------
        Optional[TelemetryMessage]
            A telemetry snapshot if the command produced one (e.g. step),
            otherwise None.
        """
        match command:
            case WSStartCommand():
                await self.start()
            case WSStopCommand():
                await self.stop()
            case WSPauseCommand():
                await self.pause()
            case WSResumeCommand():
                await self.resume()
            case WSResetCommand():
                await self.reset()
            case WSStepCommand(steps=n):
                return await self.step(n)
            case WSSetParamCommand(name=name, value=value, scope=scope):
                self._apply_single_param(name, value, scope)
            case WSSetSimulationParamsCommand(params=params):
                self.update_sim_params(params)
            case WSSetControlParamsCommand(params=params):
                self.update_ctrl_params(params)
            case WSSetControlModeCommand(mode=mode):
                self.set_control_mode(mode)
            case WSSetManualVoltageCommand(voltage=voltage):
                self.set_manual_voltage(voltage)
            case WSSetSpeedCommand(multiplier=multiplier):
                self.set_speed_multiplier(multiplier)
            case WSSetDisturbanceCommand(config=config):
                await self.apply_disturbance(config)
            case WSClearDisturbanceCommand(id=id):
                await self.clear_disturbance(id)
            case WSAutoTunerStartCommand(initial_angle=initial_angle, target=target):
                self._auto_tuner.update_params(
                    self._sim.params, self._ctrl_manager.control_params
                )
                await self._auto_tuner.start(initial_angle, target=target)
            case WSAutoTunerStopCommand():
                await self._auto_tuner.stop()

        return None

    # ------------------------------------------------------------------
    # Background physics loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Main background coroutine: advances physics and broadcasts telemetry.

        Runs from startup() until shutdown(). When the simulation status is
        not 'running', the loop sleeps without advancing physics but remains
        alive so the manager stays responsive to external method calls.
        """
        loop = asyncio.get_event_loop()
        try:
            while not self._shutdown_event.is_set():
                iteration_start = loop.time()

                if self._status == SimulationStatus.running:
                    dt = self._sim.time_step

                    # Determine how many physics steps to take based on
                    # elapsed real time since the last iteration, scaled
                    # by the speed multiplier.
                    elapsed = iteration_start - self._last_iteration_time
                    n_steps = int(elapsed * self._speed_multiplier / dt) if dt > 0 else 1
                    n_steps = max(1, min(n_steps, _MAX_CATCHUP_STEPS))

                    should_send = False
                    try:
                        for _ in range(n_steps):
                            self._physics_step()
                            if self._ws_manager.should_broadcast():
                                should_send = True
                    except Exception:
                        logger.exception("Error in physics step; pausing simulation.")
                        self._status = SimulationStatus.paused
                        self._warnings.append(
                            "Simulation paused due to a computation error. "
                            "Check parameters and reset."
                        )
                        should_send = False

                    if should_send and self._ws_manager.has_clients:
                        mode_int = MODE_TO_INT.get(self._ctrl_manager.mode.value, 0)
                        values = self._sim.get_telemetry_values(mode_int)
                        self._ws_manager.add_telemetry_values(values)
                        if self._ws_manager.batch_ready:
                            await self._ws_manager.flush_batch()
                        # Update last_telemetry lazily (only when queried via REST/WS snapshot)
                        self._last_telemetry = None

                self._last_iteration_time = loop.time()

                # Pace the loop: sleep for approximately one physics step.
                # When not running, use a longer idle sleep to reduce CPU.
                if self._status == SimulationStatus.running:
                    sleep_time = self._sim.time_step - (loop.time() - iteration_start)
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    else:
                        await asyncio.sleep(0)
                else:
                    # Idle: check back periodically without burning CPU.
                    await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            logger.debug("Simulation loop cancelled.")
            raise

    def _physics_step(self) -> None:
        """Execute a single physics step: compute voltage, integrate, update state.

        Uses direct state array access to avoid per-step dict allocation.
        Evaluates all active disturbances and sums their contributions.
        """
        s = self._sim.state_array
        voltage = self._ctrl_manager.compute_voltage(
            theta=float(s[0]),
            theta_dot=float(s[1]),
            phi_dot=float(s[3]),
            current=float(s[4]),
            energy=self._sim.cached_energy,
            time=self._sim.time,
        )

        total_dist_voltage = 0.0
        total_dist_torque = 0.0
        t = self._sim.time
        
        to_remove: list[str] = []
        for dist_id, config in self._active_disturbances.items():
            steps = self._disturbance_step_counts[dist_id]
            
            val = 0.0
            wf = config.waveform
            if wf == DisturbanceWaveform.constant:
                val = config.amplitude
            elif wf == DisturbanceWaveform.sinusoidal:
                val = config.amplitude * np.sin(2.0 * np.pi * config.frequency * t)
            elif wf == DisturbanceWaveform.pulse:
                phase = (t * config.frequency) % 1.0
                val = config.amplitude if phase < config.duty_cycle else 0.0
            elif wf == DisturbanceWaveform.sawtooth:
                val = config.amplitude * (2.0 * ((t * config.frequency) % 1.0) - 1.0)
            elif wf == DisturbanceWaveform.gaussian_noise:
                val = np.random.normal(config.mean, config.std)
                
            if config.channel == DisturbanceChannel.voltage:
                total_dist_voltage += val
            else:
                total_dist_torque += val
                
            self._disturbance_step_counts[dist_id] += 1
            if config.duration_steps > 0 and steps >= config.duration_steps:
                to_remove.append(dist_id)
                
        for dist_id in to_remove:
            del self._active_disturbances[dist_id]
            del self._disturbance_step_counts[dist_id]
            
        voltage += total_dist_voltage
        self._sim.step(voltage, external_torque=total_dist_torque)
        self._last_voltage = voltage

        # Guard against numerical blowup: if state contains NaN or Inf,
        # reset to initial conditions to prevent permanent corruption.
        if not self._sim.state_is_finite:
            logger.warning("Non-finite state detected; resetting simulation.")
            self._sim.reset()
            self._ctrl_manager.reset_active()
            self._warnings.append(
                "Numerical instability detected; simulation was auto-reset."
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_single_param(
        self, name: str, value: float, scope: Optional[str]
    ) -> None:
        """Apply a single parameter update by name.

        Determines whether the parameter belongs to simulation or control
        params, constructs an updated model via model_validate (triggering
        full Pydantic validation), and applies it.

        Raises
        ------
        ValueError
            If the parameter name is unrecognized or validation fails.
        """
        sim_fields = set(SimulationParameters.model_fields.keys())
        ctrl_fields = set(ControlParameters.model_fields.keys())

        if scope == "simulation" or (scope is None and name in sim_fields):
            current = self._sim.params
            data = {**current.model_dump(), name: value}
            updated = SimulationParameters.model_validate(data)
            self.update_sim_params(updated)
        elif scope == "control" or (scope is None and name in ctrl_fields):
            current = self._ctrl_manager.control_params
            data = {**current.model_dump(), name: value}
            updated = ControlParameters.model_validate(data)
            self.update_ctrl_params(updated)
        else:
            raise ValueError(
                f"Unknown parameter '{name}' (scope={scope}). "
                f"Valid simulation params: {sorted(sim_fields)}. "
                f"Valid control params: {sorted(ctrl_fields)}."
            )

    async def _on_tuning_complete(self, target: TuningTarget, gains: dict[str, float]) -> None:
        """Callback invoked when auto-tuning completes with best gains.

        Updates the live control parameters with the tuned gains and
        broadcasts the new parameters to all connected clients. The gains
        dictionary is filtered to fields that exist on ControlParameters,
        so any tuning target (PID, LQR, swing-up variants) is applied
        generically.

        Parameters
        ----------
        target : TuningTarget
            Which controller was tuned.
        gains : dict[str, float]
            Tuned gain values keyed by parameter name.
        """
        ctrl_fields = set(ControlParameters.model_fields.keys())
        update = {k: v for k, v in gains.items() if k in ctrl_fields}
        if not update:
            logger.warning(
                "Auto-tuner produced no applicable gains for target '%s'.",
                target.value,
            )
            return
        current = self._ctrl_manager.control_params
        updated = current.model_copy(update=update)
        self.update_ctrl_params(updated)
        await self._ws_manager.broadcast_params(self.get_params().model_dump())
        logger.info(
            "Auto-tuner applied best gains for %s: %s.",
            target.value,
            ", ".join(f"{k}={v:.4f}" for k, v in update.items()),
        )

    def _collect_warnings(self) -> None:
        """Refresh the non-fatal warnings list from subsystems."""
        self._warnings.clear()
        lqr_warning = self._ctrl_manager.lqr_warning
        if lqr_warning:
            self._warnings.append(lqr_warning)