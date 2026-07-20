"""API integration tests using httpx AsyncClient with ASGI transport.

The background simulation loop runs but the simulation stays in 'stopped'
state, so no physics advances unless explicitly triggered via step/start.
All tests are deterministic and independent of wall-clock timing.
"""

from __future__ import annotations

import pytest
import httpx

from models import ControlMode, SimulationStatus


class TestStatusEndpoint:
    """GET /api/simulation/status"""

    async def test_initial_status_stopped(self, client: httpx.AsyncClient):
        resp = await client.get("/api/simulation/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["time"] == pytest.approx(0.0)
        assert data["control_mode"] == "none"
        assert data["client_count"] == 0
        assert isinstance(data["warnings"], list)

    async def test_status_after_start(self, client: httpx.AsyncClient):
        await client.post("/api/simulation/start")
        resp = await client.get("/api/simulation/status")
        data = resp.json()
        assert data["status"] == "running"

    async def test_status_after_pause(self, client: httpx.AsyncClient):
        await client.post("/api/simulation/start")
        await client.post("/api/simulation/pause")
        resp = await client.get("/api/simulation/status")
        data = resp.json()
        assert data["status"] == "paused"

    async def test_status_after_stop(self, client: httpx.AsyncClient):
        await client.post("/api/simulation/start")
        await client.post("/api/simulation/stop")
        resp = await client.get("/api/simulation/status")
        data = resp.json()
        assert data["status"] == "stopped"


class TestParamsEndpoint:
    """GET and POST /api/simulation/params"""

    async def test_get_default_params(self, client: httpx.AsyncClient):
        resp = await client.get("/api/simulation/params")
        assert resp.status_code == 200
        data = resp.json()
        assert "simulation" in data
        assert "control" in data
        assert data["simulation"]["pendulum_mass"] == pytest.approx(1.0)
        assert data["simulation"]["time_step"] == pytest.approx(0.001)
        assert data["simulation"]["max_voltage"] == pytest.approx(12.0)
        assert data["simulation"]["motor_resistance"] == pytest.approx(1.0)
        assert data["control"]["pid_kp"] == pytest.approx(50.0)
        assert data["control"]["manual_voltage"] == pytest.approx(0.0)

    async def test_partial_simulation_param_update(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/params",
            json={"simulation": {"pendulum_mass": 2.0}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulation"]["pendulum_mass"] == pytest.approx(2.0)
        # Other fields unchanged
        assert data["simulation"]["pendulum_length"] == pytest.approx(0.5)

    async def test_partial_control_param_update(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/params",
            json={"control": {"pid_kp": 75.0}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["control"]["pid_kp"] == pytest.approx(75.0)
        assert data["control"]["pid_kd"] == pytest.approx(10.0)

    async def test_invalid_param_rejected(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/params",
            json={"simulation": {"pendulum_mass": -1.0}},
        )
        assert resp.status_code == 422

    async def test_invalid_time_step_rejected(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/params",
            json={"simulation": {"time_step": 0.0}},
        )
        assert resp.status_code == 422

    async def test_com_exceeding_length_rejected(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/params",
            json={"simulation": {"pendulum_com_length": 1.0, "pendulum_length": 0.5}},
        )
        assert resp.status_code == 422


class TestControlModeEndpoint:
    """POST /api/simulation/control-mode"""

    async def test_set_lqr_mode(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/control-mode",
            json={"mode": "lqr"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["control_mode"] == "lqr"

    async def test_set_pid_mode(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/control-mode",
            json={"mode": "pid"},
        )
        assert resp.status_code == 200
        assert resp.json()["control_mode"] == "pid"

    async def test_set_energy_swing_up_mode(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/control-mode",
            json={"mode": "energy_swing_up"},
        )
        assert resp.status_code == 200
        assert resp.json()["control_mode"] == "energy_swing_up"

    async def test_invalid_mode_rejected(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/control-mode",
            json={"mode": "nonexistent"},
        )
        assert resp.status_code == 422


class TestManualVoltageEndpoint:
    """POST /api/simulation/manual-voltage"""

    async def test_set_manual_voltage(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/manual-voltage",
            json={"voltage": 5.0},
        )
        assert resp.status_code == 200
        assert resp.json()["voltage"] == pytest.approx(5.0)

    async def test_set_negative_voltage(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/manual-voltage",
            json={"voltage": -3.5},
        )
        assert resp.status_code == 200
        assert resp.json()["voltage"] == pytest.approx(-3.5)


class TestResetEndpoint:
    """POST /api/simulation/reset"""

    async def test_reset_clears_time(self, client: httpx.AsyncClient):
        # Advance a few steps
        await client.post("/api/simulation/step", json={"steps": 10})
        resp = await client.post("/api/simulation/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["time"] == pytest.approx(0.0)

    async def test_reset_after_start_stops_simulation(self, client: httpx.AsyncClient):
        await client.post("/api/simulation/start")
        resp = await client.post("/api/simulation/reset")
        data = resp.json()
        assert data["status"] == "stopped"


class TestStepEndpoint:
    """POST /api/simulation/step"""

    async def test_single_step_advances_time(self, client: httpx.AsyncClient):
        resp = await client.post("/api/simulation/step", json={"steps": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["time"] == pytest.approx(0.001)
        assert "theta" in data
        assert "theta_dot" in data
        assert "phi_dot" in data
        assert "voltage" in data
        assert "current" in data
        assert "back_emf" in data
        assert "motor_torque" in data
        assert "wheel_torque" in data
        assert "energy" in data
        assert "mode" in data

    async def test_multi_step_advances_time(self, client: httpx.AsyncClient):
        resp = await client.post("/api/simulation/step", json={"steps": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert data["time"] == pytest.approx(0.1)

    async def test_step_default_is_one(self, client: httpx.AsyncClient):
        resp = await client.post("/api/simulation/step")
        assert resp.status_code == 200
        data = resp.json()
        assert data["time"] == pytest.approx(0.001)

    async def test_step_with_lqr_mode(self, client: httpx.AsyncClient):
        await client.post("/api/simulation/control-mode", json={"mode": "lqr"})
        resp = await client.post("/api/simulation/step", json={"steps": 50})
        data = resp.json()
        assert data["mode"] == "lqr"
        # LQR should produce non-zero voltage for non-zero initial theta
        assert data["voltage"] != 0.0

    async def test_step_invalid_steps_rejected(self, client: httpx.AsyncClient):
        resp = await client.post("/api/simulation/step", json={"steps": 0})
        assert resp.status_code == 422


class TestDisturbanceEndpoint:
    """POST /api/simulation/disturbance"""

    async def test_apply_disturbance(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/disturbance",
            json={"voltage": 0.5, "duration_steps": 10},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stopped"

    async def test_disturbance_invalid_duration(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/disturbance",
            json={"voltage": 0.5, "duration_steps": 0},
        )
        assert resp.status_code == 422


class TestSpeedEndpoint:
    """POST /api/simulation/speed"""

    async def test_set_speed(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/speed",
            json={"multiplier": 2.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["speed_multiplier"] == pytest.approx(2.0)

    async def test_speed_in_status(self, client: httpx.AsyncClient):
        await client.post("/api/simulation/speed", json={"multiplier": 3.0})
        resp = await client.get("/api/simulation/status")
        data = resp.json()
        assert data["speed_multiplier"] == pytest.approx(3.0)

    async def test_speed_clamped(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/speed",
            json={"multiplier": 0.01},
        )
        assert resp.status_code == 422

    async def test_set_sliding_mode(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/simulation/control-mode",
            json={"mode": "sliding_mode"},
        )
        assert resp.status_code == 200
        assert resp.json()["control_mode"] == "sliding_mode"


class TestWebSocket:
    """WebSocket endpoint: connection, snapshot, and command validation.

    The WebSocket now uses binary MessagePack frames. Tests use
    receive_bytes + msgpack.unpackb to decode responses.
    """

    async def test_connection_and_initial_snapshot(self, client: httpx.AsyncClient):
        """Connecting should receive an immediate binary state snapshot."""
        import msgpack
        from starlette.testclient import TestClient
        from main import app

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/telemetry") as ws:
                raw = ws.receive_bytes()
                data = msgpack.unpackb(raw, raw=False)
                # Should receive either telemetry (t=0) or status (t=1)
                assert data["t"] in (0, 1)

    async def test_command_validation_invalid_type(self, client: httpx.AsyncClient):
        """Sending an unknown command type should return a binary error."""
        import msgpack
        from starlette.testclient import TestClient
        from main import app

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/telemetry") as ws:
                ws.receive_bytes()
                ws.send_json({"type": "invalid_command"})
                raw = ws.receive_bytes()
                response = msgpack.unpackb(raw, raw=False)
                assert response["t"] == 2
                assert "error" in response

    async def test_command_validation_missing_type(self, client: httpx.AsyncClient):
        """Sending a message without 'type' field should return a binary error."""
        import msgpack
        from starlette.testclient import TestClient
        from main import app

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/telemetry") as ws:
                ws.receive_bytes()
                ws.send_json({"value": 42})
                raw = ws.receive_bytes()
                response = msgpack.unpackb(raw, raw=False)
                assert response["t"] == 2
                assert "error" in response

    async def test_valid_step_command(self, client: httpx.AsyncClient):
        """A valid step command over WebSocket should be accepted."""
        import msgpack
        from starlette.testclient import TestClient
        from main import app

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/telemetry") as ws:
                ws.receive_bytes()
                ws.send_json({"type": "step", "steps": 5})
                # Step produces a telemetry broadcast (binary)
                raw = ws.receive_bytes()
                data = msgpack.unpackb(raw, raw=False)
                assert data["t"] == 0
                # Verify connection is still alive
                ws.send_json({"type": "stop"})

    async def test_valid_set_manual_voltage_command(self, client: httpx.AsyncClient):
        """A valid set_manual_voltage command over WebSocket should be accepted."""
        from starlette.testclient import TestClient
        from main import app

        with TestClient(app) as tc:
            with tc.websocket_connect("/ws/telemetry") as ws:
                ws.receive_bytes()
                ws.send_json({"type": "set_manual_voltage", "voltage": 3.0})
                # No error expected; verify connection alive
                ws.send_json({"type": "stop"})