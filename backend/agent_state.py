from __future__ import annotations

from pathlib import Path

from .git_scan import get_branch, get_dirty_files, get_head_commit, get_recent_files
from .models import AgentHeartbeat, normalize_path, to_iso8601, utc_now


def build_agent_heartbeat(
    agent_id: str,
    repo_path: str | Path,
    worktree_path: str | Path,
    task: str,
    status: str,
    last_event: str,
    command: list[str] | None = None,
    pid: int | None = None,
    exit_code: int | None = None,
    is_dev: bool = False,
) -> AgentHeartbeat:
    repo = Path(repo_path).expanduser().resolve()
    worktree = Path(worktree_path).expanduser().resolve()
    dirty_files = get_dirty_files(str(worktree))
    return AgentHeartbeat(
        agent_id=agent_id,
        pid=pid,
        repo_path=normalize_path(repo),
        worktree_path=normalize_path(worktree),
        branch=get_branch(str(worktree)),
        head_commit=get_head_commit(str(worktree)),
        is_dev=is_dev,
        cwd=normalize_path(worktree),
        task=task,
        status=status,
        last_seen=to_iso8601(utc_now()),
        uptime_seconds=0,
        dirty_file_count=len(dirty_files),
        dirty_files=dirty_files,
        recent_files=get_recent_files(str(worktree)),
        last_event=last_event,
        command=list(command or []),
        exit_code=exit_code,
    )
