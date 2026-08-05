from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QCheckBox, QLabel

from orbit_control.github_tools import GitHubRepo, summarize_repositories
from orbit_control.models import ServiceConfig
from orbit_control.process_manager import ProcessManager
from orbit_control.ui import DragHandle, GitHubDialog, MainWindow, ServiceDialog


class FakeCloseEvent:
    def __init__(self) -> None:
        self.accepted = False
        self.ignored = False

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.script = self.root / "demo.py"
        self.script.write_text("print('demo')\n", encoding="utf-8")
        self.manager = ProcessManager(self.root / "data")

    def tearDown(self) -> None:
        self.manager.close()
        self.temp.cleanup()

    def test_service_dialog_builds_valid_config(self) -> None:
        dialog = ServiceDialog(None)
        dialog.name_input.setText("Demo desktop")
        dialog.target_input.setText(str(self.script))
        dialog.workdir_input.setText(str(self.root))
        dialog.environment_input.setPlainText("MODE=test")
        dialog.port_input.setValue(5050)
        dialog._save()

        self.assertIsNotNone(dialog.result_config)
        assert dialog.result_config is not None
        self.assertEqual(dialog.result_config.name, "Demo desktop")
        self.assertEqual(dialog.result_config.environment, {"MODE": "test"})
        self.assertEqual(dialog.result_config.port, 5050)
        dialog.deleteLater()

    def test_main_window_renders_service_card_without_browser(self) -> None:
        service = ServiceConfig(name="Demo", target=str(self.script), working_directory=str(self.root))
        self.manager.add_service(service)
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        window._apply_snapshots(self.manager.snapshots())

        self.assertEqual(window.stat_cards["services"].value_label.text(), "1")
        self.assertGreater(window.cards_layout.count(), 0)
        self.assertNotIn("localhost", window.windowTitle().lower())
        self.assertIsNotNone(window.cards_layout.itemAt(0).widget().findChild(DragHandle))

        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_close_event_cancel_keeps_app_open(self) -> None:
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        event = FakeCloseEvent()

        with patch.object(window, "_close_confirmation", return_value="cancel"):
            window.closeEvent(event)

        self.assertTrue(event.ignored)
        self.assertFalse(event.accepted)
        self.assertFalse(window._closing)
        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_close_event_minimize_keeps_services_alive(self) -> None:
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        event = FakeCloseEvent()

        with (
            patch.object(window, "_close_confirmation", return_value="minimize"),
            patch.object(window, "_minimize_to_tray") as minimize,
            patch.object(self.manager, "stop_all_services") as stop_all,
        ):
            window.closeEvent(event)

        self.assertTrue(event.ignored)
        self.assertFalse(event.accepted)
        minimize.assert_called_once()
        stop_all.assert_not_called()
        self.assertFalse(window._closing)
        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_close_event_exit_stops_services_and_accepts(self) -> None:
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        event = FakeCloseEvent()

        with (
            patch.object(window, "_close_confirmation", return_value="exit"),
            patch.object(self.manager, "stop_all_services", return_value=(1, [])) as stop_all,
        ):
            window.closeEvent(event)

        self.assertTrue(event.accepted)
        self.assertFalse(event.ignored)
        self.assertTrue(window._closing)
        stop_all.assert_called_once()
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_projects_folder_button_opens_configured_projects_path(self) -> None:
        window = MainWindow(self.manager)
        window.refresh_timer.stop()

        with (
            patch("orbit_control.ui.PROJECTS_DIR", self.root),
            patch("orbit_control.ui.QDesktopServices.openUrl") as open_url,
        ):
            window.open_projects_folder()

        open_url.assert_called_once()
        self.assertEqual(Path(open_url.call_args.args[0].toLocalFile()), self.root)
        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_backup_buttons_export_and_import_services_json(self) -> None:
        service = ServiceConfig(name="Demo", target=str(self.script), working_directory=str(self.root))
        self.manager.add_service(service)
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        backup_path = self.root / "apps-backup"

        with patch("orbit_control.ui.QFileDialog.getSaveFileName", return_value=(str(backup_path), "")):
            window.export_services_backup()

        backup_json = backup_path.with_suffix(".json")
        self.assertTrue(backup_json.exists())
        payload = json.loads(backup_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "orbit-control-services")
        self.assertEqual(payload["services"][0]["name"], "Demo")

        self.manager.remove_service(service.id)
        with patch("orbit_control.ui.QFileDialog.getOpenFileName", return_value=(str(backup_json), "")):
            window.import_services_backup()

        self.assertEqual(self.manager.get_service(service.id).name, "Demo")
        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_github_panel_button_opens_dialog(self) -> None:
        window = MainWindow(self.manager)
        window.refresh_timer.stop()

        with patch("orbit_control.ui.GitHubDialog") as dialog_class:
            dialog = dialog_class.return_value
            window.open_github_panel()

        dialog_class.assert_called_once_with(window, self.manager)
        dialog.exec.assert_called_once()
        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_github_dialog_saves_clears_and_deletes_token(self) -> None:
        dialog = GitHubDialog(None, self.manager)
        dialog.token_input.setText("ghp_demo")
        dialog._github_login = "annibale"
        dialog.save_token()

        preferences = self.manager.storage.load_preferences()
        self.assertEqual(preferences["github_token"], "ghp_demo")
        self.assertEqual(preferences["github_active_connection"], "annibale")
        self.assertEqual(preferences["github_connections"][0]["login"], "annibale")
        self.assertEqual(preferences["github_connections"][0]["token"], "ghp_demo")
        self.assertEqual(dialog.connection_combo.count(), 2)
        dialog.token_input.clear()
        self.assertEqual(dialog.token_input.text(), "")
        dialog.connection_combo.setCurrentIndex(0)
        dialog.connection_combo.setCurrentIndex(1)
        self.assertEqual(dialog.token_input.text(), "ghp_demo")

        dialog.delete_saved_token()

        self.assertNotIn("github_token", self.manager.storage.load_preferences())
        self.assertEqual(self.manager.storage.load_preferences().get("github_connections"), [])
        self.assertEqual(dialog.account_label.text(), "Desconectado")
        self.assertFalse(dialog.upload_button.isEnabled())
        dialog.deleteLater()

    def test_github_dialog_exports_and_imports_github_settings_json(self) -> None:
        dialog = GitHubDialog(None, self.manager)
        dialog.token_input.setText("ghp_demo")
        dialog._github_login = "annibale"
        dialog.save_token()
        dialog.repo_combo.setEditText("annibale/demo")
        dialog.private_check.setChecked(True)
        settings_path = self.root / "github-settings"

        with patch("orbit_control.ui.QFileDialog.getSaveFileName", return_value=(str(settings_path), "")):
            dialog.export_github_settings()

        settings_json = settings_path.with_suffix(".json")
        payload = json.loads(settings_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "orbit-control-github-settings")
        self.assertEqual(payload["github"]["connections"][0]["login"], "annibale")
        dialog.deleteLater()

        restored = GitHubDialog(None, self.manager)
        restored.delete_saved_token()
        with patch("orbit_control.ui.QFileDialog.getOpenFileName", return_value=(str(settings_json), "")):
            restored.import_github_settings()

        preferences = self.manager.storage.load_preferences()
        self.assertEqual(preferences["github_connections"][0]["login"], "annibale")
        self.assertEqual(restored.token_input.text(), "ghp_demo")
        self.assertEqual(restored.repo_combo.currentText(), "annibale/demo")
        self.assertTrue(restored.private_check.isChecked())
        restored.deleteLater()

    def test_github_dialog_lists_apps_and_suggests_repo_name(self) -> None:
        service = ServiceConfig(name="Demo", target=str(self.script), working_directory=str(self.root))
        self.manager.add_service(service)

        dialog = GitHubDialog(None, self.manager)

        self.assertEqual(dialog.app_combo.count(), 1)
        self.assertEqual(dialog.app_combo.currentData(), service.id)
        self.assertTrue(dialog.repo_combo.currentText())
        dialog.deleteLater()

    def test_github_dialog_accepts_unlisted_local_project_path(self) -> None:
        project = self.root / "Projeto Livre"
        project.mkdir()
        dialog = GitHubDialog(None, self.manager)

        dialog.app_combo.setEditText(str(project))
        selected = dialog._selected_service()
        dialog.repo_combo.clear()
        dialog._sync_repo_name(force=True)

        self.assertEqual(selected.name, "Projeto Livre")
        self.assertEqual(Path(selected.working_directory), project)
        self.assertEqual(Path(selected.target), project)
        self.assertEqual(dialog.repo_combo.currentText(), "projeto-livre")
        dialog.deleteLater()

    def test_github_dialog_browse_button_sets_unlisted_project(self) -> None:
        project = self.root / "Projeto Fora Do Orbit"
        project.mkdir()
        dialog = GitHubDialog(None, self.manager)

        with patch("orbit_control.ui.QFileDialog.getExistingDirectory", return_value=str(project)):
            dialog.browse_local_project()

        self.assertEqual(dialog.app_combo.currentText(), str(project))
        self.assertIn("Projeto livre", dialog.app_hint_label.text())
        self.assertEqual(dialog.repo_combo.currentText(), "projeto-fora-do-orbit")
        dialog.deleteLater()

    def test_github_dialog_loads_repositories_into_dropdown(self) -> None:
        dialog = GitHubDialog(None, self.manager)
        repos = [
            GitHubRepo("meu/user-api", "https://github.com/meu/user-api", "", False, 1, 2, 3, "main"),
            GitHubRepo("meu/web-app", "https://github.com/meu/web-app", "", True, 4, 5, 6, "main"),
        ]

        dialog._apply_stats(repos, summarize_repositories(repos))

        self.assertEqual(dialog.repo_combo.count(), 2)
        self.assertEqual([dialog.repo_combo.itemText(index) for index in range(2)], ["meu/user-api", "meu/web-app"])
        self.assertEqual(dialog.repo_list.count(), 2)
        dialog._connected = True
        dialog.repo_list.setCurrentRow(1)
        self.assertEqual(dialog.repo_combo.currentText(), "meu/web-app")
        self.assertEqual(dialog.selected_repo_label.toolTip(), "meu/web-app")
        self.assertTrue(dialog.update_repo_button.isEnabled())
        self.assertIn("2 repo", dialog.repo_count_label.text())
        dialog.deleteLater()

    def test_github_dialog_creates_new_repo_and_selects_it(self) -> None:
        dialog = GitHubDialog(None, self.manager)
        dialog.token_input.setText("token")
        created_repo = GitHubRepo(
            "meu/novo-repo",
            "https://github.com/meu/novo-repo",
            "https://github.com/meu/novo-repo.git",
            True,
            0,
            0,
            0,
            "main",
        )
        calls: list[dict[str, object]] = []

        class FakeClient:
            def __init__(self, token: str) -> None:
                self.token = token

            def create_repository(self, repo_name: str, *, private: bool, description: str = "", auto_init: bool = False):
                calls.append(
                    {
                        "repo_name": repo_name,
                        "private": private,
                        "description": description,
                        "auto_init": auto_init,
                    }
                )
                return created_repo

            def list_repositories(self):
                return [created_repo]

        def run_now(function, on_result, failure_prefix="Falha"):
            on_result(function())

        with (
            patch("orbit_control.ui.GitHubClient", FakeClient),
            patch.object(
                dialog,
                "_new_repo_options",
                return_value={
                    "name": "novo-repo",
                    "private": True,
                    "description": "Repo criado pelo Orbit",
                    "auto_init": True,
                },
            ),
            patch.object(dialog, "_submit_github_task", side_effect=run_now),
        ):
            dialog.create_new_repo()

        self.assertEqual(
            calls,
            [
                {
                    "repo_name": "novo-repo",
                    "private": True,
                    "description": "Repo criado pelo Orbit",
                    "auto_init": True,
                }
            ],
        )
        self.assertEqual(dialog.repo_combo.currentText(), "meu/novo-repo")
        self.assertEqual(dialog.repo_list.count(), 1)
        self.assertEqual(dialog.selected_repo_label.toolTip(), "meu/novo-repo")
        dialog.deleteLater()

    def test_github_dialog_reflows_between_wide_and_narrow_layouts(self) -> None:
        dialog = GitHubDialog(None, self.manager)

        def position(widget):
            return dialog.github_content_layout.getItemPosition(dialog.github_content_layout.indexOf(widget))

        dialog.github_scroll.resize(1000, 760)
        dialog._apply_github_layout(force=True)
        self.assertEqual(position(dialog.left_panel)[:2], (0, 0))
        self.assertEqual(position(dialog.right_panel)[:2], (0, 1))

        dialog.github_scroll.resize(720, 620)
        dialog._apply_github_layout(force=True)
        self.assertEqual(position(dialog.left_panel)[:2], (0, 0))
        self.assertEqual(position(dialog.right_panel)[:2], (1, 0))
        dialog.deleteLater()

    def test_service_card_autostart_toggle_persists(self) -> None:
        service = ServiceConfig(name="Demo", target=str(self.script), working_directory=str(self.root))
        self.manager.add_service(service)
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        window._apply_snapshots(self.manager.snapshots())
        card = window.cards_layout.itemAtPosition(0, 0).widget()
        assert card is not None
        toggles = [item for item in card.findChildren(QCheckBox) if item.property("startupToggle")]

        self.assertEqual(len(toggles), 1)
        self.assertFalse(toggles[0].isChecked())
        toggles[0].setChecked(True)
        window.thread_pool.waitForDone(1000)

        self.assertTrue(self.manager.get_service(service.id).autostart)
        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_compact_mode_shows_command_list_and_survives_restart(self) -> None:
        service = ServiceConfig(
            name="Demo",
            target=str(self.script),
            working_directory=str(self.root),
            arguments="--port 5050",
        )
        self.manager.add_service(service)
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        window._apply_snapshots(self.manager.snapshots())

        window.toggle_compact_mode(True)

        row = window.cards_layout.itemAtPosition(0, 0).widget()
        assert row is not None
        command_labels = [item for item in row.findChildren(QLabel) if item.property("compactCommand")]
        self.assertTrue(window._compact_mode)
        self.assertTrue(window.compact_button.isChecked())
        self.assertTrue(window.stats_host.isHidden())
        self.assertTrue(row.property("compactRow"))
        self.assertEqual(self.manager.storage.load_preferences()["compact_mode"], True)
        self.assertIn(str(self.script), command_labels[0].toolTip())
        self.assertIn("--port 5050", command_labels[0].toolTip())

        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

        restored = MainWindow(self.manager)
        restored.refresh_timer.stop()
        self.assertTrue(restored._compact_mode)
        self.assertTrue(restored.compact_button.isChecked())
        restored._closing = True
        restored.thread_pool.waitForDone(1000)
        restored.deleteLater()

    def test_theme_toggle_changes_icon_and_survives_restart(self) -> None:
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        self.assertEqual(window._theme, "light")
        self.assertIn("☾", window.theme_button.text())

        window.toggle_theme()
        self.assertEqual(window._theme, "dark")
        self.assertIn("☀", window.theme_button.text())
        self.assertEqual(self.manager.storage.load_preferences()["theme"], "dark")
        self.assertIn("#0f1117", window.styleSheet())

        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

        restored = MainWindow(self.manager)
        restored.refresh_timer.stop()
        self.assertEqual(restored._theme, "dark")
        self.assertIn("☀", restored.theme_button.text())
        restored._closing = True
        restored.thread_pool.waitForDone(1000)
        restored.deleteLater()

    def test_reorder_visible_cards_preserves_hidden_service_slots(self) -> None:
        services = []
        for name, description in (("Alpha", "visible"), ("Bravo", "hidden"), ("Charlie", "visible")):
            service = ServiceConfig(
                name=name,
                target=str(self.script),
                description=description,
                working_directory=str(self.root),
            )
            self.manager.add_service(service)
            services.append(service)

        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        window._apply_snapshots(self.manager.snapshots())
        window.search_input.setText("visible")
        window._reorder_visible(services[2].id, 0)

        self.assertEqual(
            [item.id for item in self.manager.list_services()],
            [services[2].id, services[1].id, services[0].id],
        )
        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_refresh_and_reorder_are_deferred_while_dragging(self) -> None:
        services = []
        for name in ("Alpha", "Bravo"):
            service = ServiceConfig(name=name, target=str(self.script), working_directory=str(self.root))
            self.manager.add_service(service)
            services.append(service)

        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        window._apply_snapshots(self.manager.snapshots())
        original_first = window.cards_layout.itemAtPosition(0, 0).widget()
        assert original_first is not None

        window._set_drag_active(True)
        window._apply_snapshots(self.manager.snapshots())
        window._reorder_visible(services[1].id, 0)

        # The card used as QDrag's source must remain alive until mouse release.
        self.assertIs(window.cards_layout.itemAtPosition(0, 0).widget(), original_first)
        self.assertFalse(window.refresh_timer.isActive())
        self.assertTrue(window._rebuild_pending)

        window._set_drag_active(False)
        rebuilt_first = window.cards_layout.itemAtPosition(0, 0).widget()
        assert rebuilt_first is not None
        self.assertEqual(rebuilt_first.property("serviceId"), services[1].id)
        self.assertTrue(window.refresh_timer.isActive())
        self.assertFalse(window._drag_active)

        window._closing = True
        window.refresh_timer.stop()
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_filter_rebuild_waits_until_drag_finishes(self) -> None:
        service = ServiceConfig(name="Alpha", target=str(self.script), working_directory=str(self.root))
        self.manager.add_service(service)
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        window._apply_snapshots(self.manager.snapshots())
        card = window.cards_layout.itemAtPosition(0, 0).widget()

        window._set_drag_active(True)
        window.search_input.setText("não existe")
        self.assertIs(window.cards_layout.itemAtPosition(0, 0).widget(), card)

        window._set_drag_active(False)
        empty_state = window.cards_layout.itemAtPosition(0, 0).widget()
        assert empty_state is not None
        self.assertEqual(empty_state.objectName(), "emptyState")

        window._closing = True
        window.refresh_timer.stop()
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_main_window_reflows_header_stats_and_bulk_actions(self) -> None:
        window = MainWindow(self.manager)
        window.refresh_timer.stop()

        def position(layout, widget) -> tuple[int, int, int, int]:
            return layout.getItemPosition(layout.indexOf(widget))

        window.resize(900, 700)
        window._apply_responsive_layout(force=True)
        self.assertEqual(position(window.header_layout, window.search_input)[:2], (1, 0))
        self.assertEqual(position(window.stats_layout, window.stat_cards["attention"])[:2], (0, 3))
        self.assertEqual(position(window.bulk_layout, window.bulk_actions)[:2], (0, 1))

        window.resize(720, 700)
        window._apply_responsive_layout(force=True)
        self.assertEqual(position(window.header_layout, window.status_combo)[:2], (2, 0))
        self.assertEqual(position(window.header_layout, window.add_button)[:2], (2, 1))
        self.assertEqual(position(window.stats_layout, window.stat_cards["attention"])[:2], (1, 1))
        self.assertEqual(position(window.bulk_layout, window.bulk_actions)[:2], (1, 0))
        self.assertEqual(window._column_count_for_width(616), 1)

        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_card_grid_drops_stale_column_stretch_after_resize(self) -> None:
        for index in range(4):
            self.manager.add_service(
                ServiceConfig(
                    name=f"Demo {index}",
                    target=str(self.script),
                    working_directory=str(self.root),
                )
            )
        window = MainWindow(self.manager)
        window.refresh_timer.stop()
        window.cards_layout.setColumnStretch(2, 1)
        window._column_count = lambda: 2
        window._apply_snapshots(self.manager.snapshots())

        self.assertEqual(window.cards_layout.columnStretch(0), 1)
        self.assertEqual(window.cards_layout.columnStretch(1), 1)
        self.assertEqual(window.cards_layout.columnStretch(2), 0)
        first_card = window.cards_layout.itemAtPosition(0, 0).widget()
        assert first_card is not None
        self.assertEqual(first_card.minimumWidth(), 0)

        window._closing = True
        window.thread_pool.waitForDone(1000)
        window.deleteLater()

    def test_card_column_breakpoints_are_fluid(self) -> None:
        self.assertEqual(MainWindow._column_count_for_width(699), 2)
        self.assertEqual(MainWindow._column_count_for_width(1039), 2)
        self.assertEqual(MainWindow._column_count_for_width(1040), 3)

    def test_service_dialog_shows_detected_project_python(self) -> None:
        scripts = self.root / ".venv" / "Scripts"
        scripts.mkdir(parents=True)
        project_python = scripts / "python.exe"
        project_python.write_text("placeholder", encoding="utf-8")
        dialog = ServiceDialog(None)
        dialog.target_input.setText(str(self.script))
        dialog.workdir_input.setText(str(self.root))
        dialog._update_python_hint()

        self.assertIn("Detectado automaticamente", dialog.python_hint.text())
        self.assertIn(str(project_python.resolve()), dialog.python_hint.text())
        dialog.deleteLater()

    def test_service_dialog_autofills_project_metadata_and_requirements_option(self) -> None:
        dialog = ServiceDialog(None)
        dialog.target_input.setText(str(self.script))
        dialog._autofill_from_target()

        self.assertEqual(dialog.name_input.text(), self.root.name)
        self.assertEqual(dialog.workdir_input.text(), str(self.root))
        self.assertEqual(dialog.kind_combo.currentData(), "python")
        dialog.install_requirements_check.setChecked(True)
        dialog._save()
        assert dialog.result_config is not None
        self.assertTrue(dialog.result_config.install_requirements)
        dialog.deleteLater()

    def test_service_dialog_detects_type_from_target_text(self) -> None:
        batch = self.root / "INICIAR.bat"
        batch.write_text("@echo off\necho READY\n", encoding="utf-8")
        dialog = ServiceDialog(None)
        dialog.target_input.setText(str(batch))
        dialog._autodetect_kind_from_target()

        self.assertEqual(dialog.kind_combo.currentData(), "batch")
        dialog.target_input.setText(str(self.script))
        dialog._autodetect_kind_from_target()
        self.assertEqual(dialog.kind_combo.currentData(), "python")
        dialog.deleteLater()

    def test_service_dialog_accepts_and_autofills_batch_file(self) -> None:
        batch = self.root / "INICIAR.bat"
        batch.write_text("@echo off\necho READY\n", encoding="utf-8")
        dialog = ServiceDialog(None)
        dialog.target_input.setText(str(batch))
        dialog._autofill_from_target()

        self.assertEqual(dialog.name_input.text(), self.root.name)
        self.assertEqual(dialog.workdir_input.text(), str(self.root))
        self.assertEqual(dialog.kind_combo.currentData(), "batch")
        self.assertFalse(dialog.install_requirements_check.isEnabled())
        dialog._save()
        assert dialog.result_config is not None
        self.assertEqual(dialog.result_config.kind, "batch")
        self.assertFalse(dialog.result_config.install_requirements)
        dialog.deleteLater()

    def test_service_dialog_autofills_node_project_and_scripts(self) -> None:
        project = self.root / "painel-node"
        project.mkdir()
        (project / "package.json").write_text(
            json.dumps({"scripts": {"dev": "vite", "preview": "vite preview"}}),
            encoding="utf-8",
        )
        (project / "pnpm-lock.yaml").write_text("", encoding="utf-8")

        dialog = ServiceDialog(None)
        dialog.target_input.setText(str(project))
        dialog._autofill_from_target()

        self.assertEqual(dialog.name_input.text(), "painel-node")
        self.assertEqual(dialog.workdir_input.text(), str(project))
        self.assertEqual(dialog.kind_combo.currentData(), "node")
        self.assertFalse(dialog.node_group.isHidden())
        self.assertEqual(dialog.package_command_combo.currentText(), "dev")
        self.assertIn("Detectado: pnpm", dialog.node_hint.text())

        dialog.install_node_dependencies_check.setChecked(True)
        dialog.node_install_command_input.setText("install --frozen-lockfile")
        dialog.package_command_combo.setEditText("pnpm dev")
        dialog._save()
        assert dialog.result_config is not None
        self.assertEqual(dialog.result_config.kind, "node")
        self.assertEqual(dialog.result_config.package_manager, "auto")
        self.assertEqual(dialog.result_config.package_command, "pnpm dev")
        self.assertTrue(dialog.result_config.install_node_dependencies)
        self.assertEqual(dialog.result_config.node_install_command, "install --frozen-lockfile")
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
