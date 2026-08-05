from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from orbit_control.models import ServiceConfig
from orbit_control.process_manager import ProcessManager, ServiceError


def wait_until(predicate, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.08)
    return False


class ProcessManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.worker = self.root / "worker.py"
        self.worker.write_text(
            "import time\nprint('READY', flush=True)\nwhile True: time.sleep(0.1)\n",
            encoding="utf-8",
        )
        self.manager = ProcessManager(self.root / "data")
        self.service = ServiceConfig(
            name="Worker",
            target=str(self.worker),
            python_executable=sys.executable,
            working_directory=str(self.root),
        )
        self.manager.add_service(self.service)

    def tearDown(self) -> None:
        try:
            if self.manager.is_running(self.service.id):
                self.manager.stop(self.service.id, timeout=2)
        finally:
            self.manager.close()
            self.temp.cleanup()

    def test_lifecycle_and_logs(self) -> None:
        self.manager.start(self.service.id)
        self.assertTrue(wait_until(lambda: self.manager.snapshot(self.service.id).status == "running"))
        self.assertTrue(wait_until(lambda: "READY" in self.manager.tail_service_log(self.service.id)))

        try:
            self.manager.pause(self.service.id)
        except ServiceError as exc:
            # Some CI containers intentionally hide child PIDs from psutil.
            self.assertIn("não permitiu suspender", str(exc))
        else:
            self.assertEqual(self.manager.snapshot(self.service.id).status, "paused")
            self.manager.resume(self.service.id)
            self.assertEqual(self.manager.snapshot(self.service.id).status, "running")

        self.manager.stop(self.service.id, timeout=2)
        self.assertEqual(self.manager.snapshot(self.service.id).status, "stopped")

    def test_crud_and_bulk(self) -> None:
        updated = ServiceConfig.from_dict(self.service.to_dict())
        updated.description = "Atualizado"
        self.manager.update_service(updated)
        self.assertEqual(self.manager.get_service(updated.id).description, "Atualizado")

        success, errors = self.manager.bulk([updated.id], "remove_service")
        self.assertEqual((success, errors), (1, []))
        self.assertEqual(self.manager.list_services(), [])

    def test_stop_all_services_stops_every_configured_service(self) -> None:
        with patch.object(self.manager, "bulk", return_value=(1, [])) as bulk:
            result = self.manager.stop_all_services()

        self.assertEqual(result, (1, []))
        bulk.assert_called_once_with([self.service.id], "stop")

    def test_reorder_services_is_persisted(self) -> None:
        second = ServiceConfig(
            name="Second",
            target=str(self.worker),
            python_executable=sys.executable,
            working_directory=str(self.root),
        )
        self.manager.add_service(second)
        self.manager.reorder_services([second.id, self.service.id])

        self.assertEqual([item.id for item in self.manager.list_services()], [second.id, self.service.id])
        self.assertEqual([item.position for item in self.manager.list_services()], [0, 1])

        self.manager.close()
        self.manager = ProcessManager(self.root / "data")
        self.assertEqual([item.id for item in self.manager.list_services()], [second.id, self.service.id])

    def test_set_autostart_persists_service_toggle(self) -> None:
        self.assertFalse(self.manager.get_service(self.service.id).autostart)

        self.manager.set_autostart(self.service.id, True)

        self.assertTrue(self.manager.get_service(self.service.id).autostart)
        self.manager.close()
        self.manager = ProcessManager(self.root / "data")
        self.assertTrue(self.manager.get_service(self.service.id).autostart)

    def test_services_backup_exports_and_imports_services(self) -> None:
        backup = self.manager.export_services_backup()
        self.assertEqual(backup["format"], "orbit-control-services")
        self.assertEqual(len(backup["services"]), 1)

        restored = ProcessManager(self.root / "restored-data")
        try:
            added, updated = restored.import_services_backup(backup)

            self.assertEqual((added, updated), (1, 0))
            self.assertEqual(restored.get_service(self.service.id).name, "Worker")

            backup["services"][0]["description"] = "Restaurado"
            added, updated = restored.import_services_backup(backup)

            self.assertEqual((added, updated), (0, 1))
            self.assertEqual(restored.get_service(self.service.id).description, "Restaurado")
        finally:
            restored.close()

    def test_reset_all_data_clears_configs_preferences_and_logs(self) -> None:
        self.manager.storage.save_preferences({"theme": "dark", "compact_mode": True})
        self.manager.storage.service_log_path(self.service.id).write_text("log", encoding="utf-8")
        self.manager.storage.system_log_path.write_text("system", encoding="utf-8")

        self.manager.reset_all_data()

        self.assertEqual(self.manager.list_services(), [])
        self.assertFalse(self.manager.storage.services_path.exists())
        self.assertFalse(self.manager.storage.runtime_path.exists())
        self.assertFalse(self.manager.storage.preferences_path.exists())
        self.assertEqual(list(self.manager.storage.logs_dir.glob("*.log")), [])
        self.assertTrue(self.manager.storage.archive_dir.exists())

    def test_old_services_are_migrated_in_alphabetical_order(self) -> None:
        legacy_data = self.root / "legacy-data"
        legacy_storage = self.manager.storage.__class__(legacy_data)
        legacy_storage.save_services(
            [
                ServiceConfig(name="Zulu", target=str(self.worker)),
                ServiceConfig(name="Alpha", target=str(self.worker)),
            ]
        )

        legacy_manager = ProcessManager(legacy_data)
        try:
            self.assertEqual([item.name for item in legacy_manager.list_services()], ["Alpha", "Zulu"])
            self.assertEqual([item.position for item in legacy_manager.list_services()], [0, 1])
        finally:
            legacy_manager.close()

    def test_reorder_rejects_incomplete_id_list(self) -> None:
        with self.assertRaisesRegex(ServiceError, "ordem dos serviços"):
            self.manager.reorder_services([])

    def test_rejects_missing_python_script(self) -> None:
        bad = ServiceConfig(name="Missing", target=str(self.root / "missing.py"))
        with self.assertRaises(ServiceError):
            self.manager.add_service(bad)

    def test_frozen_app_uses_real_windows_python_launcher(self) -> None:
        def locate(command: str) -> str | None:
            return r"C:\Windows\py.exe" if command in {"py.exe", "py"} else None

        with (
            patch.object(sys, "frozen", True, create=True),
            patch("orbit_control.process_manager.os.name", "nt"),
            patch("orbit_control.process_manager.shutil.which", side_effect=locate),
        ):
            self.assertEqual(self.manager._python_command(), [r"C:\Windows\py.exe", "-3"])

    def test_service_prefers_its_project_virtual_environment(self) -> None:
        project = self.root / "flask-project"
        scripts = project / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        project_python = scripts / "python.exe"
        project_python.write_text("placeholder", encoding="utf-8")
        target = project / "app.py"
        target.write_text("print('flask')\n", encoding="utf-8")
        service = ServiceConfig(name="Flask", target=str(target), working_directory=str(project))

        command = self.manager._build_command(service)

        self.assertEqual(Path(command[0]), project_python.resolve())
        self.assertEqual(command[1:3], ["-u", str(target)])

    def test_explicit_python_overrides_project_virtual_environment(self) -> None:
        project = self.root / "project"
        scripts = project / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        (scripts / "python.exe").write_text("project", encoding="utf-8")
        target = project / "app.py"
        target.write_text("print('demo')\n", encoding="utf-8")
        chosen = self.root / "chosen-python"
        chosen.write_text("manual", encoding="utf-8")
        service = ServiceConfig(
            name="Manual",
            target=str(target),
            python_executable=str(chosen),
        )

        self.assertEqual(self.manager._build_command(service)[0], str(chosen))

    def test_optional_requirements_install_uses_service_python(self) -> None:
        requirements = self.root / "requirements.txt"
        requirements.write_text("", encoding="utf-8")
        updated = ServiceConfig.from_dict(self.service.to_dict())
        updated.install_requirements = True
        self.manager.update_service(updated)

        with patch("orbit_control.process_manager.subprocess.run") as install:
            install.return_value.returncode = 0
            self.manager.start(updated.id)

        command = install.call_args.args[0]
        self.assertEqual(command[:4], [sys.executable, "-m", "pip", "install"])
        self.assertEqual(command[-2:], ["-r", str(requirements.resolve())])
        self.manager.stop(updated.id, timeout=2)

    def test_requirements_install_reports_missing_file(self) -> None:
        updated = ServiceConfig.from_dict(self.service.to_dict())
        updated.install_requirements = True
        self.manager.update_service(updated)

        with self.assertRaisesRegex(ServiceError, "requirements.txt não foi encontrado"):
            self.manager.start(updated.id)

    def test_batch_file_uses_windows_command_processor(self) -> None:
        batch = self.root / "Iniciar Meu App.bat"
        batch.write_text("@echo off\necho READY\n", encoding="utf-8")
        service = ServiceConfig(
            name="Meu BAT",
            target=str(batch),
            kind="batch",
            working_directory=str(self.root),
            arguments='--nome "Meu app"',
        )

        with (
            patch("orbit_control.process_manager.os.name", "nt"),
            patch.dict("orbit_control.process_manager.os.environ", {"COMSPEC": r"C:\Windows\System32\cmd.exe"}),
        ):
            command = self.manager._build_command(service)

        self.assertEqual(
            command,
            [
                r"C:\Windows\System32\cmd.exe",
                "/d",
                "/s",
                "/c",
                "call",
                str(batch),
                "--nome",
                "Meu app",
            ],
        )

    def test_batch_kind_rejects_non_batch_target(self) -> None:
        wrong = ServiceConfig(name="Errado", target=str(self.worker), kind="batch")
        with self.assertRaisesRegex(ServiceError, "arquivo .bat ou .cmd"):
            self.manager.add_service(wrong)

    def test_managed_services_default_to_utf8_output(self) -> None:
        environment = self.manager._service_environment(self.service)

        self.assertEqual(environment["PYTHONUTF8"], "1")
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(environment["PYTHONUNBUFFERED"], "1")

    def test_service_can_explicitly_override_default_encoding(self) -> None:
        service = ServiceConfig.from_dict(self.service.to_dict())
        service.environment = {"PYTHONIOENCODING": "cp1252", "EXAMPLE": "yes"}

        environment = self.manager._service_environment(service)

        self.assertEqual(environment["PYTHONIOENCODING"], "cp1252")
        self.assertEqual(environment["EXAMPLE"], "yes")

    def test_managed_python_can_write_emoji_when_parent_requests_cp1252(self) -> None:
        emoji_worker = self.root / "emoji_worker.py"
        emoji_worker.write_text(
            "import time\nprint('🌾 Colheiteira iniciado', flush=True)\nwhile True: time.sleep(0.1)\n",
            encoding="utf-8",
        )
        service = ServiceConfig(
            name="Colheiteira",
            target=str(emoji_worker),
            python_executable=sys.executable,
            working_directory=str(self.root),
        )
        self.manager.add_service(service)

        try:
            with patch.dict("orbit_control.process_manager.os.environ", {"PYTHONIOENCODING": "cp1252"}):
                self.manager.start(service.id)

            self.assertTrue(wait_until(lambda: "🌾 Colheiteira iniciado" in self.manager.tail_service_log(service.id)))
            self.assertNotIn("UnicodeEncodeError", self.manager.tail_service_log(service.id))
        finally:
            if self.manager.is_running(service.id):
                self.manager.stop(service.id, timeout=2)

    def _node_service(self, manager: str = "pnpm", command: str = "dev") -> ServiceConfig:
        project = self.root / "painel-node"
        project.mkdir(exist_ok=True)
        (project / "package.json").write_text(
            json.dumps({"scripts": {"dev": "vite", "start": "node server.js"}}),
            encoding="utf-8",
        )
        return ServiceConfig(
            name="Painel Node",
            target=str(project),
            kind="node",
            working_directory=str(project),
            package_manager=manager,  # type: ignore[arg-type]
            package_command=command,
        )

    def test_node_service_builds_pnpm_script_command(self) -> None:
        service = self._node_service()
        with patch("orbit_control.process_manager.shutil.which", return_value="/usr/local/bin/pnpm"):
            command = self.manager._build_command(service)
        self.assertEqual(command, ["/usr/local/bin/pnpm", "dev"])

    def test_node_service_accepts_full_npm_command(self) -> None:
        service = self._node_service(manager="npm", command="npm run dev")
        service.arguments = "-- --host 127.0.0.1"
        with patch("orbit_control.process_manager.shutil.which", return_value="/usr/local/bin/npm"):
            command = self.manager._build_command(service)
        self.assertEqual(
            command,
            ["/usr/local/bin/npm", "run", "dev", "--", "--host", "127.0.0.1"],
        )

    def test_node_dependency_install_uses_selected_manager(self) -> None:
        service = self._node_service()
        service.install_node_dependencies = True
        service.node_install_command = "install --frozen-lockfile"
        log_path = self.root / "node-install.log"

        with (
            patch.object(
                self.manager,
                "_node_command",
                return_value=["/usr/local/bin/pnpm", "install", "--frozen-lockfile"],
            ),
            patch("orbit_control.process_manager.subprocess.run") as install,
            log_path.open("ab", buffering=0) as log_handle,
        ):
            install.return_value.returncode = 0
            self.manager._install_node_dependencies(service, str(service.working_directory), {}, log_handle)

        self.assertEqual(
            install.call_args.args[0],
            ["/usr/local/bin/pnpm", "install", "--frozen-lockfile"],
        )
        self.assertIn("PNPM OK", log_path.read_text(encoding="utf-8"))

    def test_node_service_requires_valid_package_json(self) -> None:
        project = self.root / "sem-package-json"
        project.mkdir()
        service = ServiceConfig(name="Inválido", target=str(project), kind="node")
        with self.assertRaisesRegex(ServiceError, "package.json não foi encontrado"):
            self.manager.add_service(service)

    def test_windows_package_manager_cmd_is_wrapped_silently(self) -> None:
        command = [r"C:\Program Files\nodejs\pnpm.cmd", "dev"]
        with (
            patch("orbit_control.process_manager.os.name", "nt"),
            patch.dict(
                "orbit_control.process_manager.os.environ",
                {"COMSPEC": r"C:\Windows\System32\cmd.exe"},
            ),
        ):
            wrapped = self.manager._wrap_windows_script(command)
        self.assertEqual(
            wrapped,
            [r"C:\Windows\System32\cmd.exe", "/d", "/s", "/c", "call", *command],
        )


if __name__ == "__main__":
    unittest.main()
