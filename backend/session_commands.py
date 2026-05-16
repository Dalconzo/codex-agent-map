from __future__ import annotations

import argparse
from pathlib import Path

from .agent_state import build_agent_heartbeat
from .heartbeat import read_heartbeat_for_agent, remove_heartbeat, write_heartbeat


def _validate_paths(repo: str, worktree: str) -> tuple[Path, Path]:
    repo_path = Path(repo).expanduser().resolve()
    worktree_path = Path(worktree).expanduser().resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")
    if not worktree_path.exists():
        raise FileNotFoundError(f"Worktree path does not exist: {worktree_path}")
    return repo_path, worktree_path


def register_agent(args: argparse.Namespace) -> int:
    repo_path, worktree_path = _validate_paths(args.repo, args.worktree)
    heartbeat = build_agent_heartbeat(
        agent_id=args.agent,
        repo_path=repo_path,
        worktree_path=worktree_path,
        task=args.task,
        status=args.status,
        last_event=args.event,
        command=[],
        pid=None,
        is_dev=args.dev,
        resume_target=getattr(args, "resume_target", "") or "",
        window_group=getattr(args, "window_group", "") or "",
        tab_title=getattr(args, "tab_title", "") or "",
    )
    write_heartbeat(heartbeat, args.heartbeat_root)
    return 0


def ping_agent(args: argparse.Namespace) -> int:
    heartbeat = read_heartbeat_for_agent(args.agent, args.heartbeat_root)
    heartbeat.status = args.status or heartbeat.status or "active"
    heartbeat.last_event = args.event
    refreshed = build_agent_heartbeat(
        agent_id=heartbeat.agent_id,
        repo_path=heartbeat.repo_path,
        worktree_path=heartbeat.worktree_path,
        task=heartbeat.task,
        status=heartbeat.status,
        last_event=heartbeat.last_event,
        command=heartbeat.command,
        pid=heartbeat.pid,
        exit_code=heartbeat.exit_code,
        is_dev=heartbeat.is_dev,
        resume_target=heartbeat.resume_target,
        window_group=heartbeat.window_group,
        tab_title=heartbeat.tab_title,
    )
    refreshed.uptime_seconds = heartbeat.uptime_seconds
    write_heartbeat(refreshed, args.heartbeat_root)
    return 0


def stop_agent(args: argparse.Namespace) -> int:
    heartbeat = read_heartbeat_for_agent(args.agent, args.heartbeat_root)
    heartbeat.status = args.status
    heartbeat.last_event = args.event
    write_heartbeat(heartbeat, args.heartbeat_root)
    if args.remove:
        remove_heartbeat(args.agent, args.heartbeat_root)
    return 0
