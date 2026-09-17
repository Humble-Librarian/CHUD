# ─────────────────────────────────────────────
#  CHUD — bytecode.py
#  The instruction set the compiler emits into
#  and the VM executes. This file defines WHAT
#  an instruction is — nothing here executes
#  anything.
# ─────────────────────────────────────────────

class OpCode:
    """Every instruction the CHUD VM understands.
    Grouped by category for readability — the
    actual values don't matter, just uniqueness.
    """

    # ── Stack basics ──
    PUSH_CONST   = 'PUSH_CONST'    # push constants[arg] onto the stack
    POP          = 'POP'          # discard top of stack

    # ── Variables ──
    LOAD_VAR     = 'LOAD_VAR'     # push value of variable named arg
    STORE_VAR    = 'STORE_VAR'    # pop value, store into variable named arg (declare)
    ASSIGN_VAR   = 'ASSIGN_VAR'   # pop value, assign into EXISTING variable named arg

    # ── Arithmetic (binary — pop 2, push 1) ──
    ADD          = 'ADD'
    SUB          = 'SUB'
    MUL          = 'MUL'
    DIV          = 'DIV'

    # ── Unary (pop 1, push 1) ──
    NEG          = 'NEG'          # unary minus
    POS          = 'POS'          # unary plus (no-op numerically, but type-checks)

    # ── Comparison (pop 2, push 1 bool) ──
    EQ           = 'EQ'
    NEQ          = 'NEQ'
    LT           = 'LT'
    GT           = 'GT'
    LTE          = 'LTE'
    GTE          = 'GTE'

    # ── Control flow ──
    JUMP         = 'JUMP'            # unconditional: ip = arg
    JUMP_IF_FALSE= 'JUMP_IF_FALSE'   # pop condition; if falsy, ip = arg

    # ── I/O ──
    PRINT        = 'PRINT'        # pop value, output it (yap)
    HEAR         = 'HEAR'         # pop prompt, read input, push converted value

    # ── Functions & Calls ──
    CALL         = 'CALL'         # arg = (function_name, arg_count)
    RETURN       = 'RETURN'       # pop return value, exit function chunk

    # ── Program structure ──
    HALT         = 'HALT'         # stop execution


class CHUDFunctionProto:
    """Bytecode representation of a compiled function."""
    __slots__ = ('name', 'parameters', 'chunk')

    def __init__(self, name, parameters, chunk):
        self.name       = name
        self.parameters = parameters
        self.chunk      = chunk

    def __repr__(self):
        return f"<fn {self.name}({', '.join(self.parameters)})>"


class Instruction:
    """One bytecode instruction."""
    __slots__ = ('op', 'arg', 'line')

    def __init__(self, op, arg=None, line=None):
        self.op   = op
        self.arg  = arg
        self.line = line

    def __repr__(self):
        arg_str = f" {self.arg}" if self.arg is not None else ""
        return f"{self.op}{arg_str}"


class Chunk:
    """A compiled unit of bytecode: a flat list of
    instructions plus a constant pool (numbers,
    strings, booleans referenced by PUSH_CONST).
    """
    def __init__(self):
        self.instructions = []   # list[Instruction]
        self.constants    = []   # list[Any] — the constant pool

    # ── building ──

    def add_constant(self, value):
        """Add a value to the constant pool, returning its index.
        Reuses an existing identical constant if present
        (small optimization, not required but free).
        """
        for i, existing in enumerate(self.constants):
            if type(existing) == type(value) and existing == value:
                return i
        self.constants.append(value)
        return len(self.constants) - 1

    def emit(self, op, arg=None, line=None):
        """Append an instruction, return its index in the
        instruction list. The index is important — control
        flow (Step 4) needs to patch JUMP targets after the
        fact, once we know how far to jump.
        """
        self.instructions.append(Instruction(op, arg, line))
        return len(self.instructions) - 1

    def patch_jump(self, instruction_index, target_index):
        """Overwrite a previously-emitted JUMP / JUMP_IF_FALSE's
        arg with the correct target. Used because when we emit
        a jump for 'check', we don't yet know how many
        instructions the body will take — we emit a placeholder,
        compile the body, THEN patch the jump target.
        """
        self.instructions[instruction_index].arg = target_index

    def current_offset(self):
        """The index the NEXT emitted instruction will land at.
        Used to compute jump targets (e.g. 'jump back to the
        start of this loop's condition check').
        """
        return len(self.instructions)

    # ── inspection / debugging ──

    def disassemble(self):
        """Human-readable dump — invaluable for debugging at 2am.
        Print this whenever bytecode isn't doing what you expect.
        """
        lines = []
        for i, instr in enumerate(self.instructions):
            arg_display = instr.arg
            if instr.op == 'PUSH_CONST' and isinstance(instr.arg, int) and instr.arg < len(self.constants):
                arg_display = f"{instr.arg} ({self.constants[instr.arg]!r})"
            lines.append(f"{i:4d}  {instr.op:<16} {arg_display if arg_display is not None else ''}")
        return "\n".join(lines)

    def __repr__(self):
        return f"Chunk({len(self.instructions)} instructions, {len(self.constants)} constants)"


# ── Quick sanity check ────────────────────────
if __name__ == '__main__':
    # Manually build bytecode for:  let x = 2 + 3 \n yap x
    # (this is what the compiler will do automatically in Step 2)
    chunk = Chunk()

    c0 = chunk.add_constant(2)
    c1 = chunk.add_constant(3)

    chunk.emit(OpCode.PUSH_CONST, c0, line=1)
    chunk.emit(OpCode.PUSH_CONST, c1, line=1)
    chunk.emit(OpCode.ADD, line=1)
    chunk.emit(OpCode.STORE_VAR, 'x', line=1)

    chunk.emit(OpCode.LOAD_VAR, 'x', line=2)
    chunk.emit(OpCode.PRINT, line=2)
    chunk.emit(OpCode.HALT, line=2)

    print(chunk)
    print(chunk.disassemble())
