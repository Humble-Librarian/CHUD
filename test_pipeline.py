# ─────────────────────────────────────────────
#  CHUD — test_pipeline.py
#  Full pipeline verification script
# ─────────────────────────────────────────────

import sys
from lexer import Lexer
from parser import Parser
from ast_serializer import ast_to_d3
from cst_generator import generate_cst
from interpreter import Interpreter, interpret

code = '''
let name = "bro"
let age = 19

check age >= 18 {
    yap "approved: " + name
} otherwise {
    yap "denied"
}

let i = 0
keep i < 3 {
    yap i
    i = i + 1
}
'''

def test_full_pipeline():
    # 1. Lexer
    tokens = Lexer(code).tokenize()
    assert len(tokens) > 10, "Lexer failed"
    print(f"[OK] Lexer produced {len(tokens)} tokens")

    # 2. Parser & AST
    ast = Parser(tokens).parse()
    assert len(ast.statements) == 5, f"Expected 5 statements, got {len(ast.statements)}"
    print(f"[OK] Parser produced AST with {len(ast.statements)} statements")

    # 3. AST Serializer
    ast_dict = ast_to_d3(ast)
    assert ast_dict["type"] == "Program"
    assert len(ast_dict["children"]) == 5
    print(f"[OK] AST Serializer generated root: {ast_dict['name']}")

    # 4. CST Generator
    cst_dict = generate_cst(code)
    assert cst_dict["name"] == "<program>"
    assert len(cst_dict["children"]) > 0
    print(f"[OK] CST Generator generated root: {cst_dict['name']} with {len(cst_dict['children'])} children")

    # 5. Interpreter
    res = interpret(code)
    assert res["success"] is True, f"Interpreter failed: {res['error']}"
    assert res["output"] == ["approved: bro", "0", "1", "2"], f"Unexpected output: {res['output']}"
    assert res["variables"]["name"] == "bro"
    assert res["variables"]["age"] == "19"
    assert res["variables"]["i"] == "3"
    print(f"[OK] Interpreter executed successfully! Output: {res['output']}")
    print(f"[OK] Final Environment: {res['variables']}")

    print("\nALL 5 CORE PIPELINE COMPONENTS VERIFIED SUCCESSFULLY!")

if __name__ == '__main__':
    test_full_pipeline()
