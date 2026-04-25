from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .models import RecentFile, RepoTreeNode, WorktreeInfo, normalize_path, to_iso8601


IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    "__pycache__",
    ".cache",
    ".next",
    ".beads",
}


def run_git(path: str | Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(Path(path).expanduser().resolve()), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def get_branch(path: str) -> str:
    try:
        return run_git(path, "branch", "--show-current")
    except subprocess.CalledProcessError:
        return ""


def get_head_commit(path: str, short: bool = False) -> str:
    args = ["rev-parse"]
    if short:
        args.append("--short=12")
    args.append("HEAD")
    try:
        return run_git(path, *args)
    except subprocess.CalledProcessError:
        return ""


def get_dirty_files(path: str) -> list[str]:
    try:
        output = run_git(path, "status", "--porcelain")
    except subprocess.CalledProcessError:
        return []

    dirty_files: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        entry = line[3:] if len(line) > 3 else line
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        dirty_files.append(entry)
    return dirty_files


def get_worktrees(repo_path: str) -> list[WorktreeInfo]:
    try:
        output = run_git(repo_path, "worktree", "list", "--porcelain")
    except subprocess.CalledProcessError:
        return []

    items: list[WorktreeInfo] = []
    current: dict[str, str | bool] = {}
    for line in output.splitlines():
        if not line.strip():
            if current:
                items.append(_build_worktree(current))
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value if value else True
    if current:
        items.append(_build_worktree(current))
    return items


def get_branches(repo_path: str) -> list[str]:
    try:
        output = run_git(repo_path, "branch", "--format", "%(refname:short)")
    except subprocess.CalledProcessError:
        return []
    branches = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("(HEAD detached")]
    return sorted(dict.fromkeys(branches), key=str.lower)


def _build_worktree(current: dict[str, str | bool]) -> WorktreeInfo:
    branch = current.get("branch")
    branch_name = None
    if isinstance(branch, str):
        branch_name = branch.removeprefix("refs/heads/")
    return WorktreeInfo(
        path=normalize_path(str(current["worktree"])),
        head=str(current["HEAD"]) if "HEAD" in current else None,
        branch=branch_name,
        is_detached=bool(current.get("detached")),
        is_bare=bool(current.get("bare")),
        is_locked=bool(current.get("locked")),
        prunable=str(current["prunable"]) if "prunable" in current else None,
    )


def get_recent_files(path: str, since_seconds: int = 300) -> list[RecentFile]:
    root = Path(path).expanduser().resolve()
    cutoff = datetime.now(UTC).timestamp() - since_seconds
    recent: list[RecentFile] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRS]
        for filename in filenames:
            file_path = Path(dirpath, filename)
            try:
                stat = file_path.stat()
            except OSError:
                continue
            if stat.st_mtime < cutoff:
                continue
            modified_at = datetime.fromtimestamp(stat.st_mtime, UTC)
            recent.append(
                RecentFile(
                    path=file_path.relative_to(root).as_posix(),
                    modified_at=to_iso8601(modified_at),
                )
            )
    recent.sort(key=lambda item: item.modified_at, reverse=True)
    return recent[:25]


def get_repo_tree(
    path: str,
    max_depth: int = 4,
    include_paths: list[str] | None = None,
    max_children: int = 16,
) -> RepoTreeNode:
    root = Path(path).expanduser().resolve()
    focus_prefixes = _build_focus_prefixes(root, include_paths or [])
    return _build_tree_node(
        root,
        root,
        depth=0,
        max_depth=max_depth,
        focus_prefixes=focus_prefixes,
        max_children=max_children,
    )


def _build_focus_prefixes(root: Path, include_paths: list[str]) -> set[str]:
    prefixes: set[str] = set()
    for raw_path in include_paths:
        try:
            candidate = Path(raw_path).expanduser().resolve().relative_to(root)
        except (OSError, ValueError):
            continue
        parts = candidate.parts
        for index in range(1, len(parts) + 1):
            prefixes.add(Path(*parts[:index]).as_posix())
    return prefixes


def _build_tree_node(
    root: Path,
    current: Path,
    depth: int,
    max_depth: int,
    focus_prefixes: set[str],
    max_children: int,
) -> RepoTreeNode:
    node_type = "repo" if depth == 0 else ("folder" if current.is_dir() else "file")
    node = RepoTreeNode(
        name=current.name if depth else root.name,
        path=normalize_path(current),
        node_type=node_type,
    )
    if not current.is_dir() or depth >= max_depth:
        return node

    try:
        entries = sorted(current.iterdir(), key=lambda entry: (entry.is_file(), entry.name.lower()))
    except OSError:
        return node

    visible_entries: list[Path] = []
    hidden_count = 0
    for entry in entries:
        if entry.name in IGNORED_DIRS:
            continue
        child_rel = entry.relative_to(root).as_posix()
        keep_entry = not focus_prefixes or depth == 0 or child_rel in focus_prefixes
        if keep_entry:
            visible_entries.append(entry)
        else:
            hidden_count += 1

    if not focus_prefixes and len(visible_entries) > max_children:
        hidden_count += len(visible_entries) - max_children
        visible_entries = visible_entries[:max_children]

    for entry in visible_entries:
        child = _build_tree_node(
            root,
            entry,
            depth + 1,
            max_depth,
            focus_prefixes,
            max_children,
        )
        node.children.append(child)

    if hidden_count > 0:
        node.children.append(
            RepoTreeNode(
                name=f"... {hidden_count} more",
                path=f"{normalize_path(current)}#truncated",
                node_type="truncated",
                meta={"hidden_count": hidden_count},
            )
        )
    return node
