# ─────────────────────────────────────────────
#  CHUD — test_all.py
#  Automated test suite verifying all 5 components:
#  1. AST Serializer
#  2. CST Generator
#  3. Interpreter
#  4. HTTP Server / API Endpoints
#  5. Frontend files existence & integrity
# ─────────────────────────────────────────────

import os
import json
import threading
import time
import urllib.request

from lexer import Lexer
from parser import Parser
from ast_serializer import ast_to_d3
from cst_generator import generate_cst
from interpreter import Interpreter, interpret
from server import run_server

def test_ast_serializer():
    src = 'let x = 10\nyap x + 5'
    tokens = Lexer(src).tokenize()
    ast = Parser(tokens).parse()
    d3_data = ast_to_d3(ast)
    assert d3_data["type"] == "Program"
    assert len(d3_data["children"]) == 2
    print("[OK] Task 1 Passed: AST Serializer")

def test_cst_generator():
    src = 'check x >= 10 { yap "yes" }'
    cst = generate_cst(src)
    assert cst["type"] == "rule"
    assert cst["name"] == "<program>"
    # Verify concrete tokens exist in CST
    def find_token(node, tok_type):
        if node.get("token") == tok_type:
            return True
        for child in node.get("children", []):
            if find_token(child, tok_type):
                return True
        return False
    assert find_token(cst, "CHECK")
    assert find_token(cst, "LBRACE")
    assert find_token(cst, "RBRACE")
    print("[OK] Task 2 Passed: CST Generator captures grammar rules and concrete tokens")

def test_interpreter():
    src = '''
    let x = 10
    let y = 20
    let sum = x + y
    let flag = W
    check sum == 30 {
        yap "sum is 30"
    } otherwise {
        yap "sum is wrong"
    }
    let count = 0
    keep count < 5 {
        count = count + 1
        check count == 2 {
            stop
        }
    }
    '''
    res = interpret(src)
    assert res["success"] is True, res["error"]
    assert res["output"] == ["sum is 30"]
    assert res["variables"]["sum"] == "30"
    assert res["variables"]["count"] == "2"
    assert res["variables"]["flag"] == "W"
    print("[OK] Task 5 Passed: Tree-Walk Interpreter (vars, math, check/otherwise, keep, stop, W/L)")

def test_frontend_files():
    for filename in ["index.html", "style.css", "app.js"]:
        assert os.path.isfile(filename), f"Missing {filename}"
        assert os.path.getsize(filename) > 0, f"Empty {filename}"
    print("[OK] Task 3 Passed: Frontend files exist and are populated")

def test_server():
    port = 8765
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(1)

    # 1. Test Static files
    res = urllib.request.urlopen(f"http://localhost:{port}/")
    assert res.status == 200
    html = res.read().decode('utf-8')
    assert "CHUD" in html

    # 2. Test /api/parse
    payload = json.dumps({"code": "let z = 99\nyap z"}).encode('utf-8')
    req = urllib.request.Request(
        f"http://localhost:{port}/api/parse",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    assert data["success"] is True
    assert data["ast"]["type"] == "Program"
    assert data["cst"]["type"] == "rule"

    # 3. Test /api/run
    req = urllib.request.Request(
        f"http://localhost:{port}/api/run",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    assert data["success"] is True
    assert data["output"] == ["99"]

    # 4. Test /api/all
    req = urllib.request.Request(
        f"http://localhost:{port}/api/all",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    assert data["success"] is True
    assert data["output"] == ["99"]
    assert data["ast"] is not None

    print("[OK] Task 4 Passed: Server static files and all API endpoints (/api/parse, /api/run, /api/all)")

if __name__ == '__main__':
    test_ast_serializer()
    test_cst_generator()
    test_interpreter()
    test_frontend_files()
    test_server()
    print("\n[CHUD] ALL 5 TASKS VERIFIED SUCCESSFULLY WITH ZERO BLOAT!")
