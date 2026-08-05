from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import ServiceConfig

GITHUB_API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


@dataclass(slots=True)
class GitHubRepo:
    full_name: str
    html_url: str
    clone_url: str
    private: bool
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    default_branch: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitHubRepo":
        return cls(
            full_name=str(data.get("full_name") or ""),
            html_url=str(data.get("html_url") or ""),
            clone_url=str(data.get("clone_url") or ""),
            private=bool(data.get("private")),
            stargazers_count=int(data.get("stargazers_count") or 0),
            forks_count=int(data.get("forks_count") or 0),
            open_issues_count=int(data.get("open_issues_count") or 0),
            default_branch=str(data.get("default_branch") or "main"),
        )


class GitHubClient:
    def __init__(self, token: str) -> None:
        self.token = token.strip()
        if not self.token:
            raise GitHubError("Informe um token do GitHub.")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{GITHUB_API}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "Orbit-Control",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            message = exc.reason
            try:
                data = json.loads(exc.read().decode("utf-8"))
                message = data.get("message") or message
            except (OSError, json.JSONDecodeError):
                pass
            raise GitHubError(f"GitHub HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            raise GitHubError(f"Nao foi possivel conectar ao GitHub: {exc.reason}") from exc

    def current_user(self) -> dict[str, Any]:
        return dict(self._request("GET", "/user"))

    def list_repositories(self, max_pages: int | None = None) -> list[GitHubRepo]:
        repos: list[GitHubRepo] = []
        page = 1
        while max_pages is None or page <= max_pages:
            data = self._request("GET", f"/user/repos?per_page=100&page={page}&sort=updated")
            if not isinstance(data, list):
                break
            repos.extend(GitHubRepo.from_dict(item) for item in data if isinstance(item, dict))
            if len(data) < 100:
                break
            page += 1
        return repos

    def get_repository(self, full_name: str) -> GitHubRepo:
        owner, name = split_repo_name(full_name, self.current_user_login())
        data = self._request("GET", f"/repos/{owner}/{name}")
        return GitHubRepo.from_dict(dict(data))

    def current_user_login(self) -> str:
        login = str(self.current_user().get("login") or "")
        if not login:
            raise GitHubError("Nao foi possivel identificar o usuario do GitHub.")
        return login

    def ensure_repository(self, repo_name: str, *, private: bool, create_missing: bool = True) -> GitHubRepo:
        split_repo_name(repo_name, self.current_user_login())
        try:
            return self.get_repository(repo_name)
        except GitHubError as exc:
            if "HTTP 404" not in str(exc) or not create_missing:
                raise

        return self.create_repository(repo_name, private=private)

    def create_repository(
        self,
        repo_name: str,
        *,
        private: bool,
        description: str = "",
        auto_init: bool = False,
    ) -> GitHubRepo:
        default_owner = self.current_user_login()
        owner, name = split_repo_name(repo_name, default_owner)
        payload: dict[str, Any] = {"name": name, "private": private, "auto_init": auto_init}
        if description.strip():
            payload["description"] = description.strip()
        if owner == default_owner:
            data = self._request("POST", "/user/repos", payload)
        else:
            data = self._request("POST", f"/orgs/{owner}/repos", payload)
        return GitHubRepo.from_dict(dict(data))

    def delete_repository(self, full_name: str) -> None:
        owner, name = split_repo_name(full_name, self.current_user_login())
        self._request("DELETE", f"/repos/{owner}/{name}")

    def repository_stats(self) -> dict[str, int]:
        return summarize_repositories(self.list_repositories())


def summarize_repositories(repos: list[GitHubRepo]) -> dict[str, int]:
    return {
        "repos": len(repos),
        "private": sum(repo.private for repo in repos),
        "public": sum(not repo.private for repo in repos),
        "stars": sum(repo.stargazers_count for repo in repos),
        "forks": sum(repo.forks_count for repo in repos),
        "issues": sum(repo.open_issues_count for repo in repos),
    }


def split_repo_name(value: str, default_owner: str) -> tuple[str, str]:
    cleaned = value.strip().strip("/")
    if not cleaned:
        raise GitHubError("Informe o nome do repositorio.")
    if "/" in cleaned:
        owner, name = cleaned.split("/", 1)
    else:
        owner, name = default_owner, cleaned
    owner = owner.strip()
    name = name.strip()
    if not owner or not name:
        raise GitHubError("Nome do repositorio invalido.")
    return owner, name


def service_project_directory(service: ServiceConfig) -> Path:
    if service.working_directory:
        return Path(service.working_directory).expanduser().resolve()
    target = Path(service.target).expanduser()
    if target.is_dir():
        return target.resolve()
    return target.parent.resolve()


def infer_repo_name(service: ServiceConfig) -> str:
    base = service_project_directory(service).name or service.name
    safe = "".join(char.lower() if char.isalnum() else "-" for char in base)
    safe = "-".join(part for part in safe.split("-") if part)
    return safe or "orbit-app"


def upload_project_to_github(
    project_dir: Path,
    repo: GitHubRepo,
    token: str,
    commit_message: str,
) -> str:
    if not project_dir.is_dir():
        raise GitHubError(f"Pasta do app nao encontrada: {project_dir}")
    if not shutil_which("git"):
        raise GitHubError("Git nao foi encontrado no PATH.")

    try:
        return upload_project_in_place(project_dir, repo, token, commit_message)
    except GitHubError as exc:
        if not is_local_git_permission_error(str(exc)):
            raise
        return upload_project_via_temporary_clone(project_dir, repo, token, commit_message)


def upload_project_in_place(
    project_dir: Path,
    repo: GitHubRepo,
    token: str,
    commit_message: str,
) -> str:
    repair_git_metadata_permissions(project_dir)
    ensure_git_repository(project_dir)
    ensure_public_remote(project_dir, repo.clone_url)
    commit_and_push(project_dir, repo, token, commit_message)
    return repo.html_url


def commit_and_push(project_dir: Path, repo: GitHubRepo, token: str, commit_message: str) -> None:
    run_git(project_dir, "add", "-A")

    if has_staged_changes(project_dir) or not has_commits(project_dir):
        message = commit_message.strip() or "Atualiza app pelo Orbit Control"
        run_git(
            project_dir,
            "-c",
            "user.name=Orbit Control",
            "-c",
            "user.email=orbit-control@local",
            "commit",
            "--allow-empty",
            "-m",
            message,
        )

    branch = current_branch(project_dir) or repo.default_branch or "main"
    run_git(project_dir, "branch", "-M", branch)
    auth_url = authenticated_clone_url(repo.clone_url, token)
    run_git(project_dir, "push", "-u", auth_url, f"HEAD:{branch}")


def upload_project_via_temporary_clone(
    project_dir: Path,
    repo: GitHubRepo,
    token: str,
    commit_message: str,
) -> str:
    with tempfile.TemporaryDirectory(prefix="orbit-github-") as temp:
        clone_parent = Path(temp)
        clone_dir = clone_parent / "repo"
        run_git(clone_parent, "clone", authenticated_clone_url(repo.clone_url, token), str(clone_dir))
        clear_work_tree(clone_dir)
        copy_project_snapshot(project_dir, clone_dir)
        commit_and_push(clone_dir, repo, token, commit_message)
    return repo.html_url


def is_local_git_permission_error(message: str) -> bool:
    lowered = message.casefold()
    return (
        "permission denied" in lowered
        or "unable to write new index file" in lowered
        or "could not write config file" in lowered
        or "could not lock config file" in lowered
    )


def clear_work_tree(project_dir: Path) -> None:
    for child in project_dir.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copy_project_snapshot(source_dir: Path, target_dir: Path) -> None:
    files = git_visible_files(source_dir) if is_git_work_tree(source_dir) else []
    if files:
        for relative in files:
            source = source_dir / relative
            target = target_dir / relative
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        return
    copy_project_tree(source_dir, target_dir)


def git_visible_files(project_dir: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=project_dir,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        return []
    return [Path(item.decode("utf-8", errors="replace")) for item in completed.stdout.split(b"\0") if item]


def copy_project_tree(source_dir: Path, target_dir: Path) -> None:
    ignored_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
    for source in source_dir.rglob("*"):
        relative = source.relative_to(source_dir)
        if any(part in ignored_dirs for part in relative.parts):
            continue
        target = target_dir / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def run_git(project_dir: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_dir,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise GitHubError(f"Git falhou: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "erro desconhecido").strip()
        raise GitHubError(detail)
    return completed.stdout.strip()


def is_git_work_tree(project_dir: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_dir,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0 and completed.stdout.strip().casefold() == "true"


def ensure_git_repository(project_dir: Path) -> None:
    if is_git_work_tree(project_dir):
        return
    run_git(project_dir, "init")


def repair_git_metadata_permissions(project_dir: Path) -> None:
    git_dir = project_dir / ".git"
    if not git_dir.exists():
        return
    make_tree_writable(git_dir)
    if os.name == "nt":
        grant_windows_git_modify_permission(git_dir)


def make_tree_writable(path: Path) -> None:
    for item in [path, *path.rglob("*")]:
        try:
            item.chmod(item.stat().st_mode | stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass


def grant_windows_git_modify_permission(git_dir: Path) -> None:
    username = os.environ.get("USERNAME", "").strip()
    if not username:
        return
    domain = os.environ.get("USERDOMAIN", "").strip()
    account = f"{domain}\\{username}" if domain else username
    subprocess.run(
        ["icacls", str(git_dir), "/grant", f"{account}:(OI)(CI)M", "/T", "/C"],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def shutil_which(command: str) -> str | None:
    from shutil import which

    return which(command)


def ensure_public_remote(project_dir: Path, clone_url: str) -> None:
    completed = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=project_dir,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        run_git(project_dir, "remote", "add", "origin", clone_url)


def has_staged_changes(project_dir: Path) -> bool:
    return bool(run_git(project_dir, "status", "--porcelain"))


def has_commits(project_dir: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def current_branch(project_dir: Path) -> str:
    return run_git(project_dir, "branch", "--show-current").strip()


def authenticated_clone_url(clone_url: str, token: str) -> str:
    if not clone_url.startswith("https://"):
        raise GitHubError("Use um repositorio HTTPS do GitHub.")
    escaped = quote(token, safe="")
    return clone_url.replace("https://", f"https://x-access-token:{escaped}@", 1)
