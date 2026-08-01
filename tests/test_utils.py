from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from orbit_control.utils import (
    human_duration,
    infer_service_kind,
    infer_service_name,
    parse_environment,
    split_arguments,
    tail_file,
)


class UtilsTests(unittest.TestCase):
    def test_parse_environment(self) -> None:
        self.assertEqual(
            parse_environment("# comentário\nPORT=5000\nMODE=dev=local\n"),
            {"PORT": "5000", "MODE": "dev=local"},
        )

    def test_invalid_environment(self) -> None:
        with self.assertRaises(ValueError):
            parse_environment("INVALID")

    def test_split_arguments_keeps_quoted_values(self) -> None:
        self.assertEqual(split_arguments('--name "Orbit Control" --debug'), ["--name", "Orbit Control", "--debug"])

    def test_human_duration(self) -> None:
        self.assertEqual(human_duration(9), "9s")
        self.assertEqual(human_duration(75), "1m 15s")
        self.assertEqual(human_duration(90061), "1d 1h")

    def test_infer_service_name_from_windows_project_path(self) -> None:
        self.assertEqual(
            infer_service_name(r"E:\my_projects\senhas_dashboard\app.py"),
            "senhas_dashboard",
        )

    def test_infer_batch_kind(self) -> None:
        self.assertEqual(infer_service_kind(r"E:\my_projects\meu painel\ABRIR.bat"), "batch")
        self.assertEqual(infer_service_kind(r"E:\my_projects\meu painel\iniciar.CMD"), "batch")

    def test_infer_node_project_name_and_kind(self) -> None:
        manifest = r"E:\my_projects\painel_node\package.json"
        self.assertEqual(infer_service_name(manifest), "painel_node")
        self.assertEqual(infer_service_kind(manifest), "node")

    def test_infer_node_project_from_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "meu-site"
            root.mkdir()
            (root / "package.json").write_text("{}", encoding="utf-8")
            self.assertEqual(infer_service_name(str(root)), "meu-site")
            self.assertEqual(infer_service_kind(str(root)), "node")

    def test_tail_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "log.txt"
            path.write_text("a\nb\nc\nd\n", encoding="utf-8")
            self.assertEqual(tail_file(path, max_lines=2), "c\nd")


if __name__ == "__main__":
    unittest.main()
