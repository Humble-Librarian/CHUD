# ─────────────────────────────────────────────
#  CHUD — test_pipeline.py
#  Full pipeline verification script
# ─────────────────────────────────────────────

import sys
from lexer import Lexer, LexerError
from parser import Parser, ParseError
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


def test_runtime_errors_are_chud_errors():
    bad_math = interpret('let greeting = "hello"\nyap greeting - 1')
    assert bad_math["success"] is False
    assert "line 2" in bad_math["error"]
    assert "needs a number" in bad_math["error"]

    division_by_zero = interpret('yap 10 / 0')
    assert division_by_zero["success"] is False
    assert "line 1" in division_by_zero["error"]
    assert "Division by zero" in division_by_zero["error"]
    print("[OK] Runtime type and arithmetic errors are clear CHUD diagnostics")


def test_scope_input_and_control_flow():
    source = '''
let score = 1
check W {
    let local_only = 99
    score = score + 1
}
let answer = hear
keep W {
    stop
}
yap score + answer
'''
    result = interpret(source, input_fn=lambda prompt: "40")
    assert result["success"] is True, result["error"]
    assert result["output"] == ["42"]
    assert result["variables"]["score"] == "2"
    assert result["variables"]["answer"] == "40"
    assert "local_only" not in result["variables"]

    outside_stop = interpret("stop")
    assert outside_stop["success"] is False
    assert "outside" in outside_stop["error"]
    print("[OK] Scope, hear input, and stop control flow behave as specified")


def test_invalid_source_is_rejected():
    try:
        Lexer("let value = @").tokenize()
        raise AssertionError("Expected LexerError for invalid character")
    except LexerError:
        pass

    try:
        Parser(Lexer("check W { yap 1").tokenize()).parse()
        raise AssertionError("Expected ParseError for missing closing brace")
    except ParseError:
        pass
    print("[OK] Invalid characters and incomplete blocks are rejected")

if __name__ == '__main__':
    test_full_pipeline()
    test_runtime_errors_are_chud_errors()
    test_scope_input_and_control_flow()
    test_invalid_source_is_rejected()
