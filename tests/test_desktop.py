from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from orbit_control.models import ServiceConfig
from orbit_control.process_manager import ProcessManager
from orbit_control.ui import DragHandle, MainWindow, ServiceDialog


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
