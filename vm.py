# ─────────────────────────────────────────────
#  CHUD — vm.py
#  Executes a Chunk of bytecode.
#  A stack machine: instructions push/pop values,
#  the instruction pointer (ip) walks the chunk.
#
#  Scope for this file (Step 3): straight-line
#  code only — no JUMP / JUMP_IF_FALSE handling
#  of actual control flow yet (that's Step 4,
#  though the opcodes are handled here so the
#  VM is ready for them).
# ─────────────────────────────────────────────

from bytecode import OpCode, CHUDFunctionProto
from lexer import roast


class VMRuntimeError(Exception):
    pass


class VM:
    def __init__(self, input_fn=None, output_fn=None):
        self.stack     = []          # the value stack
        self.variables = {}          # variable table
        self.output    = []          # collected yap output
        self.output_fn = output_fn   # optional live callback
        self.input_fn  = input_fn or input  # input callback for hear

    # ── helpers (same shape as interpreter.py) ──

    def stringify(self, val):
        if isinstance(val, bool):
            return "W" if val else "L"
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)

    def _type_name(self, value):
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    def _require_number(self, value, line, operator):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise VMRuntimeError(
                f"line {line}: Operator '{operator}' needs a number, not {self._type_name(value)}.\n→ {roast()}"
            )

    def push(self, value):
        self.stack.append(value)

    def pop(self):
        if not self.stack:
            raise VMRuntimeError(f"Stack underflow — VM tried to pop an empty stack.\n→ {roast()}")
        return self.stack.pop()

    # ══════════════════════════════════════════
    #  THE MAIN LOOP
    #  This is the entire "execution engine".
    #  Everything else in this file just supports it.
    # ══════════════════════════════════════════

    def run(self, chunk):
        self.stack = []
        stack = self.stack
        constants = chunk.constants
        variables = self.variables
        instructions = [(instr.op, instr.arg, instr.line) for instr in chunk.instructions]
        n_instructions = len(instructions)
        ip = 0

        try:
            while ip < n_instructions:
                op, arg, line = instructions[ip]

                # ── stack basics ──
                if op == OpCode.PUSH_CONST:
                    stack.append(constants[arg])

                elif op == OpCode.POP:
                    stack.pop()

                # ── variables ──
                elif op == OpCode.STORE_VAR:
                    variables[arg] = stack.pop()

                elif op == OpCode.ASSIGN_VAR:
                    if arg not in variables:
                        raise VMRuntimeError(
                            f"line {line}: Cannot assign to '{arg}' before declaring with 'let'.\n→ {roast()}"
                        )
                    variables[arg] = stack.pop()

                elif op == OpCode.LOAD_VAR:
                    if arg not in variables:
                        raise VMRuntimeError(
                            f"line {line}: Variable '{arg}' is not defined.\n→ {roast()}"
                        )
                    stack.append(variables[arg])

                # ── arithmetic ──
                elif op == OpCode.ADD:
                    b, a = stack.pop(), stack.pop()
                    if isinstance(a, str) or isinstance(b, str):
                        stack.append(self.stringify(a) + self.stringify(b))
                    else:
                        self._require_number(a, line, '+')
                        self._require_number(b, line, '+')
                        stack.append(a + b)

                elif op == OpCode.SUB:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '-')
                    self._require_number(b, line, '-')
                    stack.append(a - b)

                elif op == OpCode.MUL:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '*')
                    self._require_number(b, line, '*')
                    stack.append(a * b)

                elif op == OpCode.DIV:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '/')
                    self._require_number(b, line, '/')
                    if b == 0:
                        raise VMRuntimeError(f"line {line}: Division by zero is forbidden.\n→ {roast()}")
                    res = a / b
                    stack.append(int(res) if isinstance(res, float) and res.is_integer() else res)

                # ── unary ──
                elif op == OpCode.NEG:
                    a = stack.pop()
                    self._require_number(a, line, '-')
                    stack.append(-a)

                elif op == OpCode.POS:
                    a = stack.pop()
                    self._require_number(a, line, '+')
                    stack.append(+a)

                # ── comparisons ──
                elif op == OpCode.EQ:
                    b, a = stack.pop(), stack.pop()
                    stack.append(a == b)

                elif op == OpCode.NEQ:
                    b, a = stack.pop(), stack.pop()
                    stack.append(a != b)

                elif op == OpCode.LT:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '<'); self._require_number(b, line, '<')
                    stack.append(a < b)

                elif op == OpCode.GT:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '>'); self._require_number(b, line, '>')
                    stack.append(a > b)

                elif op == OpCode.LTE:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '<='); self._require_number(b, line, '<=')
                    stack.append(a <= b)

                elif op == OpCode.GTE:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '>='); self._require_number(b, line, '>=')
                    stack.append(a >= b)

                # ── control flow ──
                elif op == OpCode.JUMP:
                    ip = arg
                    continue

                elif op == OpCode.JUMP_IF_FALSE:
                    cond = stack.pop()
                    if not cond:
                        ip = arg
                        continue
                    # else: fall through, ip += 1 as normal

                # ── I/O ──
                elif op == OpCode.PRINT:
                    val = stack.pop()
                    out_str = self.stringify(val)
                    self.output.append(out_str)
                    if self.output_fn:
                        self.output_fn(out_str)

                elif op == OpCode.HEAR:
                    prompt = stack.pop()
                    raw = str(self.input_fn(str(prompt) if prompt is not None else ""))
                    val = raw
                    if raw == "W":
                        val = True
                    elif raw == "L":
                        val = False
                    else:
                        try:
                            val = int(raw)
                        except ValueError:
                            try:
                                val = float(raw)
                            except ValueError:
                                val = raw
                    stack.append(val)

                # ── functions ──
                elif op == OpCode.CALL:
                    fn_name, arg_count = arg
                    args = [stack.pop() for _ in range(arg_count)][::-1]
                    if fn_name not in variables:
                        raise VMRuntimeError(f"line {line}: Function '{fn_name}' is not defined.")
                    fn_proto = variables[fn_name]
                    if not isinstance(fn_proto, CHUDFunctionProto):
                        raise VMRuntimeError(f"line {line}: '{fn_name}' is not a function.")
                    if len(args) != len(fn_proto.parameters):
                        raise VMRuntimeError(
                            f"line {line}: Function '{fn_name}' expects {len(fn_proto.parameters)} args, got {len(args)}."
                        )
                    child_vm = VM(input_fn=self.input_fn, output_fn=self.output_fn)
                    child_vm.variables.update(variables)
                    for p_name, p_val in zip(fn_proto.parameters, args):
                        child_vm.variables[p_name] = p_val
                    res = child_vm.run(fn_proto.chunk)
                    self.output.extend(child_vm.output)
                    if not res["success"]:
                        raise VMRuntimeError(res["error"])
                    stack.append(res.get("return_value"))

                elif op == OpCode.RETURN:
                    ret_val = stack.pop() if stack else None
                    return {
                        "success": True,
                        "output": self.output,
                        "variables": {k: self.stringify(v) for k, v in self.variables.items()},
                        "error": None,
                        "return_value": ret_val
                    }

                elif op == OpCode.HALT:
                    break

                else:
                    raise VMRuntimeError(f"Unknown opcode '{op}' at instruction {ip}")

                ip += 1

            return {
                "success": True,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.variables.items()},
                "error": None,
                "return_value": None
            }

        except VMRuntimeError as e:
            return {
                "success": False,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.variables.items()},
                "error": str(e),
                "return_value": None
            }


def run_source(source_code, input_fn=None):
    """Convenience: CHUD source string -> VM execution result."""
    from compiler import compile_source
    chunk = compile_source(source_code)
    vm = VM(input_fn=input_fn)
    return vm.run(chunk)


# ── Quick test ────────────────────────────────
if __name__ == '__main__':
    src = '''
let x = 2 + 3 * 4
let y = x - 1
yap y
yap x >= 10
yap "hello " + "bro"
'''
    result = run_source(src)
    print("Success:", result["success"])
    print("Output:", result["output"])
    print("Variables:", result["variables"])
