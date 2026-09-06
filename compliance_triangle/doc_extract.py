"""Extract plain text from uploaded documents — stdlib only, no third-party deps.

Supported inputs (by extension):
  - .txt / .md / .json / .csv / .log ... : decoded as text (utf-8 → gbk → latin-1)
  - .docx                              : OOXML (Office Open XML) — unzipped with the
                                         standard-library ``zipfile`` + ``xml`` modules
                                         and the paragraph text pulled out of
                                         ``word/document.xml``.

Unsupported:
  - .doc (legacy binary OLE2 Word) — recommend converting to .docx first.
"""
from __future__ import annotations

import io
import json
import zipfile
import xml.etree.ElementTree as ET
from typing import Tuple

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Extensions we treat as plain text (decode, no structural parsing).
_TEXT_EXTS = {".txt", ".md", ".markdown", ".json", ".csv", ".log", ".text", ".rst"}


class UnsupportedFormat(Exception):
    """Raised when the uploaded file type cannot be parsed."""


def extract_text(filename: str, raw: bytes) -> str:
    """Return the plain-text content of ``raw`` bytes from ``filename``.

    Raises :class:`UnsupportedFormat` for binary formats we cannot read.
    """
    ext = _ext(filename)
    if ext == ".docx":
        return _extract_docx(raw)
    if ext in _TEXT_EXTS:
        return _decode_text(raw)
    if ext == ".doc":
        raise UnsupportedFormat(
            "不支持旧版 .doc（OLE2 二进制）格式；请先在 Word 中另存为 .docx 后上传。")
    # Unknown extension: best-effort treat as UTF-8 text; if it looks binary, bail.
    return _decode_text(raw, strict=False)


def _ext(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot >= 0 else ""


def _decode_text(raw: bytes, strict: bool = True) -> str:
    # utf-8 first (most AI exports / modern files); fall back to gbk for
    # Chinese Windows-origin text, then latin-1 as a lossy last resort.
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    if strict:
        raise UnsupportedFormat("无法以 utf-8 / gbk / latin-1 解码该文件。")
    return raw.decode("latin-1", errors="replace")


def _extract_docx(raw: bytes) -> str:
    try:
        buf = io.BytesIO(raw)
        with zipfile.ZipFile(buf) as zf:
            if "word/document.xml" not in zf.namelist():
                raise UnsupportedFormat("不是有效的 .docx 文件（缺少 word/document.xml）。")
            xml_bytes = zf.read("word/document.xml")
    except zipfile.BadZipFile:
        raise UnsupportedFormat("不是有效的 .docx 文件（ZIP 解析失败）。")

    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for p in root.iter(f"{{{W_NS}}}p"):
        runs = []
        for t in p.iter(f"{{{W_NS}}}t"):
            runs.append(t.text or "")
        # <w:tab/> and <w:br/> produce spacing; keep simple: join run text.
        text = "".join(runs)
        paragraphs.append(text)
    # Drop trailing empty paragraphs for cleaner display, keep internal blanks.
    while paragraphs and paragraphs[-1] == "":
        paragraphs.pop()
    return "\n".join(paragraphs)


# --------------------------------------------------------------------------- #
# minimal multipart/form-data parser (stdlib only) — used by the HTTP upload
# endpoint so we don't need a web framework to accept file uploads.
# --------------------------------------------------------------------------- #
def parse_multipart(body: bytes, boundary: str) -> list:
    """Parse a multipart/form-data body.

    Returns a list of parts, each ``{"name", "filename"(optional), "content_type",
    "data": bytes}``.
    """
    delim = ("--" + boundary).encode("utf-8")
    parts: list = []
    # Split on the delimiter; each segment between boundaries is one part.
    segments = body.split(delim)
    for seg in segments:
        # Boundaries are followed by \r\n; the final boundary ends with --.
        if seg in (b"", b"--", b"--\r\n", b"\r\n"):
            continue
        if not seg.startswith(b"\r\n"):
            continue
        # Strip the leading CRLF and the trailing CRLF before the next boundary.
        seg = seg[2:]
        if seg.endswith(b"\r\n"):
            seg = seg[:-2]
        header_end = seg.find(b"\r\n\r\n")
        if header_end < 0:
            continue
        header_blob = seg[:header_end].decode("utf-8", "replace")
        content = seg[header_end + 4:]
        name = filename = content_type = None
        for line in header_blob.split("\r\n"):
            low = line.lower()
            if low.startswith("content-disposition:"):
                name = _attr(line, "name")
                filename = _attr(line, "filename")
            elif low.startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip()
        parts.append({
            "name": name,
            "filename": filename,
            "content_type": content_type or "",
            "data": content,
        })
    return parts


def _attr(header_line: str, key: str):
    """Extract an unquoted/quoted attribute value from a header line."""
    import re
    m = re.search(rf'{key}="([^"]*)"', header_line)
    if m:
        return m.group(1)
    m = re.search(rf"{key}=([^;]+)", header_line)
    return m.group(1).strip() if m else None
