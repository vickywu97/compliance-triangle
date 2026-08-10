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

# Load the Bench KB at startup, but NEVER let a missing Bench repo crash the
# whole server. If the KB can't be found, we still serve the (empty) offline
# showcase with a clear notice, and /verify returns 503 instead of 500.
KB_AVAILABLE = True
KB_ERROR = ""
LAWS = None
DEMO_DATA = []
KB_LAW_COUNT = 0
KB_ARTICLE_COUNT = 0
try:
    config.ensure_bench_importable()
    LAWS = kb.load_kb()
    DEMO_DATA = build_demo_data(LAWS)
    # LAWS is keyed by name/code/alias, so len(LAWS) is NOT the law count.
    KB_LAW_COUNT = kb.count_laws(LAWS)
    KB_ARTICLE_COUNT = kb.count_articles(LAWS)
except Exception as e:  # noqa: BLE001 - bench missing must not crash the server
    KB_AVAILABLE = False
    KB_ERROR = str(e)


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
            notice = None
            if not KB_AVAILABLE:
                notice = ("基准库 legal-hallucination-bench 未加载，展示页为离线结构；"
                          "实时校验 /verify 暂不可用。请克隆同级仓库或设置环境变量 "
                          "COMPLIANCE_TRIANGLE_BENCH 指向它。")
            html = build_report_html(DEMO_DATA, with_live=KB_AVAILABLE,
                                     kb_laws=KB_LAW_COUNT,
                                     kb_articles=KB_ARTICLE_COUNT,
                                     notice=notice,
                                     caveats=config.COVERAGE_CAVEATS)
            self._send(200, html)
        else:
            self._send(404, "Not Found")

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/verify":
            if not KB_AVAILABLE:
                self._send(503, json.dumps(
                    {"error": f"基准库未加载，无法核验：{KB_ERROR}"}, ensure_ascii=False),
                    "application/json; charset=utf-8")
                return
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
