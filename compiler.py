# ─────────────────────────────────────────────
#  CHUD — compiler.py
#  Walks the SAME AST the interpreter walks, but
#  instead of executing each node, EMITS bytecode
#  instructions for it.
#
#  Scope for this file (Step 2): straight-line
#  code only. NumberNode, StringNode, BoolNode,
#  IdentifierNode, BinOpNode, UnaryOpNode,
#  AssignNode, YapNode, ProgramNode.
#
#  CheckNode / KeepNode / LoopNode / FunctionNode
#  etc. are added in Step 4 (control flow) and
#  a later step (functions) — NOT here.
# ─────────────────────────────────────────────

from ast_nodes import (
    ProgramNode, AssignNode, YapNode,
    BinOpNode, UnaryOpNode,
    NumberNode, StringNode, BoolNode, IdentifierNode,
    CheckNode, KeepNode, LoopNode, StopNode, HearNode,
    FunctionNode, CallNode, ReturnNode,
)
from bytecode import Chunk, OpCode, CHUDFunctionProto


class CompileError(Exception):
    pass


# Maps CHUD's BinOpNode.op string to the OpCode that handles it.
BINOP_TO_OPCODE = {
    '+':  OpCode.ADD,
    '-':  OpCode.SUB,
    '*':  OpCode.MUL,
    '/':  OpCode.DIV,
    '==': OpCode.EQ,
    '!=': OpCode.NEQ,
    '<':  OpCode.LT,
    '>':  OpCode.GT,
    '<=': OpCode.LTE,
    '>=': OpCode.GTE,
}


class Compiler:
    def __init__(self):
        self.chunk = Chunk()
        self.break_patches = []   # Stack of lists for pending 'stop' (break) jump patches

    def compile(self, ast):
        """Entry point: compile a full ProgramNode into a Chunk."""
        self.compile_node(ast)
        self.chunk.emit(OpCode.HALT)
        return self.chunk

    # ══════════════════════════════════════════
    #  DISPATCH
    # ══════════════════════════════════════════

    def compile_node(self, node):
        if isinstance(node, ProgramNode):
            return self.compile_program(node)
        if isinstance(node, AssignNode):
            return self.compile_assign(node)
        if isinstance(node, YapNode):
            return self.compile_yap(node)
        if isinstance(node, CheckNode):
            return self.compile_check(node)
        if isinstance(node, KeepNode):
            return self.compile_keep(node)
        if isinstance(node, LoopNode):
            return self.compile_loop(node)
        if isinstance(node, StopNode):
            return self.compile_stop(node)
        if isinstance(node, HearNode):
            return self.compile_hear(node)
        if isinstance(node, FunctionNode):
            return self.compile_function(node)
        if isinstance(node, CallNode):
            return self.compile_call(node)
        if isinstance(node, ReturnNode):
            return self.compile_return(node)
        if isinstance(node, BinOpNode):
            return self.compile_binop(node)
        if isinstance(node, UnaryOpNode):
            return self.compile_unaryop(node)
        if isinstance(node, NumberNode):
            return self.compile_number(node)
        if isinstance(node, StringNode):
            return self.compile_string(node)
        if isinstance(node, BoolNode):
            return self.compile_bool(node)
        if isinstance(node, IdentifierNode):
            return self.compile_identifier(node)

        raise CompileError(f"Unsupported AST node type: {type(node).__name__}")

    # ══════════════════════════════════════════
    #  STATEMENTS
    # ══════════════════════════════════════════

    def compile_program(self, node):
        """program → statement*
        Just compile every statement in order — no stack
        value survives between top-level statements.
        """
        for stmt in node.statements:
            self.compile_node(stmt)

    def compile_assign(self, node):
        """let x = expr   OR   x = expr

        Bytecode shape:
            <compile the value expression — leaves 1 value on stack>
            STORE_VAR x     (if 'let', i.e. is_declaration=True)
            ASSIGN_VAR x    (if reassignment)

        This mirrors interpreter.py's execute() for AssignNode:
        eval_expr(node.value) then env.define() or env.assign().
        Here: compile the value expression (which will push its
        result at RUNTIME), then emit ONE instruction that will
        pop that result into the variable.
        """
        self.compile_node(node.value)   # pushes the computed value at runtime
        op = OpCode.STORE_VAR if node.is_declaration else OpCode.ASSIGN_VAR
        self.chunk.emit(op, node.name, line=node.line)

    def compile_yap(self, node):
        """yap expr
        Compile the expression (pushes its value), then PRINT
        pops and outputs it.
        """
        self.compile_node(node.value)
        self.chunk.emit(OpCode.PRINT, line=node.line)

    def compile_check(self, node):
        """check condition { body } otherwise { else_body }

        THE CORE PROBLEM: JUMP_IF_FALSE needs to know WHERE to
        jump to (an instruction index) — but we don't know how
        many instructions the body will take until AFTER we
        compile it. Chicken-and-egg.

        THE FIX (jump patching):
          1. Emit JUMP_IF_FALSE with a PLACEHOLDER arg (None).
             Remember its index in the instruction list.
          2. Compile the body normally — instructions just pile up.
          3. NOW we know exactly where the body ended. Go back and
             patch step 1's placeholder with that real index.

        Bytecode shape (no otherwise):
            <condition>
            JUMP_IF_FALSE  -> [A]      (placeholder, patched below)
            <body>
        [A]:  <code after check>

        Bytecode shape (with otherwise):
            <condition>
            JUMP_IF_FALSE  -> [ELSE]   (placeholder #1)
            <body>
            JUMP           -> [END]    (placeholder #2 — skip the else)
        [ELSE]: <else_body>
        [END]:  <code after check>

        The second JUMP is essential — without it, after running
        the 'then' body, execution would fall straight through
        into the 'otherwise' body too. That JUMP is what makes
        them mutually exclusive.
        """
        self.compile_node(node.condition)

        # Placeholder #1: "jump somewhere if condition is false"
        # We don't know where yet — arg=None for now.
        jump_to_else_idx = self.chunk.emit(OpCode.JUMP_IF_FALSE, None, line=node.line)

        # Compile the 'then' body — its instructions land right
        # after the JUMP_IF_FALSE we just emitted.
        for stmt in node.body:
            self.compile_node(stmt)

        if node.else_body is not None:
            # There's an otherwise block, so after the 'then' body
            # finishes, we must JUMP PAST the else body entirely —
            # otherwise execution would fall into it.
            jump_to_end_idx = self.chunk.emit(OpCode.JUMP, None, line=node.line)

            # NOW we know where the else body starts: right here,
            # right now, at the current instruction count.
            else_start = self.chunk.current_offset()
            self.chunk.patch_jump(jump_to_else_idx, else_start)

            for stmt in node.else_body:
                self.compile_node(stmt)

            # NOW we know where everything ends.
            end = self.chunk.current_offset()
            self.chunk.patch_jump(jump_to_end_idx, end)
        else:
            # No otherwise — the false-jump target is simply
            # wherever we are right now, after the body.
            after_body = self.chunk.current_offset()
            self.chunk.patch_jump(jump_to_else_idx, after_body)

    def compile_keep(self, node):
        loop_start = self.chunk.current_offset()
        self.compile_node(node.condition)
        jump_to_end_idx = self.chunk.emit(OpCode.JUMP_IF_FALSE, None, line=node.line)

        self.break_patches.append([])
        for stmt in node.body:
            self.compile_node(stmt)

        self.chunk.emit(OpCode.JUMP, loop_start, line=node.line)
        end = self.chunk.current_offset()
        self.chunk.patch_jump(jump_to_end_idx, end)
        for break_idx in self.break_patches.pop():
            self.chunk.patch_jump(break_idx, end)

    def compile_loop(self, node):
        if node.initializer is not None:
            self.compile_node(node.initializer)

        loop_start = self.chunk.current_offset()
        self.compile_node(node.condition)
        jump_to_end_idx = self.chunk.emit(OpCode.JUMP_IF_FALSE, None, line=node.line)

        self.break_patches.append([])
        for stmt in node.body:
            self.compile_node(stmt)

        if node.update is not None:
            self.compile_node(node.update)

        self.chunk.emit(OpCode.JUMP, loop_start, line=node.line)
        end = self.chunk.current_offset()
        self.chunk.patch_jump(jump_to_end_idx, end)
        for break_idx in self.break_patches.pop():
            self.chunk.patch_jump(break_idx, end)

    def compile_stop(self, node):
        if not self.break_patches:
            raise CompileError(f"line {node.line}: 'stop' used outside of any loop.")
        jump_idx = self.chunk.emit(OpCode.JUMP, None, line=node.line)
        self.break_patches[-1].append(jump_idx)

    def compile_hear(self, node):
        idx = self.chunk.add_constant(node.prompt if node.prompt is not None else "")
        self.chunk.emit(OpCode.PUSH_CONST, idx, line=node.line)
        self.chunk.emit(OpCode.HEAR, line=node.line)

    def compile_function(self, node):
        parent_chunk = self.chunk
        self.chunk = Chunk()
        for stmt in node.body:
            self.compile_node(stmt)
        self.chunk.emit(OpCode.HALT, line=node.line)
        fn_chunk = self.chunk
        self.chunk = parent_chunk

        proto = CHUDFunctionProto(node.name, node.parameters, fn_chunk)
        idx = self.chunk.add_constant(proto)
        self.chunk.emit(OpCode.PUSH_CONST, idx, line=node.line)
        self.chunk.emit(OpCode.STORE_VAR, node.name, line=node.line)

    def compile_call(self, node):
        for arg in node.arguments:
            self.compile_node(arg)
        self.chunk.emit(OpCode.CALL, (node.name, len(node.arguments)), line=node.line)

    def compile_return(self, node):
        if node.value is not None:
            self.compile_node(node.value)
        else:
            idx = self.chunk.add_constant(None)
            self.chunk.emit(OpCode.PUSH_CONST, idx, line=node.line)
        self.chunk.emit(OpCode.RETURN, line=node.line)

    # ══════════════════════════════════════════
    #  EXPRESSIONS
    #  Each of these, at RUNTIME, will leave exactly
    #  ONE value on top of the stack when it finishes.
    #  This invariant is what makes composition work —
    #  BinOpNode doesn't care HOW its operands were
    #  computed, only that each left exactly 1 value.
    # ══════════════════════════════════════════

    def compile_binop(self, node):
        """left OP right
        Bytecode shape:
            <compile left>    — pushes 1 value
            <compile right>   — pushes 1 value
            OP_INSTRUCTION    — pops 2, pushes 1 (the result)

        This is identical in spirit to interpreter.py's
        eval_expr(BinOpNode): evaluate left, evaluate right,
        THEN combine. Here 'evaluate' means 'emit code that
        will compute it at runtime', not compute it now.
        """
        self.compile_node(node.left)
        self.compile_node(node.right)

        opcode = BINOP_TO_OPCODE.get(node.op)
        if opcode is None:
            raise CompileError(f"Unknown binary operator '{node.op}' at line {node.line}")
        self.chunk.emit(opcode, line=node.line)

    def compile_unaryop(self, node):
        """-x  or  +x
        Compile the operand, then negate/pos it.
        """
        self.compile_node(node.operand)
        if node.op == '-':
            self.chunk.emit(OpCode.NEG, line=node.line)
        elif node.op == '+':
            self.chunk.emit(OpCode.POS, line=node.line)
        else:
            raise CompileError(f"Unknown unary operator '{node.op}' at line {node.line}")

    def compile_number(self, node):
        """A literal number — add to constant pool, push it."""
        idx = self.chunk.add_constant(node.value)
        self.chunk.emit(OpCode.PUSH_CONST, idx, line=node.line)

    def compile_string(self, node):
        """A literal string — same mechanism as numbers."""
        idx = self.chunk.add_constant(node.value)
        self.chunk.emit(OpCode.PUSH_CONST, idx, line=node.line)

    def compile_bool(self, node):
        """W or L — stored as Python True/False in the constant pool,
        exactly like the interpreter stores them.
        """
        idx = self.chunk.add_constant(node.value)
        self.chunk.emit(OpCode.PUSH_CONST, idx, line=node.line)

    def compile_identifier(self, node):
        """A variable reference — push its current value."""
        self.chunk.emit(OpCode.LOAD_VAR, node.name, line=node.line)


def compile_source(source_code):
    """Convenience: CHUD source string -> Chunk.
    Mirrors interpreter.py's interpret() convenience function.
    """
    from lexer import Lexer
    from parser import Parser
    tokens = Lexer(source_code).tokenize()
    ast = Parser(tokens).parse()
    return Compiler().compile(ast)


# ── Quick test ────────────────────────────────
if __name__ == '__main__':
    src = '''
let x = 2 + 3 * 4
let y = x - 1
yap y
yap x >= 10
'''
    chunk = compile_source(src)
    print(chunk)
    print(chunk.disassemble())
