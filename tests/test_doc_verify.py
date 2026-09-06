"""Tests for document-level citation verification (upload .txt/.md/.docx).

Covers:
  - text extraction from plain files and synthetic .docx (stdlib zip+xml)
  - multipart/form-data parsing (the upload wire format)
  - the /verify-file legacy endpoint end-to-end (when the KB is loadable)
"""
from __future__ import annotations

import io
import json
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

from compliance_triangle.doc_extract import extract_text, parse_multipart
from compliance_triangle.server.app import ServerContext, make_server
from compliance_triangle.server import store  # noqa: F401  (ensures importable)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

SAMPLE_TXT = "依据《公司法》第142条规定，公司不得收购本公司股份。\n依据《增值税法》第15条，进项税额可以抵扣。"


def _build_docx(paras) -> bytes:
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="' + W_NS + '"><w:body>'
        + "".join(
            '<w:p><w:r><w:t>' + p.replace("&", "&amp;").replace("<", "&lt;")
            + "</w:t></w:r></w:p>"
            for p in paras
        )
        + "</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


class TestDocExtract(unittest.TestCase):
    def test_extract_plain_txt(self):
        self.assertEqual(extract_text("memo.txt", SAMPLE_TXT.encode("utf-8")), SAMPLE_TXT)

    def test_extract_md_uses_text_path(self):
        md = "# 标题\n依据《合同法》第107条违约方应担责。"
        self.assertIn("第107条", extract_text("x.md", md.encode("utf-8")))

    def test_extract_docx(self):
        raw = _build_docx([
            "依据《公司法》第142条规定，公司不得收购本公司股份。",
            "依据《增值税法》第15条，进项税额可以抵扣。",
        ])
        out = extract_text("opinion.docx", raw)
        self.assertIn("《公司法》第142条", out)
        self.assertIn("《增值税法》第15条", out)
        # two paragraphs should be separated by a newline
        self.assertEqual(len(out.splitlines()), 2)

    def test_unsupported_doc_format(self):
        with self.assertRaises(Exception):
            extract_text("old.doc", b"\xd0\xcf\x11\xe0legacy")


class TestMultipart(unittest.TestCase):
    def test_parse_multipart_file_part(self):
        boundary = "BOUNDARYXYZ"
        head = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="o.docx"\r\n'
            "Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n"
            "\r\n"
        ).encode("utf-8")
        raw = b"PK\x03\x04fakezip"
        tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = head + raw + tail
        parts = parse_multipart(body, boundary)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["name"], "file")
        self.assertEqual(parts[0]["filename"], "o.docx")
        self.assertTrue(parts[0]["data"].startswith(b"PK\x03\x04"))


class TestVerifyFileEndpoint(unittest.TestCase):
    """Boots the real HTTP server (legacy /verify-file, no auth on loopback)."""

    @classmethod
    def setUpClass(cls):
        cls.ctx = ServerContext(db_path=":memory:", host="127.0.0.1")
        cls.server = make_server(cls.ctx, "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post_file(self, filename, raw):
        boundary = "BNDRY"
        head = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
        data = head + raw + tail
        req = urllib.request.Request(self.base + "/verify-file", data=data, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_kb_unavailable_skips_cleanly(self):
        if not self.ctx.kb_available:
            self.skipTest("KB (legal-hallucination-bench) not loadable in this env")

    def test_verify_txt_file(self):
        if not self.ctx.kb_available:
            self.skipTest("KB not loadable")
        code, body = self._post_file("memo.txt", SAMPLE_TXT.encode("utf-8"))
        self.assertEqual(code, 200, body)
        self.assertIn("result", body)
        items = body["result"]["items"]
        laws = {it.get("law_canonical") or it["raw_law"] for it in items}
        self.assertTrue(any("公司法" in l for l in laws))
        self.assertTrue(any("增值税法" in l for l in laws))

    def test_verify_docx_file(self):
        if not self.ctx.kb_available:
            self.skipTest("KB not loadable")
        raw = _build_docx([
            "依据《公司法》第142条规定，公司不得收购本公司股份。",
            "依据《增值税法》第15条，进项税额可以抵扣。",
        ])
        code, body = self._post_file("opinion.docx", raw)
        self.assertEqual(code, 200, body)
        items = body["result"]["items"]
        laws = {it.get("law_canonical") or it["raw_law"] for it in items}
        self.assertTrue(any("公司法" in l for l in laws))
        self.assertTrue(any("增值税法" in l for l in laws))


if __name__ == "__main__":
    unittest.main()
