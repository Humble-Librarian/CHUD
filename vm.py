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

from bytecode import OpCode, CHUDFunctionProto, CallFrame
from lexer import roast


class VMRuntimeError(Exception):
    pass


class VM:
    def __init__(self, input_fn=None, output_fn=None):
        self.stack     = []          # the value stack
        self.globals   = {}          # global variable table
        self.variables = self.globals# alias for testing/external compatibility
        self.frames    = []          # call stack of CallFrame objects
        self.output    = []          # collected yap output
        self.output_fn = output_fn   # optional live callback
        self.input_fn  = input_fn or input  # input callback for hear

    # ── helpers (same shape as interpreter.py) ──

    def stringify(self, val):
        if isinstance(val, bool):
            return "W" if val else "L"
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        if isinstance(val, list):
            return "[" + ", ".join(self.stringify(x) for x in val) + "]"
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
    #  Single-instance CallFrame stack machine.
    # ══════════════════════════════════════════

    def run(self, chunk):
        self.stack = []
        self.output = []
        self.globals = {}
        self.variables = self.globals
        stack = self.stack

        # Initialize root/main call frame
        main_proto = CHUDFunctionProto("<main>", [], chunk)
        self.frames = [CallFrame(main_proto, self.globals)]

        try:
            while self.frames:
                frame = self.frames[-1]
                instructions = frame.instructions
                constants = frame.constants

                if frame.ip >= len(instructions):
                    self.frames.pop()
                    if self.frames:
                        stack.append(None)
                    continue

                op, arg, line = instructions[frame.ip]

                # ── stack basics ──
                if op == OpCode.PUSH_CONST:
                    stack.append(constants[arg])

                elif op == OpCode.POP:
                    stack.pop()

                # ── variables ──
                elif op == OpCode.STORE_VAR:
                    frame.locals[arg] = stack.pop()

                elif op == OpCode.ASSIGN_VAR:
                    val = stack.pop()
                    for f in reversed(self.frames):
                        if arg in f.locals:
                            f.locals[arg] = val
                            break
                    else:
                        raise VMRuntimeError(
                            f"line {line}: Cannot assign to '{arg}' before declaring with 'let'.\n→ {roast()}"
                        )

                elif op == OpCode.LOAD_VAR:
                    for f in reversed(self.frames):
                        if arg in f.locals:
                            stack.append(f.locals[arg])
                            break
                    else:
                        raise VMRuntimeError(
                            f"line {line}: Variable '{arg}' is not defined.\n→ {roast()}"
                        )

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

                elif op == OpCode.MOD:
                    b, a = stack.pop(), stack.pop()
                    self._require_number(a, line, '%')
                    self._require_number(b, line, '%')
                    if b == 0:
                        raise VMRuntimeError(f"line {line}: Modulo by zero is forbidden.\n→ {roast()}")
                    res = a % b
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

                elif op == OpCode.NOT:
                    a = stack.pop()
                    stack.append(not self.is_truthy(a))

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
                    frame.ip = arg
                    continue

                elif op == OpCode.JUMP_IF_FALSE:
                    cond = stack.pop()
                    if not cond:
                        frame.ip = arg
                        continue

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

                    # Built-in function: len
                    if fn_name == 'len':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'len' expects 1 argument, but received {len(args)}.")
                        target = args[0]
                        if not isinstance(target, (list, str)):
                            raise VMRuntimeError(f"line {line}: 'len' argument must be an array or string, not {self._type_name(target)}.\n→ {roast()}")
                        stack.append(len(target))
                        frame.ip += 1
                        continue

                    # Built-in function: push
                    if fn_name == 'push':
                        if len(args) != 2:
                            raise VMRuntimeError(f"line {line}: 'push' expects 2 arguments (array, item), but received {len(args)}.")
                        target, item = args[0], args[1]
                        if not isinstance(target, list):
                            raise VMRuntimeError(f"line {line}: 'push' first argument must be an array, not {self._type_name(target)}.\n→ {roast()}")
                        target.append(item)
                        stack.append(None)
                        frame.ip += 1
                        continue

                    # Built-in function: pop
                    if fn_name == 'pop':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'pop' expects 1 argument (array), but received {len(args)}.")
                        target = args[0]
                        if not isinstance(target, list):
                            raise VMRuntimeError(f"line {line}: 'pop' argument must be an array, not {self._type_name(target)}.\n→ {roast()}")
                        if not target:
                            raise VMRuntimeError(f"line {line}: Cannot pop from an empty array.\n→ {roast()}")
                        stack.append(target.pop())
                        frame.ip += 1
                        continue

                    fn_proto = None
                    for f in reversed(self.frames):
                        if fn_name in f.locals:
                            fn_proto = f.locals[fn_name]
                            break
                    if fn_proto is None:
                        raise VMRuntimeError(f"line {line}: Function '{fn_name}' is not defined.")
                    if not isinstance(fn_proto, CHUDFunctionProto):
                        raise VMRuntimeError(f"line {line}: '{fn_name}' is not a function.")
                    if len(args) != len(fn_proto.parameters):
                        raise VMRuntimeError(
                            f"line {line}: Function '{fn_name}' expects {len(fn_proto.parameters)} args, got {len(args)}."
                        )
                    if len(self.frames) >= 1000:
                        raise VMRuntimeError(f"line {line}: Maximum call stack depth exceeded.\n→ {roast()}")

                    # Advance caller ip to next instruction before pushing callee frame
                    frame.ip += 1
                    callee_locals = {p: v for p, v in zip(fn_proto.parameters, args)}
                    callee_frame = CallFrame(fn_proto, locals_dict=callee_locals)
                    self.frames.append(callee_frame)
                    continue

                # ── arrays / lists ──
                elif op == OpCode.BUILD_LIST:
                    count = arg
                    items = [stack.pop() for _ in range(count)][::-1]
                    stack.append(items)

                elif op == OpCode.LOAD_INDEX:
                    idx = stack.pop()
                    target = stack.pop()
                    if not isinstance(target, (list, str)):
                        raise VMRuntimeError(f"line {line}: Cannot index into non-array/string type {self._type_name(target)}.\n→ {roast()}")
                    if not isinstance(idx, int) or isinstance(idx, bool):
                        raise VMRuntimeError(f"line {line}: Array index must be an integer, not {self._type_name(idx)}.\n→ {roast()}")
                    if idx < 0 or idx >= len(target):
                        raise VMRuntimeError(f"line {line}: Array index out of bounds (index {idx}, length {len(target)}).\n→ {roast()}")
                    stack.append(target[idx])

                elif op == OpCode.STORE_INDEX:
                    val = stack.pop()
                    idx = stack.pop()
                    target = stack.pop()
                    if not isinstance(target, list):
                        raise VMRuntimeError(f"line {line}: Cannot assign index to non-array type {self._type_name(target)}.\n→ {roast()}")
                    if not isinstance(idx, int) or isinstance(idx, bool):
                        raise VMRuntimeError(f"line {line}: Array index must be an integer, not {self._type_name(idx)}.\n→ {roast()}")
                    if idx < 0 or idx >= len(target):
                        raise VMRuntimeError(f"line {line}: Array index out of bounds (index {idx}, length {len(target)}).\n→ {roast()}")
                    target[idx] = val

                elif op == OpCode.RETURN:
                    ret_val = stack.pop() if stack else None
                    self.frames.pop()
                    if self.frames:
                        stack.append(ret_val)
                        continue
                    else:
                        return {
                            "success": True,
                            "output": self.output,
                            "variables": {k: self.stringify(v) for k, v in self.globals.items() if not isinstance(v, CHUDFunctionProto)},
                            "error": None,
                            "return_value": ret_val
                        }

                elif op == OpCode.HALT:
                    self.frames.pop()
                    if self.frames:
                        stack.append(None)
                        continue
                    else:
                        break

                else:
                    raise VMRuntimeError(f"Unknown opcode '{op}' at instruction {frame.ip}")

                frame.ip += 1

            return {
                "success": True,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.globals.items() if not isinstance(v, CHUDFunctionProto)},
                "error": None,
                "return_value": None
            }

        except VMRuntimeError as e:
            return {
                "success": False,
                "output": self.output,
                "variables": {k: self.stringify(v) for k, v in self.globals.items() if not isinstance(v, CHUDFunctionProto)},
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
