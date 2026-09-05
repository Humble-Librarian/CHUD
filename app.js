// ─────────────────────────────────────────────
//  CHUD Language Studio — app.js
//  Pure Vanilla JS + D3.js v7 Interactive Visualizer
// ─────────────────────────────────────────────

const EXAMPLES = {
  showcase: `// CHUD Language Showcase
let name = "bro"
let age  = 19

check age >= 18 {
    yap "you are a real one, " + name
} otherwise {
    yap "L behavior"
}

let i = 0
keep i < 5 {
    yap "count: " + i
    i = i + 1
    check i == 3 {
        yap "stopping early at 3!"
        stop
    }
}`,

  math: `// Math & Variable Expressions
let a = 15
let b = 4
let sum = a + b
let diff = a - b
let prod = a * b
let div = a / b

yap "sum = " + sum
yap "diff = " + diff
yap "prod = " + prod
yap "div = " + div
yap "is a > b? " + (a > b)`,

  branching: `// Nested Check / Otherwise
let score = 85

check score >= 90 {
    yap "Grade: Sigma (A)"
} otherwise {
    check score >= 75 {
        yap "Grade: Respectable (B)"
    } otherwise {
        yap "Grade: Cooked (F)"
    }
}`,

  loop_break: `// Keep Loop with Stop Break
let count = 0
keep count < 10 {
    check count == 4 {
        yap "Reached 4! Breaking out..."
        stop
    }
    yap "current = " + count
    count = count + 1
}`,

  game: `// Number Guessing Game (with 'hear' user input)
yap "=== SECRET NUMBER GAME ==="
let secret = 7
yap "Enter your guess: "
let guess = hear

check guess == secret {
    yap "W BEHAVIOR! You got it right!"
} otherwise {
    yap "L behavior! The secret was 7."
}`,

  rizz: `// Sigma Rizz Evaluator (with 'hear' user input)
yap "What is your name?"
let name = hear

yap "Hours of sleep?"
let sleep = hear

let score = sleep * 12
yap name + " has Rizz Score: " + score

check score >= 80 {
    yap "Verdict: Certified Sigma W!"
} otherwise {
    yap "Verdict: Needs more sleep, bro."
}`,

  error_demo: `// Syntax Error Demo (triggers roast)
let broken = 42 +
yap broken`
};

// State
let currentAstData = null;
let currentCstData = null;
let activeTreeMode = 'ast'; // 'ast' or 'cst'
let allNodesCollapsed = false;

// DOM Elements
const editor = document.getElementById('code-editor');
const exampleSelect = document.getElementById('example-select');
const btnRun = document.getElementById('btn-run');
const btnVisualize = document.getElementById('btn-visualize');
const btnAll = document.getElementById('btn-all');
const modeAst = document.getElementById('mode-ast');
const modeCst = document.getElementById('mode-cst');
const sourceStatus = document.getElementById('source-status');
const consoleOutput = document.getElementById('console-output');
const varsTable = document.getElementById('vars-table').querySelector('tbody');
const tokensView = document.getElementById('tokens-view');
const tooltip = document.getElementById('tree-tooltip');

// D3 Setup
const svg = d3.select("#tree-svg");
const g = svg.append("g").attr("class", "tree-root-group");

const zoom = d3.zoom()
  .scaleExtent([0.1, 3])
  .on("zoom", (event) => {
    g.attr("transform", event.transform);
  });

svg.call(zoom);

let treeLayout = d3.tree().nodeSize([38, 170]);
let rootHierarchy = null;

// Initialize
editor.value = EXAMPLES.showcase;

// Event Listeners
exampleSelect.addEventListener('change', (e) => {
  if (EXAMPLES[e.target.value]) {
    editor.value = EXAMPLES[e.target.value];
    updateStatus("Loaded " + e.target.value);
  }
});

btnRun.addEventListener('click', runCode);
btnVisualize.addEventListener('click', visualizeCode);
btnAll.addEventListener('click', runAndVisualize);

modeAst.addEventListener('click', () => switchTreeMode('ast'));
modeCst.addEventListener('click', () => switchTreeMode('cst'));

document.getElementById('btn-zoom-in').addEventListener('click', () => {
  svg.transition().duration(250).call(zoom.scaleBy, 1.3);
});
document.getElementById('btn-zoom-out').addEventListener('click', () => {
  svg.transition().duration(250).call(zoom.scaleBy, 0.77);
});
document.getElementById('btn-zoom-reset').addEventListener('click', resetView);

document.getElementById('btn-toggle-expand').addEventListener('click', () => {
  if (!rootHierarchy) return;
  allNodesCollapsed = !allNodesCollapsed;
  const btn = document.getElementById('btn-toggle-expand');
  btn.textContent = allNodesCollapsed ? "Expand All" : "Collapse All";

  function toggleAll(d) {
    if (allNodesCollapsed) {
      if (d.children) {
        d._children = d.children;
        d.children = null;
      }
    } else {
      if (d._children) {
        d.children = d._children;
        d._children = null;
      }
    }
    const ch = d.children || d._children;
    if (ch) ch.forEach(toggleAll);
  }

  // Keep root expanded when collapsing all
  if (allNodesCollapsed) {
    if (rootHierarchy.children) {
      rootHierarchy.children.forEach(toggleAll);
    }
  } else {
    toggleAll(rootHierarchy);
  }
  updateTree(rootHierarchy);
});

// Keyboard Shortcut: Ctrl/Cmd + Enter -> Run & Visualize
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    runAndVisualize();
  }
});

// Drawer Tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const tabId = btn.getAttribute('data-tab');
    document.getElementById(tabId).classList.add('active');
  });
});

function updateStatus(text, isError = false) {
  sourceStatus.textContent = text;
  sourceStatus.style.color = isError ? '#f87171' : '#38bdf8';
}

// ── API Calls ──

function collectInputs(code) {
  const inputs = [];
  const matches = code.match(/\bhear\b/g);
  if (matches && matches.length > 0) {
    for (let i = 0; i < matches.length; i++) {
      const val = window.prompt(`[CHUD User Input ${i + 1}/${matches.length}]\nEnter value for 'hear':`, "7");
      inputs.push(val !== null ? val : "0");
    }
  }
  return inputs;
}

async function runCode() {
  updateStatus("Running...");
  const inputs = collectInputs(editor.value);
  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.value, inputs })
    });
    const data = await res.json();
    displayRunResult(data);
  } catch (err) {
    displayError("Network / Server Error: " + err.message);
  }
}

async function visualizeCode() {
  updateStatus("Parsing...");
  try {
    const res = await fetch('/api/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.value })
    });
    const data = await res.json();
    displayParseResult(data);
  } catch (err) {
    displayError("Network / Server Error: " + err.message);
  }
}

async function runAndVisualize() {
  updateStatus("Executing & Parsing...");
  const inputs = collectInputs(editor.value);
  try {
    const res = await fetch('/api/all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.value, inputs })
    });
    const data = await res.json();
    displayRunResult(data);
    displayParseResult(data);
  } catch (err) {
    displayError("Network / Server Error: " + err.message);
  }
}

function displayRunResult(data) {
  if (!data.success) {
    updateStatus("Execution Failed", true);
    consoleOutput.innerHTML = `<div class="log-error">${escapeHtml(data.error || "Unknown Error")}</div>`;
  } else {
    updateStatus("Finished");
    if (data.output && data.output.length > 0) {
      consoleOutput.innerHTML = data.output
        .map(line => `<div class="log-line">→ ${escapeHtml(line)}</div>`)
        .join('');
    } else {
      consoleOutput.innerHTML = `<span class="log-hint">Program finished with no yap output.</span>`;
    }
  }

  // Update variables table
  renderVariables(data.variables || {});
}

function displayParseResult(data) {
  if (!data.success && !data.ast && !data.cst) {
    updateStatus("Parse Error", true);
    consoleOutput.innerHTML = `<div class="log-error">${escapeHtml(data.error || "Syntax Error")}</div>`;
    return;
  }

  currentAstData = data.ast;
  currentCstData = data.cst;

  renderTokens(data.tokens || []);
  renderCurrentTree();
}

function displayError(errText) {
  updateStatus("Error", true);
  consoleOutput.innerHTML = `<div class="log-error">${escapeHtml(errText)}</div>`;
}

function renderVariables(vars) {
  const keys = Object.keys(vars);
  if (keys.length === 0) {
    varsTable.innerHTML = `<tr><td colspan="2" class="empty-hint">No variables defined</td></tr>`;
    return;
  }
  varsTable.innerHTML = keys
    .map(k => `<tr><td><strong>${escapeHtml(k)}</strong></td><td>${escapeHtml(vars[k])}</td></tr>`)
    .join('');
}

function renderTokens(tokens) {
  if (!tokens || tokens.length === 0) {
    tokensView.innerHTML = `<span class="empty-hint">No tokens</span>`;
    return;
  }
  tokensView.innerHTML = tokens
    .map(t => `<div class="token-pill"><span class="token-type">${escapeHtml(t.type)}</span><span class="token-val">${t.value !== null ? escapeHtml(String(t.value)) : ''}</span></div>`)
    .join('');
}

function switchTreeMode(mode) {
  activeTreeMode = mode;
  modeAst.classList.toggle('active', mode === 'ast');
  modeCst.classList.toggle('active', mode === 'cst');
  renderCurrentTree();
}

function renderCurrentTree() {
  const data = activeTreeMode === 'ast' ? currentAstData : currentCstData;
  if (!data) return;

  rootHierarchy = d3.hierarchy(data, d => d.children);
  rootHierarchy.x0 = 0;
  rootHierarchy.y0 = 0;

  updateTree(rootHierarchy);
  resetView();
}

// ── D3 Tree Layout & Transitions ──

function getNodeColor(d) {
  const type = d.data.type || "";
  const name = d.data.name || "";

  if (activeTreeMode === 'cst') {
    if (type === 'rule' || name.startsWith('<')) return '#ec4899'; // pink
    if (type === 'terminal') return '#f59e0b'; // amber
    return '#8b5cf6';
  }

  // AST color palette
  if (['Program', 'Assign', 'Yap', 'Check', 'Keep', 'Stop', 'Block'].includes(type)) {
    return '#3b82f6'; // blue (statements / control)
  }
  if (['BinOp', 'UnaryOp', 'Label'].includes(type)) {
    return '#8b5cf6'; // purple (expressions / operators)
  }
  if (['Number', 'String', 'Bool', 'Identifier'].includes(type)) {
    return '#10b981'; // emerald (literals / leaves)
  }
  return '#06b6d4'; // cyan fallback
}

function updateTree(source) {
  const treeData = treeLayout(rootHierarchy);
  const nodes = treeData.descendants();
  const links = treeData.links();

  // Normalize depth spacing
  nodes.forEach(d => {
    d.y = d.depth * 170;
  });

  // ── Nodes ──
  let i = 0;
  const node = g.selectAll('g.node')
    .data(nodes, d => d.id || (d.id = ++i));

  const nodeEnter = node.enter().append('g')
    .attr('class', 'node')
    .attr('transform', () => `translate(${source.y0 || 0},${source.x0 || 0})`)
    .on('click', (event, d) => {
      // Toggle collapse
      if (d.children) {
        d._children = d.children;
        d.children = null;
      } else if (d._children) {
        d.children = d._children;
        d._children = null;
      }
      updateTree(d);
    })
    .on('mouseenter', (event, d) => showTooltip(event, d))
    .on('mousemove', (event) => moveTooltip(event))
    .on('mouseleave', hideTooltip);

  nodeEnter.append('circle')
    .attr('r', 1e-6)
    .style('fill', d => d._children ? '#fff' : getNodeColor(d))
    .style('stroke', d => getNodeColor(d));

  nodeEnter.append('text')
    .attr('dy', '.35em')
    .attr('x', d => (d.children || d._children) ? -13 : 13)
    .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start')
    .text(d => d.data.name)
    .style('fill-opacity', 1e-6);

  // Transition nodes to their new position
  const nodeUpdate = node.merge(nodeEnter).transition().duration(350)
    .attr('transform', d => `translate(${d.y},${d.x})`);

  nodeUpdate.select('circle')
    .attr('r', d => (d.data.type === 'rule' || d.data.type === 'Program') ? 8 : 6)
    .style('fill', d => d._children ? '#fff' : getNodeColor(d))
    .style('stroke', d => getNodeColor(d));

  nodeUpdate.select('text')
    .attr('x', d => (d.children || d._children) ? -13 : 13)
    .attr('text-anchor', d => (d.children || d._children) ? 'end' : 'start')
    .style('fill-opacity', 1);

  // Transition exiting nodes
  const nodeExit = node.exit().transition().duration(350)
    .attr('transform', () => `translate(${source.y},${source.x})`)
    .remove();

  nodeExit.select('circle').attr('r', 1e-6);
  nodeExit.select('text').style('fill-opacity', 1e-6);

  // ── Links ──
  const link = g.selectAll('path.link')
    .data(links, d => d.target.id);

  const linkEnter = link.enter().insert('path', 'g')
    .attr('class', 'link')
    .attr('d', () => {
      const o = { x: source.x0 || 0, y: source.y0 || 0 };
      return diagonal(o, o);
    });

  link.merge(linkEnter).transition().duration(350)
    .attr('d', d => diagonal(d.source, d.target));

  link.exit().transition().duration(350)
    .attr('d', () => {
      const o = { x: source.x, y: source.y };
      return diagonal(o, o);
    })
    .remove();

  // Store old positions for smooth transitions
  nodes.forEach(d => {
    d.x0 = d.x;
    d.y0 = d.y;
  });
}

function diagonal(s, d) {
  return `M ${s.y} ${s.x}
          C ${(s.y + d.y) / 2} ${s.x},
            ${(s.y + d.y) / 2} ${d.x},
            ${d.y} ${d.x}`;
}

function resetView() {
  if (!rootHierarchy) return;
  const container = document.getElementById('tree-container');
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 600;

  const transform = d3.zoomIdentity.translate(80, height / 2).scale(0.85);
  svg.transition().duration(400).call(zoom.transform, transform);
}

// ── Tooltip ──

function showTooltip(event, d) {
  let content = `<strong>${escapeHtml(d.data.name)}</strong><br/>`;
  if (d.data.type) content += `Type: <span style="color:#60a5fa">${escapeHtml(d.data.type)}</span><br/>`;
  if (d.data.line !== undefined) content += `Line: ${d.data.line}<br/>`;
  if (d.data.value !== undefined) content += `Value: <span style="color:#a7f3d0">${escapeHtml(String(d.data.value))}</span><br/>`;
  if (d._children) content += `<span style="color:#fcd34d">Click to expand (${d._children.length} children)</span>`;
  else if (d.children) content += `<span style="color:#fcd34d">Click to collapse</span>`;

  tooltip.innerHTML = content;
  tooltip.classList.remove('hidden');
  moveTooltip(event);
}

function moveTooltip(event) {
  const container = document.getElementById('tree-container').getBoundingClientRect();
  const x = event.clientX - container.left + 15;
  const y = event.clientY - container.top + 15;
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function hideTooltip() {
  tooltip.classList.add('hidden');
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Initial Run and Visualize on page load
runAndVisualize();
