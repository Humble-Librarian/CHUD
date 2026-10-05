# ─────────────────────────────────────────────
#  CHUD — test_optimizer.py
#  Test Suite for Phase 4 AST & Bytecode Optimizer
# ─────────────────────────────────────────────

import unittest
from lexer import Lexer
from chud_parser import Parser
from ast_optimizer import ASTOptimizer
from bytecode_optimizer import BytecodeOptimizer
from compiler import Compiler
from vm import VM
from interpreter import Interpreter
from ast_nodes import NumberNode, StringNode, BoolNode, CheckNode, BinOpNode


class TestCHUDOptimizer(unittest.TestCase):

    def parse_source(self, code):
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        return parser.parse()

    def test_ast_constant_folding_arithmetic(self):
        code = "let x = 2 + 3 * 4 - (10 / 2)"  # 2 + 12 - 5 = 9
        ast = self.parse_source(code)
        opt = ASTOptimizer()
        opt_ast = opt.optimize(ast)

        # The assignment value should fold to a single NumberNode(9)
        assign_node = opt_ast.statements[0]
        self.assertIsInstance(assign_node.value, NumberNode)
        self.assertEqual(assign_node.value.value, 9)
        self.assertGreater(opt.constants_folded, 0)
        self.assertLess(opt.nodes_after, opt.nodes_before)

    def test_ast_constant_folding_strings(self):
        code = 'let greeting = "Hello, " + "CHUD " + "World!"'
        ast = self.parse_source(code)
        opt = ASTOptimizer()
        opt_ast = opt.optimize(ast)

        assign_node = opt_ast.statements[0]
        self.assertIsInstance(assign_node.value, StringNode)
        self.assertEqual(assign_node.value.value, "Hello, CHUD World!")

    def test_ast_constant_folding_booleans_and_unary(self):
        code = "let flag = not (W and L) or (!W)"  # not (False) or False => True
        ast = self.parse_source(code)
        opt = ASTOptimizer()
        opt_ast = opt.optimize(ast)

        assign_node = opt_ast.statements[0]
        self.assertIsInstance(assign_node.value, BoolNode)
        self.assertEqual(assign_node.value.value, True)

    def test_ast_dead_branch_pruning(self):
        code = """
        check W {
            let reached = 1
        } otherwise {
            let dead = 2
        }
        """
        ast = self.parse_source(code)
        opt = ASTOptimizer()
        opt_ast = opt.optimize(ast)

        # The CheckNode should be stripped, replaced directly by 'let reached = 1'
        self.assertEqual(len(opt_ast.statements), 1)
        self.assertEqual(opt_ast.statements[0].name, "reached")
        self.assertGreater(opt.dead_branches_pruned, 0)

    def test_ast_dead_code_post_return(self):
        code = """
        make get_val() {
            return 42
            let dead1 = 100
            yap "unreachable"
        }
        """
        ast = self.parse_source(code)
        opt = ASTOptimizer()
        opt_ast = opt.optimize(ast)

        fn_node = opt_ast.statements[0]
        # Only the return statement should remain in the function body
        self.assertEqual(len(fn_node.body), 1)
        self.assertEqual(opt.dead_stmts_removed, 2)

    def test_bytecode_jump_threading_and_peephole(self):
        code = """
        let x = 10
        check x > 5 {
            x = x + 1
        }
        yap x
        """
        ast = self.parse_source(code)
        compiler = Compiler()
        raw_chunk = compiler.compile(ast)
        instrs_before = len(raw_chunk.instructions)

        bc_opt = BytecodeOptimizer()
        bc_opt.optimize_chunk(raw_chunk)
        instrs_after = len(raw_chunk.instructions)

        self.assertLessEqual(instrs_after, instrs_before)

        # VM execution parity check
        vm = VM()
        vm.run(raw_chunk)
        self.assertEqual(vm.output, ["11"])

    def test_optimizer_full_parity_on_complex_program(self):
        code = """
        make factorial(n) {
            check n <= 1 {
                return 1
            }
            return n * factorial(n - 1)
        }

        let a = 5 * 2 + (10 - 4) / 2 // 10 + 3 = 13
        let fact = factorial(5) // 120
        yap "Calculated A: " + a
        yap "Calculated Fact: " + fact
        """
        # Run on Tree-Walk Interpreter (baseline)
        raw_ast = self.parse_source(code)
        interp = Interpreter()
        interp.run(raw_ast)
        expected_output = interp.output

        # Run with AST Optimizer + Compiler + Bytecode Optimizer (-O2 mode)
        opt_ast = ASTOptimizer().optimize(self.parse_source(code))
        opt_chunk = Compiler().compile(opt_ast)
        BytecodeOptimizer().optimize_chunk(opt_chunk)

        vm = VM()
        vm.run(opt_chunk)
        self.assertEqual(vm.output, expected_output)


    def test_keep_loop_constant_false_elimination(self):
        code = """
        let count = 0
        keep L {
            count = count + 100
        }
        yap count
        """
        ast = self.parse_source(code)
        opt = ASTOptimizer()
        opt_ast = opt.optimize(ast)

        # The keep loop should be eliminated completely
        self.assertEqual(len(opt_ast.statements), 2)  # 'let count = 0' and 'yap count'
        self.assertGreater(opt.dead_branches_pruned, 0)

    def test_algebraic_identities(self):
        code = """
        let x = 10
        let a = x + 0
        let b = 1 * x
        let c = x - 0
        yap a
        yap b
        yap c
        """
        ast = self.parse_source(code)
        opt = ASTOptimizer()
        opt_ast = opt.optimize(ast)

        # x + 0 and 1 * x should be simplified to IdentifierNode('x')
        self.assertEqual(opt_ast.statements[1].value.name, 'x')
        self.assertEqual(opt_ast.statements[2].value.name, 'x')
        self.assertEqual(opt_ast.statements[3].value.name, 'x')

    def test_bubble_sort_optimization_parity(self):
        code = """
        make bubble_sort(arr) {
            let n = len(arr)
            let i = 0
            keep i < n {
                let j = 0
                keep j < n - i - 1 {
                    check arr[j] > arr[j + 1] {
                        let temp = arr[j]
                        arr[j] = arr[j + 1]
                        arr[j + 1] = temp
                    }
                    j = j + 1
                }
                i = i + 1
            }
            return arr
        }

        let numbers = [64, 34, 25, 12, 22, 11, 90]
        let sorted = bubble_sort(numbers)
        yap sorted
        """
        raw_ast = self.parse_source(code)
        interp = Interpreter()
        interp.run(raw_ast)

        opt_ast = ASTOptimizer().optimize(self.parse_source(code))
        opt_chunk = Compiler().compile(opt_ast)
        BytecodeOptimizer().optimize_chunk(opt_chunk)

        vm = VM()
        vm.run(opt_chunk)
        self.assertEqual(vm.output, interp.output)


def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCHUDOptimizer)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        exit(1)
    print("\n[CHUD] ALL PHASE 4 OPTIMIZER TESTS PASSED WITH 100% PARITY!")


if __name__ == '__main__':
    run_tests()
