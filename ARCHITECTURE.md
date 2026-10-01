# 📘 CHUD Architecture & System Walkthrough

> **Simple Summary:**  
> **CHUD (Custom High-level User Development Language)** is an educational, full-stack programming language and visual compiler workbench built from scratch with zero external dependencies. It takes high-level source code and executes it through a complete 5-stage compiler pipeline—featuring **Lexical Analysis (Maximal Munch)**, **Recursive-Descent Parsing**, **Dual Tree Generation (CST & AST)**, and **Dual Execution Engines** (an AST Tree-Walk Interpreter and a stack-based Bytecode Compiler & Virtual Machine with 100% execution parity), accompanied by a real-time web-based visual debugger.
>
> ⚡ **Zero External Dependencies:** Built 100% on Python's standard library (`http.server`, `json`, `re`, `urllib`). Runs out of the box with zero `pip` installations.

---

## 🗺️ The 5-Stage Compilation & Execution Pipeline

Here is how CHUD source code travels from raw text to execution and visual inspection:

```mermaid
flowchart TD
    A["📄 CHUD Source Code<br>(game.chud / rizz_calculator.chud)"] --> S1["Stage 1: Lexical Analysis & Tokenization<br>(Maximal-Munch Regex Lexer with Line Tracking)"]
    S1 --> S2["Stage 2: Syntax Analysis & Tree Generation<br>(Recursive-Descent Parser → CST & AST)"]
    S2 --> S3["Stage 3A: Scoped Tree-Walk Interpreter<br>(Recursive AST Traversal & Environment Chaining)"]
    S2 --> S4["Stage 3B: Bytecode Compiler & Stack VM<br>(Single-Pass Emitter + Backpatching + Call Frames)"]
    S3 --> S5["Stage 5: Visual Studio & Web Workbench<br>(D3.js Tree Graphs, Token Data Table & Live Scope)"]
    S4 --> S5

    style A fill:#313244,stroke:#89b4fa,stroke-width:2px,color:#cdd6f4
    style S1 fill:#1e1e2e,stroke:#a6adc8,stroke-width:2px,color:#cdd6f4
    style S2 fill:#181825,stroke:#f9e2af,stroke-width:2px,color:#cdd6f4
    style S3 fill:#181825,stroke:#cba6f7,stroke-width:2px,color:#cdd6f4
    style S4 fill:#11111b,stroke:#89dceb,stroke-width:2px,color:#cdd6f4
    style S5 fill:#11111b,stroke:#a6e3a1,stroke-width:2px,color:#cdd6f4
```

---

## 🔍 Step-by-Step Deep Dive: What Happens at Every Stage

---

### 🔤 Stage 1: Lexical Analysis & Tokenization
**Files involved:** [`lexer.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/lexer.py)

#### 🎯 Goal
Scan the raw source code text, strip whitespace and comments, and convert the character stream into an ordered sequence of typed **Token** objects with line-number metadata.

```mermaid
flowchart LR
    Raw["Raw CHUD Code<br>let score = 42"] --> Lexer{"Lexer Loop<br>Maximal Munch"}
    
    Lexer -->|Whitespace / Comments| Skip["⏭️ Ignore & Advance"]
    Lexer -->|Keywords: check, let, make| KW["🏷️ Keyword Token"]
    Lexer -->|Numbers / Floats: 42, 3.14| Num["🔢 Number / Float Token"]
    Lexer -->|Strings: text| Str["📝 String Token"]
    Lexer -->|Operators: ==, <=, +| Op["⚡ Operator Token"]
    Lexer -->|Identifiers: score| Id["👤 Identifier Token"]
    
    KW --> Stream["Ordered Token Stream + EOF"]
    Num --> Stream
    Str --> Stream
    Op --> Stream
    Id --> Stream
```

#### 💡 How It Works
1. **Maximal Munch Principle:** The lexer matches the longest possible valid token at any cursor position. For instance:
   - `==` is captured as `EQEQ`, never as two separate `=` (`EQ`) tokens.
   - `<=` and `>=` take precedence over `<` and `>`.
   - `3.14` is matched as `FLOAT`, rather than `NUMBER` + `.` + `NUMBER`.
2. **Priority-Ordered Token Patterns:** Regex patterns are evaluated in strict precedence (`FLOAT` $\rightarrow$ `NUMBER` $\rightarrow$ `STRING` $\rightarrow$ `EQEQ` $\rightarrow$ `NEQ` $\rightarrow$ `LE` $\rightarrow$ `GE` $\rightarrow$ `EQ` $\rightarrow$ Single Character Operators $\rightarrow$ `IDENTIFIER`).
3. **Keyword Discrimination:** Any word matching the identifier pattern is checked against the internal `KEYWORDS` dictionary (`check`, `otherwise`, `keep`, `loop`, `let`, `make`, `return`, `yap`, `hear`, `stop`, `W`, `L`). If found, it receives a dedicated keyword token type; otherwise, it remains an `IDENTIFIER`.
4. **Line-Numbered Error Diagnostics:** Every token retains its 1-indexed source line. If an unknown character is encountered, a descriptive `LexError` is raised with the line number and diagnostic feedback.

---

### 🌳 Stage 2: Syntax Analysis & Grammar Parsing (CST & AST)
**Files involved:** [`parser.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/parser.py), [`ast_nodes.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py), [`cst_generator.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/cst_generator.py), [`ast_serializer.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_serializer.py)

#### 🎯 Goal
Validate the token stream against the formal CHUD grammar using **Recursive Descent Parsing** and generate two distinct structural trees: the **Concrete Syntax Tree (CST)** and the **Abstract Syntax Tree (AST)**.

```mermaid
flowchart TD
    Tokens["Token Stream from Lexer"] --> Parser["Recursive-Descent Parser (LL1)"]
    
    Parser --> GrammarRules["Grammar Rule Handlers:<br>• parse_program()<br>• parse_statement()<br>• parse_expression()<br>• parse_comparison()<br>• parse_term()<br>• parse_factor()<br>• parse_unary()<br>• parse_primary()"]
    
    GrammarRules --> CST["🌳 CST Generator<br>Full Derivation Tree<br>(Retains all punctuation & grammar steps)"]
    GrammarRules --> AST["🌿 AST Node Builder<br>Semantic Tree<br>(Clean nodes: Let, BinOp, Function, Check)"]
    
    AST --> Serializer["📊 AST Serializer<br>D3-ready JSON + Depth & Compaction Metrics"]
```

#### 💡 How It Works
1. **Recursive Descent Architecture:** Each non-terminal grammar rule is mapped to a dedicated parsing method. The parser uses `peek()`, `advance()`, and `expect(token_type)` to consume tokens without backtracking.
2. **Operator Precedence Cascade:** Mathematical and logical operators are structured hierarchically to enforce standard PEMDAS and relational ordering:
   $$\text{Comparison } (==, !=, <, >, <=, >=) \longrightarrow \text{Term } (+, -) \longrightarrow \text{Factor } (*, /) \longrightarrow \text{Unary } (+, -) \longrightarrow \text{Primary}$$
3. **CST vs. AST Distinction:**
   - **CST (Concrete Syntax Tree):** Captures every lexical artifact (braces, parentheses, semicolons, grammar non-terminals) for complete compiler-theoretical derivation.
   - **AST (Abstract Syntax Tree):** Distills the syntax down to pure semantic nodes ([`ProgramNode`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py), [`AssignNode`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py), [`BinOpNode`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py), [`CheckNode`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py), [`FunctionNode`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py)), stripping away syntactic fluff.
4. **AST Serialization & Stats:** `ast_serializer.py` computes tree statistics (Node Count, Maximum Tree Depth, Statement Counts, and CST-to-AST compactness percentage) for real-time visualization.

---

### ⚙️ Stage 3: Dual Execution Engine (Interpreter vs. Bytecode VM)
**Files involved:** [`interpreter.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/interpreter.py), [`compiler.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/compiler.py), [`vm.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/vm.py), [`test_vm_parity.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/test_vm_parity.py)

#### 🎯 Goal
Execute the validated program using two fundamentally different runtime paradigms and guarantee 100% execution output parity.

```mermaid
flowchart TD
    AST["Validated Abstract Syntax Tree (AST)"] --> Choice{"Execution Mode"}
    
    Choice -->|Engine A| Interp["🏃 Tree-Walk Interpreter (interpreter.py)<br>• Evaluates AST nodes recursively<br>• Lexical Environment Scope chain<br>• Direct expression evaluation"]
    
    Choice -->|Engine B| Comp["⚡ Bytecode Compiler (compiler.py)<br>• Emits flat instruction stream (Chunk)<br>• Constant pool deduplication<br>• Jump backpatching"]
    
    Comp --> VM["🖥️ Stack-based VM (vm.py)<br>• Instruction Pointer (ip)<br>• Push/Pop Value Stack<br>• Call Frames for functions"]
    
    Interp --> Out["Terminal Output + Variable State"]
    VM --> Out
```

#### 💡 Comparative Engine Architecture:

| Feature | Tree-Walk Interpreter (`interpreter.py`) | Bytecode Virtual Machine (`compiler.py` + `vm.py`) |
| :--- | :--- | :--- |
| **Execution Model** | Recursive visitor on AST node hierarchy | Linear instruction dispatch loop on a stack machine |
| **Intermediate Representation** | In-Memory AST Node Graph | Flat `Chunk` of numeric OpCodes & Constants |
| **Memory / Variable State** | Chained `Environment` symbol table dictionaries | Local/Global variable tables & Value Stack slots |
| **Function Invocations** | Python recursive calls creating new `Environment` instances | Discrete `CallFrame` stack with isolated `ip` and base pointer |
| **Loop / Jump Handling** | Native Python `while` / `for` loop traversal | `OP_JUMP` & `OP_JUMP_IF_FALSE` relative bytecode offsets |
| **Safety Guard** | 100,000 max loop iteration threshold | Instruction-level boundary & stack underflow protection |

---

### ⚡ Stage 4: Bytecode Compilation & Stack-Based VM Deep Dive
**Files involved:** [`bytecode.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/bytecode.py), [`compiler.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/compiler.py), [`vm.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/vm.py)

#### 🎯 Goal
Flatten complex hierarchical control flow, arithmetic, and lexical function calls into a linear bytecode sequence executable by an industrial-style virtual machine.

```mermaid
flowchart LR
    SubAST["AST: 2 + 3 * 4"] --> Comp["Compiler Visitor"]
    Comp --> Chk["Chunk Instructions:<br>1. OP_CONST 2<br>2. OP_CONST 3<br>3. OP_CONST 4<br>4. OP_MUL<br>5. OP_ADD<br>6. OP_HALT"]
    Chk --> VMExec["VM Execution Loop:<br>• Push 2<br>• Push 3<br>• Push 4<br>• Pop 4 and 3 => Push 12<br>• Pop 12 and 2 => Push 14"]
```

#### 💡 Key VM & Compiler Mechanisms:
1. **Bytecode OpCode Set:** Clean, modular instructions defining language operations:
   - **Stack & Constants:** `OP_CONST`, `OP_LOAD`, `OP_STORE`, `OP_POP`
   - **Arithmetic & Logic:** `OP_ADD`, `OP_SUB`, `OP_MUL`, `OP_DIV`, `OP_EQ`, `OP_NEQ`, `OP_LT`, `OP_GT`, `OP_LTE`, `OP_GTE`, `OP_NEG`, `OP_POS`
   - **Control Flow:** `OP_JUMP`, `OP_JUMP_IF_FALSE`, `OP_HALT`
   - **I/O & Subroutines:** `OP_YAP`, `OP_HEAR`, `OP_DEF_FUNC`, `OP_CALL`, `OP_RETURN`
2. **Backpatching for Jumps:** When compiling `check` conditionals or `keep` loops, forward target jump addresses are unknown. The compiler emits dummy placeholder operands, tracks the emitted position, compiles the body, and "backpatches" the exact relative jump offset.
3. **Loop `stop` (Break) Patch Stacks:** Nested loops maintain a stack of unresolved break jumps. When the loop body finishes, all pending `stop` statements are patched to jump directly past the loop exit.
4. **CallFrame Subroutine Architecture:** When `OP_CALL` executes, a new `CallFrame` is pushed containing the target `CHUDFunctionProto`, its own instruction pointer (`ip`), and local argument values. `OP_RETURN` unwinds the top frame and restores caller state.

---

### 🖥️ Stage 5: Interactive Visual Studio & Zero-Dependency HTTP Server
**Files involved:** [`server.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/server.py), [`index.html`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/index.html), [`style.css`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/style.css), [`app.js`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/app.js)

#### 🎯 Goal
Provide a modern developer studio for real-time visual inspection of compiler stages, token streams, syntax trees, and live runtime memory.

```mermaid
flowchart TD
    Client["🌐 Browser Frontend (app.js + index.html)"] --> API{"REST JSON Endpoints<br>server.py on port 8000"}
    
    API -->|POST /api/parse| PRes["Returns: Tokens Stream, AST D3 Graph, CST D3 Graph"]
    API -->|POST /api/compile| CRes["Returns: Bytecode Disassembly & Constants Pool"]
    API -->|POST /api/run| RRes["Returns: Execution Output, Active Scope & Diagnostics"]
    API -->|POST /api/all| ARes["Returns: Complete Parse + Compile + Run Composite Payload"]
```

#### 💡 Visual Studio Capabilities:
1. **Split-Pane IDE Layout:** Left-hand code editor with line gutter and syntax tracking; right-hand interactive inspector tabs.
2. **Interactive D3.js Tree Graphs:** Dynamic vector trees for both CST and AST with pan/zoom controls, node searching, collapsible branches, and SVG export.
3. **Lexical Tokens Pro Data Table:** Searchable, category-filtered table displaying token indices, types, lexemes, categories, and one-click source line jumping.
4. **Interactive JSON Tree Inspector:** Collapsible JSON tree viewer with live payload metrics (Node Count, Tree Depth, Payload Size in KB) and JSON export.
5. **Interactive Input Modal:** Graceful browser-native modal prompts for `hear` statements with type coercion.
6. **Multi-Theme Engine:** Space Dark, Studio Light, Midnight Blue, and Titanium Monochrome themes.

---

## 📁 Complete File Directory Reference

| File Path | Primary Function |
| :--- | :--- |
| [`lexer.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/lexer.py) | Maximal-munch lexical analyzer converting raw CHUD source into typed, line-numbered `Token` streams. |
| [`parser.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/parser.py) | LL(1)-style recursive-descent parser constructing hierarchical AST nodes and validating syntax rules. |
| [`ast_nodes.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_nodes.py) | Object-oriented AST node schema definitions for statements, expressions, control blocks, and functions. |
| [`cst_generator.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/cst_generator.py) | Full Concrete Syntax Tree generator capturing all grammar non-terminals, tokens, and punctuation. |
| [`ast_serializer.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/ast_serializer.py) | D3-compliant tree serializer with node hierarchy formatting, tree depth calculation, and compactness metrics. |
| [`interpreter.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/interpreter.py) | Scoped Tree-Walk Interpreter with lexical `Environment` chaining, runtime type-checking, and loop safety limits. |
| [`compiler.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/compiler.py) | Single-pass bytecode compiler translating AST into bytecode chunks with constant pooling and jump backpatching. |
| [`vm.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/vm.py) | Stack-based Virtual Machine with `CallFrame` subroutine management, instruction dispatch, and runtime stack. |
| [`bytecode.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/bytecode.py) | Bytecode `OpCode` definitions, `Chunk` container, `CHUDFunctionProto`, and human-readable disassembler. |
| [`server.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/server.py) | Zero-dependency HTTP server (`http.server`) hosting the studio web client and REST JSON API endpoints. |
| [`chud.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/chud.py) | Standalone CLI entrypoint supporting `.chud` script execution and interactive REPL mode. |
| [`index.html`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/index.html) | Split-pane Studio Web IDE user interface with D3 canvas, token data table, and JSON inspector. |
| [`style.css`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/style.css) | Custom styling, CSS variable design systems, responsive split panes, and multi-theme definitions. |
| [`app.js`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/app.js) | Frontend controller managing D3 graph rendering, zoom/pan controls, token filtering, and API communication. |
| [`test_all.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/test_all.py) | End-to-end integration test suite verifying Lexer, Parser, CST, AST, Interpreter, and Server components. |
| [`test_vm_parity.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/test_vm_parity.py) | 19-test automated parity test suite verifying identical execution between the Tree-Walk Interpreter and Bytecode VM. |
| [`test_pipeline.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/test_pipeline.py) | Multi-stage pipeline verification suite testing parsing, serialization, and compilation stages. |
| [`test_server.py`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/test_server.py) | Unit tests verifying HTTP endpoints (`/api/parse`, `/api/compile`, `/api/run`, `/api/all`). |
| [`game.chud`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/game.chud) | Interactive number guessing game demonstrating loops, conditionals, input, and state mutation in CHUD. |
| [`rizz_calculator.chud`](file:///d:/CHUD%20-%20Custom%20High-level%20User%20Development%20Language/rizz_calculator.chud) | Sample CHUD script demonstrating functions, arithmetic evaluation, and conditional branching. |

---

## 🚀 Quick Commands Cheatsheet

```bash
# 1. Launch the Interactive Visualizer Studio Web Workbench
python server.py
# -> Open http://localhost:8000 in your browser (or python server.py 8080 for custom port)

# 2. Run CHUD Script Files from Command Line
python chud.py game.chud
python chud.py rizz_calculator.chud

# 3. Launch the Interactive CHUD REPL
python chud.py

# 4. Run the Full Compiler & Integration Test Suite
python test_all.py

# 5. Run the Bytecode VM vs. Interpreter Parity Verification Suite (19 Tests)
python test_vm_parity.py

# 6. Run Server API & Pipeline Test Suites
python test_server.py
python test_pipeline.py
```
