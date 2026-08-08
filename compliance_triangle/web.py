"""Zero-dependency local web app for compliance-triangle (stdlib only).

Serves a self-contained HTML showcase of the built-in demo scenarios and
provides a live ``/verify`` endpoint that runs the Bench verify engine on a
pasted LLM answer. No third-party packages — only the Python standard library.

Usage:
    python -m compliance_triangle.web            # http://127.0.0.1:8000
    PORT=8080 python -m compliance_triangle.web
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from compliance_triangle import config, kb
from compliance_triangle.verify_integration import verify_answer
from compliance_triangle.memo import build_report_html
from compliance_triangle.runner import build_demo_data

config.ensure_bench_importable()
LAWS = kb.load_kb()
DEMO_DATA = build_demo_data(LAWS)
KB_COUNT = len(LAWS)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body, ctype: str = "text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            html = build_report_html(DEMO_DATA, with_live=True, kb_count=KB_COUNT)
            self._send(200, html)
        else:
            self._send(404, "Not Found")

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/verify":
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw.decode("utf-8") or "{}")
                answer = payload.get("answer", "")
                as_of = payload.get("as_of_date") or "2026-08-01"
                result = verify_answer("LIVE", answer, as_of, LAWS)
                self._send(200, json.dumps(result, ensure_ascii=False),
                           "application/json; charset=utf-8")
            except Exception as e:  # noqa: BLE001 - surface errors to client
                self._send(500, json.dumps({"error": str(e)}, ensure_ascii=False),
                           "application/json; charset=utf-8")
        else:
            self._send(404, "Not Found")

    def log_message(self, *args):  # quiet
        pass


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"合规三角 · 本地服务已启动: http://127.0.0.1:{port}")
    print(f"  - KB: {KB_COUNT} 部法（来自 legal-hallucination-bench）")
    print(f"  - 演示场景: {len(DEMO_DATA)} 个")
    print("  - 按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[stop] 服务已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
