from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orbit_control.models import RuntimeState, ServiceConfig
from orbit_control.storage import JsonStorage


class StorageTests(unittest.TestCase):
    def test_round_trip_services_and_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            storage = JsonStorage(temp)
            service = ServiceConfig(
                name="Demo",
                target="demo.py",
                port=5000,
                install_requirements=True,
                package_manager="pnpm",
                package_command="dev",
                install_node_dependencies=True,
                node_install_command="install --frozen-lockfile",
                position=3,
            )
            runtime = RuntimeState(service_id=service.id, pid=123, desired_running=True)

            storage.save_services([service])
            storage.save_runtime({service.id: runtime})

            loaded_service = storage.load_services()[0]
            loaded_runtime = storage.load_runtime()[service.id]
            self.assertEqual(loaded_service.name, "Demo")
            self.assertEqual(loaded_service.port, 5000)
            self.assertTrue(loaded_service.install_requirements)
            self.assertEqual(loaded_service.package_manager, "pnpm")
            self.assertEqual(loaded_service.package_command, "dev")
            self.assertTrue(loaded_service.install_node_dependencies)
            self.assertEqual(loaded_service.node_install_command, "install --frozen-lockfile")
            self.assertEqual(loaded_service.position, 3)
            self.assertEqual(loaded_runtime.pid, 123)
            self.assertTrue(loaded_runtime.desired_running)

    def test_preferences_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            storage = JsonStorage(temp)
            storage.save_preferences({"theme": "dark", "future_option": True})

            self.assertEqual(storage.load_preferences(), {"theme": "dark", "future_option": True})

    def test_corrupt_json_is_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            storage = JsonStorage(temp)
            storage.services_path.write_text("{invalid", encoding="utf-8")
            self.assertEqual(storage.load_services(), [])
            self.assertTrue(Path(str(storage.services_path) + ".corrupt").exists())


if __name__ == "__main__":
    unittest.main()
