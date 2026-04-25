# Codex Mission Control

Local wrapper and live dashboard for monitoring multiple Codex sessions across Git worktrees.

`specs.txt` is the source spec. Beads is initialized locally in `.beads/`.

## Current MVP

- `cmc register` records agent/task/worktree metadata without wrapping Codex
- `cmc ping` refreshes an existing heartbeat without changing the task
- `cmc task` updates the top-level task text when the assignment materially changes
- `cmc stop` marks an agent stopped or removes its heartbeat
- `cmc dashboard` runs a FastAPI server with:
  - `GET /api/agents`
  - `GET /api/worktrees`
  - `GET /api/tree?worktree=...`
  - `GET /api/state`
  - `WS /ws/state`
- `/` serves a live browser dashboard with:
  - agent list
  - worktree list
  - focused repo tree
  - details panel
  - event log

## Run It

Register an agent session without wrapping Codex:

```powershell
python .\cmc.py register --agent deploy --repo C:\qc --worktree C:\QC-deploy --task "Deploy work"
```

Update a running agent's task without restarting it:

```powershell
python .\cmc.py task --agent deploy --task "Investigating trace upload failures"
```

Refresh the heartbeat without changing the task:

```powershell
python .\cmc.py ping --agent deploy
```

Stop showing an agent:

```powershell
python .\cmc.py stop --agent deploy --remove
```

Start the dashboard:

```powershell
python .\cmc.py dashboard
```

Then open:

```text
http://127.0.0.1:8765
```

Heartbeat files are written to:

```text
%USERPROFILE%\.codex-mission-control\heartbeats
```

## Layout

```text
backend/
  heartbeat.py
  git_scan.py
  models.py
  server.py
  wrapper.py
frontend/
  index.html
  app.js
  styles.css
heartbeats/
cmc.py
specs.txt
```
