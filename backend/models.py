from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso8601(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class RecentFile:
    path: str
    modified_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RepoTreeNode:
    name: str
    path: str
    node_type: str
    children: list["RepoTreeNode"] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.node_type,
            "meta": self.meta,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass(slots=True)
class WorktreeInfo:
    path: str
    head: str | None
    branch: str | None
    is_detached: bool = False
    is_bare: bool = False
    is_locked: bool = False
    prunable: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentHeartbeat:
    agent_id: str
    pid: int | None
    repo_path: str
    worktree_path: str
    branch: str
    head_commit: str
    is_dev: bool
    cwd: str
    task: str
    status: str
    last_seen: str
    uptime_seconds: int
    dirty_file_count: int
    dirty_files: list[str] = field(default_factory=list)
    recent_files: list[RecentFile] = field(default_factory=list)
    last_event: str = ""
    command: list[str] = field(default_factory=list)
    exit_code: int | None = None
    resume_target: str = ""
    window_group: str = ""
    tab_title: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recent_files"] = [item.to_dict() for item in self.recent_files]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentHeartbeat":
        recent_files = [
            item if isinstance(item, RecentFile) else RecentFile(**item)
            for item in payload.get("recent_files", [])
        ]
        return cls(
            agent_id=payload["agent_id"],
            pid=payload.get("pid"),
            repo_path=payload["repo_path"],
            worktree_path=payload["worktree_path"],
            branch=payload.get("branch", ""),
            head_commit=payload.get("head_commit", ""),
            is_dev=bool(payload.get("is_dev", False)),
            cwd=payload.get("cwd", payload["worktree_path"]),
            task=payload.get("task", ""),
            status=payload.get("status", "unknown"),
            last_seen=payload.get("last_seen", to_iso8601(utc_now())),
            uptime_seconds=int(payload.get("uptime_seconds", 0)),
            dirty_file_count=int(payload.get("dirty_file_count", len(payload.get("dirty_files", [])))),
            dirty_files=list(payload.get("dirty_files", [])),
            recent_files=recent_files,
            last_event=payload.get("last_event", ""),
            command=list(payload.get("command", [])),
            exit_code=payload.get("exit_code"),
            resume_target=payload.get("resume_target", ""),
            window_group=payload.get("window_group", ""),
            tab_title=payload.get("tab_title", ""),
        )


def normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())
