from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CHECKLIST_PATH = Path(__file__).resolve().parent.parent / "handoffs" / "next-deployment-checklist.md"
CHECKLIST_ITEM_RE = re.compile(
    r"^\s*-\s*\[(?P<marker>[ xX~!\?])\]\s*"
    r"(?:`(?P<bead>[^`]+)`\s*)?"
    r"(?:\[(?P<owner>[^\[\]]+)\]\s*)?"
    r"(?P<summary>.+?)\s*$"
)

MARKER_TO_STATUS = {
    " ": "pending",
    "x": "complete",
    "X": "complete",
    "~": "in_progress",
    "!": "blocked",
    "?": "conditional",
}


def load_deployment_checklist(path: Path | None = None) -> dict[str, Any]:
    target = path or CHECKLIST_PATH
    if not target.exists():
        return {
            "title": "Next deployment checklist",
            "path": str(target),
            "updated_at": None,
            "items": [],
        }

    lines = target.read_text(encoding="utf-8").splitlines()
    title = "Next deployment checklist"
    items: list[dict[str, Any]] = []
    current_note_lines: list[str] = []

    def flush_note() -> None:
        if not items:
            current_note_lines.clear()
            return
        note = " ".join(line.strip() for line in current_note_lines if line.strip())
        if note:
            items[-1]["note"] = note
        current_note_lines.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip() or title
            continue

        match = CHECKLIST_ITEM_RE.match(line)
        if match:
            flush_note()
            marker = match.group("marker")
            summary = match.group("summary").strip()
            items.append(
                {
                    "marker": marker,
                    "status": MARKER_TO_STATUS.get(marker, "pending"),
                    "bead_id": (match.group("bead") or "").strip(),
                    "owner": (match.group("owner") or "").strip(),
                    "summary": summary,
                    "note": "",
                }
            )
            continue

        if items and stripped:
            current_note_lines.append(stripped)

    flush_note()

    return {
        "title": title,
        "path": str(target),
        "updated_at": target.stat().st_mtime,
        "items": items,
    }
