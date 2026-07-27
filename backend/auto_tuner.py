"""Automatic PID gain tuner using coordinate descent optimization.

Runs a background asyncio task that evaluates candidate PID gains by
simulating the pendulum with local Simulation and PIDController instances
and computing the ITAE (Integral of Time-weighted Absolute Error) cost
over a 3-second window. Coordinate descent searches the kp, ki, kd space
iteratively, broadcasting progress and best step-response data over
WebSocket.

The evaluator yields to the event loop periodically to avoid blocking
the async runtime during the compute-intensive simulation loop.
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Awaitable, Callable, Optional

from controller import PIDController
from models import AutoTunerStatus, ControlParameters, SimulationParameters
from simulation import Simulation
from websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuner configuration constants
# ---------------------------------------------------------------------------

_TUNING_DURATION_S: float = 3.0
_MAX_ITERATIONS: int = 10
_STEP_FACTORS: tuple[float, ...] = (0.25, 0.5, 0.75, 1.25, 1.5, 2.0, 3.0, 5.0)
_YIELD_INTERVAL: int = 100
_DECIMATION_FACTOR: int = 10
_FALL_ANGLE: float = math.pi / 2.0
_FALL_PENALTY: float = 1e4
_MIN_GAIN: float = 0.0
_MAX_GAIN: float = 1000.0
_EFFORT_WEIGHT: float = 1e-3
_DEFAULT_INITIAL_ANGLE: float = math.radians(5.0)

# Multi-scenario robustness: test gains across varied initial conditions
_TEST_WHEEL_SPEED: float = 5.0
_TEST_ANGLE_SCALE: float = 2.0

# Oscillation and settling penalties
_OSCILLATION_PENALTY: float = 5.0
_UNSETTLED_ANGLE: float = 0.05
_UNSETTLED_PENALTY: float = 50.0
_WHEEL_SPEED_THRESHOLD: float = 10.0
_WHEEL_SPEED_PENALTY: float = 50.0


class AutoTunerManager:
    """Background PID auto-tuner using coordinate descent optimization.

    Instantiates local :class:`Simulation` and :class:`PIDController`
    objects for each candidate gain evaluation. The cost function is ITAE
    over a 3-second simulation; if the pendulum falls (angle exceeds
    pi/2), the cost is infinity.

    Progress is broadcast via
    :meth:`WebSocketManager.broadcast_tuning_progress` and the best step
    response via :meth:`WebSocketManager.broadcast_tuning_step_response`.

    Parameters
    ----------
    ws_manager : WebSocketManager
        WebSocket manager for broadcasting tuning progress and results.
    sim_params : SimulationParameters
        Base physical simulation parameters (copied internally).
    ctrl_params : ControlParameters
        Base control parameters providing initial PID gains.
    """

    def __init__(
        self,
        ws_manager: WebSocketManager,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
        on_complete: Optional[Callable[[float, float, float], Awaitable[None]]] = None,
    ) -> None:
        self._ws_manager: WebSocketManager = ws_manager
        self._sim_params: SimulationParameters = sim_params.model_copy()
        self._ctrl_params: ControlParameters = ctrl_params.model_copy()
        self._on_complete: Optional[Callable[[float, float, float], Awaitable[None]]] = on_complete
        self._task: Optional[asyncio.Task[None]] = None
        self._status: AutoTunerStatus = AutoTunerStatus.idle
        self._initial_angle: float = _DEFAULT_INITIAL_ANGLE
        self._iteration: int = 0
        self._best_kp: float = ctrl_params.pid_kp
        self._best_ki: float = ctrl_params.pid_ki
        self._best_kd: float = ctrl_params.pid_kd
        self._best_cost: float = float("inf")

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> AutoTunerStatus:
        """Current tuner status."""
        return self._status

    @property
    def iteration(self) -> int:
        """Current iteration number (0 if not started)."""
        return self._iteration

    @property
    def best_gains(self) -> tuple[float, float, float]:
        """Best (kp, ki, kd) found so far."""
        return (self._best_kp, self._best_ki, self._best_kd)

    @property
    def best_cost(self) -> float:
        """Lowest ITAE cost achieved."""
        return self._best_cost

    # ------------------------------------------------------------------
    # Parameter management
    # ------------------------------------------------------------------

    def update_params(
        self,
        sim_params: SimulationParameters,
        ctrl_params: ControlParameters,
    ) -> None:
        """Update base simulation and control parameters.

        Takes effect on the next evaluation; does not interrupt a
        running optimization.
        """
        self._sim_params = sim_params.model_copy()
        self._ctrl_params = ctrl_params.model_copy()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, initial_angle: float = _DEFAULT_INITIAL_ANGLE) -> None:
        """Start the background optimization task.

        Parameters
        ----------
        initial_angle : float
            Initial pendulum angle for each evaluation [rad].
        """
        if self._status == AutoTunerStatus.running:
            logger.warning("Auto-tuner is already running; ignoring start request.")
            return

        self._initial_angle = initial_angle
        self._status = AutoTunerStatus.running
        self._iteration = 0
        self._best_kp = self._ctrl_params.pid_kp
        self._best_ki = self._ctrl_params.pid_ki
        self._best_kd = self._ctrl_params.pid_kd
        self._best_cost = float("inf")
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Cancel the background optimization task."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._status = AutoTunerStatus.idle

    # ------------------------------------------------------------------
    # Internal task
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Entry point for the background task."""
        try:
            await self._coordinate_descent()
            self._status = AutoTunerStatus.complete
            if self._on_complete is not None:
                await self._on_complete(self._best_kp, self._best_ki, self._best_kd)
                if self._best_cost >= _FALL_PENALTY:
                    logger.warning(
                        "Auto-tuner applied best available gains, but system may still be unstable (best cost: %.6e).",
                        self._best_cost,
                    )
        except asyncio.CancelledError:
            self._status = AutoTunerStatus.idle
            raise
        except Exception:
            logger.exception("Auto-tuner optimization failed.")
            self._status = AutoTunerStatus.idle

    async def _coordinate_descent(self) -> None:
        """Run coordinate descent over kp, ki, kd."""
        best_kp = self._best_kp
        best_ki = self._best_ki
        best_kd = self._best_kd
        best_cost, best_times, best_thetas = await self._evaluate(
            best_kp, best_ki, best_kd
        )
        self._best_cost = best_cost

        await self._broadcast_progress(
            0,
            best_kp, best_ki, best_kd, best_cost,
            best_kp, best_ki, best_kd, best_cost,
        )
        if best_times:
            await self._ws_manager.broadcast_tuning_step_response(
                best_times, best_thetas
            )

        for iteration in range(1, _MAX_ITERATIONS + 1):
            self._iteration = iteration
            improved = False

            for param_idx in range(3):
                for factor in _STEP_FACTORS:
                    trial = [best_kp, best_ki, best_kd]
                    trial[param_idx] = max(_MIN_GAIN, trial[param_idx] * factor)
                    if trial[param_idx] > _MAX_GAIN:
                        continue
                    kp, ki, kd = trial
                    cost, times, thetas = await self._evaluate(kp, ki, kd)

                    await self._broadcast_progress(
                        iteration,
                        best_kp, best_ki, best_kd, best_cost,
                        kp, ki, kd, cost,
                    )

                    if cost < best_cost:
                        best_cost = cost
                        best_kp, best_ki, best_kd = kp, ki, kd
                        best_times, best_thetas = times, thetas
                        improved = True
                        self._best_kp = best_kp
                        self._best_ki = best_ki
                        self._best_kd = best_kd
                        self._best_cost = best_cost

                        if best_times:
                            await self._ws_manager.broadcast_tuning_step_response(
                                best_times, best_thetas
                            )

            if not improved:
                logger.info(
                    "Auto-tuner converged at iteration %d. Best cost: %.6e",
                    iteration,
                    best_cost,
                )
                break

        self._status = AutoTunerStatus.complete
        await self._broadcast_progress(
            self._iteration,
            best_kp, best_ki, best_kd, best_cost,
            best_kp, best_ki, best_kd, best_cost,
        )
        if best_times:
            await self._ws_manager.broadcast_tuning_step_response(
                best_times, best_thetas
            )

    async def _broadcast_progress(
        self,
        iteration: int,
        best_kp: float,
        best_ki: float,
        best_kd: float,
        best_cost: float,
        current_kp: float,
        current_ki: float,
        current_kd: float,
        current_cost: float,
    ) -> None:
        """Helper to broadcast a tuning progress frame."""
        await self._ws_manager.broadcast_tuning_progress(
            iteration=iteration,
            status=self._status.value,
            best_kp=best_kp,
            best_ki=best_ki,
            best_kd=best_kd,
            best_cost=best_cost,
            current_kp=current_kp,
            current_ki=current_ki,
            current_kd=current_kd,
            current_cost=current_cost,
        )

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _get_test_scenarios(self) -> list[tuple[float, float, float, float]]:
        """Return initial conditions for multi-scenario robustness evaluation.

        Scenarios test candidate gains across varied starting states to
        ensure stability beyond a single nominal condition:

        - Nominal: configured initial angle, zero wheel speed.
        - Larger angle: ``_TEST_ANGLE_SCALE`` × initial angle (capped
          below the fall threshold) to catch instability at bigger
          perturbations.
        - Non-zero wheel speed: nominal angle with an initial wheel
          velocity to verify robustness against spinning start states.

        Returns
        -------
        list[tuple[float, float, float, float]]
            List of (initial_theta, initial_theta_dot, initial_phi,
            initial_phi_dot).
        """
        angle = self._initial_angle
        larger_angle = min(angle * _TEST_ANGLE_SCALE, _FALL_ANGLE * 0.8)
        return [
            (angle, 0.0, 0.0, 0.0),
            (larger_angle, 0.0, 0.0, 0.0),
            (angle, 0.0, 0.0, _TEST_WHEEL_SPEED),
        ]

    async def _evaluate(
        self,
        kp: float,
        ki: float,
        kd: float,
    ) -> tuple[float, list[float], list[float]]:
        """Evaluate PID gains across multiple scenarios for robustness.

        Runs the pendulum from several initial conditions (nominal angle,
        larger angle, non-zero wheel speed) and sums the per-scenario
        costs. The step-response data returned is from the primary
        (nominal) scenario for visualization.

        Parameters
        ----------
        kp : float
            Proportional gain to evaluate.
        ki : float
            Integral gain to evaluate.
        kd : float
            Derivative gain to evaluate.

        Returns
        -------
        tuple[float, list[float], list[float]]
            (total_cost, decimated_times, decimated_thetas from the
            primary scenario).
        """
        scenarios = self._get_test_scenarios()
        total_cost: float = 0.0
        primary_times: list[float] = []
        primary_thetas: list[float] = []

        for idx, (init_theta, init_theta_dot, init_phi, init_phi_dot) in enumerate(scenarios):
            cost, times, thetas = await self._evaluate_single(
                kp, ki, kd,
                init_theta, init_theta_dot, init_phi, init_phi_dot,
            )
            total_cost += cost
            if idx == 0:
                primary_times = times
                primary_thetas = thetas

        return total_cost, primary_times, primary_thetas

    async def _evaluate_single(
        self,
        kp: float,
        ki: float,
        kd: float,
        init_theta: float,
        init_theta_dot: float,
        init_phi: float,
        init_phi_dot: float,
    ) -> tuple[float, list[float], list[float]]:
        """Evaluate PID gains for a single initial condition.

        Computes ITAE + effort cost over a 3-second simulation, plus
        penalties for oscillation (excess zero crossings of theta) and
        unsettled end state (residual angle or wheel speed). One zero
        crossing is allowed for free (the expected return to upright).

        Parameters
        ----------
        kp : float
            Proportional gain to evaluate.
        ki : float
            Integral gain to evaluate.
        kd : float
            Derivative gain to evaluate.
        init_theta : float
            Initial pendulum angle [rad].
        init_theta_dot : float
            Initial pendulum angular velocity [rad/s].
        init_phi : float
            Initial wheel angle [rad].
        init_phi_dot : float
            Initial wheel angular velocity [rad/s].

        Returns
        -------
        tuple[float, list[float], list[float]]
            (cost, decimated_times, decimated_thetas).
        """
        sim_params = self._sim_params.model_copy(
            update={
                "initial_theta": init_theta,
                "initial_theta_dot": init_theta_dot,
                "initial_phi": init_phi,
                "initial_phi_dot": init_phi_dot,
                "initial_current": 0.0,
            }
        )
        ctrl_params = self._ctrl_params.model_copy(
            update={"pid_kp": kp, "pid_ki": ki, "pid_kd": kd}
        )

        sim = Simulation(sim_params)
        controller = PIDController()
        controller.reset()

        dt = sim_params.time_step
        total_steps = int(_TUNING_DURATION_S / dt)
        cost: float = 0.0
        times: list[float] = []
        thetas: list[float] = []
        zero_crossings: int = 0
        prev_theta: float = init_theta

        for step_idx in range(total_steps):
            state = sim.state_array
            theta = float(state[0])
            theta_dot = float(state[1])
            phi_dot = float(state[3])
            current = float(state[4])
            t = sim.time

            if abs(theta) > _FALL_ANGLE:
                remaining = _TUNING_DURATION_S - t
                penalty = _FALL_PENALTY * (1.0 + remaining / _TUNING_DURATION_S)
                return cost + penalty, times, thetas

            voltage = controller.compute_voltage(
                theta,
                theta_dot,
                phi_dot,
                current,
                sim.cached_energy,
                t,
                sim_params,
                ctrl_params,
            )
            sim.step(voltage)

            if not sim.state_is_finite:
                remaining = _TUNING_DURATION_S - t
                penalty = _FALL_PENALTY * (1.0 + remaining / _TUNING_DURATION_S)
                return cost + penalty, times, thetas

            cost += t * abs(theta) * dt
            cost += _EFFORT_WEIGHT * (voltage ** 2) * dt

            if prev_theta * theta < 0.0:
                zero_crossings += 1
            prev_theta = theta

            if step_idx % _DECIMATION_FACTOR == 0:
                times.append(t)
                thetas.append(theta)

            if step_idx % _YIELD_INTERVAL == 0:
                await asyncio.sleep(0)

        excess_crossings = max(0, zero_crossings - 1)
        cost += _OSCILLATION_PENALTY * excess_crossings

        final_theta = float(sim.state_array[0])
        final_phi_dot = float(sim.state_array[3])
        if abs(final_theta) > _UNSETTLED_ANGLE:
            cost += _UNSETTLED_PENALTY
        if abs(final_phi_dot) > _WHEEL_SPEED_THRESHOLD:
            cost += _WHEEL_SPEED_PENALTY

        return cost, times, thetas