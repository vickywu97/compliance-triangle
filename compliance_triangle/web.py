"""Unified entry point for compliance-triangle (stdlib only).

Historically this module *was* the server: a ~140-line ``BaseHTTPRequestHandler``
that served a pre-generated showcase and two unauthenticated endpoints. The
server now lives in :mod:`compliance_triangle.server.app`, which adds accounts,
persistence and quotas while keeping the same stdlib-only constraint.

This module is kept as the documented entry point so existing commands and
docs keep working::

    python -m compliance_triangle.web          # http://127.0.0.1:8000
    PORT=8080 python -m compliance_triangle.web
    HOST=0.0.0.0 python -m compliance_triangle.web   # deployed mode

Routes (see ``server.app`` for the full list):
    /               the SaaS single-page app
    /demo           the original pre-generated offline showcase
    /healthz        health check
    /api/*          JSON API (auth, verify, analyze, history, keys)
    /verify         legacy unauthenticated single-shot verification
    /analyze        legacy LLM analysis (auth required in deployed mode)
"""
from __future__ import annotations

import os
import sys


def main(argv: list | None = None) -> int:  # noqa: D401 - CLI entry point
    argv = list(sys.argv[1:] if argv is None else argv)
    # Deferred import: keeps `python -c "import compliance_triangle.web"` cheap
    # and avoids loading the 1.6 MB KB unless we are actually serving.
    from compliance_triangle.server.app import run_server

    host = os.environ.get("HOST") or "127.0.0.1"
    try:
        port = int(os.environ.get("PORT") or 8000)
    except ValueError:
        print("[error] PORT 必须是数字", file=sys.stderr)
        return 2
    if argv:
        try:
            port = int(argv[0])
        except ValueError:
            print(f"[error] 端口号无效: {argv[0]}", file=sys.stderr)
            return 2

    return run_server(host=host, port=port,
                      db_path=os.environ.get("COMPLIANCE_TRIANGLE_DB"))


if __name__ == "__main__":
    sys.exit(main())
