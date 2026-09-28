# CHUD — Custom High-level User Development Language

**CHUD** is a modern, educational programming language and visual compiler workbench designed to make every stage of code execution tangible and inspectable. It features a maximal-munch lexer, a recursive-descent parser, dual execution engines (a scoped **Tree-Walk Interpreter** and a stack-based **Bytecode Compiler & Virtual Machine**), and an interactive **Browser Studio**.

![CHUD pipeline architecture](pipeline.png)

---

## Key Highlights

- **Dual Execution Engines**: Execute programs via an AST Tree-Walk Interpreter or compile to a stack-based Bytecode VM with 100% execution parity.
- **Interactive Visual Studio**: Inspect Abstract Syntax Trees (AST), Concrete Parse Trees (CST), Lexical Tokens, and formatted JSON in real time.
- **Lexical Tokens Data Table**: Search, filter by token category, inspect lexemes, and click any row to jump directly to that line in the source editor.
- **Collapsible JSON Tree Inspector**: Interactive expandable tree viewer with live node counts, tree depth, payload size metrics, and one-click JSON export.
- **Zero External Dependencies**: Built entirely with Python's standard library (`http.server`, `json`, `urllib`). Runs out of the box with zero pip packages required.

---

## Language Capabilities

| Feature | Syntax & Details |
|---|---|
| **Variables & Types** | `let name = "Alice"` (declaration), `name = "Bob"` (reassignment), Numbers (`42`, `3.14`), Strings (`"hello"`), Booleans (`W` = true, `L` = false) |
| **Arithmetic & Logic** | `+`, `-`, `*`, `/`, unary `+` / `-`, string concatenation, comparisons (`==`, `!=`, `<`, `>`, `<=`, `>=`) with standard operator precedence |
| **Conditionals** | `check condition { ... } otherwise { ... }` with truthiness semantics |
| **Loops & Flow** | `keep condition { ... }` (while-loop), `loop let i = 0; i < 5; i = i + 1 { ... }` (for-loop), and `stop` (break) |
| **Functions** | `make func(a, b) { return a + b }` with parameter passing, lexical scoping, recursion, and return values |
| **Interactive I/O** | `yap "message"` (print output), `hear "prompt"` (runtime user input with automatic type coercion) |

---

## Quick Start

### Prerequisites
- **Python 3.9+**
- Modern Web Browser (Chrome, Firefox, Safari, Edge)

### 1. Launch the Visualizer Studio
```bash
python server.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

To run on a custom port:
```bash
python server.py 8080
```

### 2. Run CHUD Programs from CLI
Execute standalone `.chud` script files:
```bash
python chud.py game.chud
python chud.py rizz_calculator.chud
```

Or start the interactive REPL:
```bash
python chud.py
```

### 3. Run Automated Verification Suites
```bash
# Full test suite (Compiler, CST, AST, Interpreter, Server, Frontend)
python test_all.py

# Bytecode VM <-> Interpreter parity test suite (19 tests)
python test_vm_parity.py
```

---

## Interactive Studio Features

The CHUD Visualizer Studio provides a split-pane IDE workspace:

### Left Column: Source Cockpit & Execution Console
- **Source Editor**: Line-number gutter, syntax tracking, line counter, one-click copy, and example program loader.
- **Bottom Execution Drawer**:
  - **Console Output**: Real-time execution logs with timestamps and compiler diagnostic cards.
  - **Environment Scope Table**: Live inspection of active variables, data types (`number`, `string`, `boolean`), and values.
  - **Interactive Input Modal**: In-app modal for `hear` prompts with keyboard shortcuts (`Enter` to submit, `Esc` to cancel).

### Right Column: Syntax & Structure Inspector
- **Interactive D3 Graphs (AST & CST)**:
  - High-precision engineering node cards color-coded by grammar category (Statement, Expression, Control, Literal, Rule, Token).
  - Dot-grid background, smooth pan/zoom camera controls, node search filtering, branch collapse/expand, and vector SVG export.
  - **Tree Stats HUD**: Live node count, hierarchy depth, statement count, and CST-to-AST compactness percentage.
- **Lexical Tokens Pro Data Table**:
  - Structured columns: `#` Index, `Token Type` pill, `Value / Lexeme`, `Category`, `Line` jump tag, and `Copy` action.
  - Category filters: `All`, `Keywords`, `Identifiers`, `Literals`, `Operators`.
  - Live search input matching token names, values, or line numbers.
  - Switcher between **Data Table View** and **Pills Stream View**.
- **Interactive JSON Tree Inspector**:
  - Segmented toggle between `AST` and `CST` JSON structures.
  - Interactive collapsible tree with color-coded keys, strings, numbers, and booleans.
  - Live metrics badges: Total Nodes, Max Depth, and File Size in KB.
  - Formatted raw code viewer, one-click clipboard copy, and `.json` file download.
- **Themes**: Space Dark, Studio Light, Midnight Blue, and Titanium Monochrome.

---

## Code Example

```chud
// Define a function
make calculate_bonus(years, base) {
    check years >= 5 {
        return base * 1.5
    } otherwise {
        return base * 1.1
    }
}

let employee = hear "Enter employee name: "
let experience = 6
let salary = 50000

let total = calculate_bonus(experience, salary)
yap employee + " total compensation: " + total

// Loop example
loop let i = 1; i <= 3; i = i + 1 {
    yap "Review milestone: " + i
}
```

---

## System Architecture

```text
               ┌──────────────────────────────┐
               │         CHUD Source          │
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │    Lexer (Maximal-Munch)     │
               └──────────────┬───────────────┘
                              │ Token Stream
                              ▼
               ┌──────────────────────────────┐
               │   Recursive-Descent Parser   │
               └───────┬──────────────┬───────┘
                       │              │
           AST Nodes   │              │ CST Derivation Tree
                       ▼              ▼
     ┌───────────────────────┐  ┌───────────────────────┐
     │     AST Serializer    │  │     CST Generator     │
     └─────────┬─────────────┘  └──────────┬────────────┘
               │                           │
               ├───────────────────────────┤
               │                           │
               ▼                           ▼
 ┌───────────────────────────┐   ┌───────────────────────────┐
 │   Tree-Walk Interpreter   │   │   Bytecode Compiler & VM  │
 │     (interpreter.py)      │   │    (compiler.py / vm.py)  │
 └─────────────┬─────────────┘   └─────────────┬─────────────┘
               │                               │
               └───────────────┬───────────────┘
                               │ JSON API (/api/parse, /api/run, /api/all)
                               ▼
               ┌───────────────────────────────┐
               │      CHUD Studio Web UI       │
               │   (D3 Graphs, Tables, JSON)   │
               └───────────────────────────────┘
```

### Module Overview

| File | Purpose |
|---|---|
| [`lexer.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/lexer.py) | Tokenizes source code into structured tokens with line numbers |
| [`parser.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/parser.py) | Builds Abstract Syntax Tree (AST) using recursive-descent parsing |
| [`ast_nodes.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py) | Class definitions for AST nodes (Statements, Expressions, Functions) |
| [`ast_serializer.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_serializer.py) | Serializes AST nodes into D3 hierarchy format |
| [`cst_generator.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/cst_generator.py) | Generates full Concrete Parse Tree (CST) capturing grammar rules and tokens |
| [`interpreter.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/interpreter.py) | Tree-walk interpreter with lexical environments and error diagnostics |
| [`compiler.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/compiler.py) | Bytecode compiler emitting chunk instructions and constant pools |
| [`vm.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/vm.py) | Stack-based Bytecode Virtual Machine with function call frames |
| [`bytecode.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/bytecode.py) | Opcode definitions (`OP_CONST`, `OP_LOAD`, `OP_ADD`, `OP_JUMP`, `OP_CALL`, etc.) and disassembler |
| [`server.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/server.py) | Standard-library HTTP server hosting static files and JSON endpoints |
| [`chud.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/chud.py) | Command-line file executor and interactive REPL |
| [`index.html`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/index.html) | Studio markup with split-pane layout, token table, and JSON inspector |
| [`style.css`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/style.css) | Custom themes, glassmorphism, responsive data table, and canvas styling |
| [`app.js`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/app.js) | Frontend controller, D3 tree graph rendering, token filters, and JSON viewer |
| [`test_all.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/test_all.py) | End-to-end integration test suite |
| [`test_vm_parity.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/test_vm_parity.py) | 19 parity test cases comparing Interpreter and VM execution |

---

## HTTP JSON API

The Python server provides endpoints on port `8000`:

| Endpoint | Method | Description |
|---|---|---|
| `/api/parse` | `POST` | Parses code and returns token stream, AST data, and CST data |
| `/api/compile` | `POST` | Compiles AST into bytecode chunks with disassembled instructions |
| `/api/run` | `POST` | Executes code and returns terminal output, runtime variables, and errors |
| `/api/all` | `POST` | Parses, executes, and serializes all trees and tokens in a single request |

### Example Request Body
```json
{
  "code": "let score = 10\nyap score * 2",
  "inputs": []
}
```

---

## License

CHUD is open-source software released under the [MIT License](LICENSE).
