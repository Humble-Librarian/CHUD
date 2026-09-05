# ─────────────────────────────────────────────
#  CHUD — server.py
#  Lightweight HTTP Server & API.
#  ZERO external dependencies — 100% Python stdlib.
#  Runs with: python server.py [port]
# ─────────────────────────────────────────────

import http.server
import json
import mimetypes
import os
import sys
import traceback

from lexer import Lexer, LexerError
from parser import Parser, ParseError
from ast_serializer import ast_to_d3
from cst_generator import generate_cst
from interpreter import Interpreter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8000


class CHUDRequestHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        # Clean path and serve static files
        req_path = self.path.split('?')[0]
        if req_path == '/' or req_path == '':
            req_path = '/index.html'

        file_path = os.path.normpath(os.path.join(BASE_DIR, req_path.lstrip('/')))

        # Security check: ensure path is within BASE_DIR
        if not file_path.startswith(BASE_DIR) or not os.path.isfile(file_path):
            self.send_error(404, f"File Not Found: {req_path}")
            return

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'

        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {str(e)}")

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_len)

        try:
            payload = json.loads(post_data.decode('utf-8')) if post_data else {}
        except Exception:
            return self._send_json({"success": False, "error": "Invalid JSON payload."}, 400)

        code = payload.get("code", "")
        inputs = list(payload.get("inputs", []))
        req_path = self.path.rstrip('/')

        if req_path in ('/api/parse', '/api/compile'):
            return self._handle_parse(code)
        elif req_path == '/api/run':
            return self._handle_run(code, inputs)
        elif req_path == '/api/all':
            return self._handle_all(code, inputs)
        else:
            return self._send_json({"success": False, "error": f"Unknown endpoint '{self.path}'"}, 404)

    def _handle_parse(self, code):
        try:
            tokens = Lexer(code).tokenize()
            token_list = [
                {"type": t.type, "value": t.value, "line": t.line}
                for t in tokens if t.type != 'EOF'
            ]
            ast = Parser(tokens).parse()
            ast_d3 = ast_to_d3(ast)
            cst_d3 = generate_cst(code)

            return self._send_json({
                "success": True,
                "tokens": token_list,
                "ast": ast_d3,
                "cst": cst_d3,
                "error": None
            })
        except (LexerError, ParseError) as e:
            return self._send_json({
                "success": False,
                "error": str(e)
            }, 200)
        except Exception as e:
            return self._send_json({
                "success": False,
                "error": f"Internal Error: {str(e)}\n{traceback.format_exc()}"
            }, 500)

    def _handle_run(self, code, inputs=None):
        try:
            tokens = Lexer(code).tokenize()
            ast = Parser(tokens).parse()
            inp_queue = list(inputs or [])
            def web_input(prompt=""):
                return inp_queue.pop(0) if inp_queue else "0"
            interp = Interpreter(input_fn=web_input)
            res = interp.run(ast)
            return self._send_json(res)
        except (LexerError, ParseError) as e:
            return self._send_json({
                "success": False,
                "output": [],
                "variables": {},
                "error": str(e)
            }, 200)
        except Exception as e:
            return self._send_json({
                "success": False,
                "output": [],
                "variables": {},
                "error": f"Internal Error: {str(e)}"
            }, 500)

    def _handle_all(self, code, inputs=None):
        try:
            tokens = Lexer(code).tokenize()
            token_list = [
                {"type": t.type, "value": t.value, "line": t.line}
                for t in tokens if t.type != 'EOF'
            ]
            ast = Parser(tokens).parse()
            ast_d3 = ast_to_d3(ast)
            cst_d3 = generate_cst(code)

            inp_queue = list(inputs or [])
            def web_input(prompt=""):
                return inp_queue.pop(0) if inp_queue else "0"
            interp = Interpreter(input_fn=web_input)
            run_res = interp.run(ast)

            return self._send_json({
                "success": run_res["success"],
                "tokens": token_list,
                "ast": ast_d3,
                "cst": cst_d3,
                "output": run_res["output"],
                "variables": run_res["variables"],
                "error": run_res["error"]
            })
        except (LexerError, ParseError) as e:
            return self._send_json({
                "success": False,
                "tokens": [],
                "ast": None,
                "cst": None,
                "output": [],
                "variables": {},
                "error": str(e)
            }, 200)
        except Exception as e:
            return self._send_json({
                "success": False,
                "error": f"Internal Error: {str(e)}"
            }, 500)


def run_server(port=DEFAULT_PORT):
    server_address = ('', port)
    httpd = http.server.ThreadingHTTPServer(server_address, CHUDRequestHandler)
    print(f"[CHUD] Dev Server running at http://localhost:{port}/")
    print("[CHUD] Zero dependencies. Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[CHUD] Shutting down server.")
        httpd.server_close()


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run_server(port)
