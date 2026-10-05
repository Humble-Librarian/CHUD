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


def test_modulo_operator():
    assert_parity(
        'let a = 17 % 5\nlet b = 10 % 2\nlet c = 25 % 7\nyap a\nyap b\nyap c',
        "modulo operator (%) calculation"
    )


def test_modulo_by_zero_parity():
    assert_parity(
        'yap 10 % 0',
        "runtime error: modulo by zero"
    )


def test_logical_not_operator():
    assert_parity(
        'yap !W\nyap !L\nyap not (5 > 10)\nyap !!W\nyap not L',
        "logical not (! / not) operator"
    )


def test_logical_and_or_operators():
    assert_parity(
        'yap W and W\nyap W and L\nyap L and W\nyap L and L\nyap W or L\nyap L or W\nyap L or L\nyap 10 > 5 and 3 < 4\nyap 10 < 5 or 2 == 2',
        "logical and / or expressions"
    )


def test_short_circuit_behavior():
    src = '''
let side_effect = 0
make trigger() {
    side_effect = side_effect + 1
    return W
}
check L and trigger() {
    yap "should not run"
}
yap side_effect

check W or trigger() {
    yap "short circuit or"
}
yap side_effect
'''
    assert_parity(src, "short-circuiting of and / or operators")


def test_skip_in_keep_loop():
    src = '''
let i = 0
keep i < 5 {
    i = i + 1
    check i == 3 {
        skip
    }
    yap i
}
'''
    assert_parity(src, "skip (continue) inside keep loop")


def test_skip_in_classic_for_loop():
    src = '''
loop let i = 0; i < 5; i = i + 1 {
    check i == 2 or i == 4 {
        skip
    }
    yap i
}
'''
    assert_parity(src, "skip (continue) inside classic for loop")


def test_function_scoping_and_shadowing():
    src = '''
let x = 100
make modify(val) {
    let x = val * 2
    return x
}
let res = modify(5)
yap res
yap x
'''
    assert_parity(src, "function local shadowing vs global scope")


def test_deep_recursion_stack():
    src = '''
make sum_to(n) {
    check n <= 0 {
        return 0
    }
    return n + sum_to(n - 1)
}
yap sum_to(50)
'''
    assert_parity(src, "deep recursion with CallFrame stack (depth 50)")


def test_array_literal_and_indexing():
    src = '''
let items = [10, 20, 30, "hello", W]
yap items
yap items[0]
yap items[3]
yap items[4]
'''
    assert_parity(src, "array literal and element indexing")


def test_array_element_mutation():
    src = '''
let nums = [1, 2, 3]
nums[1] = 99
yap nums
yap nums[1]
'''
    assert_parity(src, "array element assignment / mutation")


def test_nested_arrays():
    src = '''
let matrix = [[1, 2], [3, 4]]
yap matrix[0][1]
yap matrix[1][0]
matrix[0][1] = 100
yap matrix
'''
    assert_parity(src, "nested multi-dimensional array access & mutation")


def test_array_builtins_len_push_pop():
    src = '''
let list = [5, 10]
yap len(list)
push(list, 15)
push(list, 20)
yap len(list)
yap list
let removed = pop(list)
yap removed
yap list
'''
    assert_parity(src, "array built-in functions: len, push, pop")


def test_bubble_sort_algorithm():
    src = '''
make bubble_sort(arr) {
    let n = len(arr)
    loop let i = 0; i < n; i = i + 1 {
        loop let j = 0; j < n - i - 1; j = j + 1 {
            check arr[j] > arr[j + 1] {
                let temp = arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = temp
            }
        }
    }
    return arr
}

let data = [64, 34, 25, 12, 22, 11, 90]
yap bubble_sort(data)
'''
    assert_parity(src, "bubble sort algorithm in CHUD")


def test_array_index_out_of_bounds_parity():
    src = '''
let small = [1, 2]
yap small[10]
'''
    assert_parity(src, "runtime error: array index out of bounds")


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
    test_modulo_operator()
    test_modulo_by_zero_parity()
    test_logical_not_operator()
    test_logical_and_or_operators()
    test_short_circuit_behavior()
    test_skip_in_keep_loop()
    test_skip_in_classic_for_loop()
    test_function_scoping_and_shadowing()
    test_deep_recursion_stack()
    test_array_literal_and_indexing()
    test_array_element_mutation()
    test_nested_arrays()
    test_array_builtins_len_push_pop()
    test_bubble_sort_algorithm()
    test_array_index_out_of_bounds_parity()

    print("\n[CHUD] VM <-> INTERPRETER PARITY FULLY VERIFIED -- bytecode backend is a drop-in match.")

