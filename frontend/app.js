const state = {
  latest: null,
  selectedNodePath: null,
  selectedPayload: null,
  expanded: new Set(),
  socket: null,
  pollHandle: null,
};

const summaryLineEl = document.getElementById("summary-line");
const connectionEl = document.getElementById("connection-state");
const treeRootEl = document.getElementById("tree-root");
const inspectorEl = document.getElementById("inspector");

const LEVEL_GAP = 180;
const LEAF_GAP = 92;
const PADDING_X = 120;
const PADDING_Y = 90;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setConnectionState(label, tone = "") {
  connectionEl.textContent = label;
  connectionEl.className = `chip ${tone}`.trim();
}

function setSummaryLine(data) {
  const summary = data?.summary ?? {};
  const status = summary.status_summary ?? {};
  summaryLineEl.textContent =
    `agents:${summary.agent_count ?? 0}  worktrees:${summary.worktree_count ?? 0}  active:${status.active ?? 0}  stale:${status.stale ?? 0}`;
}

function mergeRepoTree(data) {
  return structuredClone(data.repo_tree ?? {
    name: data.repo_path ?? "(repo)",
    path: data.repo_path ?? "(repo)",
    type: "repo",
    meta: {},
    children: [],
  });
}

function findNodeByPath(node, path) {
  if (!node) return null;
  if (node.path === path) return node;
  for (const child of node.children ?? []) {
    const match = findNodeByPath(child, path);
    if (match) return match;
  }
  return null;
}

function visibleChildren(node) {
  return node.children ?? [];
}

function prepareTree(node, depth = 0, parent = null) {
  const prepared = {
    ...node,
    depth,
    parent,
    children: visibleChildren(node).map((child) => prepareTree(child, depth + 1, node.path)),
  };
  return prepared;
}

function expandDefaultBranches(node) {
  state.expanded.add(node.path);
  for (const child of node.children ?? []) {
    if (child.type === "branch_group") {
      expandDefaultBranches(child);
    }
  }
}

function measureTree(root) {
  let leafIndex = 0;
  let maxDepth = 0;
  const nodes = [];
  const links = [];

  function walk(node, parent = null) {
    maxDepth = Math.max(maxDepth, node.depth);
    const children = node.children ?? [];
    children.forEach((child) => walk(child, node));

    if (!children.length) {
      node._leaf = leafIndex++;
    } else {
      const first = children[0]._leaf;
      const last = children[children.length - 1]._leaf;
      node._leaf = (first + last) / 2;
    }

    node.x = PADDING_X + node._leaf * LEAF_GAP;
    node.y = PADDING_Y + node.depth * LEVEL_GAP;
    nodes.push(node);
    if (parent) {
      links.push({ source: parent, target: node });
    }
  }

  walk(root, null);
  return {
    width: Math.max(PADDING_X * 2 + Math.max(leafIndex - 1, 0) * LEAF_GAP, 900),
    height: Math.max(PADDING_Y * 2 + maxDepth * LEVEL_GAP + 120, 500),
    nodes,
    links,
  };
}

function nodeRadius(node) {
  if (node.type === "repo") return 22;
  if (node.type === "branch_group") return 15;
  if (node.type === "branch") return 18;
  return 9;
}

function nodeColor(node) {
  const agents = node.meta?.agents ?? [];
  const statusSet = new Set(agents.map((agent) => agent.status));
  if (statusSet.has("active")) return "#7ef0a8";
  if (statusSet.has("delayed")) return "#ffd36f";
  if (statusSet.has("stale") || statusSet.has("failed") || statusSet.has("killed")) return "#ff8e78";
  if (node.meta?.dirty || node.meta?.dirty_file_count) return "#ffcf70";
  if (node.type === "repo") return "#87e2ff";
  if (node.type === "branch_group") return "#8f89ff";
  if (node.type === "branch") return "#63c7ff";
  return "#7a8f99";
}

function linkColor(link) {
  const targetColor = nodeColor(link.target);
  return targetColor;
}

function buildNodeLabel(node) {
  const badges = [];
  if (node.meta?.branch_name && node.type === "branch") badges.push(node.meta.branch_name);
  if (node.meta?.dirty_file_count) badges.push(`dirty:${node.meta.dirty_file_count}`);
  if (node.meta?.recent_count) badges.push(`recent:${node.meta.recent_count}`);
  return [node.name, ...badges].join("  ");
}

function buildAgentText(node) {
  const agents = node.meta?.agents ?? [];
  if (!agents.length) return "";
  return agents.map((agent) => agent.agent_id).join("   ");
}

function renderLink(link) {
  const startX = link.source.x;
  const startY = link.source.y + nodeRadius(link.source);
  const endX = link.target.x;
  const endY = link.target.y - nodeRadius(link.target);
  const midY = startY + (endY - startY) * 0.45;
  const path = `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`;
  const color = linkColor(link);
  return `
    <path class="tree-link glow" d="${path}" stroke="${color}" />
    <path class="tree-link core" d="${path}" stroke="${color}" />
  `;
}

function renderNode(node) {
  const radius = nodeRadius(node);
  const color = nodeColor(node);
  const selected = state.selectedNodePath === node.path ? "selected" : "";
  const hasChildren = (node.children ?? []).length > 0;
  const labelY = node.y + radius + 24;
  const agentText = buildAgentText(node);

  return `
    <g class="tree-node ${selected}" data-node-path="${escapeHtml(node.path)}" data-node-type="${escapeHtml(node.type)}">
      <circle class="node-halo" cx="${node.x}" cy="${node.y}" r="${radius + 12}" fill="${color}" />
      <circle class="node-core" cx="${node.x}" cy="${node.y}" r="${radius}" fill="${color}" stroke="${color}" />
      ${hasChildren ? `<circle class="node-ring" cx="${node.x}" cy="${node.y}" r="${radius + 6}" stroke="${color}" />` : ""}
      <text class="node-label type-${escapeHtml(node.type)}" x="${node.x}" y="${labelY}" text-anchor="middle">${escapeHtml(buildNodeLabel(node))}</text>
      ${agentText ? `<text class="agent-label" x="${node.x}" y="${labelY + 22}" text-anchor="middle">${escapeHtml(agentText)}</text>` : ""}
    </g>
  `;
}

function renderSvg(tree) {
  const prepared = prepareTree(tree);
  const layout = measureTree(prepared);
  return `
    <svg class="tree-svg" viewBox="0 0 ${layout.width} ${layout.height}" width="${layout.width}" height="${layout.height}">
      <defs>
        <filter id="softGlow">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g class="links">${layout.links.map((link) => renderLink(link)).join("")}</g>
      <g class="nodes" filter="url(#softGlow)">${layout.nodes.map((node) => renderNode(node)).join("")}</g>
    </svg>
  `;
}

async function handleNodeClick(path, type) {
  const root = mergeRepoTree(state.latest);
  const clicked = findNodeByPath(root, path);
  if (!clicked) return;

  if ((clicked.children ?? []).length) {
    if (state.expanded.has(path)) state.expanded.delete(path);
    else state.expanded.add(path);
  }

  const latestRoot = mergeRepoTree(state.latest);
  state.selectedNodePath = path;
  state.selectedPayload = findNodeByPath(latestRoot, path) ?? latestRoot;
  render(state.latest);
}

function renderInspector() {
  const node = state.selectedPayload;
  if (!node) {
    inspectorEl.className = "inspector hidden";
    inspectorEl.innerHTML = "";
    return;
  }

  const meta = node.meta ?? {};
  const lines = [
    `<div class="inspector-title">${escapeHtml(node.name)}</div>`,
    `<div class="inspector-line">type: ${escapeHtml(node.type)}</div>`,
    `<div class="inspector-line">branch: ${escapeHtml(node.meta?.branch_name || node.path)}</div>`,
  ];

  if (meta.dirty_file_count) lines.push(`<div class="inspector-line">dirty files: ${escapeHtml(meta.dirty_file_count)}</div>`);

  if ((meta.agents ?? []).length) {
    lines.push('<div class="inspector-section">agents</div>');
    for (const agent of meta.agents) {
      lines.push(
        `<div class="inspector-line">${escapeHtml(agent.agent_id)}  ${escapeHtml(agent.status)}  ${escapeHtml(agent.task || "")}</div>`
      );
    }
  }

  inspectorEl.className = "inspector";
  inspectorEl.innerHTML = lines.join("");
}

function render(data) {
  if (!data) return;
  setSummaryLine(data);
  const tree = mergeRepoTree(data);
  expandDefaultBranches(tree);

  if (!state.selectedNodePath) {
    state.selectedNodePath = tree.path;
    state.selectedPayload = tree;
  } else {
    state.selectedPayload = findNodeByPath(tree, state.selectedNodePath) ?? tree;
  }

  treeRootEl.innerHTML = renderSvg(tree);
  treeRootEl.querySelectorAll("[data-node-path]").forEach((element) => {
    element.addEventListener("click", async (event) => {
      event.stopPropagation();
      await handleNodeClick(element.dataset.nodePath, element.dataset.nodeType);
    });
  });
  renderInspector();
}

async function fetchState() {
  try {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.latest = payload;
    render(payload);
    setConnectionState("poll", "delayed");
  } catch (error) {
    console.error(error);
    setConnectionState("error", "failed");
  }
}

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws/state`);
  state.socket = socket;

  socket.addEventListener("open", () => {
    setConnectionState("live", "active");
  });

  socket.addEventListener("message", (event) => {
    state.latest = JSON.parse(event.data);
    render(state.latest);
  });

  socket.addEventListener("close", () => {
    setConnectionState("reconnecting", "stale");
    if (!state.pollHandle) {
      state.pollHandle = window.setInterval(fetchState, 3000);
      fetchState();
    }
    window.setTimeout(connect, 3000);
  });

  socket.addEventListener("error", () => {
    socket.close();
  });
}

connect();
