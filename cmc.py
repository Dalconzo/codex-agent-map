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
    register_parser.add_argument("--resume-target", default="")
    register_parser.add_argument("--window-group", default="")
    register_parser.add_argument("--tab-title", default="")

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

    layout_parser = subparsers.add_parser("layout", help="Save or restore a multi-agent terminal layout")
    layout_subparsers = layout_parser.add_subparsers(dest="layout_command", required=True)

    layout_save = layout_subparsers.add_parser("save", help="Capture the current agent heartbeat layout")
    layout_save.add_argument("--name", required=True)
    layout_save.add_argument("--repo", default=None)
    layout_save.add_argument("--heartbeat-root", default=None)
    layout_save.add_argument("--layout-root", default=None)
    layout_save.add_argument("--show-dev", action="store_true")

    layout_list = layout_subparsers.add_parser("list", help="List saved layouts")
    layout_list.add_argument("--layout-root", default=None)

    layout_show = layout_subparsers.add_parser("show", help="Show a saved layout")
    layout_show.add_argument("--name", required=True)
    layout_show.add_argument("--layout-root", default=None)

    layout_refresh = layout_subparsers.add_parser(
        "refresh",
        help="Refresh a saved layout from current heartbeats while preserving resume metadata",
    )
    layout_refresh.add_argument("--name", required=True)
    layout_refresh.add_argument("--repo", default=None)
    layout_refresh.add_argument("--heartbeat-root", default=None)
    layout_refresh.add_argument("--layout-root", default=None)
    layout_refresh.add_argument("--show-dev", action="store_true")

    layout_set = layout_subparsers.add_parser(
        "set",
        help="Set coordinator-owned metadata for one saved layout entry",
    )
    layout_set.add_argument("--name", required=True)
    layout_set.add_argument("--agent", required=True)
    layout_set.add_argument("--layout-root", default=None)
    layout_set.add_argument("--resume-target", default=None)
    layout_set.add_argument("--window-group", default=None)
    layout_set.add_argument("--tab-title", default=None)

    layout_restore = layout_subparsers.add_parser("restore", help="Restore a saved layout into Windows Terminal")
    layout_restore.add_argument("--name", required=True)
    layout_restore.add_argument("--layout-root", default=None)
    layout_restore.add_argument("--heartbeat-root", default=None)
    layout_restore.add_argument("--wt-path", default="wt")
    layout_restore.add_argument("--dry-run", action="store_true")
    layout_restore.add_argument("--allow-missing-resume", action="store_true")
    layout_restore.add_argument("--repo", default=None)

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
            resume_target=args.resume_target,
            window_group=args.window_group,
            tab_title=args.tab_title,
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

    if args.command == "layout":
        from backend.layouts import (
            list_layouts,
            refresh_layout,
            restore_layout,
            save_layout,
            set_layout_entry,
            show_layout,
        )

        if args.layout_command == "save":
            return save_layout(args)
        if args.layout_command == "list":
            return list_layouts(args)
        if args.layout_command == "show":
            return show_layout(args)
        if args.layout_command == "refresh":
            return refresh_layout(args)
        if args.layout_command == "set":
            return set_layout_entry(args)
        if args.layout_command == "restore":
            return restore_layout(args)
        parser.error(f"Unknown layout command: {args.layout_command}")
        return 2

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
