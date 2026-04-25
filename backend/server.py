from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .git_scan import get_branches, get_worktrees
from .heartbeat import describe_heartbeat_root, read_all_heartbeats
from .models import AgentHeartbeat, RepoTreeNode, normalize_path


app = FastAPI(title="Codex Mission Control")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


def get_heartbeat_root() -> str | None:
    return os.getenv("CMC_HEARTBEAT_ROOT")


def compute_agent_status(heartbeat: AgentHeartbeat) -> str:
    if heartbeat.status in {"exited", "failed", "killed"}:
        return heartbeat.status
    try:
        last_seen = datetime.fromisoformat(heartbeat.last_seen.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    age = (datetime.now(UTC) - last_seen).total_seconds()
    if age < 5:
        return "active"
    if age <= 30:
        return "delayed"
    return "stale"


def compute_age_seconds(last_seen: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(int((datetime.now(UTC) - parsed).total_seconds()), 0)


def locate_agent(heartbeat: AgentHeartbeat) -> str:
    worktree_path = Path(heartbeat.worktree_path)
    candidate_paths: list[str] = []
    candidate_paths.extend(heartbeat.dirty_files)
    candidate_paths.extend(item.path for item in heartbeat.recent_files)
    for relative_path in candidate_paths:
        full_path = worktree_path / relative_path
        if full_path.exists():
            return normalize_path(full_path)
    return normalize_path(heartbeat.cwd or heartbeat.worktree_path)


def build_events(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for agent in sorted(agents, key=lambda item: item["last_seen"], reverse=True):
        branch = agent.get("branch") or "(detached)"
        events.append(
            {
                "timestamp": agent["last_seen"],
                "message": f"{agent['agent_id']} {agent['status']} in {branch}",
            }
        )
        for recent in agent.get("recent_files", [])[:3]:
            events.append(
                {
                    "timestamp": recent["modified_at"],
                    "message": f"{agent['agent_id']} touched {recent['path']}",
                }
            )
    return events[:50]


def infer_repo_paths(agents: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for agent in agents:
        repo_path = agent.get("repo_path")
        if repo_path and repo_path not in seen:
            seen.append(repo_path)
    return seen


def summarize_statuses(agents: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for agent in agents:
        status = agent["status"]
        summary[status] = summary.get(status, 0) + 1
    return summary


def build_agent_payloads(heartbeats: list[AgentHeartbeat]) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = []
    for heartbeat in heartbeats:
        payload = heartbeat.to_dict()
        payload["head_commit"] = heartbeat.head_commit
        payload["is_dev"] = heartbeat.is_dev
        payload["status"] = compute_agent_status(heartbeat)
        payload["heartbeat_age_seconds"] = compute_age_seconds(heartbeat.last_seen)
        payload["location_path"] = locate_agent(heartbeat)
        agents.append(payload)
    agents.sort(key=lambda item: item.get("last_seen", ""), reverse=True)
    return agents


def merge_worktree_payloads(target_repo: str | None, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    if target_repo:
        for worktree in get_worktrees(target_repo):
            payload = worktree.to_dict()
            payload["name"] = Path(worktree.path).name
            payload["agents"] = []
            payloads[worktree.path] = payload

    for agent in agents:
        worktree_path = normalize_path(agent["worktree_path"])
        worktree_payload = payloads.setdefault(
            worktree_path,
            {
                "path": worktree_path,
                "head": None,
                "branch": agent.get("branch") or None,
                "is_detached": not bool(agent.get("branch")),
                "is_bare": False,
                "is_locked": False,
                "prunable": None,
                "name": Path(worktree_path).name,
                "agents": [],
            },
        )
        worktree_payload["agents"].append(agent)
        if not worktree_payload.get("branch") and agent.get("branch"):
            worktree_payload["branch"] = agent["branch"]

    worktrees = sorted(payloads.values(), key=lambda item: item["path"].lower())
    for worktree in worktrees:
        worktree["agent_count"] = len(worktree["agents"])
        worktree["dirty_file_count"] = sum(agent.get("dirty_file_count", 0) for agent in worktree["agents"])
        worktree["status_summary"] = summarize_statuses(worktree["agents"])
    return worktrees


def build_branch_tree(repo_path: str | None, worktrees: list[dict[str, Any]], agents: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not repo_path:
        return None
    root = RepoTreeNode(
        name=Path(repo_path).name,
        path=repo_path,
        node_type="repo",
        meta={"repo_path": repo_path},
    )

    all_branches = set(get_branches(repo_path))
    all_branches.update(worktree.get("branch") for worktree in worktrees if worktree.get("branch"))
    all_branches.update(agent.get("branch") for agent in agents if agent.get("branch"))

    branch_agents: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        branch_name = agent.get("branch") or "(detached)"
        branch_agents.setdefault(branch_name, []).append(agent)
        all_branches.add(branch_name)

    node_index: dict[str, RepoTreeNode] = {}
    for branch_name in sorted(all_branches, key=str.lower):
        if not branch_name:
            continue
        parts = branch_name.split("/") if branch_name != "(detached)" else [branch_name]
        parent = root
        prefix_parts: list[str] = []
        for index, part in enumerate(parts):
            prefix_parts.append(part)
            key = "/".join(prefix_parts)
            node = node_index.get(key)
            if node is None:
                node_type = "branch_group" if index < len(parts) - 1 else "branch"
                node = RepoTreeNode(
                    name=part,
                    path=key,
                    node_type=node_type,
                    meta={"branch_name": key if node_type == "branch" else None},
                )
                parent.children.append(node)
                node_index[key] = node
            parent = node

    def decorate_branch_node(node: RepoTreeNode) -> None:
        for child in node.children:
            decorate_branch_node(child)
        if node.node_type == "branch":
            node.meta["agents"] = branch_agents.get(node.path, [])
            node.meta["agent_ids"] = [agent["agent_id"] for agent in node.meta["agents"]]
            node.meta["dirty_file_count"] = sum(agent.get("dirty_file_count", 0) for agent in node.meta["agents"])
            node.meta["status_summary"] = summarize_statuses(node.meta["agents"])
        elif node.node_type == "branch_group":
            descendants = [child.meta.get("agent_ids", []) for child in node.children]
            node.meta["agent_ids"] = [agent_id for group in descendants for agent_id in group]
            dirty_counts = [child.meta.get("dirty_file_count", 0) for child in node.children]
            node.meta["dirty_file_count"] = sum(dirty_counts)
            summary: dict[str, int] = {}
            for child in node.children:
                for key, value in child.meta.get("status_summary", {}).items():
                    summary[key] = summary.get(key, 0) + value
            node.meta["status_summary"] = summary

    decorate_branch_node(root)
    return root.to_dict()


def build_state(repo_path: str | None = None, worktree_path: str | None = None) -> dict[str, Any]:
    root = get_heartbeat_root()
    heartbeats = read_all_heartbeats(root)
    agents = build_agent_payloads(heartbeats)
    target_repo = repo_path or next(iter(infer_repo_paths(agents)), None)
    worktree_payload = merge_worktree_payloads(target_repo, agents)
    repo_tree = build_branch_tree(target_repo, worktree_payload, agents)

    summary = {
        "agent_count": len(agents),
        "worktree_count": len(worktree_payload),
        "status_summary": summarize_statuses(agents),
    }

    return {
        "agents": agents,
        "worktrees": worktree_payload,
        "repo_tree": repo_tree,
        "events": build_events(agents),
        "heartbeat_root": describe_heartbeat_root(root),
        "repo_path": target_repo,
        "summary": summary,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/agents")
def api_agents() -> list[dict[str, Any]]:
    return build_state()["agents"]


@app.get("/api/worktrees")
def api_worktrees(repo: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return build_state(repo_path=repo)["worktrees"]


@app.get("/api/tree")
def api_tree(worktree: str = Query(...)) -> dict[str, Any]:
    return build_state(repo_path=worktree).get("repo_tree") or {}


@app.get("/api/state")
def api_state(repo: str | None = Query(default=None), worktree: str | None = Query(default=None)) -> dict[str, Any]:
    return build_state(repo_path=repo, worktree_path=worktree)


@app.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(build_state())
            await asyncio.sleep(1.0)
    finally:
        await websocket.close()
