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

import os
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

                elif op == OpCode.LOAD_FAST:
                    stack.append(frame.slots[arg])

                elif op == OpCode.STORE_FAST:
                    val = stack.pop()
                    if arg >= len(frame.slots):
                        frame.slots.extend([None] * (arg - len(frame.slots) + 1))
                    frame.slots[arg] = val

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
                        if not isinstance(target, (list, str, dict)):
                            raise VMRuntimeError(f"line {line}: 'len' argument must be array, string, or dict, not {self._type_name(target)}.\n→ {roast()}")
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

                    # Built-in function: keys
                    if fn_name == 'keys':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'keys' expects 1 argument (dict), but received {len(args)}.")
                        target = args[0]
                        if not isinstance(target, dict):
                            raise VMRuntimeError(f"line {line}: 'keys' argument must be a dict, not {self._type_name(target)}.\n→ {roast()}")
                        stack.append(list(target.keys()))
                        frame.ip += 1
                        continue

                    # Built-in function: values
                    if fn_name == 'values':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'values' expects 1 argument (dict), but received {len(args)}.")
                        target = args[0]
                        if not isinstance(target, dict):
                            raise VMRuntimeError(f"line {line}: 'values' argument must be a dict, not {self._type_name(target)}.\n→ {roast()}")
                        stack.append(list(target.values()))
                        frame.ip += 1
                        continue

                    # Built-in function: has
                    if fn_name == 'has':
                        if len(args) != 2:
                            raise VMRuntimeError(f"line {line}: 'has' expects 2 arguments (dict/array, key/item), but received {len(args)}.")
                        target, key = args[0], args[1]
                        if isinstance(target, (dict, list, str)):
                            stack.append(key in target)
                        else:
                            raise VMRuntimeError(f"line {line}: 'has' first argument must be dict, array, or string, not {self._type_name(target)}.\n→ {roast()}")
                        frame.ip += 1
                        continue

                    # Built-in function: read_file
                    if fn_name == 'read_file':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'read_file' expects 1 argument (path), but received {len(args)}.")
                        path = args[0]
                        if not isinstance(path, str):
                            raise VMRuntimeError(f"line {line}: 'read_file' path must be a string, not {self._type_name(path)}.\n→ {roast()}")
                        try:
                            with open(path, 'r', encoding='utf-8') as f:
                                stack.append(f.read())
                        except Exception as e:
                            raise VMRuntimeError(f"line {line}: Failed to read file '{path}': {e}\n→ {roast()}")
                        frame.ip += 1
                        continue

                    # Built-in function: write_file
                    if fn_name == 'write_file':
                        if len(args) != 2:
                            raise VMRuntimeError(f"line {line}: 'write_file' expects 2 arguments (path, content), but received {len(args)}.")
                        path, content = args[0], args[1]
                        if not isinstance(path, str) or not isinstance(content, str):
                            raise VMRuntimeError(f"line {line}: 'write_file' path and content must be strings.\n→ {roast()}")
                        try:
                            with open(path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            stack.append(None)
                        except Exception as e:
                            raise VMRuntimeError(f"line {line}: Failed to write file '{path}': {e}\n→ {roast()}")
                        frame.ip += 1
                        continue

                    # Built-in function: file_exists
                    if fn_name == 'file_exists':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'file_exists' expects 1 argument (path), but received {len(args)}.")
                        path = args[0]
                        if not isinstance(path, str):
                            raise VMRuntimeError(f"line {line}: 'file_exists' path must be a string, not {self._type_name(path)}.\n→ {roast()}")
                        stack.append(os.path.exists(path))
                        frame.ip += 1
                        continue

                    # Built-in function: slice
                    if fn_name == 'slice':
                        if len(args) != 3:
                            raise VMRuntimeError(f"line {line}: 'slice' expects 3 arguments (target, start, end), but received {len(args)}.")
                        target, start, end = args[0], args[1], args[2]
                        if not isinstance(target, (list, str)):
                            raise VMRuntimeError(f"line {line}: 'slice' target must be array or string, not {self._type_name(target)}.\n→ {roast()}")
                        if not isinstance(start, int) or not isinstance(end, int):
                            raise VMRuntimeError(f"line {line}: 'slice' start and end indices must be integers.\n→ {roast()}")
                        stack.append(target[start:end])
                        frame.ip += 1
                        continue

                    # Built-in function: split
                    if fn_name == 'split':
                        if len(args) != 2:
                            raise VMRuntimeError(f"line {line}: 'split' expects 2 arguments (string, delimiter), but received {len(args)}.")
                        target, delim = args[0], args[1]
                        if not isinstance(target, str) or not isinstance(delim, str):
                            raise VMRuntimeError(f"line {line}: 'split' requires string arguments.\n→ {roast()}")
                        stack.append(target.split(delim))
                        frame.ip += 1
                        continue

                    # Built-in function: trim
                    if fn_name == 'trim':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'trim' expects 1 argument (string), but received {len(args)}.")
                        target = args[0]
                        if not isinstance(target, str):
                            raise VMRuntimeError(f"line {line}: 'trim' argument must be string, not {self._type_name(target)}.\n→ {roast()}")
                        stack.append(target.strip())
                        frame.ip += 1
                        continue

                    # Built-in function: lower
                    if fn_name == 'lower':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'lower' expects 1 argument (string), but received {len(args)}.")
                        target = args[0]
                        if not isinstance(target, str):
                            raise VMRuntimeError(f"line {line}: 'lower' argument must be string, not {self._type_name(target)}.\n→ {roast()}")
                        stack.append(target.lower())
                        frame.ip += 1
                        continue

                    # Built-in function: upper
                    if fn_name == 'upper':
                        if len(args) != 1:
                            raise VMRuntimeError(f"line {line}: 'upper' expects 1 argument (string), but received {len(args)}.")
                        target = args[0]
                        if not isinstance(target, str):
                            raise VMRuntimeError(f"line {line}: 'upper' argument must be string, not {self._type_name(target)}.\n→ {roast()}")
                        stack.append(target.upper())
                        frame.ip += 1
                        continue

                    # Built-in function: replace
                    if fn_name == 'replace':
                        if len(args) != 3:
                            raise VMRuntimeError(f"line {line}: 'replace' expects 3 arguments (string, old, new), but received {len(args)}.")
                        target, old_s, new_s = args[0], args[1], args[2]
                        if not isinstance(target, str) or not isinstance(old_s, str) or not isinstance(new_s, str):
                            raise VMRuntimeError(f"line {line}: 'replace' arguments must be strings.\n→ {roast()}")
                        stack.append(target.replace(old_s, new_s))
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
                    slot_count = len(fn_proto.local_slots) if fn_proto.local_slots else len(fn_proto.parameters)
                    slots = [None] * max(slot_count, len(fn_proto.parameters))
                    for i, val in enumerate(args):
                        slots[i] = val
                    callee_frame = CallFrame(fn_proto, locals_dict=callee_locals, slot_values=slots)
                    self.frames.append(callee_frame)
                    continue

                # ── arrays / lists / dicts ──
                elif op == OpCode.BUILD_LIST:
                    count = arg
                    items = [stack.pop() for _ in range(count)][::-1]
                    stack.append(items)

                elif op == OpCode.BUILD_MAP:
                    count = arg
                    d = {}
                    pairs = []
                    for _ in range(count):
                        v = stack.pop()
                        k = stack.pop()
                        pairs.append((k, v))
                    for k, v in reversed(pairs):
                        d[k] = v
                    stack.append(d)

                elif op == OpCode.LOAD_INDEX:
                    idx = stack.pop()
                    target = stack.pop()
                    if isinstance(target, dict):
                        if idx not in target:
                            raise VMRuntimeError(f"line {line}: Key '{idx}' not found in dictionary.\n→ {roast()}")
                        stack.append(target[idx])
                    elif isinstance(target, (list, str)):
                        if not isinstance(idx, int) or isinstance(idx, bool):
                            raise VMRuntimeError(f"line {line}: Array/String index must be an integer, not {self._type_name(idx)}.\n→ {roast()}")
                        if idx < 0 or idx >= len(target):
                            raise VMRuntimeError(f"line {line}: Index out of bounds (index {idx}, length {len(target)}).\n→ {roast()}")
                        stack.append(target[idx])
                    else:
                        raise VMRuntimeError(f"line {line}: Cannot index into non-array/string/dict type {self._type_name(target)}.\n→ {roast()}")

                elif op == OpCode.STORE_INDEX:
                    val = stack.pop()
                    idx = stack.pop()
                    target = stack.pop()
                    if isinstance(target, dict):
                        target[idx] = val
                    elif isinstance(target, list):
                        if not isinstance(idx, int) or isinstance(idx, bool):
                            raise VMRuntimeError(f"line {line}: Array index must be an integer, not {self._type_name(idx)}.\n→ {roast()}")
                        if idx < 0 or idx >= len(target):
                            raise VMRuntimeError(f"line {line}: Array index out of bounds (index {idx}, length {len(target)}).\n→ {roast()}")
                        target[idx] = val
                    else:
                        raise VMRuntimeError(f"line {line}: Cannot assign index to non-array/dict type {self._type_name(target)}.\n→ {roast()}")

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
