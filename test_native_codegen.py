# ─────────────────────────────────────────────
#  CHUD — test_native_codegen.py
#  Tests the Native C99 Transpiler and Executable
#  compilation pipeline across various algorithms.
# ─────────────────────────────────────────────

import subprocess
import os
import sys
from interpreter import interpret
from vm import run_source
from c_codegen import transpile_source_to_c, compile_chud_to_executable, find_c_compiler


def test_native_compilation_and_parity():
    comp = find_c_compiler()
    if not comp:
        print("[SKIP] No working C compiler found on this system; skipping native binary test.")
        return

    source = '''
make fact(n) {
    check n <= 1 {
        return 1
    }
    return n * fact(n - 1)
}

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

// Test loop with skip (continue) - must not infinite loop
let evens = []
loop let k = 0; k < 10; k = k + 1 {
    check k % 2 != 0 {
        skip
    }
    push(evens, k)
}
yap "Evens: " + evens

yap "Factorial of 6: " + fact(6)
let list = [99, 12, 55, 1, 8, 43]
yap "Before sort: " + list
yap "After sort:  " + bubble_sort(list)
yap "Boolean test: " + (W and not L)
yap "Modulo test: " + (17 % 5)
'''
    exe_name = "test_binary.exe" if sys.platform == "win32" else "test_binary"
    exe_path = os.path.abspath(exe_name)
    compile_chud_to_executable(source, exe_path, compiler_cmd=comp)
    assert os.path.exists(exe_path), "Native executable was not created!"

    # Run native executable
    res = subprocess.run([exe_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0, f"Native binary crashed:\n{res.stderr}"

    native_output = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    interp_output = interpret(source)["output"]
    vm_output = run_source(source)["output"]

    print("Native Output:     ", native_output)
    print("Interpreter Output:", interp_output)
    print("VM Output:         ", vm_output)

    assert native_output == interp_output == vm_output, "Native C output differs from Interpreter/VM!"
    print("\n[OK] 100% PARITY BETWEEN NATIVE C BINARY, INTERPRETER, AND BYTECODE VM!")

    # Cleanup test files
    if os.path.exists(exe_path):
        os.remove(exe_path)
    if os.path.exists(exe_path + ".c"):
        os.remove(exe_path + ".c")


if __name__ == '__main__':
    test_native_compilation_and_parity()
