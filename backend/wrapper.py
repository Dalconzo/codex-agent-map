from __future__ import annotations

import argparse
import shutil
import signal
import subprocess
import time
from pathlib import Path

from .git_scan import get_branch, get_dirty_files, get_recent_files
from .heartbeat import describe_heartbeat_root, write_heartbeat
from .agent_state import build_agent_heartbeat


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a Codex session through the Mission Control wrapper.")
    parser.add_argument("--agent", required=True, help="Unique agent identifier.")
    parser.add_argument("--repo", required=True, help="Path to the repo root.")
    parser.add_argument("--worktree", required=True, help="Path to the worktree to run inside.")
    parser.add_argument("--task", required=True, help="Task description shown in the dashboard.")
    parser.add_argument("--heartbeat-root", default=None, help="Optional heartbeat directory override.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after '--'.")
    return parser


def validate_paths(repo: str, worktree: str) -> tuple[Path, Path]:
    repo_path = Path(repo).expanduser().resolve()
    worktree_path = Path(worktree).expanduser().resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")
    if not worktree_path.exists():
        raise FileNotFoundError(f"Worktree path does not exist: {worktree_path}")
    return repo_path, worktree_path


def resolve_launch_command(command: list[str]) -> list[str]:
    executable = command[0]
    if any(sep in executable for sep in ("\\", "/")):
        candidate = Path(executable).expanduser()
        if candidate.exists():
            command[0] = str(candidate.resolve())
            return command
        raise FileNotFoundError(f"Command executable does not exist: {candidate}")

    resolved = shutil.which(executable)
    if resolved:
        command[0] = resolved
        return command

    raise FileNotFoundError(
        f"Command executable was not found on PATH: {executable}. "
        "Try using the full executable path."
    )


def run_wrapped_command(args: argparse.Namespace) -> int:
    repo_path, worktree_path = validate_paths(args.repo, args.worktree)
    raw_command = list(args.command)
    if raw_command and raw_command[0] == "--":
        raw_command = raw_command[1:]
    if not raw_command:
        raise ValueError("No command provided. Use '-- <command>' after wrapper arguments.")
    launch_command = resolve_launch_command(list(raw_command))

    start_time = time.time()
    starting = build_agent_heartbeat(
        agent_id=args.agent,
        repo_path=repo_path,
        worktree_path=worktree_path,
        task=args.task,
        status="starting",
        last_event="wrapper starting process",
        command=raw_command,
    )
    write_heartbeat(starting, args.heartbeat_root)

    process = subprocess.Popen(launch_command, cwd=worktree_path)

    def _terminate_child(signum: int, _frame: object) -> None:
        if process.poll() is None:
            process.terminate()
        terminated = build_agent_heartbeat(
            agent_id=args.agent,
            repo_path=repo_path,
            worktree_path=worktree_path,
            task=args.task,
            status="killed",
            last_event=f"wrapper received signal {signum}",
            command=raw_command,
            pid=process.pid,
            exit_code=process.poll(),
        )
        terminated.uptime_seconds = max(int(time.time() - start_time), 0)
        write_heartbeat(terminated, args.heartbeat_root)
        raise SystemExit(130)

    signal.signal(signal.SIGINT, _terminate_child)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _terminate_child)

    while True:
        exit_code = process.poll()
        if exit_code is not None:
            status = "exited" if exit_code == 0 else "failed"
            final = build_agent_heartbeat(
                agent_id=args.agent,
                repo_path=repo_path,
                worktree_path=worktree_path,
                task=args.task,
                status=status,
                last_event=f"process exited with code {exit_code}",
                command=raw_command,
                pid=process.pid,
                exit_code=exit_code,
            )
            final.uptime_seconds = max(int(time.time() - start_time), 0)
            write_heartbeat(final, args.heartbeat_root)
            return exit_code

        heartbeat = build_agent_heartbeat(
            agent_id=args.agent,
            repo_path=repo_path,
            worktree_path=worktree_path,
            task=args.task,
            status="active",
            last_event="process alive",
            command=raw_command,
            pid=process.pid,
        )
        heartbeat.uptime_seconds = max(int(time.time() - start_time), 0)
        write_heartbeat(heartbeat, args.heartbeat_root)
        time.sleep(1.0)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_wrapped_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
