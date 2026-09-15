# CHUD

**Custom High-level User Development Language** is a small, educational programming language built to make the journey from source code to execution visible. It includes a lexer, a recursive-descent parser, AST and CST generation, a tree-walk interpreter, and a browser-based visualizer.

CHUD is currently an **interpreter project and language-learning tool**. It is not yet a native-code compiler or a production programming language. Compiler work—such as an intermediate representation, bytecode, optimization, and code generation—is planned for a future stage.

![CHUD pipeline architecture](pipeline.png)

## Why this project exists

Most programming languages hide their internals. CHUD exposes them. You can write a short program, inspect its tokens, compare its abstract and concrete syntax trees, and execute it in the same workspace.

It was created to practice and demonstrate:

- maximal-munch lexing;
- recursive-descent parsing and operator precedence;
- Abstract Syntax Tree (AST) and Concrete Syntax Tree (CST) construction;
- scoped tree-walk interpretation; and
- approachable diagnostics with a memorable personality.

## Current capabilities

| Area | What CHUD supports today |
| --- | --- |
| Language | Variables, numbers, strings, booleans, arithmetic, comparisons, conditionals, while and classic `for` loops, functions, input, output, and loop breaks |
| Frontend | Source editor, AST/CST explorer, token stream, console, variable inspector, zoom/pan, search, themes, and examples |
| Runtime | Lexical block scoping, input conversion, output capture, type diagnostics, division-by-zero protection, and loop-iteration protection |
| API | Python standard-library server with `/api/parse`, `/api/run`, `/api/all`, and `/api/compile` endpoints |
| Testing | Pipeline, interpreter behavior, parser/lexer failures, static serving, payload validation, and path-traversal checks |

## Quick start

### Requirements

- Python 3.9 or newer
- A modern browser for the visualizer

CHUD uses only the Python standard library. No packages need to be installed.

### Open the visualizer

```bash
python server.py
```

Open <http://localhost:8000>. Choose an example or write a program, then use **Run**, **Visualize**, or **Run & Visualize**.

To use a different port:

```bash
python server.py 8080
```

### Run CHUD from the terminal

```bash
python chud.py game.chud
python chud.py rizz_calculator.chud
```

Start the interactive REPL with:

```bash
python chud.py
```

### Run the checks

```bash
python test_all.py
```

For focused work, run `python test_pipeline.py` or `python test_server.py`.

## Learn to write CHUD

New to the language? Start with the [CHUD writing guide](CHUD_GUIDE.md). It walks through variables, output, input, decisions, loops, comments, common mistakes, and a complete mini-program.

## A first CHUD program

```chud
let name = hear "What is your name? "
let score = 8

check score >= 5 {
    yap "W behavior, " + name
} otherwise {
    yap "Keep practicing, " + name
}
```

More runnable examples: [game.chud](game.chud) and [rizz_calculator.chud](rizz_calculator.chud).

## Language reference

### Values and variables

```chud
let age = 19
let ratio = 3.14
let message = "hello"
let winning = W
let losing = L

age = age + 1
```

- `let` declares a variable.
- A variable must be declared before it can be reassigned.
- `W` is true and `L` is false.
- Names declared inside a `check` or `keep` block are local to that block.
- Assignments in a nested block can update names declared in an outer scope.

### Input and output

```chud
yap "Current score: " + score
let guess = hear "Enter a number: "
```

`yap` prints an expression. `hear` reads one value; numeric input becomes an integer or float, while other input remains a string.

### Expressions

```chud
let total = 2 + 3 * 4
let grouped = (2 + 3) * 4
let passed = total >= 10
```

| Operators | Meaning |
| --- | --- |
| `==` `!=` `<` `>` `<=` `>=` | Comparisons |
| `+` `-` | Addition, string concatenation, subtraction |
| `*` `/` | Multiplication and division |
| unary `+` unary `-` | Positive and negative values |

Operators are listed from lower to higher precedence. Arithmetic requires numbers, except `+`, which concatenates when either side is a string. Ordering comparisons require numbers. Parentheses control evaluation order.

### Conditions and loops

```chud
check age >= 18 {
    yap "adult"
} otherwise {
    yap "minor"
}

let count = 0
keep count < 3 {
    yap count
    count = count + 1
}
```

Conditions use normal truthiness: `L`, `0`, and an empty string are false; other values are true. `stop` exits the nearest `keep` loop.

```chud
keep W {
    yap "one pass only"
    stop
}
```

The interpreter stops a loop after 100,000 iterations to protect the browser workspace from accidental infinite loops.

For a classic `for` loop, use `loop`; this keeps it distinct from the `keep` while-loop syntax.

```chud
loop let i = 0; i < 3; i = i + 1 {
    yap i
}
```

The loop initializer is scoped to the loop. `stop` exits either type of loop.

### Functions

Declare a function with `make`, call it with parentheses, and use `return` to produce a value.

```chud
make add(first, second) {
    return first + second
}

let total = add(4, 6)
yap total
```

Parameters and variables declared inside a function are local to that call. A function must be declared before it is called, and `return` is only valid inside a function.

### Comments and current limits

```chud
// This is a single-line comment
let score = 10
```

Strings use double quotes and do not yet support escape sequences. CHUD does not yet have arrays, modules, classes, static type checking, or code generation.

## Architecture

```text
CHUD source
    |
    v
Lexer --------------> token stream
    |
    v
Recursive-descent parser
    |                 \
    v                  v
AST ----------------> tree-walk interpreter
    |                  |
    v                  v
AST serializer       output + visible variables
    |
    v
Browser visualizer (AST, CST, tokens, console)
```

### Project map

| File | Responsibility |
| --- | --- |
| `lexer.py` | Tokenizes CHUD source and tracks line numbers |
| `parser.py` | Builds an AST with recursive descent parsing |
| `ast_nodes.py` | Defines AST node structures |
| `ast_serializer.py` | Converts AST nodes to visualizer JSON |
| `cst_generator.py` | Produces a CST for grammar inspection |
| `interpreter.py` | Evaluates the AST in scoped environments |
| `server.py` | Serves the studio and exposes the JSON API |
| `chud.py` | CLI file runner and REPL |
| `index.html`, `style.css`, `app.js` | Browser studio |
| `test_pipeline.py`, `test_server.py`, `test_all.py` | Automated checks |

## HTTP API

Requests use JSON with a `code` string and, for execution, an optional `inputs` list.

| Endpoint | Purpose |
| --- | --- |
| `POST /api/parse` | Returns tokens, AST data, and CST data without execution |
| `POST /api/compile` | Alias for `/api/parse` |
| `POST /api/run` | Executes code and returns output, variables, and errors |
| `POST /api/all` | Parses and executes code in one request |

Example request:

```json
{
  "code": "let score = 4\nyap score + 1",
  "inputs": []
}
```

The server validates JSON bodies and request shapes, caps request size at 1 MB, and serves only files within the project directory.

## Error handling

CHUD catches lexical, parsing, and runtime errors and includes the relevant line when available. Its “roast” messages are part of the project personality, but the actual error is stated first.

Handled errors include unexpected characters, malformed syntax, missing braces or values, undeclared variables, invalid numeric operations, division by zero, and `stop` outside a loop.

## Roadmap

The current milestone is complete as an interpreter and visualizer. After the semester, possible next stages are:

1. functions and collections;
2. a formal grammar and richer source-span diagnostics;
3. an intermediate representation (IR) or bytecode format;
4. a bytecode virtual machine or compiler backend;
5. static analysis, types, and optimization; and
6. packaging and broader automated tests.

## License

CHUD is available under the [MIT License](LICENSE).
