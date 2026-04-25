# Mission Control Agent Guidance

Do not launch Codex through a wrapper. Start `codex` normally so resume/chat behavior is untouched.

On first reading this file in a new session, immediately register the session in Mission Control from the current worktree.

The first command to run after startup is:

```powershell
python C:\codex-agent-map\cmc.py register --agent <agent> --repo C:\qc --worktree <worktree-path> --task "<top-level assignment>"
```

Startup pattern for an agent session:

1. Read this file.
2. Immediately run the `cmc.py register` command once from the assigned worktree.
3. Continue the session normally.

Example:

```powershell
python C:\codex-agent-map\cmc.py register --agent deploy --repo C:\qc --worktree C:\QC-deploy --task "Deploy work"
```

When the user gives the agent a new substantial assignment, update the task sparingly:

```powershell
python C:\codex-agent-map\cmc.py task --agent <agent> --task "<task text>"
```

Update the heartbeat task only when the user has clearly given the agent a new substantial work assignment or materially changed the current assignment.

Do update the task when:
- the user redirects the agent to a different feature, bug, deliverable, or investigation
- the user sends a large prompt that changes the main body of implementation work
- the agent is switching from one meaningful workstream to another and the dashboard label would otherwise be misleading

Do not update the task when:
- the agent is only planning
- the agent is only reading files, reviewing code, or gathering context
- the agent is executing internal substeps of the same assignment
- the agent is running tests, formatting, validation, or cleanup for the same assignment
- the user is only asking a question, brainstorming, or requesting explanation

The task text should describe the current top-level assignment, not the immediate micro-step.

When the current assignment is done, mark the agent idle:

```powershell
python C:\codex-agent-map\cmc.py task --agent <agent> --task "idle"
```

This dashboard uses the explicit task and status you set. It does not derive `stale` from heartbeat age anymore.

When the session is done, remove the heartbeat entirely:

```powershell
python C:\codex-agent-map\cmc.py stop --agent <agent> --remove
```

Example lifecycle:

```powershell
python C:\codex-agent-map\cmc.py register --agent deploy --repo C:\qc --worktree C:\QC-deploy --task "Deploy work"
python C:\codex-agent-map\cmc.py task --agent deploy --task "Investigate deploy resume failure"
python C:\codex-agent-map\cmc.py task --agent deploy --task "idle"
python C:\codex-agent-map\cmc.py stop --agent deploy --remove
```

Good task names:
- `Build deploy heartbeat integration`
- `Investigate replay trace upload failures`
- `Implement LAN run status dashboard`

Bad task names:
- `Read server.py`
- `Plan approach`
- `Run tests`
- `Fix line 84`
- `idle` while the agent is still in the middle of a real assignment

The goal is for the dashboard to show the agent's current mission, not every internal action.
