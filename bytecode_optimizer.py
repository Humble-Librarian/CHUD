# ─────────────────────────────────────────────
#  CHUD — bytecode_optimizer.py
#  Phase 4 Bytecode-Level Optimization Engine:
#   - Peephole Instruction Window Transformations
#   - Push/Pop Redundancy Elimination
#   - Jump-to-Next-Instruction Elimination
#   - Jump Threading (Chain Shortening)
#   - Dead Bytecode Elimination (Post-Halt/Return/Jump)
#   - Constant Pool Compaction & Deduplication
# ─────────────────────────────────────────────

from bytecode import Chunk, OpCode, CHUDFunctionProto, Instruction


class BytecodeOptimizer:
    """Performs sliding-window peephole transformations, jump threading,
    and dead code elimination on compiled Chunk bytecode streams.
    """

    def __init__(self):
        self.instructions_before = 0
        self.instructions_after = 0
        self.peephole_passes = 0
        self.jumps_threaded = 0
        self.push_pop_eliminated = 0
        self.dead_code_eliminated = 0

    def optimize_chunk(self, chunk):
        """Optimizes a Chunk in-place (and any nested function prototypes)."""
        # First recursively optimize any nested function prototypes in constant pool
        for const in chunk.constants:
            if isinstance(const, CHUDFunctionProto):
                sub_opt = BytecodeOptimizer()
                sub_opt.optimize_chunk(const.chunk)
                self.jumps_threaded += sub_opt.jumps_threaded
                self.push_pop_eliminated += sub_opt.push_pop_eliminated
                self.dead_code_eliminated += sub_opt.dead_code_eliminated

        self.instructions_before += len(chunk.instructions)

        # Multi-pass iterative peephole optimization until fixed-point
        max_passes = 10
        changed = True
        while changed and self.peephole_passes < max_passes:
            changed = False
            self.peephole_passes += 1

            # 1. Jump Threading Pass
            if self._thread_jumps(chunk):
                changed = True

            # 2. Sliding-Window Peephole Pass (Push/Pop, Jump-to-next, Dead bytecode)
            if self._peephole_pass(chunk):
                changed = True

        # 3. Compact Constant Pool
        self._compact_constants(chunk)

        self.instructions_after += len(chunk.instructions)
        return chunk

    def _get_jump_targets(self, instructions):
        """Finds all instruction indices that are targeted by any jump."""
        targets = set()
        for instr in instructions:
            if instr.op in (OpCode.JUMP, OpCode.JUMP_IF_FALSE) and instr.arg is not None:
                targets.add(instr.arg)
        return targets

    def _thread_jumps(self, chunk):
        """Jump Threading: if JUMP -> target where target is also JUMP -> final_target,
        short-circuit the chain directly to final_target.
        """
        changed = False
        instructions = chunk.instructions

        for i, instr in enumerate(instructions):
            if instr.op in (OpCode.JUMP, OpCode.JUMP_IF_FALSE) and instr.arg is not None:
                target_idx = instr.arg
                visited = {target_idx}

                # Follow chain of unconditional jumps
                while (0 <= target_idx < len(instructions) and
                       instructions[target_idx].op == OpCode.JUMP and
                       instructions[target_idx].arg is not None):
                    next_target = instructions[target_idx].arg
                    if next_target in visited or next_target < 0 or next_target >= len(instructions):
                        break  # Prevent infinite loop on circular jumps
                    visited.add(next_target)
                    target_idx = next_target

                if target_idx != instr.arg:
                    instr.arg = target_idx
                    self.jumps_threaded += 1
                    changed = True

        return changed

    def _peephole_pass(self, chunk):
        """Performs a single pass of peephole pattern deletions and updates jump targets."""
        instructions = chunk.instructions
        n = len(instructions)
        if n == 0:
            return False

        jump_targets = self._get_jump_targets(instructions)
        to_delete = set()

        i = 0
        while i < n:
            op = instructions[i].op
            arg = instructions[i].arg

            # Pattern 1: Push Const followed by Pop (where Pop is not a jump target)
            if (op == OpCode.PUSH_CONST and i + 1 < n and
                    instructions[i + 1].op == OpCode.POP and
                    (i + 1) not in jump_targets):
                to_delete.add(i)
                to_delete.add(i + 1)
                self.push_pop_eliminated += 1
                i += 2
                continue

            # Pattern 2: JUMP to immediately next instruction (no-op fallthrough)
            if op == OpCode.JUMP and arg == (i + 1):
                to_delete.add(i)
                self.dead_code_eliminated += 1
                i += 1
                continue

            # Pattern 3: Unreachable code after HALT or RETURN or unconditional JUMP
            if op in (OpCode.HALT, OpCode.RETURN, OpCode.JUMP):
                j = i + 1
                while j < n and j not in jump_targets:
                    to_delete.add(j)
                    self.dead_code_eliminated += 1
                    j += 1
                i = j
                continue

            i += 1

        if not to_delete:
            return False

        # Rebuild instruction list and re-map all jump targets
        new_instructions = []
        old_to_new = {}
        curr_new = 0

        for idx, instr in enumerate(instructions):
            if idx not in to_delete:
                old_to_new[idx] = curr_new
                new_instructions.append(instr)
                curr_new += 1
            else:
                # Deleted instruction maps to next surviving instruction
                # We'll resolve this in a secondary sweep
                pass

        # Handle mapping for deleted indices: map to first surviving index at or after idx
        for idx in range(n):
            if idx not in old_to_new:
                # Find next index >= idx that was kept
                found = len(new_instructions)
                for k in range(idx + 1, n):
                    if k in old_to_new:
                        found = old_to_new[k]
                        break
                old_to_new[idx] = found

        # Update all jump targets
        for instr in new_instructions:
            if instr.op in (OpCode.JUMP, OpCode.JUMP_IF_FALSE) and instr.arg is not None:
                old_target = instr.arg
                if old_target in old_to_new:
                    instr.arg = old_to_new[old_target]

        chunk.instructions = new_instructions
        return True

    def _compact_constants(self, chunk):
        """Removes unused constants from chunk.constants and updates PUSH_CONST indices."""
        used_indices = set()
        for instr in chunk.instructions:
            if instr.op == OpCode.PUSH_CONST and isinstance(instr.arg, int):
                used_indices.add(instr.arg)

        # Build old -> new index mapping for constants
        old_to_new = {}
        new_constants = []
        for old_idx, val in enumerate(chunk.constants):
            # Keep function prototypes always, or any referenced constant
            if old_idx in used_indices or isinstance(val, CHUDFunctionProto):
                old_to_new[old_idx] = len(new_constants)
                new_constants.append(val)

        # Update PUSH_CONST instructions
        for instr in chunk.instructions:
            if instr.op == OpCode.PUSH_CONST and isinstance(instr.arg, int):
                if instr.arg in old_to_new:
                    instr.arg = old_to_new[instr.arg]

        chunk.constants = new_constants
