import os
from ast_nodes import (
    ProgramNode, AssignNode, YapNode, CheckNode,
    KeepNode, StopNode, SkipNode, BinOpNode, UnaryOpNode,
    NumberNode, StringNode, BoolNode, IdentifierNode, HearNode,
    LoopNode, FunctionNode, CallNode, ReturnNode,
    ArrayLiteralNode, IndexAccessNode, IndexAssignNode,
    DictLiteralNode, UseNode
)
from lexer import Lexer, roast
from parser import Parser


class BreakSignal(Exception):
    """Raised by 'stop' statement to break out of loops."""
    pass


class ContinueSignal(Exception):
    """Raised by 'skip' statement to continue to next iteration of loops."""
    pass


class ReturnSignal(Exception):
    """Internal control flow used to leave a function with a value."""
    def __init__(self, value):
        self.value = value


class CHUDFunction:
    """A user-defined function and the environment it was declared in."""
    def __init__(self, declaration, closure):
        self.declaration = declaration
        self.closure = closure


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
    def __init__(self, input_fn=None, stdout_fn=None):
        self.global_env = Environment()
        self.output = []
        self.input_fn = input_fn or input
        self.stdout_fn = stdout_fn

    def stringify(self, val):
        if isinstance(val, bool):
            return "W" if val else "L"
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        if isinstance(val, list):
            return "[" + ", ".join(self.stringify(x) for x in val) + "]"
        if isinstance(val, dict):
            return "{" + ", ".join(f"{self.stringify(k)}: {self.stringify(v)}" for k, v in val.items()) + "}"
        if val is None:
            return "None"
        return str(val)

    def is_truthy(self, val):
        return bool(val)

    def _type_name(self, value):
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "dict"
        return type(value).__name__

    def _runtime_error(self, node, message):
        line = f"line {node.line}: " if getattr(node, "line", None) else ""
        return CHUDRuntimeError(f"{line}{message}\n→ {roast()}")

    def _require_number(self, value, node, operator):
        # bool is intentionally excluded even though Python treats it as an int.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise self._runtime_error(
                node,
                f"Operator '{operator}' needs a number, not {self._type_name(value)}."
            )

    def eval_expr(self, node, env):
        if isinstance(node, NumberNode):
            return node.value
        if isinstance(node, StringNode):
            return node.value
        if isinstance(node, BoolNode):
            return node.value
        if isinstance(node, IdentifierNode):
            return env.get(node.name)

        if isinstance(node, DictLiteralNode):
            d = {}
            for k_expr, v_expr in node.pairs:
                k = self.eval_expr(k_expr, env)
                v = self.eval_expr(v_expr, env)
                d[k] = v
            return d

        if isinstance(node, CallNode):
            # Built-in function: len
            if node.name == 'len':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'len' expects 1 argument, but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                if not isinstance(target, (list, str, dict)):
                    raise self._runtime_error(node, f"'len' argument must be array, string, or dict, not {self._type_name(target)}.")
                return len(target)

            # Built-in function: push
            if node.name == 'push':
                if len(node.arguments) != 2:
                    raise self._runtime_error(node, f"'push' expects 2 arguments (array, item), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                item = self.eval_expr(node.arguments[1], env)
                if not isinstance(target, list):
                    raise self._runtime_error(node, f"'push' first argument must be an array, not {self._type_name(target)}.")
                target.append(item)
                return None

            # Built-in function: pop
            if node.name == 'pop':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'pop' expects 1 argument (array), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                if not isinstance(target, list):
                    raise self._runtime_error(node, f"'pop' argument must be an array, not {self._type_name(target)}.")
                if not target:
                    raise self._runtime_error(node, "Cannot pop from an empty array.")
                return target.pop()

            # Built-in function: keys
            if node.name == 'keys':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'keys' expects 1 argument (dict), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                if not isinstance(target, dict):
                    raise self._runtime_error(node, f"'keys' argument must be a dict, not {self._type_name(target)}.")
                return list(target.keys())

            # Built-in function: values
            if node.name == 'values':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'values' expects 1 argument (dict), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                if not isinstance(target, dict):
                    raise self._runtime_error(node, f"'values' argument must be a dict, not {self._type_name(target)}.")
                return list(target.values())

            # Built-in function: has
            if node.name == 'has':
                if len(node.arguments) != 2:
                    raise self._runtime_error(node, f"'has' expects 2 arguments (dict/array, key/item), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                key = self.eval_expr(node.arguments[1], env)
                if isinstance(target, (dict, list, str)):
                    return key in target
                raise self._runtime_error(node, f"'has' first argument must be dict, array, or string, not {self._type_name(target)}.")

            # Built-in function: read_file
            if node.name == 'read_file':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'read_file' expects 1 argument (path), but received {len(node.arguments)}.")
                path = self.eval_expr(node.arguments[0], env)
                if not isinstance(path, str):
                    raise self._runtime_error(node, f"'read_file' path must be a string, not {self._type_name(path)}.")
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception as e:
                    raise self._runtime_error(node, f"Failed to read file '{path}': {e}")

            # Built-in function: write_file
            if node.name == 'write_file':
                if len(node.arguments) != 2:
                    raise self._runtime_error(node, f"'write_file' expects 2 arguments (path, content), but received {len(node.arguments)}.")
                path = self.eval_expr(node.arguments[0], env)
                content = self.eval_expr(node.arguments[1], env)
                if not isinstance(path, str) or not isinstance(content, str):
                    raise self._runtime_error(node, "'write_file' path and content must be strings.")
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return None
                except Exception as e:
                    raise self._runtime_error(node, f"Failed to write file '{path}': {e}")

            # Built-in function: file_exists
            if node.name == 'file_exists':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'file_exists' expects 1 argument (path), but received {len(node.arguments)}.")
                path = self.eval_expr(node.arguments[0], env)
                if not isinstance(path, str):
                    raise self._runtime_error(node, f"'file_exists' path must be a string, not {self._type_name(path)}.")
                return os.path.exists(path)

            # Built-in function: slice
            if node.name == 'slice':
                if len(node.arguments) != 3:
                    raise self._runtime_error(node, f"'slice' expects 3 arguments (target, start, end), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                start = self.eval_expr(node.arguments[1], env)
                end = self.eval_expr(node.arguments[2], env)
                if not isinstance(target, (list, str)):
                    raise self._runtime_error(node, f"'slice' target must be array or string, not {self._type_name(target)}.")
                if not isinstance(start, int) or not isinstance(end, int):
                    raise self._runtime_error(node, "'slice' start and end indices must be integers.")
                return target[start:end]

            # Built-in function: split
            if node.name == 'split':
                if len(node.arguments) != 2:
                    raise self._runtime_error(node, f"'split' expects 2 arguments (string, delimiter), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                delim = self.eval_expr(node.arguments[1], env)
                if not isinstance(target, str) or not isinstance(delim, str):
                    raise self._runtime_error(node, "'split' requires string arguments.")
                return target.split(delim)

            # Built-in function: trim
            if node.name == 'trim':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'trim' expects 1 argument (string), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                if not isinstance(target, str):
                    raise self._runtime_error(node, f"'trim' argument must be string, not {self._type_name(target)}.")
                return target.strip()

            # Built-in function: lower
            if node.name == 'lower':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'lower' expects 1 argument (string), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                if not isinstance(target, str):
                    raise self._runtime_error(node, f"'lower' argument must be string, not {self._type_name(target)}.")
                return target.lower()

            # Built-in function: upper
            if node.name == 'upper':
                if len(node.arguments) != 1:
                    raise self._runtime_error(node, f"'upper' expects 1 argument (string), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                if not isinstance(target, str):
                    raise self._runtime_error(node, f"'upper' argument must be string, not {self._type_name(target)}.")
                return target.upper()

            # Built-in function: replace
            if node.name == 'replace':
                if len(node.arguments) != 3:
                    raise self._runtime_error(node, f"'replace' expects 3 arguments (string, old, new), but received {len(node.arguments)}.")
                target = self.eval_expr(node.arguments[0], env)
                old_s = self.eval_expr(node.arguments[1], env)
                new_s = self.eval_expr(node.arguments[2], env)
                if not isinstance(target, str) or not isinstance(old_s, str) or not isinstance(new_s, str):
                    raise self._runtime_error(node, "'replace' arguments must be strings.")
                return target.replace(old_s, new_s)

            function = env.get(node.name)
            if not isinstance(function, CHUDFunction):
                raise self._runtime_error(node, f"'{node.name}' is not a function.")
            if len(node.arguments) != len(function.declaration.parameters):
                raise self._runtime_error(
                    node,
                    f"Function '{node.name}' expects {len(function.declaration.parameters)} argument(s), "
                    f"but received {len(node.arguments)}."
                )
            values = [self.eval_expr(argument, env) for argument in node.arguments]
            call_env = Environment(function.closure)
            for parameter, value in zip(function.declaration.parameters, values):
                call_env.define(parameter, value)
            try:
                for statement in function.declaration.body:
                    self.execute(statement, call_env)
            except ReturnSignal as signal:
                return signal.value
            return None

        if isinstance(node, ArrayLiteralNode):
            return [self.eval_expr(e, env) for e in node.elements]

        if isinstance(node, IndexAccessNode):
            target = self.eval_expr(node.target, env)
            index = self.eval_expr(node.index, env)
            if isinstance(target, dict):
                if index not in target:
                    raise self._runtime_error(node, f"Key '{index}' not found in dictionary.")
                return target[index]
            if not isinstance(target, (list, str)):
                raise self._runtime_error(node, f"Cannot index into non-array/string/dict type {self._type_name(target)}.")
            if not isinstance(index, int) or isinstance(index, bool):
                raise self._runtime_error(node, f"Array/String index must be an integer, not {self._type_name(index)}.")
            if index < 0 or index >= len(target):
                raise self._runtime_error(node, f"Index out of bounds (index {index}, length {len(target)}).")
            return target[index]

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
            if node.op in ('!', 'not'):
                return not self.is_truthy(val)
            self._require_number(val, node, node.op)
            if node.op == '-':
                return -val
            if node.op == '+':
                return +val
            raise CHUDRuntimeError(f"Unknown unary operator '{node.op}'\n→ {roast()}")

        if isinstance(node, BinOpNode):
            if node.op == 'and':
                left = self.eval_expr(node.left, env)
                if not self.is_truthy(left):
                    return False
                right = self.eval_expr(node.right, env)
                return bool(self.is_truthy(right))

            if node.op == 'or':
                left = self.eval_expr(node.left, env)
                if self.is_truthy(left):
                    return True
                right = self.eval_expr(node.right, env)
                return bool(self.is_truthy(right))

            left = self.eval_expr(node.left, env)
            right = self.eval_expr(node.right, env)

            if node.op == '+':
                if isinstance(left, str) or isinstance(right, str):
                    return self.stringify(left) + self.stringify(right)
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                return left + right
            if node.op == '-':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                return left - right
            if node.op == '*':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                return left * right
            if node.op == '/':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                if right == 0:
                    raise self._runtime_error(node, "Division by zero is forbidden.")
                res = left / right
                return int(res) if isinstance(res, float) and res.is_integer() else res
            if node.op == '%':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                if right == 0:
                    raise self._runtime_error(node, "Modulo by zero is forbidden.")
                res = left % right
                return int(res) if isinstance(res, float) and res.is_integer() else res

            if node.op == '==':
                return left == right
            if node.op == '!=':
                return left != right
            if node.op == '<':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                return left < right
            if node.op == '<=':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                return left <= right
            if node.op == '>':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                return left > right
            if node.op == '>=':
                self._require_number(left, node, node.op)
                self._require_number(right, node, node.op)
                return left >= right

            raise CHUDRuntimeError(f"Unknown binary operator '{node.op}'\n→ {roast()}")

        raise CHUDRuntimeError(f"Cannot evaluate node {type(node).__name__}\n→ {roast()}")

    def execute(self, node, env):
        if isinstance(node, CallNode):
            self.eval_expr(node, env)
            return

        if isinstance(node, AssignNode):
            val = self.eval_expr(node.value, env)
            if node.is_declaration:
                env.define(node.name, val)
            else:
                env.assign(node.name, val)
            return

        if isinstance(node, IndexAssignNode):
            target = self.eval_expr(node.target, env)
            index = self.eval_expr(node.index, env)
            val = self.eval_expr(node.value, env)
            if isinstance(target, dict):
                target[index] = val
                return
            if not isinstance(target, list):
                raise self._runtime_error(node, f"Cannot assign index to non-array/dict type {self._type_name(target)}.")
            if not isinstance(index, int) or isinstance(index, bool):
                raise self._runtime_error(node, f"Array index must be an integer, not {self._type_name(index)}.")
            if index < 0 or index >= len(target):
                raise self._runtime_error(node, f"Array index out of bounds (index {index}, length {len(target)}).")
            target[index] = val
            return

        if isinstance(node, UseNode):
            mod_path = node.module_path
            if not os.path.exists(mod_path):
                raise self._runtime_error(node, f"Cannot use module '{mod_path}': File not found.")
            with open(mod_path, 'r', encoding='utf-8') as f:
                mod_code = f.read()
            mod_tokens = Lexer(mod_code).tokenize()
            mod_ast = Parser(mod_tokens).parse()
            self.execute(mod_ast, env)
            return

        if isinstance(node, YapNode):
            val = self.eval_expr(node.value, env)
            out_str = self.stringify(val)
            self.output.append(out_str)
            if self.stdout_fn:
                self.stdout_fn(out_str)
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
                except ContinueSignal:
                    continue
            return

        if isinstance(node, LoopNode):
            # The initializer and its variable live only for this loop.
            loop_env = Environment(env)
            self.execute(node.initializer, loop_env)
            loop_iterations = 0
            while self.is_truthy(self.eval_expr(node.condition, loop_env)):
                loop_iterations += 1
                if loop_iterations > 100000:
                    raise self._runtime_error(node, "Loop exceeded 100,000 iterations. Infinite loop detected!")
                try:
                    body_env = Environment(loop_env)
                    for stmt in node.body:
                        self.execute(stmt, body_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    pass
                self.execute(node.update, loop_env)
            return

        if isinstance(node, FunctionNode):
            env.define(node.name, CHUDFunction(node, env))
            return

        if isinstance(node, ReturnNode):
            raise ReturnSignal(self.eval_expr(node.value, env))

        if isinstance(node, StopNode):
            raise BreakSignal()

        if isinstance(node, SkipNode):
            raise ContinueSignal()

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
                "variables": {k: self.stringify(v) for k, v in self.global_env.all_bindings().items() if not isinstance(v, CHUDFunction)},
                "error": None
            }
        except BreakSignal:
            return {
                "success": False,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.global_env.all_bindings().items() if not isinstance(v, CHUDFunction)},
                "error": "Syntax/Runtime error: 'stop' called outside of any 'keep' loop."
            }
        except ReturnSignal:
            return {
                "success": False,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.global_env.all_bindings().items() if not isinstance(v, CHUDFunction)},
                "error": "Syntax/Runtime error: 'return' called outside of any 'make' function."
            }
        except CHUDRuntimeError as e:
            return {
                "success": False,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.global_env.all_bindings().items() if not isinstance(v, CHUDFunction)},
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
