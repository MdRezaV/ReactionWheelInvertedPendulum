"""Shared fixtures for backend test suite.

Provides deterministic test clients with the background simulation loop
managed explicitly so tests never depend on wall-clock timing.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import httpx

from main import app, _sim_manager
from models import ControlParameters, SimulationParameters
from simulation import Simulation


@pytest.fixture
def default_sim_params() -> SimulationParameters:
    """Fresh default simulation parameters."""
    return SimulationParameters()


@pytest.fixture
def default_ctrl_params() -> ControlParameters:
    """Fresh default control parameters."""
    return ControlParameters()


@pytest.fixture
def sim(default_sim_params: SimulationParameters) -> Simulation:
    """A Simulation instance with default parameters."""
    return Simulation(default_sim_params)


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client with managed simulation lifecycle.

    The background loop is started (simulation begins in 'stopped' state,
    so no physics advances) and shut down cleanly after each test.
    State is reset before yielding to ensure test isolation.
    """
    await _sim_manager.startup()
    await _sim_manager.reset()
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            yield c
    finally:
        await _sim_manager.reset()
        await _sim_manager.shutdown()