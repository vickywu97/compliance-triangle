#!/usr/bin/env python3
"""Refresh the vendored Bench KB snapshot bundled in compliance-triangle.

Run this whenever legal-hallucination-bench updates its statutes.jsonl,
laws_index.json, loader.py, or DEPRECATED_LAW_NAMES trap list.

Usage (from compliance-triangle repo root):

    /Users/vickywu/.workbuddy/binaries/python/versions/3.13.12/bin/python3 \
        scripts/sync_kb_from_bench.py [path/to/legal-hallucination-bench]

If no path is given, it looks for a sibling ``legal-hallucination-bench`` repo
or the ``COMPLIANCE_TRIANGLE_BENCH`` environment variable.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path


def find_bench_repo() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    env = os.environ.get("COMPLIANCE_TRIANGLE_BENCH")
    if env:
        return Path(env).resolve()
    sibling = Path(__file__).resolve().parent.parent.parent / "legal-hallucination-bench"
    if sibling.exists():
        return sibling
    raise SystemExit(
        "Could not find legal-hallucination-bench. Pass the path as argument "
        "or set COMPLIANCE_TRIANGLE_BENCH."
    )


def main() -> None:
    bench = find_bench_repo()
    ct_root = Path(__file__).resolve().parent.parent
    vendor_dir = ct_root / "compliance_triangle" / "vendor" / "bench_kb"
    vendor_laws = vendor_dir / "laws"
    vendor_laws.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        (bench / "knowledge_base" / "laws" / "laws_index.json", vendor_laws / "laws_index.json"),
        (bench / "knowledge_base" / "laws" / "statutes.jsonl", vendor_laws / "statutes.jsonl"),
        (bench / "knowledge_base" / "loader.py", vendor_dir / "loader.py"),
    ]
    for src, dst in files_to_copy:
        if not src.exists():
            raise SystemExit(f"Missing source file: {src}")
        shutil.copy2(src, dst)
        print(f"Copied {src} -> {dst}")

    # Patch loader.py to import the vendored extract module instead of benchmark.extract.
    loader_path = vendor_dir / "loader.py"
    content = loader_path.read_text(encoding="utf-8")
    content = content.replace(
        "from benchmark.extract import DEPRECATED_LAW_NAMES",
        "from .extract import DEPRECATED_LAW_NAMES",
    )
    loader_path.write_text(content, encoding="utf-8")
    print(f"Patched {loader_path} import")

    # Refresh the vendored DEPRECATED_LAW_NAMES constant.
    extract_src = bench / "benchmark" / "extract.py"
    extract_dst = vendor_dir / "extract.py"
    text = extract_src.read_text(encoding="utf-8")
    match = re.search(r"DEPRECATED_LAW_NAMES = \{.*?\n\}", text, re.DOTALL)
    if not match:
        raise SystemExit("Could not locate DEPRECATED_LAW_NAMES in benchmark/extract.py")
    constant = match.group(0)
    extract_dst.write_text(
        '"""Vendored subset of benchmark.extract for offline fallback."""\n\n'
        + constant
        + "\n",
        encoding="utf-8",
    )
    print(f"Updated {extract_dst}")

    # Write a small provenance note.
    snapshot_note = vendor_dir / "SNAPSHOT.md"
    snapshot_note.write_text(
        f"""# Vendored Bench KB snapshot

- Source repo: `{bench}`
- Copied on: {os.popen('date -u +%Y-%m-%dT%H:%M:%SZ').read().strip()}
- Files: `laws/laws_index.json`, `laws/statutes.jsonl`, `loader.py`, `extract.py`

This snapshot exists so compliance-triangle can run standalone without the
Bench repo as a sibling. The live Bench KB is always preferred when available;
see `compliance_triangle/kb.py`.
""",
        encoding="utf-8",
    )
    print(f"Wrote {snapshot_note}")


if __name__ == "__main__":
    main()
