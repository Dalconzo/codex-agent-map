from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from .heartbeat import describe_heartbeat_root, read_all_heartbeats


console = Console()
LANE_STYLES = [
    "bright_cyan",
    "bright_magenta",
    "bright_green",
    "bright_yellow",
    "bright_blue",
    "bright_red",
]


def compute_agent_status(current_status: str, task: str) -> str:
    status = (current_status or "").strip().lower()
    task_text = (task or "").strip().lower()
    if status:
        return status
    if task_text == "idle":
        return "idle"
    return "active"


def status_tone(status: str) -> str:
    if status == "active":
        return "green"
    if status == "idle":
        return "bright_black"
    if status in {"failed", "killed"}:
        return "red"
    if status == "exited":
        return "bright_black"
    if status in {"blocked", "paused"}:
        return "yellow"
    return "cyan"


def run_git(repo_path: str, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def infer_repo_path(explicit_repo: str | None, heartbeat_root: str | None) -> str:
    if explicit_repo:
        return str(Path(explicit_repo).expanduser().resolve())
    for heartbeat in read_all_heartbeats(heartbeat_root):
        if heartbeat.repo_path:
            return heartbeat.repo_path
    return str(Path.cwd())


def _parse_ref_count(decorations: str) -> int:
    text = decorations.strip()
    if not text:
        return 0
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    if not text:
        return 0
    return text.count(",") + 1


def get_visible_heartbeats(heartbeat_root: str | None, show_dev: bool) -> list:
    heartbeats = read_all_heartbeats(heartbeat_root)
    if show_dev:
        return heartbeats
    return [heartbeat for heartbeat in heartbeats if not heartbeat.is_dev]


def get_agent_commit_map(heartbeat_root: str | None, show_dev: bool = False) -> dict[str, list[dict[str, str]]]:
    commit_map: dict[str, list[dict[str, str]]] = {}
    for heartbeat in get_visible_heartbeats(heartbeat_root, show_dev):
        status = compute_agent_status(heartbeat.status, heartbeat.task)
        commit = (heartbeat.head_commit or "").strip().lower()
        if not commit:
            try:
                commit = run_git(heartbeat.worktree_path, "rev-parse", "--short=12", "HEAD").strip().lower()
            except subprocess.CalledProcessError:
                continue
        commit_map.setdefault(commit, []).append(
            {
                "agent_id": heartbeat.agent_id,
                "status": status,
                "task": heartbeat.task.strip() or status,
                "branch": heartbeat.branch or "(detached)",
            }
        )
    return commit_map


def _lane_style(index: int) -> str:
    return LANE_STYLES[index % len(LANE_STYLES)]


def _render_graph_prefix(prefix: str) -> Text:
    rendered = Text()
    for idx, char in enumerate(prefix):
        style = _lane_style(idx)
        if char in {"|", "*", "/", "\\", "_"}:
            rendered.append(char, style=style)
        else:
            rendered.append(char)
    return rendered


def _build_commit_text(
    graph_prefix: str,
    short_commit: str,
    decorations: str,
    subject: str,
    suppress_decorations: bool = False,
) -> Text:
    ref_count = _parse_ref_count(decorations)
    line = _render_graph_prefix(graph_prefix)
    line.append(short_commit, style="bold white")
    if ref_count <= 1:
        if subject.strip():
            line.append(f" {subject.strip()}", style="white")
        if decorations.strip() and not suppress_decorations:
            line.append(f" {decorations.strip()}", style="bright_black")
    return line


def _append_agent_annotations(line: Text, matches: list[dict[str, str]]) -> None:
    for agent in sorted(matches, key=lambda item: (item["branch"], item["agent_id"])):
        tone = status_tone(agent["status"])
        label = agent["task"] if agent["status"] not in {"failed", "killed", "exited"} else agent["status"]
        branch = agent["branch"] or "(detached)"
        line.append("  ")
        line.append(branch, style="bright_black")
        line.append(" => ", style="bright_black")
        line.append(f"[{agent['agent_id']}:{label}]", style=tone)


def build_graph_lines(repo_path: str, max_lines: int, heartbeat_root: str | None, show_dev: bool) -> list[Text]:
    pretty = "__CMC__%h__DEC__%d__SUBJ__%s"
    try:
        output = run_git(
            repo_path,
            "log",
            "--graph",
            "--all",
            "--decorate=short",
            "--date-order",
            f"--pretty=format:{pretty}",
            f"-n{max_lines}",
        )
    except subprocess.CalledProcessError as exc:
        return [f"[red]git log failed: {exc}[/red]"]

    commit_map = get_agent_commit_map(heartbeat_root, show_dev=show_dev)
    lines: list[Text] = []
    for raw_line in output.splitlines():
        commit = None
        visible_line = Text(raw_line)
        if "__CMC__" in raw_line:
            graph_prefix, _, suffix = raw_line.partition("__CMC__")
            short_commit, _, remainder = suffix.partition("__DEC__")
            decorations, _, subject = remainder.partition("__SUBJ__")
            commit = short_commit.lower()
            matches = commit_map.get(commit) or []
            if not matches and len(commit) == 7:
                matches = [
                    agent
                    for full_commit, agents in commit_map.items()
                    if full_commit.startswith(commit)
                    for agent in agents
                ]
            visible_line = _build_commit_text(
                graph_prefix,
                short_commit,
                decorations,
                subject,
                suppress_decorations=bool(matches),
            )
        else:
            visible_line = _render_graph_prefix(raw_line)
        if commit:
            if matches:
                _append_agent_annotations(visible_line, matches)
        lines.append(visible_line)
    return lines


def build_frame(repo_path: str, heartbeat_root: str | None, show_dev: bool) -> Group:
    size = shutil.get_terminal_size(fallback=(140, 40))
    graph_height = max(size.lines - 4, 10)
    graph_lines = build_graph_lines(repo_path, graph_height, heartbeat_root, show_dev)
    visible_map = get_agent_commit_map(heartbeat_root, show_dev=show_dev)
    all_map = get_agent_commit_map(heartbeat_root, show_dev=True)
    active_agents = sum(len(agents) for agents in visible_map.values())
    hidden_dev_agents = max(sum(len(agents) for agents in all_map.values()) - active_agents, 0)
    title_text = f" codex mission control  repo:{repo_path}  agents:{active_agents} "
    if hidden_dev_agents and not show_dev:
        title_text += f" hidden_dev:{hidden_dev_agents} "
    title = Text(title_text, style="cyan")
    root_line = Text(f" heartbeat_root:{describe_heartbeat_root(heartbeat_root)} ", style="bright_black")
    divider = Text("-" * min(size.columns, max(20, size.columns)), style="bright_black")
    graph = graph_lines[:graph_height]
    return Group(title, root_line, divider, *graph)


def render_terminal_dashboard(
    repo_path: str | None = None,
    heartbeat_root: str | None = None,
    interval: float = 1.0,
    show_dev: bool = False,
) -> int:
    resolved_repo = infer_repo_path(repo_path, heartbeat_root)
    try:
        with Live(
            build_frame(resolved_repo, heartbeat_root, show_dev),
            console=console,
            refresh_per_second=max(1, int(1 / interval)),
            screen=True,
        ) as live:
            while True:
                live.update(build_frame(resolved_repo, heartbeat_root, show_dev))
                time.sleep(interval)
    except KeyboardInterrupt:
        return 0
