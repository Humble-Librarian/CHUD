# ─────────────────────────────────────────────
#  CHUD — ast_nodes.py
#  Every node type the parser will produce.
#  These are pure data classes — no logic here.
# ─────────────────────────────────────────────

class NumberNode:
    """A literal number: 42, 3, 100"""
    def __init__(self, value, line=None):
        self.value = value          # float or int
        self.line  = line

    def __repr__(self):
        return f"Number({self.value})"


class StringNode:
    """A literal string: "hello bro" """
    def __init__(self, value, line=None):
        self.value = value          # str, without quotes
        self.line  = line

    def __repr__(self):
        return f"String({repr(self.value)})"


class BoolNode:
    """A boolean literal: W (true) or L (false)"""
    def __init__(self, value, line=None):
        self.value = value          # Python bool
        self.line  = line

    def __repr__(self):
        return f"Bool({'W' if self.value else 'L'})"


class IdentifierNode:
    """A variable name: score, age, name"""
    def __init__(self, name, line=None):
        self.name = name            # str
        self.line = line

    def __repr__(self):
        return f"Id({self.name})"


class HearNode:
    """User input expression: hear or hear "Prompt: " """
    def __init__(self, prompt=None, line=None):
        self.prompt = prompt        # str or None
        self.line   = line

    def __repr__(self):
        return f"Hear({repr(self.prompt)})"


class UnaryOpNode:
    """A unary operation: OP operand (e.g. -5, -x)"""
    def __init__(self, op, operand, line=None):
        self.op      = op           # str: '-' or '+'
        self.operand = operand      # any expression node
        self.line    = line

    def __repr__(self):
        return f"UnaryOp({self.op}{self.operand})"


class BinOpNode:
    """A binary operation: left OP right
    e.g. 2 + 3,  x * 4,  age >= 18
    """
    def __init__(self, left, op, right, line=None):
        self.left  = left           # any expression node
        self.op    = op             # str: '+' '-' '*' '/' '==' '<' '>' '<=' '>='
        self.right = right          # any expression node
        self.line  = line

    def __repr__(self):
        return f"BinOp({self.left} {self.op} {self.right})"


class AssignNode:
    """Variable assignment: let name = expr  OR  name = expr (reassign)
    is_declaration=True  →  'let name = ...'
    is_declaration=False →  'name = ...' (reassign existing var)
    """
    def __init__(self, name, value, is_declaration=False, line=None):
        self.name            = name             # str
        self.value           = value            # any expression node
        self.is_declaration  = is_declaration   # bool
        self.line            = line

    def __repr__(self):
        prefix = "let " if self.is_declaration else ""
        return f"Assign({prefix}{self.name} = {self.value})"


class YapNode:
    """Print statement: yap expr"""
    def __init__(self, value, line=None):
        self.value = value          # any expression node
        self.line  = line

    def __repr__(self):
        return f"Yap({self.value})"


class CheckNode:
    """If/otherwise statement:
    check condition { body } otherwise { else_body }
    else_body is optional (can be None or empty list)
    """
    def __init__(self, condition, body, else_body=None, line=None):
        self.condition = condition  # any expression node
        self.body      = body       # list of statement nodes
        self.else_body = else_body  # list of statement nodes or None
        self.line      = line

    def __repr__(self):
        has_else = self.else_body is not None
        return f"Check({self.condition}, body={len(self.body)} stmts, otherwise={'yes' if has_else else 'no'})"


class KeepNode:
    """While loop: keep condition { body }"""
    def __init__(self, condition, body, line=None):
        self.condition = condition  # any expression node
        self.body      = body       # list of statement nodes
        self.line      = line

    def __repr__(self):
        return f"Keep({self.condition}, body={len(self.body)} stmts)"


class StopNode:
    """Break statement: stop (exits the nearest keep loop)"""
    def __init__(self, line=None):
        self.line = line

    def __repr__(self):
        return "Stop()"


class ProgramNode:
    """Root node — the entire CHUD program.
    Contains a list of top-level statements.
    """
    def __init__(self, statements):
        self.statements = statements    # list of statement nodes

    def __repr__(self):
        return f"Program({len(self.statements)} statements)"
