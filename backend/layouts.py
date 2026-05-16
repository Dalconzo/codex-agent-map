from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from collections import defaultdict
from pathlib import Path

from .heartbeat import read_all_heartbeats
from .models import normalize_path, to_iso8601, utc_now

DEFAULT_LAYOUT_ROOT = Path.home() / ".codex-mission-control" / "layouts"


def get_layout_root(root: str | Path | None = None) -> Path:
    if root:
        return Path(root).expanduser().resolve()
    return DEFAULT_LAYOUT_ROOT


def layout_path(name: str, root: str | Path | None = None) -> Path:
    safe_name = name.strip()
    if not safe_name:
        raise ValueError("Layout name cannot be empty.")
    return get_layout_root(root) / f"{safe_name}.json"


def _load_layout(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _maybe_existing_layout(name: str, root: str | Path | None) -> dict | None:
    path = layout_path(name, root)
    if not path.exists():
        return None
    return _load_layout(path)


def _filter_heartbeats(repo: str | None, heartbeat_root: str | None, show_dev: bool) -> list:
    repo_path = normalize_path(repo) if repo else None
    heartbeats = []
    for heartbeat in read_all_heartbeats(heartbeat_root):
        if not show_dev and heartbeat.is_dev:
            continue
        if repo_path and normalize_path(heartbeat.repo_path) != repo_path:
            continue
        heartbeats.append(heartbeat)
    heartbeats.sort(key=lambda item: (item.window_group or "main", item.agent_id))
    return heartbeats


def _entry_key_by_worktree(entry: dict) -> str:
    worktree = entry.get("worktree_path", "")
    return normalize_path(worktree) if worktree else ""


def _existing_layout_maps(layout: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    entries = list(layout.get("agents", []))
    by_agent = {item["agent_id"]: item for item in entries if item.get("agent_id")}
    by_worktree = {_entry_key_by_worktree(item): item for item in entries if item.get("worktree_path")}
    return by_agent, by_worktree


def _resolve_existing_entry(existing_by_agent: dict[str, dict], existing_by_worktree: dict[str, dict], heartbeat) -> dict:
    existing = existing_by_agent.get(heartbeat.agent_id)
    if existing:
        return existing
    return existing_by_worktree.get(normalize_path(heartbeat.worktree_path), {})


def _merge_entry(existing_entries: dict[str, dict], heartbeat) -> dict:
    existing = existing_entries.get(heartbeat.agent_id, {})
    return {
        "agent_id": heartbeat.agent_id,
        "repo_path": normalize_path(heartbeat.repo_path),
        "worktree_path": normalize_path(heartbeat.worktree_path),
        "task": heartbeat.task,
        "status": heartbeat.status,
        "is_dev": heartbeat.is_dev,
        "resume_target": heartbeat.resume_target or existing.get("resume_target", ""),
        "window_group": heartbeat.window_group or existing.get("window_group", "main"),
        "tab_title": heartbeat.tab_title or existing.get("tab_title", heartbeat.agent_id),
    }


def _merge_heartbeat_into_entry(existing: dict, heartbeat) -> dict:
    return {
        "agent_id": heartbeat.agent_id,
        "repo_path": normalize_path(heartbeat.repo_path),
        "worktree_path": normalize_path(heartbeat.worktree_path),
        "task": heartbeat.task,
        "status": heartbeat.status,
        "is_dev": heartbeat.is_dev,
        "resume_target": existing.get("resume_target", ""),
        "window_group": existing.get("window_group", "main"),
        "tab_title": existing.get("tab_title", heartbeat.agent_id),
    }


def _write_layout_payload(name: str, root: str | Path | None, payload: dict) -> Path:
    path = layout_path(name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def save_layout(args: argparse.Namespace) -> int:
    heartbeats = _filter_heartbeats(args.repo, args.heartbeat_root, args.show_dev)
    if not heartbeats:
        raise SystemExit("No matching heartbeats found to save.")

    existing_layout = _maybe_existing_layout(args.name, args.layout_root) or {}
    existing_entries, _ = _existing_layout_maps(existing_layout)
    agents = [_merge_entry(existing_entries, heartbeat) for heartbeat in heartbeats]
    repo_path = normalize_path(args.repo) if args.repo else normalize_path(heartbeats[0].repo_path)
    payload = {
        "name": args.name,
        "saved_at": to_iso8601(utc_now()),
        "repo_path": repo_path,
        "agents": agents,
    }

    path = _write_layout_payload(args.name, args.layout_root, payload)
    print(str(path))
    return 0


def list_layouts(args: argparse.Namespace) -> int:
    root = get_layout_root(args.layout_root)
    if not root.exists():
        return 0
    for path in sorted(root.glob("*.json")):
        print(path.stem)
    return 0


def show_layout(args: argparse.Namespace) -> int:
    path = layout_path(args.name, args.layout_root)
    print(path.read_text(encoding="utf-8"))
    return 0


def refresh_layout(args: argparse.Namespace) -> int:
    path = layout_path(args.name, args.layout_root)
    layout = _load_layout(path)
    existing_by_agent, existing_by_worktree = _existing_layout_maps(layout)
    heartbeats = _filter_heartbeats(args.repo or layout.get("repo_path"), args.heartbeat_root, args.show_dev)
    refreshed_agents: list[dict] = []
    matched_existing_ids: set[str] = set()

    for heartbeat in heartbeats:
        existing = _resolve_existing_entry(existing_by_agent, existing_by_worktree, heartbeat)
        if existing:
            matched_existing_ids.add(existing["agent_id"])
        refreshed_agents.append(_merge_heartbeat_into_entry(existing, heartbeat))

    for entry in layout.get("agents", []):
        if entry.get("agent_id") not in matched_existing_ids and entry.get("agent_id") not in {
            item["agent_id"] for item in refreshed_agents
        }:
            refreshed_agents.append(entry)

    refreshed_agents.sort(key=lambda item: (item.get("window_group") or "main", item["agent_id"]))
    payload = {
        "name": args.name,
        "saved_at": to_iso8601(utc_now()),
        "repo_path": normalize_path(args.repo) if args.repo else layout.get("repo_path", ""),
        "agents": refreshed_agents,
    }
    updated_path = _write_layout_payload(args.name, args.layout_root, payload)
    print(str(updated_path))
    return 0


def set_layout_entry(args: argparse.Namespace) -> int:
    path = layout_path(args.name, args.layout_root)
    layout = _load_layout(path)
    entries = list(layout.get("agents", []))
    target = next((item for item in entries if item.get("agent_id") == args.agent), None)
    if target is None:
        raise SystemExit(f"Layout entry not found for agent: {args.agent}")

    if args.resume_target is not None:
        target["resume_target"] = args.resume_target
    if args.window_group is not None:
        target["window_group"] = args.window_group
    if args.tab_title is not None:
        target["tab_title"] = args.tab_title

    entries.sort(key=lambda item: (item.get("window_group") or "main", item["agent_id"]))
    layout["agents"] = entries
    layout["saved_at"] = to_iso8601(utc_now())
    updated_path = _write_layout_payload(args.name, args.layout_root, layout)
    print(str(updated_path))
    return 0


def _powershell_resume_command(entry: dict, heartbeat_root: str | None) -> str:
    worktree = entry["worktree_path"]
    repo = entry["repo_path"]
    task = entry["task"]
    agent = entry["agent_id"]
    resume_target = (entry.get("resume_target") or "").strip()
    cmc_path = str((Path(__file__).resolve().parent.parent / "cmc.py"))
    quoted = lambda value: value.replace("'", "''")

    register_parts = [
        "python",
        cmc_path,
        "register",
        "--agent",
        agent,
        "--repo",
        repo,
        "--worktree",
        worktree,
        "--task",
        task,
    ]
    if heartbeat_root:
        register_parts.extend(["--heartbeat-root", heartbeat_root])
    if resume_target:
        register_parts.extend(["--resume-target", resume_target])
    if entry.get("window_group"):
        register_parts.extend(["--window-group", entry["window_group"]])
    if entry.get("tab_title"):
        register_parts.extend(["--tab-title", entry["tab_title"]])
    if entry.get("is_dev"):
        register_parts.append("--dev")

    command_parts = [
        f"Set-Location '{quoted(worktree)}'",
        " ".join(shlex.quote(part) for part in register_parts),
    ]
    if resume_target:
        command_parts.append(" ".join(shlex.quote(part) for part in ["codex", "resume", resume_target]))
    else:
        command_parts.append("Write-Host 'No resume target configured for this agent layout entry.' -ForegroundColor Yellow")
    return "; ".join(command_parts)


def _build_terminal_invocations(layout: dict, heartbeat_root: str | None, wt_path: str, allow_missing_resume: bool) -> list[list[str]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    missing_resume: list[str] = []
    for entry in layout.get("agents", []):
        grouped[entry.get("window_group") or "main"].append(entry)
        if not allow_missing_resume and not (entry.get("resume_target") or "").strip():
            missing_resume.append(entry["agent_id"])

    if missing_resume:
        raise SystemExit(
            "Layout entries are missing resume targets: "
            + ", ".join(sorted(missing_resume))
            + ". Add --resume-target when agents register, or restore with --allow-missing-resume."
        )

    invocations: list[list[str]] = []
    for window_group, entries in sorted(grouped.items()):
        args: list[str] = [wt_path, "-w", "new"]
        for index, entry in enumerate(entries):
            if index > 0:
                args.append(";")
            title = entry.get("tab_title") or entry["agent_id"]
            shell_command = _powershell_resume_command(entry, heartbeat_root)
            args.extend(
                [
                    "new-tab",
                    "--title",
                    title,
                    "powershell",
                    "-NoExit",
                    "-Command",
                    shell_command,
                ]
            )
        invocations.append(args)
    return invocations


def restore_layout(args: argparse.Namespace) -> int:
    path = layout_path(args.name, args.layout_root)
    layout = _load_layout(path)
    if args.repo:
        layout["repo_path"] = normalize_path(args.repo)

    invocations = _build_terminal_invocations(
        layout=layout,
        heartbeat_root=args.heartbeat_root,
        wt_path=args.wt_path,
        allow_missing_resume=args.allow_missing_resume,
    )

    if args.dry_run:
        for invocation in invocations:
            print(subprocess.list2cmdline(invocation))
        return 0

    for invocation in invocations:
        subprocess.Popen(invocation)
    return 0
