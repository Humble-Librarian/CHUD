# ─────────────────────────────────────────────
#  CHUD — interpreter.py
#  Tree-walk interpreter for CHUD AST.
#  Evaluates expressions and executes statements.
# ─────────────────────────────────────────────

from ast_nodes import (
    ProgramNode, AssignNode, YapNode, CheckNode,
    KeepNode, StopNode, BinOpNode, UnaryOpNode,
    NumberNode, StringNode, BoolNode, IdentifierNode, HearNode
)
from lexer import Lexer, roast
from parser import Parser


class BreakSignal(Exception):
    """Raised by 'stop' statement to break out of keep loops."""
    pass


class CHUDRuntimeError(Exception):
    """Runtime error with contextual roast."""
    pass


class Environment:
    """Scoped variable storage environment."""
    def __init__(self, parent=None):
        self.values = {}
        self.parent = parent

    def define(self, name, value):
        self.values[name] = value

    def assign(self, name, value):
        if name in self.values:
            self.values[name] = value
            return
        if self.parent:
            self.parent.assign(name, value)
            return
        raise CHUDRuntimeError(
            f"Cannot assign to '{name}' before declaring with 'let'.\n→ {roast()}"
        )

    def get(self, name):
        if name in self.values:
            return self.values[name]
        if self.parent:
            return self.parent.get(name)
        raise CHUDRuntimeError(
            f"Variable '{name}' is not defined.\n→ {roast()}"
        )

    def all_bindings(self):
        """Flatten all visible variable bindings for inspection."""
        b = self.parent.all_bindings() if self.parent else {}
        b.update(self.values)
        return b


class Interpreter:
    def __init__(self, input_fn=None):
        self.global_env = Environment()
        self.output = []
        self.input_fn = input_fn or input

    def stringify(self, val):
        if isinstance(val, bool):
            return "W" if val else "L"
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)

    def is_truthy(self, val):
        return bool(val)

    def eval_expr(self, node, env):
        if isinstance(node, NumberNode):
            return node.value
        if isinstance(node, StringNode):
            return node.value
        if isinstance(node, BoolNode):
            return node.value
        if isinstance(node, IdentifierNode):
            return env.get(node.name)

        if isinstance(node, HearNode):
            prompt = node.prompt if node.prompt is not None else ""
            try:
                raw_val = self.input_fn(prompt)
            except (EOFError, KeyboardInterrupt):
                raw_val = ""
            # Auto-cast to int / float if numeric
            try:
                if '.' in str(raw_val):
                    return float(raw_val)
                return int(raw_val)
            except ValueError:
                return str(raw_val)

        if isinstance(node, UnaryOpNode):
            val = self.eval_expr(node.operand, env)
            if node.op == '-':
                return -val
            if node.op == '+':
                return +val
            raise CHUDRuntimeError(f"Unknown unary operator '{node.op}'\n→ {roast()}")

        if isinstance(node, BinOpNode):
            left = self.eval_expr(node.left, env)
            right = self.eval_expr(node.right, env)

            if node.op == '+':
                if isinstance(left, str) or isinstance(right, str):
                    return self.stringify(left) + self.stringify(right)
                return left + right
            if node.op == '-':
                return left - right
            if node.op == '*':
                return left * right
            if node.op == '/':
                if right == 0:
                    raise CHUDRuntimeError(f"Division by zero is forbidden.\n→ {roast()}")
                res = left / right
                return int(res) if isinstance(res, float) and res.is_integer() else res

            if node.op == '==':
                return left == right
            if node.op == '!=':
                return left != right
            if node.op == '<':
                return left < right
            if node.op == '<=':
                return left <= right
            if node.op == '>':
                return left > right
            if node.op == '>=':
                return left >= right

            raise CHUDRuntimeError(f"Unknown binary operator '{node.op}'\n→ {roast()}")

        raise CHUDRuntimeError(f"Cannot evaluate node {type(node).__name__}\n→ {roast()}")

    def execute(self, node, env):
        if isinstance(node, AssignNode):
            val = self.eval_expr(node.value, env)
            if node.is_declaration:
                env.define(node.name, val)
            else:
                env.assign(node.name, val)
            return

        if isinstance(node, YapNode):
            val = self.eval_expr(node.value, env)
            out_str = self.stringify(val)
            self.output.append(out_str)
            return

        if isinstance(node, CheckNode):
            cond = self.eval_expr(node.condition, env)
            if self.is_truthy(cond):
                block_env = Environment(env)
                for stmt in node.body:
                    self.execute(stmt, block_env)
            elif node.else_body is not None:
                block_env = Environment(env)
                for stmt in node.else_body:
                    self.execute(stmt, block_env)
            return

        if isinstance(node, KeepNode):
            loop_iterations = 0
            while self.is_truthy(self.eval_expr(node.condition, env)):
                loop_iterations += 1
                if loop_iterations > 100000:
                    raise CHUDRuntimeError(f"Loop exceeded 100,000 iterations. Infinite loop detected!\n→ {roast()}")
                try:
                    block_env = Environment(env)
                    for stmt in node.body:
                        self.execute(stmt, block_env)
                except BreakSignal:
                    break
            return

        if isinstance(node, StopNode):
            raise BreakSignal()

        if isinstance(node, ProgramNode):
            for stmt in node.statements:
                self.execute(stmt, env)
            return

        raise CHUDRuntimeError(f"Cannot execute statement {type(node).__name__}\n→ {roast()}")

    def run(self, ast):
        self.output = []
        try:
            self.execute(ast, self.global_env)
            return {
                "success": True,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.global_env.all_bindings().items()},
                "error": None
            }
        except BreakSignal:
            return {
                "success": False,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.global_env.all_bindings().items()},
                "error": "Syntax/Runtime error: 'stop' called outside of any 'keep' loop."
            }
        except (CHUDRuntimeError, Exception) as e:
            return {
                "success": False,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.global_env.all_bindings().items()},
                "error": str(e)
            }


def interpret(source_code, input_fn=None):
    """Convenience function: source code string -> execution result dict."""
    tokens = Lexer(source_code).tokenize()
    ast = Parser(tokens).parse()
    interp = Interpreter(input_fn=input_fn)
    return interp.run(ast)


if __name__ == '__main__':
    code = '''
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
}
'''
    res = interpret(code)
    print("Execution Success:", res["success"])
    print("Output:")
    for line in res["output"]:
        print("  ", line)
    print("Variables:", res["variables"])
