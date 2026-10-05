# ─────────────────────────────────────────────
#  CHUD — chud.py
#  Command-line interface & Compiler driver for CHUD.
#  Supports:
#    - Tree-Walk Interpretation
#    - Bytecode Virtual Machine Execution
#    - Binary Bytecode (.chudc) Compilation & Loading
#    - C99 Transpilation & Native .exe Compilation
#
#  Usage:
#     python chud.py script.chud               (Runs program)
#     python chud.py script.chudc              (Runs binary bytecode instantly)
#     python chud.py --vm script.chud          (Runs via Bytecode VM)
#     python chud.py --emit-bc script.chud -o script.chudc  (Compiles binary bytecode)
#     python chud.py --emit-c script.chud -o script.c       (Emits C99 source)
#     python chud.py --compile script.chud -o script.exe    (Compiles native binary)
#     python chud.py                           (Starts interactive REPL)
# ─────────────────────────────────────────────

import sys
import os
import argparse

from lexer import Lexer, LexerError
from parser import Parser, ParseError
from interpreter import Interpreter, CHUDRuntimeError
from vm import VM, VMRuntimeError
from compiler import Compiler, CompileError
from c_codegen import transpile_source_to_c, compile_chud_to_executable
from bytecode_serializer import (
    compile_source_to_chudc, load_chudc_file,
    SerializationError, MAGIC_BYTES
)


def run_file(filepath, engine="interp"):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    # Check for binary .chudc file auto-detection
    with open(filepath, 'rb') as f:
        head = f.read(4)

    if head == MAGIC_BYTES or filepath.endswith(".chudc"):
        try:
            chunk = load_chudc_file(filepath)
            vm = VM(input_fn=input, output_fn=print)
            res = vm.run(chunk)
            if not res["success"]:
                print(res["error"])
                sys.exit(1)
            return
        except SerializationError as e:
            print(f"[CHUD Binary Error] {e}")
            sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        if engine == "vm":
            tokens = Lexer(source).tokenize()
            ast = Parser(tokens).parse()
            chunk = Compiler().compile(ast)
            vm = VM(input_fn=input, output_fn=print)
            res = vm.run(chunk)
        else:
            tokens = Lexer(source).tokenize()
            ast = Parser(tokens).parse()
            interp = Interpreter(input_fn=input, stdout_fn=print)
            res = interp.run(ast)

        if not res["success"]:
            print(res["error"])
            sys.exit(1)
    except (LexerError, ParseError, CHUDRuntimeError, VMRuntimeError, CompileError) as e:
        print(e)
        sys.exit(1)


def compile_file_to_bytecode(filepath, output_chudc=None):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    if not output_chudc:
        base, _ = os.path.splitext(filepath)
        output_chudc = base + ".chudc"

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        out_path = compile_source_to_chudc(source, output_chudc)
        print(f"[CHUD] SUCCESS: Compiled binary bytecode -> {out_path}")
    except Exception as e:
        print(f"Bytecode Compilation Error: {e}")
        sys.exit(1)


def compile_file_to_c(filepath, output_c=None):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        c_code = transpile_source_to_c(source)
        if output_c:
            with open(output_c, 'w', encoding='utf-8') as f:
                f.write(c_code)
            print(f"[CHUD] C source emitted to: {output_c}")
        else:
            print(c_code)
    except Exception as e:
        print(f"Compilation Error: {e}")
        sys.exit(1)


def compile_file_to_native(filepath, output_exe):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    if not output_exe:
        base, _ = os.path.splitext(filepath)
        output_exe = base + (".exe" if os.name == "nt" else "")

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        print(f"[CHUD] Transpiling {filepath} -> C99 -> GCC Native Compilation...")
        exe_path = compile_chud_to_executable(source, output_exe)
        print(f"[CHUD] SUCCESS: Built native standalone binary -> {exe_path}")
    except Exception as e:
        print(f"Native Build Error: {e}")
        sys.exit(1)


def repl():
    print("CHUD Interactive REPL (v2.0.0 - Multi-Backend)")
    print("Type 'exit' to quit.\n")
    interp = Interpreter(input_fn=input)

    while True:
        try:
            line = input("chud> ")
            if line.strip() in ("exit", "quit"):
                break
            if not line.strip():
                continue

            tokens = Lexer(line).tokenize()
            ast = Parser(tokens).parse()
            res = interp.run(ast)
            for out in res["output"]:
                print(out)
            if not res["success"]:
                print(res["error"])
        except (KeyboardInterrupt, EOFError):
            print("\nExiting CHUD.")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    if len(sys.argv) == 1:
        repl()
        return

    parser = argparse.ArgumentParser(description="CHUD Programming Language Compiler & Runtime Driver")
    parser.add_argument("file", nargs="?", help="CHUD source file (.chud) or binary bytecode (.chudc)")
    parser.add_argument("--vm", action="store_true", help="Execute using the Bytecode VM instead of the tree-walk interpreter")
    parser.add_argument("--emit-bc", "--compile-bytecode", dest="emit_bc", action="store_true", help="Compile CHUD source into a .chudc binary bytecode file")
    parser.add_argument("--emit-c", dest="emit_c", action="store_true", help="Transpile CHUD source into C99 source code")
    parser.add_argument("-c", "--compile", action="store_true", help="Compile CHUD source to a native standalone executable")
    parser.add_argument("-o", "--output", help="Output executable, bytecode, or C source filename")

    args = parser.parse_args()

    if not args.file:
        repl()
        return

    if args.compile:
        compile_file_to_native(args.file, args.output)
    elif args.emit_bc:
        compile_file_to_bytecode(args.file, args.output)
    elif args.emit_c:
        compile_file_to_c(args.file, args.output)
    elif args.vm:
        run_file(args.file, engine="vm")
    else:
        run_file(args.file, engine="interp")


if __name__ == '__main__':
    main()
