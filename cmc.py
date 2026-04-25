from __future__ import annotations

import argparse
import os


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex Mission Control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a wrapped Codex process")
    run_parser.add_argument("--agent", required=True)
    run_parser.add_argument("--repo", required=True)
    run_parser.add_argument("--worktree", required=True)
    run_parser.add_argument("--task", required=True)
    run_parser.add_argument("--heartbeat-root", default=None)
    run_parser.add_argument("wrapped_command", nargs=argparse.REMAINDER)

    register_parser = subparsers.add_parser("register", help="Register an agent session without wrapping Codex")
    register_parser.add_argument("--agent", required=True)
    register_parser.add_argument("--repo", required=True)
    register_parser.add_argument("--worktree", required=True)
    register_parser.add_argument("--task", required=True)
    register_parser.add_argument("--heartbeat-root", default=None)
    register_parser.add_argument("--status", default="active")
    register_parser.add_argument("--event", default="agent registered")
    register_parser.add_argument("--dev", action="store_true")

    task_parser = subparsers.add_parser("task", help="Update an agent task without restarting the session")
    task_parser.add_argument("--agent", required=True)
    task_parser.add_argument("--task", required=True)
    task_parser.add_argument("--heartbeat-root", default=None)
    task_parser.add_argument("--status", default=None)
    task_parser.add_argument("--event", default="task updated")

    ping_parser = subparsers.add_parser("ping", help="Refresh an existing agent heartbeat without changing the task")
    ping_parser.add_argument("--agent", required=True)
    ping_parser.add_argument("--heartbeat-root", default=None)
    ping_parser.add_argument("--status", default=None)
    ping_parser.add_argument("--event", default="heartbeat refreshed")

    stop_parser = subparsers.add_parser("stop", help="Mark an agent inactive or remove its heartbeat")
    stop_parser.add_argument("--agent", required=True)
    stop_parser.add_argument("--heartbeat-root", default=None)
    stop_parser.add_argument("--status", default="exited")
    stop_parser.add_argument("--event", default="agent stopped")
    stop_parser.add_argument("--remove", action="store_true")

    dash_parser = subparsers.add_parser("dashboard", help="Run the dashboard")
    dash_parser.add_argument("--repo", default=None)
    dash_parser.add_argument("--host", default="127.0.0.1")
    dash_parser.add_argument("--port", type=int, default=8765)
    dash_parser.add_argument("--heartbeat-root", default=None)
    dash_parser.add_argument("--browser", action="store_true")
    dash_parser.add_argument("--show-dev", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        from backend.wrapper import run_wrapped_command

        namespace = argparse.Namespace(
            agent=args.agent,
            repo=args.repo,
            worktree=args.worktree,
            task=args.task,
            heartbeat_root=args.heartbeat_root,
            command=args.wrapped_command,
        )
        return run_wrapped_command(namespace)

    if args.command == "register":
        from backend.session_commands import register_agent

        namespace = argparse.Namespace(
            agent=args.agent,
            repo=args.repo,
            worktree=args.worktree,
            task=args.task,
            heartbeat_root=args.heartbeat_root,
            status=args.status,
            event=args.event,
            dev=args.dev,
        )
        return register_agent(namespace)

    if args.command == "dashboard":
        if args.heartbeat_root:
            os.environ["CMC_HEARTBEAT_ROOT"] = args.heartbeat_root
        if args.browser:
            import uvicorn

            uvicorn.run("backend.server:app", host=args.host, port=args.port, reload=False)
            return 0

        from backend.terminal_dashboard import render_terminal_dashboard

        return render_terminal_dashboard(
            repo_path=args.repo,
            heartbeat_root=args.heartbeat_root,
            show_dev=args.show_dev,
        )

    if args.command == "task":
        from backend.task_update import update_agent_task

        namespace = argparse.Namespace(
            agent=args.agent,
            task=args.task,
            heartbeat_root=args.heartbeat_root,
            status=args.status,
            event=args.event,
        )
        return update_agent_task(namespace)

    if args.command == "ping":
        from backend.session_commands import ping_agent

        namespace = argparse.Namespace(
            agent=args.agent,
            heartbeat_root=args.heartbeat_root,
            status=args.status,
            event=args.event,
        )
        return ping_agent(namespace)

    if args.command == "stop":
        from backend.session_commands import stop_agent

        namespace = argparse.Namespace(
            agent=args.agent,
            heartbeat_root=args.heartbeat_root,
            status=args.status,
            event=args.event,
            remove=args.remove,
        )
        return stop_agent(namespace)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
