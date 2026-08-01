from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from orbit_control.node_tools import (
    default_package_script,
    detect_package_manager,
    find_package_json,
    normalize_package_command,
    package_scripts,
)


class NodeToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "painel-node"
        self.root.mkdir()
        self.package_json = self.root / "package.json"
        self.package_json.write_text(
            json.dumps(
                {
                    "name": "painel-node",
                    "scripts": {"dev": "vite", "start": "node server.js", "preview": "vite preview"},
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_finds_manifest_and_scripts_from_folder(self) -> None:
        self.assertEqual(find_package_json(str(self.root)), self.package_json.resolve())
        self.assertEqual(package_scripts(str(self.root)), ["dev", "start", "preview"])
        self.assertEqual(default_package_script(package_scripts(str(self.root))), "dev")

    def test_detects_each_package_manager(self) -> None:
        expectations = {
            "pnpm-lock.yaml": "pnpm",
            "yarn.lock": "yarn",
            "bun.lockb": "bun",
            "package-lock.json": "npm",
        }
        for filename, expected in expectations.items():
            for candidate in expectations:
                (self.root / candidate).unlink(missing_ok=True)
            (self.root / filename).write_text("", encoding="utf-8")
            self.assertEqual(detect_package_manager(str(self.root)), expected)

    def test_package_manager_field_wins_over_lockfile(self) -> None:
        data = json.loads(self.package_json.read_text(encoding="utf-8"))
        data["packageManager"] = "pnpm@10.0.0"
        self.package_json.write_text(json.dumps(data), encoding="utf-8")
        (self.root / "package-lock.json").write_text("{}", encoding="utf-8")
        self.assertEqual(detect_package_manager(str(self.package_json)), "pnpm")

    def test_normalizes_short_and_full_commands(self) -> None:
        scripts = package_scripts(str(self.root))
        self.assertEqual(normalize_package_command("dev", "npm", scripts), ["run", "dev"])
        self.assertEqual(normalize_package_command("npm run dev", "npm", scripts), ["run", "dev"])
        self.assertEqual(normalize_package_command("pnpm dev", "pnpm", scripts), ["dev"])
        self.assertEqual(normalize_package_command("yarn start", "yarn", scripts), ["start"])
        self.assertEqual(normalize_package_command("bun run preview", "bun", scripts), ["run", "preview"])

    def test_preserves_package_manager_operations_and_arguments(self) -> None:
        scripts = package_scripts(str(self.root))
        self.assertEqual(
            normalize_package_command("install --frozen-lockfile", "pnpm", scripts),
            ["install", "--frozen-lockfile"],
        )
        self.assertEqual(
            normalize_package_command("npm run dev -- --host 0.0.0.0", "npm", scripts),
            ["run", "dev", "--", "--host", "0.0.0.0"],
        )


if __name__ == "__main__":
    unittest.main()
