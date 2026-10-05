# ─────────────────────────────────────────────
#  CHUD — ast_optimizer.py
#  Phase 4 AST-Level Optimization Engine:
#   - Constant Folding (Arithmetic, Strings, Booleans, Unary)
#   - Algebraic Simplifications (Identity rules)
#   - Dead Branch Pruning (check W / L evaluation)
#   - Dead Code Elimination (Post-return/stop/skip stripping)
# ─────────────────────────────────────────────

from ast_nodes import (
    ProgramNode, AssignNode, YapNode,
    BinOpNode, UnaryOpNode,
    NumberNode, StringNode, BoolNode, IdentifierNode,
    CheckNode, KeepNode, LoopNode, StopNode, SkipNode, HearNode,
    FunctionNode, CallNode, ReturnNode,
    ArrayLiteralNode, IndexAccessNode, IndexAssignNode,
    DictLiteralNode, UseNode
)


class ASTOptimizer:
    """Recursively transforms an Abstract Syntax Tree (AST) to simplify
    constant expressions, prune dead control branches, and eliminate
    unreachable code at compile-time.
    """

    def __init__(self):
        self.constants_folded = 0
        self.dead_branches_pruned = 0
        self.dead_stmts_removed = 0
        self.nodes_before = 0
        self.nodes_after = 0

    def count_nodes(self, node):
        """Recursively count AST nodes for optimization metrics."""
        if node is None:
            return 0
        count = 1
        if isinstance(node, ProgramNode):
            for stmt in node.statements:
                count += self.count_nodes(stmt)
        elif isinstance(node, AssignNode):
            count += self.count_nodes(node.value)
        elif isinstance(node, YapNode):
            count += self.count_nodes(node.value)
        elif isinstance(node, BinOpNode):
            count += self.count_nodes(node.left) + self.count_nodes(node.right)
        elif isinstance(node, UnaryOpNode):
            count += self.count_nodes(node.operand)
        elif isinstance(node, CheckNode):
            count += self.count_nodes(node.condition)
            for s in node.body:
                count += self.count_nodes(s)
            if node.else_body:
                for s in node.else_body:
                    count += self.count_nodes(s)
        elif isinstance(node, KeepNode):
            count += self.count_nodes(node.condition)
            for s in node.body:
                count += self.count_nodes(s)
        elif isinstance(node, LoopNode):
            count += self.count_nodes(node.initializer) + self.count_nodes(node.condition) + self.count_nodes(node.update)
            for s in node.body:
                count += self.count_nodes(s)
        elif isinstance(node, FunctionNode):
            for s in node.body:
                count += self.count_nodes(s)
        elif isinstance(node, CallNode):
            for arg in node.arguments:
                count += self.count_nodes(arg)
        elif isinstance(node, ReturnNode):
            count += self.count_nodes(node.value)
        elif isinstance(node, ArrayLiteralNode):
            for el in node.elements:
                count += self.count_nodes(el)
        elif isinstance(node, DictLiteralNode):
            for k, v in node.pairs:
                count += self.count_nodes(k) + self.count_nodes(v)
        elif isinstance(node, IndexAccessNode):
            count += self.count_nodes(node.target) + self.count_nodes(node.index)
        elif isinstance(node, IndexAssignNode):
            count += self.count_nodes(node.target) + self.count_nodes(node.index) + self.count_nodes(node.value)
        elif isinstance(node, UseNode):
            pass
        return count

    def optimize(self, ast):
        """Main entry point for AST optimization pass."""
        self.nodes_before = self.count_nodes(ast)
        optimized_ast = self._transform(ast)
        self.nodes_after = self.count_nodes(optimized_ast)
        return optimized_ast

    def _transform(self, node):
        if node is None:
            return None

        if isinstance(node, ProgramNode):
            return self._transform_program(node)
        if isinstance(node, AssignNode):
            return self._transform_assign(node)
        if isinstance(node, YapNode):
            return self._transform_yap(node)
        if isinstance(node, BinOpNode):
            return self._transform_binop(node)
        if isinstance(node, UnaryOpNode):
            return self._transform_unaryop(node)
        if isinstance(node, CheckNode):
            return self._transform_check(node)
        if isinstance(node, KeepNode):
            return self._transform_keep(node)
        if isinstance(node, LoopNode):
            return self._transform_loop(node)
        if isinstance(node, FunctionNode):
            return self._transform_function(node)
        if isinstance(node, CallNode):
            return self._transform_call(node)
        if isinstance(node, ReturnNode):
            return self._transform_return(node)
        if isinstance(node, ArrayLiteralNode):
            return self._transform_array_literal(node)
        if isinstance(node, DictLiteralNode):
            return self._transform_dict_literal(node)
        if isinstance(node, IndexAccessNode):
            return self._transform_index_access(node)
        if isinstance(node, IndexAssignNode):
            return self._transform_index_assign(node)
        if isinstance(node, UseNode):
            return node

        # Leaf nodes (NumberNode, StringNode, BoolNode, IdentifierNode, StopNode, SkipNode, HearNode)
        return node

    # ─────────────────────────────────────────────
    #  Statement Transformations
    # ─────────────────────────────────────────────

    def _transform_statements_list(self, statements):
        """Optimizes a list of statements and removes unreachable code after
        unconditional return, stop, or skip statements.
        """
        optimized = []
        terminated = False

        for stmt in statements:
            if terminated:
                self.dead_stmts_removed += 1
                continue

            trans = self._transform(stmt)
            if trans is None:
                continue

            if isinstance(trans, list):
                for s in trans:
                    if s is not None:
                        optimized.append(s)
                        if isinstance(s, (ReturnNode, StopNode, SkipNode)):
                            terminated = True
                            break
            else:
                optimized.append(trans)
                if isinstance(trans, (ReturnNode, StopNode, SkipNode)):
                    terminated = True

        return optimized

    def _transform_program(self, node):
        stmts = self._transform_statements_list(node.statements)
        return ProgramNode(stmts)

    def _transform_assign(self, node):
        opt_val = self._transform(node.value)
        return AssignNode(node.name, opt_val, node.is_declaration, line=node.line)

    def _transform_yap(self, node):
        opt_val = self._transform(node.value)
        return YapNode(opt_val, line=node.line)

    def _transform_return(self, node):
        opt_val = self._transform(node.value) if node.value is not None else None
        return ReturnNode(opt_val, line=node.line)

    def _transform_function(self, node):
        opt_body = self._transform_statements_list(node.body)
        return FunctionNode(node.name, node.parameters, opt_body, line=node.line)

    def _transform_check(self, node):
        """Optimizes CheckNode. If the condition is statically known (BoolNode),
        prune the dead branch entirely.
        """
        opt_cond = self._transform(node.condition)
        opt_body = self._transform_statements_list(node.body)
        opt_else = self._transform_statements_list(node.else_body) if node.else_body is not None else None

        # Constant condition folding
        if isinstance(opt_cond, BoolNode):
            self.dead_branches_pruned += 1
            if opt_cond.value is True:
                # Then-branch always executes, else-branch is dead
                return opt_body
            else:
                # Else-branch executes (or nothing)
                return opt_else if opt_else is not None else []

        return CheckNode(opt_cond, opt_body, opt_else, line=node.line)

    def _transform_keep(self, node):
        """Optimizes KeepNode. If condition is statically False (L), loop is eliminated."""
        opt_cond = self._transform(node.condition)
        opt_body = self._transform_statements_list(node.body)

        if isinstance(opt_cond, BoolNode) and opt_cond.value is False:
            self.dead_branches_pruned += 1
            return []

        return KeepNode(opt_cond, opt_body, line=node.line)

    def _transform_loop(self, node):
        opt_init = self._transform(node.initializer)
        opt_cond = self._transform(node.condition)
        opt_update = self._transform(node.update)
        opt_body = self._transform_statements_list(node.body)

        if isinstance(opt_cond, BoolNode) and opt_cond.value is False:
            self.dead_branches_pruned += 1
            # Init might have side-effects, so keep init if present
            return [opt_init] if opt_init is not None else []

        return LoopNode(opt_init, opt_cond, opt_update, opt_body, line=node.line)

    # ─────────────────────────────────────────────
    #  Expression Transformations & Constant Folding
    # ─────────────────────────────────────────────

    def _transform_binop(self, node):
        left = self._transform(node.left)
        right = self._transform(node.right)
        op = node.op
        line = node.line

        # 1. Both operands are literal Numbers
        if isinstance(left, NumberNode) and isinstance(right, NumberNode):
            lv, rv = left.value, right.value
            try:
                if op == '+':
                    self.constants_folded += 1
                    return NumberNode(lv + rv, line=line)
                elif op == '-':
                    self.constants_folded += 1
                    return NumberNode(lv - rv, line=line)
                elif op == '*':
                    self.constants_folded += 1
                    return NumberNode(lv * rv, line=line)
                elif op == '/':
                    if rv == 0:
                        return BinOpNode(left, op, right, line=line)
                    self.constants_folded += 1
                    res = lv / rv
                    # Integer division simplification if exact
                    if isinstance(lv, int) and isinstance(rv, int) and lv % rv == 0:
                        return NumberNode(int(res), line=line)
                    return NumberNode(res, line=line)
                elif op == '%':
                    if rv == 0:
                        return BinOpNode(left, op, right, line=line)
                    self.constants_folded += 1
                    return NumberNode(lv % rv, line=line)
                elif op == '==':
                    self.constants_folded += 1
                    return BoolNode(lv == rv, line=line)
                elif op == '!=':
                    self.constants_folded += 1
                    return BoolNode(lv != rv, line=line)
                elif op == '<':
                    self.constants_folded += 1
                    return BoolNode(lv < rv, line=line)
                elif op == '<=':
                    self.constants_folded += 1
                    return BoolNode(lv <= rv, line=line)
                elif op == '>':
                    self.constants_folded += 1
                    return BoolNode(lv > rv, line=line)
                elif op == '>=':
                    self.constants_folded += 1
                    return BoolNode(lv >= rv, line=line)
            except Exception:
                return BinOpNode(left, op, right, line=line)

        # 2. String Concatenation & Comparisons
        if isinstance(left, StringNode) and isinstance(right, StringNode):
            lv, rv = left.value, right.value
            if op == '+':
                self.constants_folded += 1
                return StringNode(lv + rv, line=line)
            elif op == '==':
                self.constants_folded += 1
                return BoolNode(lv == rv, line=line)
            elif op == '!=':
                self.constants_folded += 1
                return BoolNode(lv != rv, line=line)

        # 3. Boolean Logic Folding (and, or, ==, !=)
        if isinstance(left, BoolNode) and isinstance(right, BoolNode):
            lv, rv = left.value, right.value
            if op == 'and':
                self.constants_folded += 1
                return BoolNode(lv and rv, line=line)
            elif op == 'or':
                self.constants_folded += 1
                return BoolNode(lv or rv, line=line)
            elif op == '==':
                self.constants_folded += 1
                return BoolNode(lv == rv, line=line)
            elif op == '!=':
                self.constants_folded += 1
                return BoolNode(lv != rv, line=line)

        # 4. Short-Circuiting Algebraic Simplifications with one boolean literal
        if op == 'and':
            if isinstance(left, BoolNode):
                if left.value is False:
                    # False and X => False
                    self.constants_folded += 1
                    return BoolNode(False, line=line)
                else:
                    # True and X => X
                    self.constants_folded += 1
                    return right
            elif isinstance(right, BoolNode) and right.value is False and isinstance(left, (NumberNode, StringNode, BoolNode)):
                self.constants_folded += 1
                return BoolNode(False, line=line)

        if op == 'or':
            if isinstance(left, BoolNode):
                if left.value is True:
                    # True or X => True
                    self.constants_folded += 1
                    return BoolNode(True, line=line)
                else:
                    # False or X => X
                    self.constants_folded += 1
                    return right
            elif isinstance(right, BoolNode) and right.value is True and isinstance(left, (NumberNode, StringNode, BoolNode)):
                self.constants_folded += 1
                return BoolNode(True, line=line)

        # 5. Arithmetic Identity Simplifications (where side-effect free)
        if op == '+' and isinstance(right, NumberNode) and right.value == 0:
            return left
        if op == '+' and isinstance(left, NumberNode) and left.value == 0 and not isinstance(right, StringNode):
            return right
        if op == '-' and isinstance(right, NumberNode) and right.value == 0:
            return left
        if op == '*' and isinstance(right, NumberNode) and right.value == 1:
            return left
        if op == '*' and isinstance(left, NumberNode) and left.value == 1:
            return right

        return BinOpNode(left, op, right, line=line)

    def _transform_unaryop(self, node):
        operand = self._transform(node.operand)
        op = node.op
        line = node.line

        if isinstance(operand, NumberNode):
            if op == '-':
                self.constants_folded += 1
                return NumberNode(-operand.value, line=line)
            elif op == '+':
                self.constants_folded += 1
                return NumberNode(+operand.value, line=line)

        if isinstance(operand, BoolNode):
            if op in ('!', 'not'):
                self.constants_folded += 1
                return BoolNode(not operand.value, line=line)

        # Double negation elimination on unary: !(!x) => x
        if isinstance(operand, UnaryOpNode) and op in ('!', 'not') and operand.op in ('!', 'not'):
            self.constants_folded += 1
            return operand.operand

        return UnaryOpNode(op, operand, line=line)

    def _transform_array_literal(self, node):
        opt_elements = [self._transform(el) for el in node.elements]
        return ArrayLiteralNode(opt_elements, line=node.line)

    def _transform_dict_literal(self, node):
        opt_pairs = [(self._transform(k), self._transform(v)) for k, v in node.pairs]
        return DictLiteralNode(opt_pairs, line=node.line)

    def _transform_index_access(self, node):
        opt_target = self._transform(node.target)
        opt_index = self._transform(node.index)
        return IndexAccessNode(opt_target, opt_index, line=node.line)

    def _transform_index_assign(self, node):
        opt_target = self._transform(node.target)
        opt_index = self._transform(node.index)
        opt_value = self._transform(node.value)
        return IndexAssignNode(opt_target, opt_index, opt_value, line=node.line)

    def _transform_call(self, node):
        opt_args = [self._transform(arg) for arg in node.arguments]
        return CallNode(node.name, opt_args, line=node.line)
