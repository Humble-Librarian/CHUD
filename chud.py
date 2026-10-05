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
from chud_parser import Parser, ParseError
from interpreter import Interpreter, CHUDRuntimeError
from vm import VM, VMRuntimeError
from compiler import Compiler, CompileError
from c_codegen import transpile_source_to_c, compile_chud_to_executable
from bytecode_serializer import (
    compile_source_to_chudc, load_chudc_file,
    SerializationError, MAGIC_BYTES
)
from ast_optimizer import ASTOptimizer
from bytecode_optimizer import BytecodeOptimizer


def print_opt_stats(ast_opt, bc_opt, opt_level):
    print("=" * 60)
    print(f"            CHUD OPTIMIZER TELEMETRY (-O{opt_level})")
    print("=" * 60)
    if ast_opt:
        node_delta = ast_opt.nodes_before - ast_opt.nodes_after
        node_pct = (node_delta / ast_opt.nodes_before * 100) if ast_opt.nodes_before > 0 else 0
        print(f" AST Nodes (Before / After):   {ast_opt.nodes_before} -> {ast_opt.nodes_after} (-{node_pct:.1f}%)")
        print(f" Constants Folded:             {ast_opt.constants_folded}")
        print(f" Dead Branches Pruned:         {ast_opt.dead_branches_pruned}")
        print(f" Dead Stmts Eliminated:        {ast_opt.dead_stmts_removed}")
    if bc_opt:
        instr_delta = bc_opt.instructions_before - bc_opt.instructions_after
        instr_pct = (instr_delta / bc_opt.instructions_before * 100) if bc_opt.instructions_before > 0 else 0
        print(f" Bytecode Instrs (Before/After): {bc_opt.instructions_before} -> {bc_opt.instructions_after} (-{instr_pct:.1f}%)")
        print(f" Peephole Passes Run:          {bc_opt.peephole_passes}")
        print(f" Jumps Threaded:               {bc_opt.jumps_threaded}")
        print(f" Push/Pop Pairs Removed:       {bc_opt.push_pop_eliminated}")
        print(f" Dead Instructions Stripped:   {bc_opt.dead_code_eliminated}")
    print("=" * 60)


def run_file(filepath, engine="interp", opt_level=1, show_stats=False):
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
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        ast_opt = None
        bc_opt = None

        if opt_level >= 1:
            ast_opt = ASTOptimizer()
            ast = ast_opt.optimize(ast)

        if engine == "vm":
            chunk = Compiler().compile(ast)
            if opt_level >= 2:
                bc_opt = BytecodeOptimizer()
                bc_opt.optimize_chunk(chunk)
            if show_stats:
                print_opt_stats(ast_opt, bc_opt, opt_level)
            vm = VM(input_fn=input, output_fn=print)
            res = vm.run(chunk)
        else:
            if show_stats:
                print_opt_stats(ast_opt, None, opt_level)
            interp = Interpreter(input_fn=input, stdout_fn=print)
            res = interp.run(ast)

        if not res["success"]:
            print(res["error"])
            sys.exit(1)
    except (LexerError, ParseError, CHUDRuntimeError, VMRuntimeError, CompileError) as e:
        print(e)
        sys.exit(1)


def compile_file_to_bytecode(filepath, output_chudc=None, opt_level=2, show_stats=False):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    if not output_chudc:
        base, _ = os.path.splitext(filepath)
        output_chudc = base + ".chudc"

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        if show_stats:
            tokens = Lexer(source).tokenize()
            ast = Parser(tokens).parse()
            ast_opt = ASTOptimizer() if opt_level >= 1 else None
            if ast_opt:
                ast = ast_opt.optimize(ast)
            chunk = Compiler().compile(ast)
            bc_opt = BytecodeOptimizer() if opt_level >= 2 else None
            if bc_opt:
                bc_opt.optimize_chunk(chunk)
            print_opt_stats(ast_opt, bc_opt, opt_level)

        out_path = compile_source_to_chudc(source, output_chudc, opt_level=opt_level)
        print(f"[CHUD] SUCCESS: Compiled binary bytecode -> {out_path} (Opt level: -O{opt_level})")
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
    print("CHUD Interactive REPL (v2.0.0 - Multi-Backend & Optimizer)")
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
    parser.add_argument("-O0", dest="opt_0", action="store_true", help="Disable all optimizations")
    parser.add_argument("-O1", dest="opt_1", action="store_true", help="Enable AST-level constant folding and dead branch pruning")
    parser.add_argument("-O2", dest="opt_2", action="store_true", help="Enable full optimization (AST folding + Bytecode peephole)")
    parser.add_argument("--opt-stats", action="store_true", help="Display compiler optimization telemetry metrics")
    parser.add_argument("--emit-bc", "--compile-bytecode", dest="emit_bc", action="store_true", help="Compile CHUD source into a .chudc binary bytecode file")
    parser.add_argument("--emit-c", dest="emit_c", action="store_true", help="Transpile CHUD source into C99 source code")
    parser.add_argument("-c", "--compile", action="store_true", help="Compile CHUD source to a native standalone executable")
    parser.add_argument("-o", "--output", help="Output executable, bytecode, or C source filename")

    args = parser.parse_args()

    if not args.file:
        repl()
        return

    # Determine optimization level
    opt_level = 2
    if args.opt_0:
        opt_level = 0
    elif args.opt_1:
        opt_level = 1
    elif args.opt_2:
        opt_level = 2

    if args.compile:
        compile_file_to_native(args.file, args.output)
    elif args.emit_bc:
        compile_file_to_bytecode(args.file, args.output, opt_level=opt_level, show_stats=args.opt_stats)
    elif args.emit_c:
        compile_file_to_c(args.file, args.output)
    elif args.vm:
        run_file(args.file, engine="vm", opt_level=opt_level, show_stats=args.opt_stats)
    else:
        run_file(args.file, engine="interp", opt_level=opt_level, show_stats=args.opt_stats)


if __name__ == '__main__':
    main()
