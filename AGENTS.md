# Codex Mission Control - Agent Notes

Use this repo to monitor Codex worktrees and agent sessions. The terminal dashboard is driven by local heartbeat files plus a small amount of planner-maintained markdown.

## Session Recovery

This repo also owns the local-only multi-agent session recovery flow.

Use it to reopen Windows Terminal tabs and resume Codex sessions after a reboot or crash.

Core commands:

```powershell
python .\cmc.py layout save --name <project> --repo <repo-path>
python .\cmc.py layout refresh --name <project> --repo <repo-path>
python .\cmc.py layout set --name <project> --agent <agent> --resume-target <target> --window-group <group> --tab-title <title>
python .\cmc.py layout show --name <project>
python .\cmc.py layout restore --name <project> --dry-run
python .\cmc.py layout restore --name <project>
```

Execution agents should still register with their live work context, but the coordinator owns the durable recovery metadata.

For reliable restore, each layout entry needs:

- `--resume-target`
- `--window-group`
- `--tab-title`

Preferred workflow:

```powershell
python .\cmc.py register --agent storage --repo C:\qc --worktree C:\QC-Boundary-Detection --task "Storage work"
python .\cmc.py layout set --name qc --agent storage --resume-target 01JXYZABC123 --window-group qc-core --tab-title storage
python .\cmc.py layout refresh --name qc --repo C:\qc
```

Saved layouts are local only and live under:

```text
%USERPROFILE%\.codex-mission-control\layouts
```

Do not commit project-specific layout JSON into Git. The code is portable; the saved session state is not.

## Deployment Checklist Source

The terminal dashboard shown by `python .\cmc.py dashboard --repo C:\qc` renders a deployment checklist above the Git tree from:

- `handoffs/next-deployment-checklist.md`

Keep that file short and planner-maintained. It is meant to answer one question quickly:

- what still needs to be done before the next deployment

### Checklist format

Use one markdown bullet per item:

```md
- [ ] `QC-123` [storage] Pending item
- [~] `QC-456` [deploy] In-progress item
- [x] `QC-789` [lan-backend] Completed item
- [!] `QC-999` [planning] Blocked item
- [?] `QC-321` [deploy] Conditional item
```

The owner token is optional but recommended when a lane is clearly responsible.

Optional indented text below an item becomes its note in the UI.

Status mapping:

- `[ ]` pending
- `[~]` in progress
- `[x]` complete
- `[!]` blocked
- `[?]` conditional

## How To Update

1. Edit `handoffs/next-deployment-checklist.md`.
2. Save the file.
3. Refresh the terminal dashboard view if needed.

The terminal renderer reads this file on each refresh; no extra sync step is needed.

## Main Files

- `backend/checklist.py` parses the markdown checklist
- `backend/terminal_dashboard.py` renders the checklist and Git graph
- `handoffs/future-terminal-dashboard-spec.md` captures the next terminal-only dashboard improvements
