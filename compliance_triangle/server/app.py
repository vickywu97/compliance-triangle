"""HTTP API + static asset server for the compliance-triangle SaaS (stdlib only).

Routing
-------
Public:
    GET  /healthz            liveness + KB status (used by the PaaS health check)
    GET  /api/meta           KB counts, available models, coverage caveats
    GET  /demo               the original pre-generated offline showcase page

Accounts:
    POST /api/auth/register  {email, password, display_name?} -> {token, user}
    POST /api/auth/login     {email, password}                -> {token, user}
    POST /api/auth/logout    invalidate the current session
    GET  /api/me             profile + usage/quota summary

Product (authenticated; each call consumes monthly quota):
    POST   /api/verify       {answer, as_of_date?}       -> 🟢🟡🔴 report
    POST   /api/verify-file  multipart file | {text,filename?} -> doc-level 🟢🟡🔴 report
    POST   /api/verify-batch {items:[{id?,text}], text?, as_of_date?} -> consolidated 🟢🟡🔴 report (Markdown/CSV)
    POST   /api/analyze      {scenario, model?, as_of?}  -> LLM answer + report
    GET    /api/analyses     history (tenant-scoped)
    GET    /api/analyses/<id>
    DELETE /api/analyses/<id>
    GET    /api/keys         list programmatic API keys
    POST   /api/keys         {label?} -> {key}  (shown once)
    DELETE /api/keys/<key>   revoke

Legacy (kept for the documented local flow ``python -m compliance_triangle.web``):
    POST /verify    unauthenticated: cheap KB lookup, no persistence
    POST /analyze   LLM-backed, so it requires auth in deployed mode; anonymous
                    use is allowed only when bound to loopback (local demo) or
                    when ``CT_ALLOW_ANON_ANALYZE=1``.

Authentication: ``Authorization: Bearer <session-or-api-key>`` or a
``ct_session`` cookie. Sessions are server-side rows, so logout really works.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib.parse import urlparse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from compliance_triangle import config, kb
from compliance_triangle import live as live_mod
from compliance_triangle.memo import build_report_html
from compliance_triangle.runner import build_demo_data
from compliance_triangle.verify_integration import verify_answer
from compliance_triangle.doc_extract import (
    parse_multipart, extract_text, UnsupportedFormat,
)
from compliance_triangle.server.batch_report import (
    verify_batch, parse_lines, MAX_ITEMS,
)
from compliance_triangle.server import auth as auth_mod
from compliance_triangle.server import store

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SESSION_COOKIE = "ct_session"
DEFAULT_AS_OF = "2026-08-01"

# Anonymous /analyze calls a paid LLM, so it is off by default in deployment.
ANON_ANALYZE_ENV = "CT_ALLOW_ANON_ANALYZE"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


# --------------------------------------------------------------------------- #
# rate limiting (in-memory; per-process, good enough for a single instance)
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Sliding-window limiter. Not shared across processes — documented as such."""

    def __init__(self, max_calls: int = 60, window: float = 60.0):
        self.max_calls = max_calls
        self.window = window
        self._hits: Dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, identity: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(identity, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_calls:
                return False
            q.append(now)
            return True


# --------------------------------------------------------------------------- #
# server state
# --------------------------------------------------------------------------- #
class ServerContext:
    """Everything the request handlers need, built once at startup."""

    def __init__(self, db_path: Optional[str] = None, host: str = "127.0.0.1"):
        self.conn = store.connect(db_path)
        self.host = host
        self.limiter = RateLimiter()
        self.kb_available = True
        self.kb_error = ""
        self.kb_source = ""
        self.laws = None
        self.kb_laws = 0
        self.kb_articles = 0
        self.demo_data = []
        # A missing Bench repo must degrade gracefully, never crash the boot.
        try:
            config.ensure_bench_importable()
            self.laws = kb.load_kb()
            self.kb_source = kb.kb_source()
            self.kb_laws = kb.count_laws(self.laws)
            self.kb_articles = kb.count_articles(self.laws)
            self.demo_data = build_demo_data(self.laws)
        except Exception as e:  # noqa: BLE001
            self.kb_available = False
            self.kb_error = str(e)

    # -- helpers ---------------------------------------------------------- #
    def allow_anon_analyze(self) -> bool:
        if os.environ.get(ANON_ANALYZE_ENV) == "1":
            return True
        return self.host in ("127.0.0.1", "localhost", "::1")

    def live_models(self) -> list:
        try:
            return live_mod.live_models()
        except Exception:  # noqa: BLE001
            return []

    def meta(self) -> Dict:
        return {
            "kb_available": self.kb_available,
            "kb_error": self.kb_error,
            "kb_source": self.kb_source,
            "kb_laws": self.kb_laws,
            "kb_articles": self.kb_articles,
            "live_models": self.live_models(),
            "caveats": list(config.COVERAGE_CAVEATS),
            "default_as_of": DEFAULT_AS_OF,
        }


# --------------------------------------------------------------------------- #
# request handler
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    ctx: ServerContext = None  # injected by make_server()

    # -- low-level helpers ------------------------------------------------ #
    def _send(self, code: int, body, ctype: str = "text/html; charset=utf-8",
              extra: Optional[Dict[str, str]] = None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, obj, extra: Optional[Dict[str, str]] = None):
        self._send(code, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8", extra)

    def _error(self, code: int, message: str):
        self._json(code, {"error": message})

    def _body(self) -> Dict:
        raw = self._body_bytes()
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return {}

    def _body_bytes(self) -> bytes:
        # Cache: the request body can only be read once from the socket. Several
        # handlers (file upload: extract text + read as_of_date) need it twice,
        # and a second raw read on an exhausted stream would BLOCK indefinitely.
        cached = getattr(self, "_cached_body_bytes", None)
        if cached is not None:
            return cached
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        self._cached_body_bytes = self.rfile.read(length) if length else b""
        return self._cached_body_bytes

    def _extract_upload_text(self) -> tuple:
        """Return (text, filename, source) from either multipart/form-data or a
        JSON ``{text, filename?}`` body. Used by the file-verify endpoints."""
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" in ctype:
            boundary = ctype.split("boundary=")[-1].strip().strip('"')
            parts = parse_multipart(self._body_bytes(), boundary)
            for p in parts:
                if p["name"] in ("file", "answer") and p["data"]:
                    fn = p.get("filename") or "upload.bin"
                    return extract_text(fn, p["data"]), fn, "file"
            return "", "", "file"
        # JSON fallback for API clients that already have plain text.
        payload = self._body()
        text = payload.get("text") or payload.get("answer") or ""
        return text, payload.get("filename") or "", "json"

    def _client_ip(self) -> str:
        return self.headers.get("X-Forwarded-For", "").split(",")[0].strip() \
            or self.client_address[0]

    # -- auth ------------------------------------------------------------- #
    def _bearer_token(self) -> str:
        hdr = self.headers.get("Authorization", "")
        if hdr.lower().startswith("bearer "):
            return hdr[7:].strip()
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(SESSION_COOKIE + "="):
                return part.split("=", 1)[1].strip()
        return ""

    def _current_user(self):
        token = self._bearer_token()
        if not token:
            return None
        with store.db_lock():
            user = store.get_session_user(self.ctx.conn, token)
            if user is None:
                user = store.resolve_api_key(self.ctx.conn, token)
            return user

    def _require_user(self):
        user = self._current_user()
        if user is None:
            self._error(401, "需要登录：请在 Authorization 头提供 Bearer 令牌，或先调用 /api/auth/login")
        return user

    def _rate_identity(self) -> str:
        return self._bearer_token() or f"ip:{self._client_ip()}"

    # -- quota ------------------------------------------------------------ #
    def _consume_quota(self, user) -> bool:
        """Return True if the request may proceed; False (and 429) if over quota."""
        with store.db_lock():
            summary = store.usage_summary(self.ctx.conn, user)
            if summary["remaining"] <= 0:
                self._json(429, {
                    "error": f"已达到本月配额上限（{summary['quota']} 次），请下月再试或联系升级套餐。",
                    "usage": summary,
                })
                return False
            store.increment_usage(self.ctx.conn, int(user["id"]))
        return True

    # -- routing ---------------------------------------------------------- #
    def do_OPTIONS(self):  # CORS preflight for programmatic API-key clients
        self._send(204, b"", "text/plain; charset=utf-8", {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
        })

    def do_GET(self):
        self._dispatch("GET", urlparse(self.path).path)

    def do_POST(self):
        self._dispatch("POST", urlparse(self.path).path)

    def do_DELETE(self):
        self._dispatch("DELETE", urlparse(self.path).path)

    def do_HEAD(self):
        self._dispatch("HEAD", urlparse(self.path).path)

    def _dispatch(self, method: str, path: str):
        if not self.ctx.limiter.allow(self._rate_identity()):
            return self._error(429, "请求过于频繁，请稍后再试（限流：60 次/分钟）")
        try:
            self._route(method, path.rstrip("/") or "/")
        except Exception as e:  # noqa: BLE001 - never leak a stack trace to clients
            self._error(500, f"服务器内部错误：{e}")

    def _route(self, method: str, path: str):
        # ---------------- public ---------------- #
        if method in ("GET", "HEAD") and path == "/healthz":
            return self._json(200, {
                "ok": True,
                "kb_available": self.ctx.kb_available,
                "kb_laws": self.ctx.kb_laws,
                "kb_articles": self.ctx.kb_articles,
            })

        if method == "GET" and path == "/api/meta":
            return self._json(200, self.ctx.meta())

        if method == "GET" and path == "/demo":
            return self._serve_demo()

        # ---------------- accounts ---------------- #
        if method == "POST" and path == "/api/auth/register":
            return self._register()
        if method == "POST" and path == "/api/auth/login":
            return self._login()
        if method == "POST" and path == "/api/auth/logout":
            return self._logout()
        if method == "GET" and path == "/api/me":
            return self._me()

        # ---------------- product ---------------- #
        if method == "POST" and path == "/api/verify":
            return self._api_verify()
        if method == "POST" and path == "/api/verify-file":
            return self._api_verify_file()
        if method == "POST" and path == "/api/verify-batch":
            return self._api_verify_batch()
        if method == "POST" and path == "/api/analyze":
            return self._api_analyze()
        if method == "GET" and path == "/api/analyses":
            return self._list_analyses()
        if method == "GET" and path.startswith("/api/analyses/"):
            return self._get_analysis(path.rsplit("/", 1)[-1])
        if method == "DELETE" and path.startswith("/api/analyses/"):
            return self._delete_analysis(path.rsplit("/", 1)[-1])
        if method == "GET" and path == "/api/keys":
            return self._list_keys()
        if method == "POST" and path == "/api/keys":
            return self._create_key()
        if method == "DELETE" and path.startswith("/api/keys/"):
            return self._revoke_key(path.rsplit("/", 1)[-1])

        # ---------------- legacy local API ---------------- #
        if method == "POST" and path == "/verify":
            return self._legacy_verify()
        if method == "POST" and path == "/verify-file":
            return self._legacy_verify_file()
        if method == "POST" and path == "/verify-batch":
            return self._legacy_verify_batch()
        if method == "POST" and path == "/analyze":
            return self._legacy_analyze()

        # ---------------- static ---------------- #
        if method in ("GET", "HEAD"):
            return self._serve_static(path)

        return self._error(404, "Not Found")

    # -- handlers: accounts ------------------------------------------------ #
    def _register(self):
        payload = self._body()
        email = (payload.get("email") or "").strip()
        password = payload.get("password") or ""
        display_name = (payload.get("display_name") or "").strip()
        if not auth_mod.valid_email(email):
            return self._error(400, "邮箱格式不正确")
        ok, msg = auth_mod.validate_password(password)
        if not ok:
            return self._error(400, msg)
        with store.db_lock():
            if store.get_user_by_email(self.ctx.conn, email):
                return self._error(409, "该邮箱已注册，请直接登录")
            uid = store.create_user(self.ctx.conn, email,
                                    auth_mod.hash_password(password), display_name)
            user = store.get_user_by_id(self.ctx.conn, uid)
        return self._issue_session(user, 201)

    def _login(self):
        payload = self._body()
        email = (payload.get("email") or "").strip()
        password = payload.get("password") or ""
        with store.db_lock():
            user = store.get_user_by_email(self.ctx.conn, email)
        if user is None or not auth_mod.verify_password(password, user["password_hash"]):
            # Same message for both cases — don't leak which emails exist.
            return self._error(401, "邮箱或密码不正确")
        return self._issue_session(user, 200)

    def _issue_session(self, user, code: int = 200):
        token = auth_mod.new_session_token()
        with store.db_lock():
            store.create_session(self.ctx.conn, int(user["id"]), token,
                                 auth_mod.session_expiry())
            store.purge_expired_sessions(self.ctx.conn)
            summary = store.usage_summary(self.ctx.conn, user)
        return self._json(code, {
            "token": token,
            "user": auth_mod.public_user(user),
            "usage": summary,
        }, {"Set-Cookie": f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"})

    def _logout(self):
        token = self._bearer_token()
        if token:
            with store.db_lock():
                store.delete_session(self.ctx.conn, token)
        return self._json(200, {"ok": True},
                          {"Set-Cookie": f"{SESSION_COOKIE}=; Path=/; Max-Age=0"})

    def _me(self):
        user = self._require_user()
        if user is None:
            return
        with store.db_lock():
            summary = store.usage_summary(self.ctx.conn, user)
            keys = [dict(r) for r in store.list_api_keys(self.ctx.conn, int(user["id"]))]
        return self._json(200, {
            "user": auth_mod.public_user(user),
            "usage": summary,
            "api_keys": keys,
        })

    # -- handlers: product ------------------------------------------------- #
    def _api_verify(self):
        user = self._require_user()
        if user is None:
            return
        if not self.ctx.kb_available:
            return self._error(503, f"基准库未加载，无法核验：{self.ctx.kb_error}")
        if not self._consume_quota(user):
            return
        payload = self._body()
        answer = payload.get("answer", "")
        if not answer.strip():
            return self._error(400, "缺少 answer 字段")
        as_of = payload.get("as_of_date") or DEFAULT_AS_OF
        result = verify_answer("API", answer, as_of, self.ctx.laws)
        title = self._derive_title(answer, payload.get("title"))
        with store.db_lock():
            aid = store.save_analysis(self.ctx.conn, int(user["id"]), "verify",
                                      title, answer, "", as_of, "", result)
            summary = store.usage_summary(self.ctx.conn, user)
        return self._json(200, {"id": aid, "result": result, "usage": summary})

    def _api_verify_file(self):
        user = self._require_user()
        if user is None:
            return
        if not self.ctx.kb_available:
            return self._error(503, f"基准库未加载，无法核验：{self.ctx.kb_error}")
        if not self._consume_quota(user):
            return
        try:
            text, filename, _src = self._extract_upload_text()
        except UnsupportedFormat as e:
            return self._error(415, str(e))
        if not text.strip():
            return self._error(400, "上传文件中未解析出可核验的文本内容")
        as_of = self._json_body_safe().get("as_of_date") or DEFAULT_AS_OF
        result = verify_answer("FILE", text, as_of, self.ctx.laws)
        title = (filename or "上传文档")[:120]
        with store.db_lock():
            aid = store.save_analysis(self.ctx.conn, int(user["id"]), "verify-file",
                                      title, text, "", as_of, "", result)
            summary = store.usage_summary(self.ctx.conn, user)
        return self._json(200, {
            "id": aid, "filename": filename, "chars": len(text),
            "result": result, "usage": summary,
        })

    def _api_verify_batch(self):
        user = self._require_user()
        if user is None:
            return
        if not self.ctx.kb_available:
            return self._error(503, f"基准库未加载，无法核验：{self.ctx.kb_error}")
        # A batch is ONE quota-consuming operation (it yields a single report).
        if not self._consume_quota(user):
            return
        report = self._build_batch_report()
        if report is None:
            return  # _build_batch_report already sent the error response
        title = f"批量自查（{report['summary']['total']} 条）"
        with store.db_lock():
            aid = store.save_analysis(
                self.ctx.conn, int(user["id"]), "verify-batch", title,
                "\n".join(f"{it['id']}: {it['text'][:200]}" for it in report["items"]),
                "", report["as_of"], "", report)
            summary = store.usage_summary(self.ctx.conn, user)
        return self._json(200, {
            "id": aid, "summary": report["summary"],
            "report_md": report["report_md"], "report_csv": report["report_csv"],
            "items": report["items"], "usage": summary,
        })

    def _legacy_verify_batch(self):
        if not self.ctx.kb_available:
            return self._json(503, {"error": f"基准库未加载，无法核验：{self.ctx.kb_error}"},
                              {"Content-Type": "application/json; charset=utf-8"})
        report = self._build_batch_report()
        if report is None:
            return
        return self._json(200, {
            "summary": report["summary"],
            "report_md": report["report_md"], "report_csv": report["report_csv"],
            "items": report["items"],
        })

    def _build_batch_report(self) -> Optional[Dict]:
        """Shared parsing for both authed and legacy batch endpoints.

        Returns the report dict, or ``None`` (after sending an error response)
        when input is invalid.
        """
        payload = self._body()
        as_of = payload.get("as_of_date") or DEFAULT_AS_OF
        items = payload.get("items")
        if items is None:
            text = payload.get("text") or ""
            items = parse_lines(text)
        if not isinstance(items, list) or not items:
            self._error(400, "缺少有效的 items（[] 或 text 字段），无法生成自查报告")
            return None
        if len(items) > MAX_ITEMS:
            items = items[:MAX_ITEMS]
        try:
            return verify_batch(items, as_of, self.ctx.laws)
        except Exception as e:  # noqa: BLE001
            self._error(500, f"批量核验失败：{e}")
            return None

    def _json_body_safe(self) -> Dict:
        # For multipart uploads the as_of_date may arrive as a separate field;
        # fall back to an empty dict when the body isn't JSON.
        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" in ctype:
            boundary = ctype.split("boundary=")[-1].strip().strip('"')
            for p in parse_multipart(self._body_bytes(), boundary):
                if p["name"] == "as_of_date" and p["data"]:
                    return {"as_of_date": p["data"].decode("utf-8", "replace").strip()}
            return {}
        return self._body()

    def _api_analyze(self):
        user = self._require_user()
        if user is None:
            return
        if not self.ctx.kb_available:
            return self._error(503, f"基准库未加载，无法核验：{self.ctx.kb_error}")
        payload = self._body()
        scenario = (payload.get("scenario") or "").strip()
        if not scenario:
            return self._error(400, "缺少 scenario 字段")
        # Charged up front: the LLM call is the expensive part, so we must not
        # let a client discover their quota is exhausted *after* we paid for it.
        if not self._consume_quota(user):
            return
        as_of = payload.get("as_of_date") or DEFAULT_AS_OF
        model = payload.get("model") or ""
        try:
            answer, result = live_mod.analyze(scenario, as_of, model, self.ctx.laws)
        except Exception as e:  # noqa: BLE001
            return self._error(502, f"模型调用失败：{e}")
        title = self._derive_title(scenario, payload.get("title"))
        with store.db_lock():
            aid = store.save_analysis(self.ctx.conn, int(user["id"]), "analyze",
                                      title, scenario, answer, as_of, model, result)
            summary = store.usage_summary(self.ctx.conn, user)
        return self._json(200, {"id": aid, "answer": answer, "result": result,
                                "usage": summary})

    def _list_analyses(self):
        user = self._require_user()
        if user is None:
            return
        limit = self._int_param("limit", 50, 1, 200)
        offset = self._int_param("offset", 0, 0, 100000)
        with store.db_lock():
            rows = store.list_analyses(self.ctx.conn, int(user["id"]), limit, offset)
        return self._json(200, {"items": [dict(r) for r in rows]})

    def _get_analysis(self, raw_id: str):
        user = self._require_user()
        if user is None:
            return
        try:
            aid = int(raw_id)
        except ValueError:
            return self._error(400, "无效的分析 ID")
        with store.db_lock():
            row = store.get_analysis(self.ctx.conn, int(user["id"]), aid)
        if row is None:
            return self._error(404, "未找到该分析记录（或不属于当前账号）")
        return self._json(200, self._analysis_payload(row))

    def _delete_analysis(self, raw_id: str):
        user = self._require_user()
        if user is None:
            return
        try:
            aid = int(raw_id)
        except ValueError:
            return self._error(400, "无效的分析 ID")
        with store.db_lock():
            ok = store.delete_analysis(self.ctx.conn, int(user["id"]), aid)
        if not ok:
            return self._error(404, "未找到该分析记录（或不属于当前账号）")
        return self._json(200, {"ok": True, "id": aid})

    # -- handlers: api keys ------------------------------------------------ #
    def _list_keys(self):
        user = self._require_user()
        if user is None:
            return
        with store.db_lock():
            rows = store.list_api_keys(self.ctx.conn, int(user["id"]))
        return self._json(200, {"items": [dict(r) for r in rows]})

    def _create_key(self):
        user = self._require_user()
        if user is None:
            return
        label = (self._body().get("label") or "").strip() or "default"
        key = auth_mod.new_api_key()
        with store.db_lock():
            store.create_api_key(self.ctx.conn, int(user["id"]), key, label)
        return self._json(201, {"key": key, "label": label,
                                "note": "请立即保存此密钥，页面刷新后无法再次查看明文。"})

    def _revoke_key(self, key: str):
        user = self._require_user()
        if user is None:
            return
        with store.db_lock():
            ok = store.revoke_api_key(self.ctx.conn, int(user["id"]), key)
        if not ok:
            return self._error(404, "未找到该密钥（或不属于当前账号）")
        return self._json(200, {"ok": True})

    # -- handlers: legacy -------------------------------------------------- #
    def _legacy_verify(self):
        if not self.ctx.kb_available:
            return self._json(503, {"error": f"基准库未加载，无法核验：{self.ctx.kb_error}"},
                              {"Content-Type": "application/json; charset=utf-8"})
        payload = self._body()
        answer = payload.get("answer", "")
        as_of = payload.get("as_of_date") or DEFAULT_AS_OF
        result = verify_answer("LIVE", answer, as_of, self.ctx.laws)
        return self._json(200, result)

    def _legacy_verify_file(self):
        if not self.ctx.kb_available:
            return self._json(503, {"error": f"基准库未加载，无法核验：{self.ctx.kb_error}"},
                              {"Content-Type": "application/json; charset=utf-8"})
        try:
            text, filename, _src = self._extract_upload_text()
        except UnsupportedFormat as e:
            return self._json(415, {"error": str(e)},
                              {"Content-Type": "application/json; charset=utf-8"})
        if not text.strip():
            return self._json(400, {"error": "上传文件中未解析出可核验的文本内容"},
                              {"Content-Type": "application/json; charset=utf-8"})
        as_of = self._json_body_safe().get("as_of_date") or DEFAULT_AS_OF
        result = verify_answer("FILE", text, as_of, self.ctx.laws)
        return self._json(200, {"filename": filename, "chars": len(text), "result": result})

    def _legacy_analyze(self):
        user = self._current_user()
        if user is None and not self.ctx.allow_anon_analyze():
            return self._error(401, "/analyze 会调用付费模型，部署模式下需先登录；"
                                    "本地演示可绑定 127.0.0.1 或设置 CT_ALLOW_ANON_ANALYZE=1")
        if not self.ctx.kb_available:
            return self._error(503, f"基准库未加载，无法核验：{self.ctx.kb_error}")
        payload = self._body()
        scenario = (payload.get("scenario") or "").strip()
        if not scenario:
            return self._error(400, "缺少 scenario 字段")
        if user is not None and not self._consume_quota(user):
            return
        as_of = payload.get("as_of_date") or DEFAULT_AS_OF
        model = payload.get("model") or ""
        try:
            answer, result = live_mod.analyze(scenario, as_of, model, self.ctx.laws)
        except Exception as e:  # noqa: BLE001
            return self._error(502, f"模型调用失败：{e}")
        return self._json(200, {"answer": answer, "result": result})

    # -- helpers ------------------------------------------------------------ #
    @staticmethod
    def _derive_title(text: str, explicit: Optional[str] = None) -> str:
        if explicit:
            return str(explicit)[:120]
        first = (text or "").strip().splitlines()
        head = first[0] if first else ""
        return (head[:60] + "…") if len(head) > 60 else (head or "未命名分析")

    def _int_param(self, name: str, default: int, low: int, high: int) -> int:
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(self.path).query)
        raw = qs.get(name, [None])[0]
        if raw is None:
            return default
        try:
            return max(low, min(high, int(raw)))
        except ValueError:
            return default

    @staticmethod
    def _analysis_payload(row) -> Dict:
        """Expand a stored row: decode ``result_json`` back into a dict."""
        return {
            "id": int(row["id"]),
            "kind": row["kind"],
            "title": row["title"],
            "input_text": row["input_text"],
            "answer_text": row["answer_text"],
            "as_of": row["as_of"],
            "model": row["model"],
            "created_at": row["created_at"],
            "result": json.loads(row["result_json"]),
        }

    def _serve_demo(self):
        notice = None
        if not self.ctx.kb_available:
            notice = (f"基准库 legal-hallucination-bench 未加载：{self.ctx.kb_error}"
                      "。实时校验暂不可用。")
        html = build_report_html(
            self.ctx.demo_data, with_live=self.ctx.kb_available,
            kb_laws=self.ctx.kb_laws, kb_articles=self.ctx.kb_articles,
            notice=notice, caveats=config.COVERAGE_CAVEATS,
            live_models=self.ctx.live_models() if self.ctx.kb_available else [])
        return self._send(200, html)

    def _serve_static(self, path: str):
        rel = "index.html" if path in ("/", "/app", "/index.html") else path.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/"):]
        # Contain path traversal: never serve outside STATIC_DIR.
        target = os.path.abspath(os.path.join(STATIC_DIR, rel))
        if not (target == STATIC_DIR or target.startswith(STATIC_DIR + os.sep)):
            return self._error(403, "Forbidden")
        if not os.path.isfile(target):
            if rel == "index.html":
                return self._error(404, "前端资源未构建：缺少 server/static/index.html")
            return self._error(404, "Not Found")
        ctype = _CONTENT_TYPES.get(os.path.splitext(target)[1].lower(),
                                   "application/octet-stream")
        try:
            with open(target, "rb") as fh:
                body = fh.read()
        except OSError:
            return self._error(500, "静态资源读取失败")
        return self._send(200, body, ctype)

    def log_message(self, *args):  # quiet by default; enable with CT_LOG=1
        if os.environ.get("CT_LOG") == "1":
            super().log_message(*args)


# --------------------------------------------------------------------------- #
# server bootstrap
# --------------------------------------------------------------------------- #
def make_server(ctx: ServerContext, host: str, port: int) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"ctx": ctx})
    return ThreadingHTTPServer((host, port), handler)


def run_server(host: str = None, port: int = None,
               db_path: Optional[str] = None) -> int:
    host = host or os.environ.get("HOST") or "127.0.0.1"
    port = int(port or os.environ.get("PORT") or 8000)
    ctx = ServerContext(db_path=db_path, host=host)
    server = make_server(ctx, host, port)
    mode = "本地演示" if ctx.allow_anon_analyze() else "部署模式（/analyze 需登录）"
    print(f"合规三角 · 服务已启动: http://{host}:{port}  [{mode}]")
    print(f"  - 法条库: {ctx.kb_laws} 部法 / {ctx.kb_articles} 条"
          f"（来源: {ctx.kb_source or '未加载'}）")
    print(f"  - 数据库: {db_path or store.default_db_path()}")
    print("  - API: /api/auth/register, /api/verify, /api/analyze, /api/analyses")
    print("  - 旧版演示页: /demo    健康检查: /healthz")
    print("  - 按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[stop] 服务已停止")
    finally:
        with store.db_lock():
            ctx.conn.close()
    return 0
