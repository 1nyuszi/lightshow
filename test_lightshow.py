import asyncio
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch


# Shutdown tests do not need the bulb library or a network connection.
spec = importlib.util.spec_from_file_location("player_under_test", Path(__file__).with_name("lightshow.py"))
player = importlib.util.module_from_spec(spec)
with patch.dict("sys.modules", {"kasa": types.SimpleNamespace(Discover=types.SimpleNamespace())}):
    spec.loader.exec_module(player)


class ShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_turns_off_before_exiting(self):
        device = types.SimpleNamespace(alias="Test bulb", model="Test", update=AsyncMock(),
                                       turn_off=AsyncMock(), disconnect=AsyncMock())
        started = asyncio.Event()

        async def playback(filename, dev):
            started.set()
            await asyncio.sleep(3600)

        with patch.object(player.Discover, "discover_single", AsyncMock(return_value=device), create=True), \
                patch.object(player, "play_script", playback), contextlib.redirect_stdout(io.StringIO()):
            task = asyncio.create_task(player.run_lighting_script("test.csv", "host", "user", "secret"))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        device.turn_off.assert_awaited_once()
        device.disconnect.assert_awaited_once()

    async def test_off_failure_is_reported_without_hiding_cancellation(self):
        device = types.SimpleNamespace(alias="Test bulb", model="Test", update=AsyncMock(),
                                       turn_off=AsyncMock(side_effect=OSError("Bulb unreachable")),
                                       disconnect=AsyncMock())
        output = io.StringIO()
        with patch.object(player.Discover, "discover_single", AsyncMock(return_value=device), create=True), \
                patch.object(player, "play_script", AsyncMock(side_effect=asyncio.CancelledError)), \
                contextlib.redirect_stdout(output):
            with self.assertRaises(asyncio.CancelledError):
                await player.run_lighting_script("test.csv", "host", "user", "secret")
        self.assertIn("Could not turn the light off", output.getvalue())
        device.disconnect.assert_awaited_once()

    async def test_empty_script_also_turns_off(self):
        device = types.SimpleNamespace(alias="Test bulb", model="Test", update=AsyncMock(),
                                       turn_off=AsyncMock(), disconnect=AsyncMock())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.csv"
            path.write_text("# Empty show\n", encoding="utf-8")
            with patch.object(player.Discover, "discover_single", AsyncMock(return_value=device), create=True), \
                    contextlib.redirect_stdout(io.StringIO()):
                await player.run_lighting_script(path, "host", "user", "secret")
        device.turn_off.assert_awaited_once()
        device.disconnect.assert_awaited_once()

    async def test_update_failure_still_disconnects(self):
        device = types.SimpleNamespace(update=AsyncMock(side_effect=OSError("Update failed")),
                                       turn_off=AsyncMock(), disconnect=AsyncMock())
        with patch.object(player.Discover, "discover_single", AsyncMock(return_value=device), create=True), \
                contextlib.redirect_stdout(io.StringIO()):
            await player.run_lighting_script("test.csv", "host", "user", "secret")
        device.disconnect.assert_awaited_once()

    async def test_turn_off_finishes_before_disconnect(self):
        calls = []

        async def turn_off():
            await asyncio.sleep(0)
            calls.append("off")

        async def disconnect():
            calls.append("disconnect")

        device = types.SimpleNamespace(alias="Test", model="Test", update=AsyncMock(),
                                       turn_off=turn_off, disconnect=disconnect)
        with patch.object(player.Discover, "discover_single", AsyncMock(return_value=device), create=True), \
                patch.object(player, "play_script", AsyncMock(side_effect=asyncio.CancelledError)), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(asyncio.CancelledError):
                await player.run_lighting_script("test.csv", "host", "user", "secret")
        self.assertEqual(calls, ["off", "disconnect"])


if __name__ == "__main__":
    unittest.main()
