# Codex Mission Control

Local wrapper and live dashboard for monitoring multiple Codex sessions across Git worktrees.

`specs.txt` is the source spec. Beads is initialized locally in `.beads/`.

## Current MVP

- `cmc register` records agent/task/worktree metadata without wrapping Codex
- `cmc ping` refreshes an existing heartbeat without changing the task
- `cmc task` updates the top-level task text when the assignment materially changes
- `cmc stop` marks an agent stopped or removes its heartbeat
- `cmc layout save` captures the current multi-agent arrangement into a reusable local recovery file
- `cmc layout refresh` updates a saved layout from current heartbeats without overwriting resume metadata
- `cmc layout set` lets the coordinator rebind one agent's saved resume metadata directly
- `cmc layout restore` reopens Windows Terminal tabs and resumes Codex sessions from that saved layout
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

Register an agent with recovery metadata so it can be resumed later:

```powershell
python .\cmc.py register --agent deploy --repo C:\qc --worktree C:\QC-deploy --task "Deploy work" --resume-target 01JXYZABC123 --window-group qc-core --tab-title deploy
```

Save the current project layout:

```powershell
python .\cmc.py layout save --name qc --repo C:\qc
```

List saved layouts:

```powershell
python .\cmc.py layout list
```

Inspect a saved layout:

```powershell
python .\cmc.py layout show --name qc
```

Refresh a saved layout from current heartbeats while preserving saved resume metadata:

```powershell
python .\cmc.py layout refresh --name qc --repo C:\qc
```

Rebind one agent's saved resume metadata without re-registering that worker lane:

```powershell
python .\cmc.py layout set --name qc --agent storage --resume-target 01JXYZABC123 --window-group qc-core --tab-title storage
```

Preview the exact Windows Terminal restore commands without launching them:

```powershell
python .\cmc.py layout restore --name qc --dry-run
```

Restore the full Codex layout in one command:

```powershell
python .\cmc.py layout restore --name qc
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

Saved layouts are written to:

```text
%USERPROFILE%\.codex-mission-control\layouts
```

The layout files stay local because they contain machine-specific paths and Codex resume targets.

Recommended coordinator-owned workflow:

1. Execution agents keep their heartbeats current with `register`, `task`, and `ping`.
2. The coordinator assigns durable recovery metadata with `layout set`.
3. The coordinator runs `layout refresh` whenever worktrees, tasks, or repo paths drift.
4. The coordinator runs `layout restore` after reboot or crash.

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
