# ─────────────────────────────────────────────
#  CHUD — test_server.py
#  Tests HTTP endpoints in server.py
# ─────────────────────────────────────────────

import http.client
import json
import threading
import time
from server import run_server

def test_endpoints():
    port = 8765
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(1)

    conn = http.client.HTTPConnection("localhost", port)

    # 1. GET /
    conn.request("GET", "/")
    res = conn.getresponse()
    body = res.read().decode('utf-8')
    assert res.status == 200
    assert "CHUD" in body
    print("[OK] GET / -> 200 OK (Served index.html)")

    # 2. POST /api/parse
    payload = json.dumps({"code": 'let a = 10\nyap a + 5'})
    headers = {"Content-Type": "application/json"}
    conn.request("POST", "/api/parse", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode('utf-8'))
    assert res.status == 200
    assert data["success"] is True
    assert "ast" in data and "cst" in data and "tokens" in data
    print("[OK] POST /api/parse -> 200 OK (AST, CST, Tokens generated)")

    # 3. POST /api/run
    payload = json.dumps({"code": 'let i = 0\nkeep i < 2 { yap i\n i = i + 1 }'})
    conn.request("POST", "/api/run", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode('utf-8'))
    assert res.status == 200
    assert data["success"] is True
    assert data["output"] == ["0", "1"]
    print(f"[OK] POST /api/run -> 200 OK (Output: {data['output']})")

    # 4. POST /api/all
    payload = json.dumps({"code": 'let msg = "sigma"\nyap msg'})
    conn.request("POST", "/api/all", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode('utf-8'))
    assert res.status == 200
    assert data["success"] is True
    assert data["output"] == ["sigma"]
    print("[OK] POST /api/all -> 200 OK (Combined compile + run)")

    conn.close()
    print("\nALL SERVER ENDPOINTS VERIFIED!")

if __name__ == '__main__':
    test_endpoints()
