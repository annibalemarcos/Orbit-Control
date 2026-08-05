from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orbit_control.github_tools import (
    GitHubClient,
    GitHubError,
    GitHubRepo,
    authenticated_clone_url,
    ensure_git_repository,
    infer_repo_name,
    split_repo_name,
    upload_project_to_github,
)
from orbit_control.models import ServiceConfig


class GitHubToolsTests(unittest.TestCase):
    def test_split_repo_name_accepts_plain_or_owner_repo_names(self) -> None:
        self.assertEqual(split_repo_name("meu-app", "usuario"), ("usuario", "meu-app"))
        self.assertEqual(split_repo_name("org/meu-app", "usuario"), ("org", "meu-app"))

        with self.assertRaises(GitHubError):
            split_repo_name("", "usuario")

    def test_infer_repo_name_uses_project_folder_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "Meu App Legal"
            project.mkdir()
            service = ServiceConfig(name="Demo", target=str(project / "main.py"), working_directory=str(project))

            self.assertEqual(infer_repo_name(service), "meu-app-legal")

    def test_authenticated_clone_url_embeds_escaped_token(self) -> None:
        url = authenticated_clone_url("https://github.com/meu/repo.git", "token@123")

        self.assertEqual(url, "https://x-access-token:token%40123@github.com/meu/repo.git")

        with self.assertRaises(GitHubError):
            authenticated_clone_url("git@github.com:meu/repo.git", "token")

    def test_list_repositories_reads_all_pages_until_last_page(self) -> None:
        client = GitHubClient("token")
        calls: list[str] = []

        def fake_request(method: str, path: str, payload=None):
            calls.append(path)
            if "&page=1&" in path:
                return [{"full_name": f"meu/repo-{index}"} for index in range(100)]
            return [{"full_name": "meu/repo-100"}]

        client._request = fake_request  # type: ignore[method-assign]

        repos = client.list_repositories()

        self.assertEqual(len(repos), 101)
        self.assertEqual(calls, ["/user/repos?per_page=100&page=1&sort=updated", "/user/repos?per_page=100&page=2&sort=updated"])

    def test_delete_repository_uses_repo_delete_endpoint(self) -> None:
        client = GitHubClient("token")
        calls: list[tuple[str, str]] = []

        def fake_request(method: str, path: str, payload=None):
            calls.append((method, path))
            if path == "/user":
                return {"login": "meu"}
            return {}

        client._request = fake_request  # type: ignore[method-assign]

        client.delete_repository("meu/repo")

        self.assertEqual(calls, [("GET", "/user"), ("DELETE", "/repos/meu/repo")])

    def test_create_repository_uses_user_repo_create_endpoint(self) -> None:
        client = GitHubClient("token")
        calls: list[tuple[str, str, dict[str, object] | None]] = []

        def fake_request(method: str, path: str, payload=None):
            calls.append((method, path, payload))
            if path == "/user":
                return {"login": "meu"}
            return {
                "full_name": "meu/novo-repo",
                "html_url": "https://github.com/meu/novo-repo",
                "clone_url": "https://github.com/meu/novo-repo.git",
                "private": True,
            }

        client._request = fake_request  # type: ignore[method-assign]

        repo = client.create_repository(
            "novo-repo",
            private=True,
            description="Repo criado pelo Orbit",
            auto_init=True,
        )

        self.assertEqual(repo.full_name, "meu/novo-repo")
        self.assertEqual(
            calls,
            [
                ("GET", "/user", None),
                (
                    "POST",
                    "/user/repos",
                    {
                        "name": "novo-repo",
                        "private": True,
                        "auto_init": True,
                        "description": "Repo criado pelo Orbit",
                    },
                ),
            ],
        )

    def test_existing_git_work_tree_does_not_run_git_init_again(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            with (
                patch("orbit_control.github_tools.is_git_work_tree", return_value=True),
                patch("orbit_control.github_tools.run_git") as run_git,
            ):
                ensure_git_repository(project)

        run_git.assert_not_called()

    def test_upload_repairs_git_metadata_before_git_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            repo = GitHubRepo(
                "meu/repo",
                "https://github.com/meu/repo",
                "https://github.com/meu/repo.git",
                False,
                0,
                0,
                0,
                "main",
            )
            calls: list[tuple[str, tuple[str, ...]]] = []

            def fake_run_git(project_dir: Path, *args: str) -> str:
                calls.append(("git", args))
                if args == ("branch", "--show-current"):
                    return "main"
                return ""

            with (
                patch("orbit_control.github_tools.shutil_which", return_value="git"),
                patch("orbit_control.github_tools.repair_git_metadata_permissions") as repair,
                patch("orbit_control.github_tools.ensure_git_repository") as ensure_repo,
                patch("orbit_control.github_tools.ensure_public_remote"),
                patch("orbit_control.github_tools.has_staged_changes", return_value=True),
                patch("orbit_control.github_tools.has_commits", return_value=True),
                patch("orbit_control.github_tools.run_git", side_effect=fake_run_git),
            ):
                upload_project_to_github(project, repo, "token", "commit")

        repair.assert_called_once_with(project)
        ensure_repo.assert_called_once_with(project)
        self.assertEqual(calls[0], ("git", ("add", "-A")))

    def test_upload_falls_back_to_temporary_clone_when_local_git_is_locked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            repo = GitHubRepo(
                "meu/repo",
                "https://github.com/meu/repo",
                "https://github.com/meu/repo.git",
                False,
                0,
                0,
                0,
                "main",
            )

            with (
                patch("orbit_control.github_tools.shutil_which", return_value="git"),
                patch(
                    "orbit_control.github_tools.upload_project_in_place",
                    side_effect=GitHubError("could not write config file .git/config: Permission denied"),
                ) as in_place,
                patch(
                    "orbit_control.github_tools.upload_project_via_temporary_clone",
                    return_value=repo.html_url,
                ) as fallback,
            ):
                url = upload_project_to_github(project, repo, "token", "commit")

        self.assertEqual(url, repo.html_url)
        in_place.assert_called_once_with(project, repo, "token", "commit")
        fallback.assert_called_once_with(project, repo, "token", "commit")


if __name__ == "__main__":
    unittest.main()
