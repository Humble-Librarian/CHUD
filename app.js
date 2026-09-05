// ─────────────────────────────────────────────────────────────
//  CHUD Language Studio — app.js
//  Elite AST/CST Graph Engine & Interactive Tree-Walk Cockpit
//  Pure Vanilla JS + D3.js v7 — Zero Framework Dependencies
// ─────────────────────────────────────────────────────────────

// ── Preset Examples ──
const EXAMPLES = {
  showcase: `// Language Overview: Variables, Conditionals & Loops
let user = "Engineer"
let access_level = 3

check access_level >= 2 {
    yap "Status: Authorized session for " + user
} otherwise {
    yap "Status: Access restricted"
}

let iteration = 0
keep iteration < 5 {
    yap "Step " + iteration + " verified"
    iteration = iteration + 1
    check iteration == 3 {
        yap "Checkpoint reached at iteration 3"
        stop
    }
}`,

  game: `// Number Guessing Game (Interactive Standard Input)
yap "=== SECRET NUMBER GAME ==="
let secret = 7
yap "Enter your secret number guess (1-10):"
let guess = hear

check guess == secret {
    yap "Success: Correct guess!"
} otherwise {
    yap "Failure: The secret number was 7."
}`,

  metrics: `// Productivity & Activity Metric Calculator
yap "What is your name?"
let name = hear

yap "How many hours of sleep did you get last night?"
let sleep = hear

yap "How many lines of code did you write today?"
let code_lines = hear

let productivity_score = (sleep * 10) + (code_lines * 2)
yap "User: " + name
yap "Calculated Productivity Score: " + productivity_score

check productivity_score >= 100 {
    yap "Evaluation: High performance benchmark achieved."
} otherwise {
    check productivity_score >= 50 {
        yap "Evaluation: Standard baseline maintained."
    } otherwise {
        yap "Evaluation: Rest and recharge recommended."
    }
}`,

  math: `// Math & Arithmetic Expressions
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

  branching: `// Conditional Branching & Grade Evaluation
let score = 85

check score >= 90 {
    yap "Grade: Distinction (A)"
} otherwise {
    check score >= 75 {
        yap "Grade: Merit (B)"
    } otherwise {
        yap "Grade: Pass (C)"
    }
}`,

  loop_break: `// Loop Iteration with Break Condition
let count = 0
keep count < 10 {
    check count == 4 {
        yap "Threshold reached at count 4 — terminating loop"
        stop
    }
    yap "Current count: " + count
    count = count + 1
}`,

  error_demo: `// Compiler Diagnostic Demo (triggers syntax diagnostic)
let broken = 42 +
yap broken`
};

// ── State Management ──
let currentAstData = null;
let currentCstData = null;
let currentTokens = [];
let currentVariables = {};
let activeTreeMode = 'ast'; // 'ast' or 'cst'
let allNodesCollapsed = false;
let searchQuery = '';
let rootHierarchy = null;
let currentZoomTransform = null;
let nodeUniqueId = 0;

// ── DOM References ──
const editor = document.getElementById('code-editor');
const lineGutter = document.getElementById('line-gutter');
const lineCounter = document.getElementById('line-counter');
const themeSelect = document.getElementById('theme-select');
const exampleSelect = document.getElementById('example-select');
const btnRun = document.getElementById('btn-run');
const btnVisualize = document.getElementById('btn-visualize');
const btnAll = document.getElementById('btn-all');
const engineStatus = document.getElementById('engine-status');
const consoleOutput = document.getElementById('console-output');
const varsTable = document.getElementById('vars-table').querySelector('tbody');
const tokensView = document.getElementById('tokens-view');
const jsonOutput = document.getElementById('json-output');
const jsonTreeLabel = document.getElementById('json-tree-label');
const tooltip = document.getElementById('tree-tooltip');
const nodeSearch = document.getElementById('node-search');
const searchCountBadge = document.getElementById('search-count-badge');
const btnSearchClear = document.getElementById('btn-search-clear');
const hudNodeCount = document.getElementById('hud-node-count');
const hudDepthCount = document.getElementById('hud-depth-count');
const hudStmtCount = document.getElementById('hud-stmt-count');
const hudCompactness = document.getElementById('hud-compactness');
const outputCountBadge = document.getElementById('output-count-badge');
const varsCountBadge = document.getElementById('vars-count-badge');
const tokensCountBadge = document.getElementById('tokens-count-badge');

// Modal Elements
const modalBackdrop = document.getElementById('input-modal-backdrop');
const modalInputsList = document.getElementById('modal-inputs-list');
const btnModalSubmit = document.getElementById('btn-modal-submit');
const btnModalCancel = document.getElementById('btn-modal-cancel');
const btnModalClose = document.getElementById('btn-modal-close');
const toastContainer = document.getElementById('toast-container');

// ── D3 Canvas & Hierarchy Configuration (OpenDesign Engineering Cards) ──
const CARD_WIDTH = 208;
const CARD_HEIGHT = 52;
const DEPTH_SPACING = 270;
const VERTICAL_SPACING = 72;

const svg = d3.select("#tree-svg");
const g = svg.append("g").attr("class", "tree-root-group");

const zoom = d3.zoom()
  .scaleExtent([0.1, 4])
  .on("zoom", (event) => {
    currentZoomTransform = event.transform;
    g.attr("transform", event.transform);
  });

svg.call(zoom).on("dblclick.zoom", null); // Disable double click zoom for better node interaction

const treeLayout = d3.tree().nodeSize([VERTICAL_SPACING, DEPTH_SPACING]);

// ── Node Categories & Visual Tokens (OpenDesign Semantic System) ──
const CATEGORY_MAP = {
  Program:   { cat: 'stmt', label: 'ROOT',       color: '#5e6ad2' },
  Assign:    { cat: 'stmt', label: 'ASSIGN',     color: '#7170ff' },
  Yap:       { cat: 'stmt', label: 'OUTPUT',     color: '#7170ff' },
  Check:     { cat: 'ctrl', label: 'BRANCH',     color: '#f5a623' },
  Keep:      { cat: 'ctrl', label: 'LOOP',       color: '#f5a623' },
  Stop:      { cat: 'ctrl', label: 'BREAK',      color: '#eb5757' },
  Block:     { cat: 'stmt', label: 'BLOCK',      color: '#8a8f98' },
  BinOp:     { cat: 'expr', label: 'OPERATOR',   color: '#38bdf8' },
  UnaryOp:   { cat: 'expr', label: 'UNARY',      color: '#38bdf8' },
  Label:     { cat: 'expr', label: 'BRANCH',     color: '#38bdf8' },
  Number:    { cat: 'lit',  label: 'NUMERIC',    color: '#27a644' },
  String:    { cat: 'lit',  label: 'STRING',     color: '#27a644' },
  Bool:      { cat: 'lit',  label: 'BOOLEAN',    color: '#27a644' },
  Identifier:{ cat: 'lit',  label: 'IDENTIFIER', color: '#3dd68c' },
  Hear:      { cat: 'ctrl', label: 'INPUT',      color: '#ff6363' },
  rule:      { cat: 'cst-rule', label: 'RULE',   color: '#8a8f98' },
  terminal:  { cat: 'cst-term', label: 'TOKEN',  color: '#eab308' }
};

function getNodeCategory(d) {
  const type = d.data.type || "";
  const name = d.data.name || "";
  if (activeTreeMode === 'cst') {
    if (type === 'terminal') return CATEGORY_MAP.terminal;
    return CATEGORY_MAP.rule;
  }
  return CATEGORY_MAP[type] || { cat: 'expr', label: type.toUpperCase() || 'NODE', color: '#55b3ff' };
}

// ── Editor Setup & Line Gutter Synchronization ──

function updateLineNumbers() {
  const lines = editor.value.split('\n');
  const count = lines.length;
  let gutterHtml = '';
  for (let i = 1; i <= count; i++) {
    gutterHtml += `<span class="line-num">${i}</span>`;
  }
  lineGutter.innerHTML = gutterHtml;
  lineCounter.textContent = `${count} line${count === 1 ? '' : 's'}`;
  lineGutter.scrollTop = editor.scrollTop;
}

editor.addEventListener('input', updateLineNumbers);
editor.addEventListener('scroll', () => {
  lineGutter.scrollTop = editor.scrollTop;
});

// Tab indentation handler (4 spaces)
editor.addEventListener('keydown', (e) => {
  if (e.key === 'Tab') {
    e.preventDefault();
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    const value = editor.value;

    if (e.shiftKey) {
      // Outdent
      const lineStart = value.lastIndexOf('\n', start - 1) + 1;
      if (value.substring(lineStart, lineStart + 4) === '    ') {
        editor.value = value.substring(0, lineStart) + value.substring(lineStart + 4);
        editor.selectionStart = Math.max(lineStart, start - 4);
        editor.selectionEnd = Math.max(lineStart, end - 4);
      }
    } else {
      // Indent 4 spaces
      editor.value = value.substring(0, start) + '    ' + value.substring(end);
      editor.selectionStart = editor.selectionEnd = start + 4;
    }
    updateLineNumbers();
  }
});

// Copy Code Button
document.getElementById('btn-copy-code').addEventListener('click', () => {
  navigator.clipboard.writeText(editor.value).then(() => {
    showToast("Source code copied to clipboard!");
  });
});

// Clear Code Button
document.getElementById('btn-clear-code').addEventListener('click', () => {
  editor.value = '';
  updateLineNumbers();
  editor.focus();
});

// Clear Terminal Button
document.getElementById('btn-clear-terminal').addEventListener('click', () => {
  consoleOutput.innerHTML = `<div class="log-info">Terminal output cleared.</div>`;
  outputCountBadge.textContent = '0';
});

// ── In-App Interactive Input Modal (Zero Extra Popups, Exact Questions) ──

let inputResolver = null;

// Exact human questions mapped to variable semantics
const EXACT_PROMPTS = {
  guess: "Enter your secret number guess (1-10):",
  secret: "Enter secret number:",
  name: "What is your name?",
  user_name: "What is your name?",
  username: "What is your username?",
  sleep: "How many hours of sleep did you get last night?",
  sleep_hours: "How many hours of sleep did you get last night?",
  code_lines: "How many lines of code did you write today?",
  lines: "How many lines of code did you write today?",
  age: "Enter your age in years:",
  user_age: "Enter your age in years:",
  score: "Enter target score value:",
  points: "Enter points value:",
  count: "Enter count number:",
  num: "Enter a number:",
  number: "Enter a number:",
  choice: "Enter your choice:"
};

const FIELD_DEFAULTS = {
  guess: { title: "Secret Number Guess", defaultVal: "7" },
  name: { title: "Your Name", defaultVal: "Chad" },
  sleep: { title: "Hours of Sleep", defaultVal: "8" },
  code_lines: { title: "Lines of Code", defaultVal: "120" },
  age: { title: "Age", defaultVal: "21" },
  score: { title: "Score", defaultVal: "90" },
  count: { title: "Count", defaultVal: "5" }
};

function getExactPrompt(varName, explicitPrompt, precedingYap) {
  // 1. Explicit prompt provided in CHUD code: hear "Prompt text"
  if (explicitPrompt && explicitPrompt.trim()) {
    return explicitPrompt.trim();
  }

  // 2. Preceding yap prompt right before hear: yap "Prompt text"
  if (precedingYap && precedingYap.trim()) {
    let clean = precedingYap.trim();
    if (!clean.endsWith(':') && !clean.endsWith('?')) {
      clean += ':';
    }
    return clean;
  }

  // 3. Exact variable semantic match
  const lower = (varName || '').toLowerCase();
  if (EXACT_PROMPTS[lower]) {
    return EXACT_PROMPTS[lower];
  }

  // 4. Clean humanized question
  if (varName) {
    const readable = varName.replace(/_/g, ' ');
    return `Enter value for ${readable}:`;
  }

  return "Enter input value:";
}

function getFieldDetails(varName) {
  const lower = (varName || '').toLowerCase();
  if (FIELD_DEFAULTS[lower]) {
    return FIELD_DEFAULTS[lower];
  }

  const title = varName 
    ? varName.charAt(0).toUpperCase() + varName.slice(1).replace(/_/g, ' ') 
    : "Value";
  return { title, defaultVal: "10" };
}

function scanForHearInputs(code) {
  const lines = code.split('\n');
  const hearList = [];
  let recentYapPrompt = null;

  for (let idx = 0; idx < lines.length; idx++) {
    const rawLine = lines[idx];

    // Strip single-line comments // ...
    const withoutComment = rawLine.replace(/\/\/.*$/, '');
    const trimmed = withoutComment.trim();

    // Skip empty lines without dropping recentYapPrompt if close
    if (!trimmed) continue;

    // Check if this line is a yap "..." prompt statement
    const yapMatch = withoutComment.match(/\byap\b\s+"([^"\\]*(?:\\.[^"\\]*)*)"/);
    if (yapMatch) {
      recentYapPrompt = yapMatch[1];
    }

    // Check for explicit prompt in hear: hear "..."
    const hearPromptMatch = withoutComment.match(/\bhear\b\s+"([^"\\]*(?:\\.[^"\\]*)*)"/);
    const explicitPrompt = hearPromptMatch ? hearPromptMatch[1] : null;

    // Mask string literals to prevent matching "hear" inside strings
    const maskedLine = withoutComment.replace(/"[^"\\]*(?:\\.[^"\\]*)*"/g, '""');

    // Test for true 'hear' keyword tokens
    if (/\bhear\b/.test(maskedLine)) {
      // Find variable name if it is an assignment
      const assignMatch = maskedLine.match(/(?:let\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*.*?\bhear\b/);
      const varName = assignMatch ? assignMatch[1] : null;

      const promptText = getExactPrompt(varName, explicitPrompt, recentYapPrompt);
      const fieldInfo = getFieldDetails(varName);

      hearList.push({
        lineNum: idx + 1,
        varName: varName || `input_${hearList.length + 1}`,
        fieldTitle: fieldInfo.title,
        prompt: promptText,
        defaultVal: fieldInfo.defaultVal
      });

      // Clear recent yap after attaching to this input
      recentYapPrompt = null;
    } else if (!yapMatch) {
      // Non-yap, non-hear code line resets recentYapPrompt
      recentYapPrompt = null;
    }
  }

  return hearList;
}

function promptForInputs(hearList) {
  return new Promise((resolve) => {
    inputResolver = resolve;

    // Update Modal Title & Description for the exact situation
    const modalTitleEl = document.getElementById('modal-title');
    const modalDescEl = document.getElementById('modal-desc');

    if (hearList.length === 1) {
      modalTitleEl.textContent = `Input Required: ${hearList[0].fieldTitle}`;
      modalDescEl.textContent = `The program is waiting for your input to continue execution:`;
    } else {
      modalTitleEl.textContent = `Program Input Required (${hearList.length} values)`;
      modalDescEl.textContent = `Please provide the ${hearList.length} required inputs below to execute the program:`;
    }

    // Render all inputs together in a single modal card
    modalInputsList.innerHTML = hearList.map((item, i) => `
      <div class="modal-input-row">
        <div class="modal-input-meta">
          <label class="modal-prompt-label" for="modal-input-${i}">
            ${escapeHtml(item.prompt)}
          </label>
          <div class="modal-meta-tags">
            <span class="modal-target-tag">let <code>${escapeHtml(item.varName)}</code></span>
            <span class="file-tag">Line ${item.lineNum}</span>
          </div>
        </div>
        <input 
          type="text" 
          id="modal-input-${i}" 
          class="modal-input-field" 
          value="${escapeHtml(item.defaultVal)}" 
          placeholder="${escapeHtml(item.defaultVal)}"
          data-index="${i}"
          autocomplete="off"
          spellcheck="false"
        />
      </div>
    `).join('');

    modalBackdrop.classList.remove('hidden');

    // Focus and select the first input field
    const firstInput = document.getElementById('modal-input-0');
    if (firstInput) {
      setTimeout(() => {
        firstInput.focus();
        firstInput.select();
      }, 50);
    }
  });
}

function submitModalInputs() {
  if (!inputResolver) return;
  const fields = modalInputsList.querySelectorAll('.modal-input-field');
  const values = Array.from(fields).map(f => f.value.trim() || "0");
  modalBackdrop.classList.add('hidden');
  const res = inputResolver;
  inputResolver = null;
  res(values);
}

function cancelModalInputs() {
  if (!inputResolver) return;
  modalBackdrop.classList.add('hidden');
  const res = inputResolver;
  inputResolver = null;
  res(null); // Execution cancelled
}

btnModalSubmit.addEventListener('click', submitModalInputs);
btnModalCancel.addEventListener('click', cancelModalInputs);
btnModalClose.addEventListener('click', cancelModalInputs);

// Modal Keyboard Shortcuts: Enter submits all, Escape cancels
window.addEventListener('keydown', (e) => {
  if (!modalBackdrop.classList.contains('hidden')) {
    if (e.key === 'Enter') {
      e.preventDefault();
      submitModalInputs();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelModalInputs();
    }
  }
});

async function resolveInputsIfNeeded() {
  const hearList = scanForHearInputs(editor.value);
  if (hearList.length === 0) {
    return [];
  }
  // Single, clear modal for all inputs - zero multiple popups
  const collected = await promptForInputs(hearList);
  return collected;
}

// ── Status Indicator ──

function updateStatus(text, isError = false, isBusy = false) {
  engineStatus.textContent = text;
  const ind = document.querySelector('.status-indicator');
  if (ind) {
    ind.className = 'status-indicator ' + (isError ? 'error' : (isBusy ? 'busy' : 'live'));
    const dot = ind.querySelector('.status-dot');
    if (dot) {
      dot.style.background = isError ? '#f43f5e' : (isBusy ? '#38bdf8' : '#10b981');
      dot.style.boxShadow = isError ? '0 0 8px rgba(244,63,94,0.7)' : (isBusy ? '0 0 8px rgba(56,189,248,0.7)' : '0 0 8px rgba(16,185,129,0.7)');
    }
  }
}

// ── API Handlers ──

async function runCode() {
  const inputs = await resolveInputsIfNeeded();
  if (inputs === null) {
    updateStatus("Execution cancelled");
    return;
  }

  updateStatus("Executing...", false, true);
  const startTime = performance.now();
  setButtonLoading(btnRun, true);

  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.value, inputs })
    });
    const data = await res.json();
    const elapsed = Math.round(performance.now() - startTime);
    displayRunResult(data, elapsed);
  } catch (err) {
    displayRunResult({ success: false, error: "Network or Server Error: " + err.message }, 0);
  } finally {
    setButtonLoading(btnRun, false);
  }
}

async function visualizeCode() {
  updateStatus("Parsing syntax trees...", false, true);
  setButtonLoading(btnVisualize, true);

  try {
    const res = await fetch('/api/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.value })
    });
    const data = await res.json();
    displayParseResult(data);
    updateStatus("Syntax Parsed");
  } catch (err) {
    displayParseResult({ success: false, error: "Network or Server Error: " + err.message });
  } finally {
    setButtonLoading(btnVisualize, false);
  }
}

async function runAndVisualize() {
  const inputs = await resolveInputsIfNeeded();
  if (inputs === null) {
    updateStatus("Execution cancelled");
    return;
  }

  updateStatus("Executing & Parsing...", false, true);
  const startTime = performance.now();
  setButtonLoading(btnAll, true);

  try {
    const res = await fetch('/api/all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.value, inputs })
    });
    const data = await res.json();
    const elapsed = Math.round(performance.now() - startTime);
    displayRunResult(data, elapsed);
    displayParseResult(data);
  } catch (err) {
    displayRunResult({ success: false, error: "Network or Server Error: " + err.message }, 0);
  } finally {
    setButtonLoading(btnAll, false);
  }
}

function setButtonLoading(btn, isLoading) {
  if (isLoading) {
    btn.style.opacity = '0.75';
    btn.style.pointerEvents = 'none';
  } else {
    btn.style.opacity = '';
    btn.style.pointerEvents = '';
  }
}

// ── Display Execution & Parse Results ──

function displayRunResult(data, elapsedMs) {
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0];

  if (!data.success) {
    updateStatus("Execution Failed", true);
    consoleOutput.innerHTML = `
      <div class="compiler-diag-card">
        <div class="diag-header">
          <svg class="diag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <span>RUNTIME EXCEPTION</span>
          <span class="diag-badge">HALTED</span>
        </div>
        <div class="diag-message">${escapeHtml(data.error || "Runtime execution error occurred.")}</div>
        <div class="diag-tip-bar">Compiler Diagnostic: Check variable definitions, type compatibility, and control flow conditions.</div>
      </div>
    `;
    outputCountBadge.textContent = '!';
    activateTab('tab-console');
  } else {
    updateStatus(`Finished in ${elapsedMs}ms`);
    if (data.output && data.output.length > 0) {
      consoleOutput.innerHTML = data.output.map(line => `
        <div class="log-entry">
          <span class="log-time">${timeStr}</span>
          <span class="log-arrow">&rarr;</span>
          <span class="log-text">${escapeHtml(line)}</span>
        </div>
      `).join('');
      outputCountBadge.textContent = String(data.output.length);
    } else {
      consoleOutput.innerHTML = `
        <div class="log-entry">
          <span class="log-time">${timeStr}</span>
          <span class="log-info">Program finished successfully with no standard output.</span>
        </div>
      `;
      outputCountBadge.textContent = '0';
    }
  }

  currentVariables = data.variables || {};
  renderVariables(currentVariables);
}

function displayParseResult(data) {
  if (!data.success && !data.ast && !data.cst) {
    updateStatus("Parse Error", true);
    consoleOutput.innerHTML = `
      <div class="compiler-diag-card">
        <div class="diag-header">
          <svg class="diag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          <span>COMPILER SYNTAX DIAGNOSTIC</span>
          <span class="diag-badge">SYNTAX ERROR</span>
        </div>
        <div class="diag-message">${escapeHtml(data.error || "Syntax parsing error.")}</div>
        <div class="diag-tip-bar">Compiler Advisory: Verify statement grammar, matching braces, or missing operator operands.</div>
      </div>
    `;
    activateTab('tab-console');
    return;
  }

  currentAstData = data.ast;
  currentCstData = data.cst;
  currentTokens = data.tokens || [];

  renderTokens(currentTokens);
  updateJsonView();
  renderCurrentTree();
  updateTreeStats();
}

function renderVariables(vars) {
  const keys = Object.keys(vars);
  varsCountBadge.textContent = String(keys.length);

  if (keys.length === 0) {
    varsTable.innerHTML = `<tr><td colspan="3" class="table-empty">No bound environment variables in scope.</td></tr>`;
    return;
  }

  varsTable.innerHTML = keys.map(k => {
    const val = vars[k];
    let typeName = typeof val;
    if (typeof val === 'boolean' || val === 'W' || val === 'L') typeName = 'boolean';
    else if (typeof val === 'number') typeName = 'number';
    else if (typeof val === 'string') typeName = 'string';

    return `
      <tr>
        <td class="var-key"><strong>${escapeHtml(k)}</strong></td>
        <td><span class="type-pill ${typeName}">${typeName}</span></td>
        <td class="var-val">${escapeHtml(String(val))}</td>
      </tr>
    `;
  }).join('');
}

function renderTokens(tokens) {
  tokensCountBadge.textContent = String(tokens.length);

  if (!tokens || tokens.length === 0) {
    tokensView.innerHTML = `<div class="empty-state">No tokens available.</div>`;
    return;
  }

  tokensView.innerHTML = tokens.map(t => {
    let cat = 'punct';
    const type = t.type || '';
    if (['LET', 'CHECK', 'OTHERWISE', 'KEEP', 'STOP', 'YAP', 'HEAR'].includes(type)) cat = 'kw';
    else if (type === 'IDENTIFIER') cat = 'id';
    else if (['NUMBER', 'STRING', 'BOOLEAN'].includes(type)) cat = 'lit';
    else if (['PLUS', 'MINUS', 'STAR', 'SLASH', 'EQEQ', 'NEQ', 'LT', 'LTE', 'GT', 'GTE', 'NOT', 'ASSIGN'].includes(type)) cat = 'op';

    const valStr = t.value !== null && t.value !== undefined ? String(t.value) : '';
    return `
      <div class="token-pill-badge ${cat}" data-line="${t.line || 1}" title="Click to scroll to Line ${t.line || 1}">
        <span class="token-type">${escapeHtml(type)}</span>
        ${valStr ? `<span class="token-val">${escapeHtml(valStr)}</span>` : ''}
        <span class="token-line">L${t.line || 1}</span>
      </div>
    `;
  }).join('');

  // Clicking a token pill highlights the line in the editor
  tokensView.querySelectorAll('.token-pill-badge').forEach(pill => {
    pill.addEventListener('click', () => {
      const line = parseInt(pill.getAttribute('data-line'), 10);
      highlightEditorLine(line);
    });
  });
}

function highlightEditorLine(lineNum) {
  const lines = editor.value.split('\n');
  let charIdx = 0;
  for (let i = 0; i < lineNum - 1 && i < lines.length; i++) {
    charIdx += lines[i].length + 1;
  }
  const endIdx = charIdx + (lines[lineNum - 1] ? lines[lineNum - 1].length : 0);
  editor.focus();
  editor.setSelectionRange(charIdx, endIdx);

  // Scroll to line
  const lineHeight = 22;
  editor.scrollTop = Math.max(0, (lineNum - 3) * lineHeight);
}

function updateJsonView() {
  const data = activeTreeMode === 'ast' ? currentAstData : currentCstData;
  jsonTreeLabel.textContent = activeTreeMode === 'ast' 
    ? "Abstract Syntax Tree (AST) JSON" 
    : "Concrete Parse Tree (CST) JSON";

  if (!data) {
    jsonOutput.innerHTML = `<code>// No tree data loaded yet.</code>`;
    return;
  }
  jsonOutput.innerHTML = `<code>${escapeHtml(JSON.stringify(data, null, 2))}</code>`;
}

// Copy JSON button
document.getElementById('btn-copy-json').addEventListener('click', () => {
  const data = activeTreeMode === 'ast' ? currentAstData : currentCstData;
  if (!data) return;
  navigator.clipboard.writeText(JSON.stringify(data, null, 2)).then(() => {
    showToast("Tree JSON copied to clipboard!");
  });
});

// ── Tree Statistics HUD ──

function countHierarchyNodes(node) {
  if (!node) return 0;
  let count = 1;
  if (node.children) {
    for (let c of node.children) count += countHierarchyNodes(c);
  }
  return count;
}

function getHierarchyDepth(node) {
  if (!node) return 0;
  if (!node.children || node.children.length === 0) return 1;
  let maxChildDepth = 0;
  for (let c of node.children) {
    maxChildDepth = Math.max(maxChildDepth, getHierarchyDepth(c));
  }
  return 1 + maxChildDepth;
}

function countStatements(data) {
  if (!data) return 0;
  let count = 0;
  function traverse(n) {
    if (['Assign', 'Yap', 'Check', 'Keep', 'Stop'].includes(n.type)) count++;
    if (n.children) n.children.forEach(traverse);
  }
  traverse(data);
  return count;
}

function updateTreeStats() {
  const astCount = currentAstData ? countHierarchyNodes(currentAstData) : 0;
  const cstCount = currentCstData ? countHierarchyNodes(currentCstData) : 0;

  const currentData = activeTreeMode === 'ast' ? currentAstData : currentCstData;
  const currentCount = currentData ? countHierarchyNodes(currentData) : 0;
  const maxDepth = currentData ? getHierarchyDepth(currentData) : 0;
  const stmts = currentAstData ? countStatements(currentAstData) : 0;

  hudNodeCount.textContent = String(currentCount);
  hudDepthCount.textContent = String(maxDepth);
  hudStmtCount.textContent = String(stmts);

  if (astCount > 0 && cstCount > 0) {
    const compactness = Math.max(0, Math.round(((cstCount - astCount) / cstCount) * 100));
    if (activeTreeMode === 'ast') {
      hudCompactness.textContent = `AST is ${compactness}% more compact than CST (${astCount} vs ${cstCount} nodes)`;
    } else {
      hudCompactness.textContent = `CST Parse Tree: ${cstCount} grammar derivation nodes`;
    }
  } else {
    hudCompactness.textContent = activeTreeMode === 'ast' ? "AST representation" : "CST Parse Tree representation";
  }
}

// ── D3 Tree Visualization ──

function switchTreeMode(mode) {
  activeTreeMode = mode;
  document.getElementById('mode-ast').classList.toggle('active', mode === 'ast');
  document.getElementById('mode-cst').classList.toggle('active', mode === 'cst');
  updateJsonView();
  renderCurrentTree();
  updateTreeStats();
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

function updateTree(source) {
  if (!rootHierarchy) return;

  const treeData = treeLayout(rootHierarchy);
  const nodes = treeData.descendants();
  const links = treeData.links();

  // Normalize depth positioning
  nodes.forEach(d => {
    d.y = d.depth * DEPTH_SPACING;
  });

  // ── Nodes Render ──
  const nodeSelection = g.selectAll('g.node-card')
    .data(nodes, d => d.id || (d.id = ++nodeUniqueId));

  const nodeEnter = nodeSelection.enter().append('g')
    .attr('class', d => `node-card category-${getNodeCategory(d).cat}`)
    .attr('transform', () => `translate(${source.y0 || 0},${source.x0 || 0})`)
    .on('click', (event, d) => {
      event.stopPropagation();
      toggleNodeCollapse(d);
    })
    .on('mouseenter', (event, d) => {
      showTooltip(event, d);
      highlightBranch(d, true);
    })
    .on('mousemove', (event) => moveTooltip(event))
    .on('mouseleave', (event, d) => {
      hideTooltip();
      highlightBranch(d, false);
    });

  // Node Card Background (High-Precision 6px engineering card)
  nodeEnter.append('rect')
    .attr('class', 'node-card-bg')
    .attr('x', 0)
    .attr('y', -CARD_HEIGHT / 2)
    .attr('width', CARD_WIDTH)
    .attr('height', CARD_HEIGHT)
    .attr('rx', 6)
    .attr('ry', 6);

  // Left Semantic Accent Bar (2.5px vertical indicator)
  nodeEnter.append('rect')
    .attr('class', 'node-accent-bar')
    .attr('x', 0)
    .attr('y', -CARD_HEIGHT / 2 + 4)
    .attr('width', 2.5)
    .attr('height', CARD_HEIGHT - 8)
    .attr('rx', 1.25)
    .attr('fill', d => getNodeCategory(d).color);

  // Category Badge Background (Subtle pill)
  nodeEnter.append('rect')
    .attr('class', 'node-badge-rect')
    .attr('x', 10)
    .attr('y', -CARD_HEIGHT / 2 + 9)
    .attr('width', d => Math.max(34, getNodeCategory(d).label.length * 6 + 10))
    .attr('height', 14)
    .attr('rx', 3)
    .attr('fill', d => getNodeCategory(d).color)
    .attr('fill-opacity', 0.12);

  // Category Badge Text
  nodeEnter.append('text')
    .attr('class', 'node-badge-text')
    .attr('x', 15)
    .attr('y', -CARD_HEIGHT / 2 + 19.5)
    .attr('fill', d => getNodeCategory(d).color)
    .text(d => getNodeCategory(d).label);

  // Line & Column Pill Text
  nodeEnter.append('text')
    .attr('class', 'node-line-text')
    .attr('x', CARD_WIDTH - 12)
    .attr('y', -CARD_HEIGHT / 2 + 19.5)
    .attr('text-anchor', 'end')
    .text(d => d.data.line !== undefined ? `L${d.data.line}` : '');

  // Card Divider Line
  nodeEnter.append('line')
    .attr('class', 'node-card-divider')
    .attr('x1', 10)
    .attr('y1', -CARD_HEIGHT / 2 + 27)
    .attr('x2', CARD_WIDTH - 10)
    .attr('y2', -CARD_HEIGHT / 2 + 27)
    .attr('stroke', 'rgba(255, 255, 255, 0.06)')
    .attr('stroke-width', 1);

  // Main Node Title
  nodeEnter.append('text')
    .attr('class', 'node-title')
    .attr('x', 10)
    .attr('y', 10)
    .text(d => truncateText(d.data.name || d.data.type || '', 24));

  // Node Subtitle / Value Text
  nodeEnter.append('text')
    .attr('class', 'node-subtext')
    .attr('x', 10)
    .attr('y', 20)
    .text(d => {
      if (d.data.value !== undefined) return `val: ${truncateText(String(d.data.value), 22)}`;
      if (d.data.type && d.data.type !== d.data.name) return truncateText(d.data.type, 22);
      return '';
    });

  // Collapse / Expand Toggle Indicator Circle
  const toggleGroup = nodeEnter.append('g')
    .attr('class', 'toggle-group')
    .attr('transform', `translate(${CARD_WIDTH}, 0)`);

  toggleGroup.append('circle')
    .attr('class', 'toggle-circle')
    .attr('r', 8)
    .attr('fill', '#090d16')
    .attr('stroke', d => getNodeCategory(d).color);

  toggleGroup.append('text')
    .attr('class', 'toggle-icon')
    .attr('y', 0.5)
    .attr('fill', '#ffffff')
    .text(d => (d._children ? `+${d._children.length}` : (d.children ? '−' : '')));

  // Node Update Transition
  const nodeUpdate = nodeSelection.merge(nodeEnter).transition().duration(350)
    .ease(d3.easeCubicOut)
    .attr('transform', d => `translate(${d.y},${d.x})`);

  // Update dynamic classes & toggle indicator
  nodeSelection.merge(nodeEnter).each(function(d) {
    const el = d3.select(this);
    const hasChildren = Boolean(d.children || d._children);
    const toggle = el.select('.toggle-group');

    if (hasChildren) {
      toggle.style('display', 'block');
      toggle.select('circle')
        .attr('fill', d._children ? getNodeCategory(d).color : '#090d16')
        .attr('stroke', getNodeCategory(d).color);
      toggle.select('.toggle-icon')
        .attr('fill', d._children ? '#ffffff' : getNodeCategory(d).color)
        .text(d._children ? `+${d._children.length}` : '−');
    } else {
      toggle.style('display', 'none');
    }

    // Apply Search Filter Classes
    if (searchQuery.trim() !== '') {
      const q = searchQuery.toLowerCase();
      const matched = (
        (d.data.name && d.data.name.toLowerCase().includes(q)) ||
        (d.data.type && d.data.type.toLowerCase().includes(q)) ||
        (d.data.value !== undefined && String(d.data.value).toLowerCase().includes(q))
      );
      el.classed('search-matched', matched);
      el.classed('search-dimmed', !matched);
    } else {
      el.classed('search-matched', false);
      el.classed('search-dimmed', false);
    }
  });

  // Node Exit Transition
  const nodeExit = nodeSelection.exit().transition().duration(350)
    .ease(d3.easeCubicOut)
    .attr('transform', () => `translate(${source.y},${source.x})`)
    .style('opacity', 0)
    .remove();

  // ── Links Render ──
  const linkSelection = g.selectAll('path.link')
    .data(links, d => d.target.id);

  const linkEnter = linkSelection.enter().insert('path', 'g')
    .attr('class', 'link')
    .attr('d', () => {
      const o = { x: source.x0 || 0, y: source.y0 || 0 };
      return diagonal(o, o);
    });

  linkSelection.merge(linkEnter).transition().duration(350)
    .ease(d3.easeCubicOut)
    .attr('d', d => diagonal(d.source, d.target));

  linkSelection.exit().transition().duration(350)
    .ease(d3.easeCubicOut)
    .attr('d', () => {
      const o = { x: source.x, y: source.y };
      return diagonal(o, o);
    })
    .remove();

  // Save current positions for subsequent transitions
  nodes.forEach(d => {
    d.x0 = d.x;
    d.y0 = d.y;
  });
}

// Horizontal Cubic Bezier Connector from Parent Right to Child Left
function diagonal(s, d) {
  const sx = s.y + CARD_WIDTH;
  const sy = s.x;
  const tx = d.y;
  const ty = d.x;
  const mx = (sx + tx) / 2;
  return `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ty}, ${tx} ${ty}`;
}

function toggleNodeCollapse(d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else if (d._children) {
    d.children = d._children;
    d._children = null;
  }
  updateTree(d);
}

function highlightBranch(node, isHovered) {
  // Highlight connected links
  g.selectAll('path.link')
    .classed('highlighted', isHovered ? d => (d.source === node || d.target === node) : false);
}

function truncateText(str, maxLen) {
  if (!str) return '';
  return str.length > maxLen ? str.substring(0, maxLen - 1) + '…' : str;
}

// ── Search & Filter ──

nodeSearch.addEventListener('input', (e) => {
  searchQuery = e.target.value;
  btnSearchClear.classList.toggle('hidden', searchQuery === '');
  applySearchFilter();
});

btnSearchClear.addEventListener('click', () => {
  nodeSearch.value = '';
  searchQuery = '';
  btnSearchClear.classList.add('hidden');
  applySearchFilter();
  nodeSearch.focus();
});

function applySearchFilter() {
  if (!rootHierarchy) return;
  const q = searchQuery.trim().toLowerCase();

  let matchCount = 0;
  g.selectAll('g.node-card').each(function(d) {
    const el = d3.select(this);
    if (q === '') {
      el.classed('search-matched', false);
      el.classed('search-dimmed', false);
    } else {
      const matched = (
        (d.data.name && d.data.name.toLowerCase().includes(q)) ||
        (d.data.type && d.data.type.toLowerCase().includes(q)) ||
        (d.data.value !== undefined && String(d.data.value).toLowerCase().includes(q))
      );
      el.classed('search-matched', matched);
      el.classed('search-dimmed', !matched);
      if (matched) matchCount++;
    }
  });

  if (q !== '') {
    searchCountBadge.textContent = `${matchCount} match${matchCount === 1 ? '' : 'es'}`;
    searchCountBadge.classList.remove('hidden');
  } else {
    searchCountBadge.classList.add('hidden');
  }
}

// ── Camera & Zoom Controls ──

function resetView() {
  if (!rootHierarchy) return;
  const container = document.getElementById('tree-container');
  const width = container.clientWidth || 800;
  const height = container.clientHeight || 600;

  const transform = d3.zoomIdentity.translate(60, height / 2).scale(0.8);
  svg.transition().duration(400).ease(d3.easeCubicOut).call(zoom.transform, transform);
}

document.getElementById('btn-zoom-in').addEventListener('click', () => {
  svg.transition().duration(250).call(zoom.scaleBy, 1.3);
});

document.getElementById('btn-zoom-out').addEventListener('click', () => {
  svg.transition().duration(250).call(zoom.scaleBy, 0.77);
});

document.getElementById('btn-zoom-reset').addEventListener('click', resetView);

// Collapse / Expand All
document.getElementById('btn-toggle-expand').addEventListener('click', () => {
  if (!rootHierarchy) return;
  allNodesCollapsed = !allNodesCollapsed;
  const btn = document.getElementById('btn-toggle-expand');
  btn.title = allNodesCollapsed ? "Expand all branches" : "Collapse all branches";

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

  if (allNodesCollapsed) {
    if (rootHierarchy.children) rootHierarchy.children.forEach(toggleAll);
  } else {
    toggleAll(rootHierarchy);
  }
  updateTree(rootHierarchy);
  showToast(allNodesCollapsed ? "Collapsed all branches" : "Expanded all branches");
});

// Export SVG Vector File
document.getElementById('btn-export-svg').addEventListener('click', () => {
  const svgEl = document.getElementById('tree-svg');
  if (!svgEl) return;

  const serializer = new XMLSerializer();
  let source = serializer.serializeToString(svgEl);

  // Add namespaces
  if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
    source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
  }

  const blob = new Blob([source], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `chud_${activeTreeMode}_tree.svg`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast("Exported tree graph as Vector SVG!");
});

// ── Tooltip ──

function showTooltip(event, d) {
  const cat = getNodeCategory(d);
  let content = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
      <span style="font-weight:700;color:${cat.color};letter-spacing:0.5px;">${escapeHtml(cat.label)}</span>
      ${d.data.line !== undefined ? `<span style="color:#64748b">Line ${d.data.line}</span>` : ''}
    </div>
    <div style="font-size:13px;font-weight:600;color:#ffffff;margin-bottom:4px;">${escapeHtml(d.data.name || d.data.type)}</div>
  `;

  if (d.data.value !== undefined) {
    content += `<div style="color:#94a3b8">Value: <span style="color:#34d399">${escapeHtml(String(d.data.value))}</span></div>`;
  }
  if (d.data.type && d.data.type !== d.data.name) {
    content += `<div style="color:#94a3b8">AST Type: <span style="color:#38bdf8">${escapeHtml(d.data.type)}</span></div>`;
  }
  if (d._children) {
    content += `<div style="margin-top:6px;color:#fcd34d">Click to expand (${d._children.length} hidden children)</div>`;
  } else if (d.children && d.children.length > 0) {
    content += `<div style="margin-top:6px;color:#94a3b8">Click to collapse branch</div>`;
  }

  tooltip.innerHTML = content;
  tooltip.classList.remove('hidden');
  tooltip.style.opacity = '1';
  moveTooltip(event);
}

function moveTooltip(event) {
  const container = document.getElementById('tree-container').getBoundingClientRect();
  let x = event.clientX - container.left + 16;
  let y = event.clientY - container.top + 16;

  // Prevent overflowing container bounds
  if (x + 280 > container.width) x -= 300;
  if (y + 140 > container.height) y -= 120;

  tooltip.style.left = `${Math.max(10, x)}px`;
  tooltip.style.top = `${Math.max(10, y)}px`;
}

function hideTooltip() {
  tooltip.classList.add('hidden');
  tooltip.style.opacity = '0';
}

// ── Tab Switching ──

function activateTab(tabId) {
  document.querySelectorAll('.drawer-tab').forEach(t => {
    const isActive = t.getAttribute('data-tab') === tabId;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });

  document.querySelectorAll('.tab-content').forEach(pane => {
    pane.classList.toggle('active', pane.id === tabId);
  });
}

document.querySelectorAll('.drawer-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    activateTab(tab.getAttribute('data-tab'));
  });
});

// ── Toast System ──

function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <svg class="toast-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
    <span>${escapeHtml(message)}</span>
  `;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 2400);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── Event Bindings ──

exampleSelect.addEventListener('change', (e) => {
  const key = e.target.value;
  if (EXAMPLES[key]) {
    editor.value = EXAMPLES[key];
    updateLineNumbers();
    updateStatus("Loaded " + key);
    showToast(`Loaded example: ${key}`);
    const hearList = scanForHearInputs(editor.value);
    if (hearList.length > 0) {
      visualizeCode();
    } else {
      runAndVisualize();
    }
  }
});

btnRun.addEventListener('click', runCode);
btnVisualize.addEventListener('click', visualizeCode);
btnAll.addEventListener('click', runAndVisualize);

document.getElementById('mode-ast').addEventListener('click', () => switchTreeMode('ast'));
document.getElementById('mode-cst').addEventListener('click', () => switchTreeMode('cst'));

// Keyboard Shortcut: Ctrl/Cmd + Enter -> Run & Visualize
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    runAndVisualize();
  }
});

// ── Theme Manager ──
function initTheme() {
  const savedTheme = localStorage.getItem('chud_theme') || 'linear';
  document.documentElement.setAttribute('data-theme', savedTheme);
  if (themeSelect) {
    themeSelect.value = savedTheme;
  }
}

if (themeSelect) {
  themeSelect.addEventListener('change', (e) => {
    const chosen = e.target.value;
    document.documentElement.setAttribute('data-theme', chosen);
    localStorage.setItem('chud_theme', chosen);
    showToast(`Applied theme: ${e.target.options[e.target.selectedIndex].text}`);
    if (rootHierarchy) {
      updateTree(rootHierarchy);
    }
  });
}

initTheme();

// ── Initial Boot ──
editor.value = EXAMPLES.showcase;
updateLineNumbers();
runAndVisualize();
