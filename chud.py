# ─────────────────────────────────────────────
#  CHUD — chud.py
#  Interactive CLI runner for CHUD programs.
#  Usage:
#     python chud.py script.chud
#     python chud.py           (starts REPL)
# ─────────────────────────────────────────────

import sys
import os

from lexer import Lexer, LexerError
from parser import Parser, ParseError
from interpreter import Interpreter, CHUDRuntimeError

def run_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        sys.exit(1)

    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()

    try:
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        interp = Interpreter(input_fn=input, stdout_fn=print)
        res = interp.run(ast)

        if not res["success"]:
            print(res["error"])
            sys.exit(1)
    except (LexerError, ParseError, CHUDRuntimeError) as e:
        print(e)
        sys.exit(1)

def repl():
    print("CHUD Interactive REPL (v1.0.0)")
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

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_file(sys.argv[1])
    else:
        repl()
