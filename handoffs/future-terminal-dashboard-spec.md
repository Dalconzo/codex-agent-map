# Terminal Dashboard Next-Step Spec

This spec covers the next iteration of `python .\cmc.py dashboard --repo C:\QC`.

The goal is not to add more raw data. The goal is to help the planner quickly answer:

1. Which agent needs prompting now?
2. What work is waiting on review?
3. What stage is each active lane in?
4. What still blocks the next deployment?

## Design Constraint

Terminal height is limited. New sections must earn their lines.

Priorities:

- favor summary over completeness
- avoid repeating the same issue ID in multiple sections when possible
- show only exception states by default
- keep the git tree visible without excessive scrolling

## Current Strengths

- deployment blockers are visible at the top
- worktree/branch location is visible in the git tree
- heartbeat/task updates make active work easier to spot

## Current Gaps

- no compact view of which agents need user prompting
- no clear distinction between `agent says ready` and `review actually needed`
- no compact stage indicator for each active lane
- no visibility into machine-test waiting vs sim-test waiting
- no easy way to spot stale in-progress work that has drifted

## Proposed Top Layout

Keep the dashboard header minimal and terminal-first.

Recommended order:

1. `deploy`
2. `attention`
3. `review`
4. git tree

The top sections should stay compact enough that the tree still starts on-screen.

## Section Rules

### `deploy`

Purpose:
- next-deployment blockers only

Source:
- `handoffs/next-deployment-checklist.md`

Display:
- one line per blocker
- format:
  - status marker
  - bead id
  - owner
  - short text

Keep:
- current compact format

Do not add:
- checklist file path
- extra framing lines
- long notes by default

### `attention`

Purpose:
- show only agents that need the user's prompt now

Suggested display:
- one line per agent
- format:
  - agent
  - reason
  - age if relevant

Example:
- `storage  review fix requested 18h`
- `deploy   ready-for-review no handoff 2h`

Suggested trigger rules:
- issue is `in_progress` and heartbeat/task is stale beyond threshold
- committed work exists but no Beads/handoff update
- handoff asks for review but no `ready-for-review` label
- issue is labeled `blocked` without a dependency or recent explanation
- agent is idle while still holding an assigned in-progress issue

Default behavior:
- omit agents with no required user action

### `review`

Purpose:
- show work waiting on planning/review

Suggested display:
- one line per issue
- format:
  - bead id
  - owner
  - review type
  - age

Review types:
- `runtime`
- `storage`
- `compat`
- `memory`

Suggested source:
- `ready-for-review` label
- optional `review:*` labels

Important distinction:
- only show items that are actually review-ready
- unresolved blockers should stay in `deploy` or `attention`, not here

## Per-Agent Stage Model

Do not show a full stage table for every agent unless there is room.

Instead, derive a single compact stage when an agent appears in `attention` or `review`.

Suggested stages:

- `impl`
- `review`
- `sim`
- `machine`
- `ready`
- `blocked`

Derivation should be heuristic, not manually curated per refresh.

Suggested mapping:

- `ready-for-review` -> `review`
- `awaiting-user-test` or machine-test marker -> `machine`
- explicit blocked label -> `blocked`
- active in-progress issue with recent heartbeat -> `impl`
- reviewed/approved with pending deployment blocker removal -> `ready`

## Future Metadata Sources

Prefer deriving state from structured data first:

- Beads status
- Beads labels
- heartbeat task text
- git dirty/ahead state

Use markdown only for planner-owned overlays:

- deployment blockers
- future planner notes when no structured source exists yet

## Compactness Rules

- no wrapped prose in the main dashboard if avoidable
- truncate long descriptions
- show ages in a short form like `2h`, `3d`
- max 3 sections above the tree after `deploy`
- if terminal height is too small, drop `review` before dropping `attention`

## Suggested Implementation Order

1. Add `attention` section
2. Add `review` section
3. Add compact stage derivation
4. Add machine-vs-sim waiting hints only if they fit cleanly

## Non-Goals

- full-screen status board above the tree
- verbose issue notes inline
- duplicating all Beads data in the dashboard
- replacing Beads with markdown state

## Acceptance Criteria

The dashboard iteration is successful if:

- the user can tell within a few seconds which agent to prompt next
- the user can see what is waiting on review without opening Beads
- the git tree remains visible in the same terminal view
- the added sections do not feel noisier than the current output
