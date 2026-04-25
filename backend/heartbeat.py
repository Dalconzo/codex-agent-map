from __future__ import annotations

import json
from pathlib import Path

from .models import AgentHeartbeat, normalize_path


DEFAULT_HEARTBEAT_ROOT = Path.home() / ".codex-mission-control" / "heartbeats"


def get_heartbeat_root(root: str | Path | None = None) -> Path:
    path = Path(root).expanduser() if root else DEFAULT_HEARTBEAT_ROOT
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def heartbeat_path(agent_id: str, root: str | Path | None = None) -> Path:
    return get_heartbeat_root(root) / f"{agent_id}.json"


def write_heartbeat(heartbeat: AgentHeartbeat, root: str | Path | None = None) -> Path:
    path = heartbeat_path(heartbeat.agent_id, root)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(heartbeat.to_dict(), indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path


def read_heartbeat(path: str | Path) -> AgentHeartbeat:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return AgentHeartbeat.from_dict(payload)


def read_heartbeat_for_agent(agent_id: str, root: str | Path | None = None) -> AgentHeartbeat:
    return read_heartbeat(heartbeat_path(agent_id, root))


def list_heartbeat_files(root: str | Path | None = None) -> list[Path]:
    heartbeat_root = get_heartbeat_root(root)
    return sorted(heartbeat_root.glob("*.json"))


def read_all_heartbeats(root: str | Path | None = None) -> list[AgentHeartbeat]:
    heartbeats: list[AgentHeartbeat] = []
    for path in list_heartbeat_files(root):
        try:
            heartbeats.append(read_heartbeat(path))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return heartbeats


def remove_heartbeat(agent_id: str, root: str | Path | None = None) -> None:
    path = heartbeat_path(agent_id, root)
    if path.exists():
        path.unlink()


def describe_heartbeat_root(root: str | Path | None = None) -> str:
    return normalize_path(get_heartbeat_root(root))
