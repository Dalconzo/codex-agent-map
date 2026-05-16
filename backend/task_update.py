from __future__ import annotations

import argparse

from .agent_state import build_agent_heartbeat
from .heartbeat import read_heartbeat_for_agent, write_heartbeat


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update the task text for a running agent heartbeat.")
    parser.add_argument("--agent", required=True, help="Agent identifier.")
    parser.add_argument("--task", required=True, help="New task description.")
    parser.add_argument("--heartbeat-root", default=None, help="Optional heartbeat directory override.")
    parser.add_argument("--status", default=None, help="Optional explicit status override.")
    parser.add_argument("--event", default="task updated", help="Last-event text to record.")
    return parser


def update_agent_task(args: argparse.Namespace) -> int:
    heartbeat = read_heartbeat_for_agent(args.agent, args.heartbeat_root)
    task = args.task
    if args.status:
        status = args.status
    elif task.strip().lower() == "idle":
        status = "idle"
    else:
        status = "active"

    refreshed = build_agent_heartbeat(
        agent_id=heartbeat.agent_id,
        repo_path=heartbeat.repo_path,
        worktree_path=heartbeat.worktree_path,
        task=task,
        status=status,
        last_event=args.event,
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return update_agent_task(args)


if __name__ == "__main__":
    raise SystemExit(main())
