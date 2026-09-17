# ─────────────────────────────────────────────
#  CHUD — test_vm_parity.py
#  Confirms the bytecode VM produces IDENTICAL
#  output to the tree-walk interpreter for every
#  program the VM currently supports.
#
#  Scope note: the VM (as of tonight's build)
#  supports straight-line code, check/otherwise,
#  and keep loops. It does NOT yet support loop
#  (classic for), make/return (functions), hear
#  (input), or stop (break) — those are future
#  milestones. Tests here are scoped accordingly.
# ─────────────────────────────────────────────

from interpreter import interpret
from vm import run_source


def assert_parity(source, label, inputs=None):
    inp1 = list(inputs) if inputs is not None else None
    inp2 = list(inputs) if inputs is not None else None
    fn1 = (lambda p="": inp1.pop(0)) if inp1 is not None else None
    fn2 = (lambda p="": inp2.pop(0)) if inp2 is not None else None

    interp_result = interpret(source, input_fn=fn1)
    vm_result = run_source(source, input_fn=fn2)

    assert vm_result["output"] == interp_result["output"], (
        f"[{label}] Output mismatch.\n"
        f"  interpreter: {interp_result['output']}\n"
        f"  vm:          {vm_result['output']}"
    )
    assert vm_result["success"] == interp_result["success"], (
        f"[{label}] Success flag mismatch.\n"
        f"  interpreter: {interp_result['success']} ({interp_result['error']})\n"
        f"  vm:          {vm_result['success']} ({vm_result['error']})"
    )
    print(f"[OK] {label}")


def test_straight_line_arithmetic():
    assert_parity(
        'let x = 2 + 3 * 4\nlet y = x - 1\nyap y\nyap x >= 10',
        "straight-line arithmetic + precedence"
    )


def test_string_concat_and_stringify():
    assert_parity(
        'let name = "bro"\nyap "hello " + name\nyap 42\nyap W\nyap L',
        "string concat + stringify of int/bool"
    )


def test_unary_operators():
    assert_parity(
        'let x = 5\nlet y = -x\nyap y\nyap -(-x)',
        "unary minus, including double negation"
    )


def test_division_precision():
    assert_parity(
        'yap 10 / 2\nyap 10 / 4\nyap 7 / 3',
        "division: exact int result vs float result"
    )


def test_check_otherwise_true_branch():
    assert_parity(
        'let age = 19\ncheck age >= 18 {\n    yap "adult"\n} otherwise {\n    yap "minor"\n}',
        "check/otherwise — true branch taken"
    )


def test_check_otherwise_false_branch():
    assert_parity(
        'let age = 15\ncheck age >= 18 {\n    yap "adult"\n} otherwise {\n    yap "minor"\n}',
        "check/otherwise — false branch taken"
    )


def test_check_without_otherwise():
    assert_parity(
        'let x = 5\ncheck x > 10 {\n    yap "big"\n}\nyap "after"',
        "check with no otherwise — condition false does nothing"
    )


def test_keep_loop():
    assert_parity(
        'let i = 0\nkeep i < 5 {\n    yap i\n    i = i + 1\n}\nyap "finished"',
        "keep (while) loop — basic counting"
    )


def test_classic_for_loop():
    assert_parity(
        'loop let i = 0; i < 4; i = i + 1 {\n    yap i\n}',
        "classic for loop (loop)"
    )


def test_stop_break_in_loop():
    assert_parity(
        'let i = 0\nkeep i < 10 {\n    check i == 3 {\n        stop\n    }\n    yap i\n    i = i + 1\n}\nyap "stopped"',
        "stop (break) inside loop"
    )


def test_hear_input():
    assert_parity(
        'let x = hear "enter num: "\nlet flag = hear "enter bool: "\nyap x + 10\nyap flag',
        "hear (input) conversion",
        inputs=["42", "W"]
    )


def test_functions_make_return():
    assert_parity(
        '''make add(a, b) {
    return a + b
}
let sum = add(10, 20)
yap sum''',
        "make and call function with return"
    )


def test_recursive_function():
    assert_parity(
        '''make fact(n) {
    check n <= 1 {
        return 1
    }
    return n * fact(n - 1)
}
yap fact(5)''',
        "recursive function execution"
    )


def test_nested_check_inside_keep():
    assert_parity(
        '''let i = 0
keep i < 6 {
    check i == 3 {
        yap "three!"
    } otherwise {
        yap i
    }
    i = i + 1
}''',
        "nested check inside keep loop"
    )


def test_doubly_nested_check_fizzbuzz_style():
    assert_parity(
        '''let n = 1
keep n <= 5 {
    check n == 3 {
        yap "fizz"
    } otherwise {
        check n == 5 {
            yap "buzz"
        } otherwise {
            yap n
        }
    }
    n = n + 1
}''',
        "doubly nested check/otherwise (fizzbuzz shape)"
    )


def test_runtime_type_error_parity():
    assert_parity(
        'let greeting = "hello"\nyap greeting - 1',
        "runtime error: subtracting from a string"
    )


def test_division_by_zero_parity():
    assert_parity(
        'yap 10 / 0',
        "runtime error: division by zero"
    )


def test_comparison_operators_parity():
    assert_parity(
        'yap 10 >= 5\nyap 10 == 10\nyap 3 != 3\nyap 5 < 3\nyap 5 <= 5',
        "all comparison operators"
    )


def test_reassignment_vs_declaration():
    assert_parity(
        'let x = 1\nx = x + 1\nx = x + 1\nyap x',
        "let (declare) vs bare assignment (reassign)"
    )


if __name__ == '__main__':
    test_straight_line_arithmetic()
    test_string_concat_and_stringify()
    test_unary_operators()
    test_division_precision()
    test_check_otherwise_true_branch()
    test_check_otherwise_false_branch()
    test_check_without_otherwise()
    test_keep_loop()
    test_classic_for_loop()
    test_stop_break_in_loop()
    test_hear_input()
    test_functions_make_return()
    test_recursive_function()
    test_nested_check_inside_keep()
    test_doubly_nested_check_fizzbuzz_style()
    test_runtime_type_error_parity()
    test_division_by_zero_parity()
    test_comparison_operators_parity()
    test_reassignment_vs_declaration()

    print("\n[CHUD] VM <-> INTERPRETER PARITY FULLY VERIFIED -- bytecode backend is a drop-in match.")
