#!/usr/bin/env python3
"""自动给合规三角演示录屏加字幕 / 片头 / 片尾。

使用方式（推荐）：
1. 按 docs/SCREENCAST_SCRIPT.md 的 5 个步骤分别录屏（不开麦克风）。
2. 把视频文件命名为 step1.mov、step2.mov、...、step5.mov，
   放到 compliance-triangle/demo/raw/ 目录。
3. 运行：

       python scripts/make_screencast.py

4. 产物：compliance-triangle/demo/screencast_subtitled.mp4

依赖：本脚本会自动找沙箱里的 imageio_ffmpeg 静态二进制，
      字体默认用 /Library/Fonts/Arial Unicode.ttf（CJK 安全）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple


# Default captions per step (derived from docs/SCREENCAST_SCRIPT.md).
# They fit on a single line in the lower-third of the screen.
# NOTE: emojis like 🟢🟡🔴 do NOT render in this ffmpeg build's drawtext,
# so we use plain text equivalents in video captions.
DEFAULT_CAPTIONS = [
    "律师·税务师·专利代理师 → AI 法律产品",
    "合规三角：给 AI 每条法条引注做三层校验",
    "本地零依赖启动 | 5 个含幻觉演示场景",
    "粘贴 LLM 回答 → 运行校验 → 核对官方法条库",
    "输入场景 → 调国产模型生成 → 自动校验",
    "底层 2327 条核验法条 · 32 测试全绿 · 开源",
]

TITLE_TEXT = "合规三角 v1.0.0 演示"
TITLE_SUB = "给 AI 法条引注做三色校验：通过 · 待复核 · 未通过"
END_TEXT = "github.com/vickywu97/compliance-triangle"
END_SUB = "地基仓库 legal-hallucination-bench · 2327 条现行法条"

FONT = "/Library/Fonts/Arial Unicode.ttf"


def _find_ffmpeg() -> str:
    """Prefer imageio_ffmpeg static binary; fallback to PATH."""
    candidate = (
        "/Users/vickywu/.workbuddy/binaries/python/envs/default/lib/python3.13/"
        "site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-x86_64-v7.1"
    )
    if os.path.exists(candidate):
        return candidate
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    raise RuntimeError("未找到 ffmpeg。请先运行：\n"
                       "  /Users/vickywu/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m venv /Users/vickywu/.workbuddy/binaries/python/envs/default\n"
                       "  /Users/vickywu/.workbuddy/binaries/python/envs/default/bin/pip install imageio-ffmpeg")


def _run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run ffmpeg and surface errors."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def _escape_text(s: str) -> str:
    """Escape characters for ffmpeg drawtext text argument."""
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _wrap_text(s: str, max_chars: int = 30) -> str:
    """Insert newlines so each line fits on screen."""
    lines = []
    cur = ""
    for ch in s:
        cur += ch
        if len(cur) >= max_chars:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    return "\\n".join(lines)


def _probe_resolution(ffmpeg: str, path: str) -> Tuple[int, int]:
    """Return (width, height) of a video file using ffmpeg (ffprobe may not be present)."""
    out = subprocess.run(
        [ffmpeg, "-i", path],
        capture_output=True, text=True,
    )
    # ffmpeg prints stream info to stderr even on success
    text = out.stdout + out.stderr
    m = re.search(r"Stream .*?Video:.*?(\d{2,})x(\d{2,})", text)
    if not m:
        raise RuntimeError(f"无法解析视频分辨率: {path}\n{text[:500]}")
    return int(m.group(1)), int(m.group(2))


def _make_title_card(ffmpeg: str, out_path: str, w: int, h: int, *,
                     duration: float = 5.0) -> None:
    """Generate a title card video with centered Chinese text."""
    main = _escape_text(_wrap_text(TITLE_TEXT, max_chars=24))
    sub = _escape_text(_wrap_text(TITLE_SUB, max_chars=34))
    vf = (
        f"drawtext=fontfile={FONT}:fontsize={int(h*0.08)}:fontcolor=white:"
        f"borderw={int(h*0.004)}:x=(w-text_w)/2:y=(h-text_h)/2-30:"
        f"text='{main}',"
        f"drawtext=fontfile={FONT}:fontsize={int(h*0.045)}:fontcolor=#E5E7EB:"
        f"borderw={int(h*0.003)}:x=(w-text_w)/2:y=(h*0.55):text='{sub}'"
    )
    _run([
        ffmpeg, "-y", "-f", "lavfi", "-i",
        f"color=c=#0f172a:s={w}x{h}:d={duration}",
        "-vf", vf, "-pix_fmt", "yuv420p", out_path,
    ])


def _make_end_card(ffmpeg: str, out_path: str, w: int, h: int, *,
                   duration: float = 5.0) -> None:
    """Generate an end card video with repo links."""
    main = _escape_text(_wrap_text(END_TEXT, max_chars=40))
    sub = _escape_text(_wrap_text(END_SUB, max_chars=44))
    vf = (
        f"drawtext=fontfile={FONT}:fontsize={int(h*0.05)}:fontcolor=white:"
        f"borderw={int(h*0.004)}:x=(w-text_w)/2:y=(h-text_h)/2-20:"
        f"text='{main}',"
        f"drawtext=fontfile={FONT}:fontsize={int(h*0.035)}:fontcolor=#94A3B8:"
        f"borderw={int(h*0.003)}:x=(w-text_w)/2:y=(h*0.55):text='{sub}'"
    )
    _run([
        ffmpeg, "-y", "-f", "lavfi", "-i",
        f"color=c=#0f172a:s={w}x{h}:d={duration}",
        "-vf", vf, "-pix_fmt", "yuv420p", out_path,
    ])


def _burn_caption(ffmpeg: str, src: str, out: str, caption: str, w: int, h: int) -> None:
    """Burn one caption into a clip, lower third, centered."""
    text = _escape_text(_wrap_text(caption, max_chars=40))
    # Semi-transparent black box behind text for readability
    vf = (
        f"drawtext=fontfile={FONT}:fontsize={int(h*0.04)}:fontcolor=white:"
        f"borderw={int(h*0.003)}:x=(w-text_w)/2:y=h-text_h-70:"
        f"text='{text}':box=1:boxcolor=black@0.6:"
        f"boxborderw={int(h*0.015)}:line_spacing={int(h*0.012)}"
    )
    _run([ffmpeg, "-y", "-i", src, "-vf", vf, "-c:a", "copy",
          "-pix_fmt", "yuv420p", out])


def _collect_clips(raw_dir: Path) -> List[Path]:
    """Find step1..stepN video files in raw_dir, sorted naturally."""
    exts = {".mov", ".mp4", ".mkv", ".avi"}
    files = [p for p in raw_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    # Try strict stepN pattern first
    step_files = sorted(
        [p for p in files if re.fullmatch(r"step\d+", p.stem, re.I)],
        key=lambda p: int(re.search(r"\d+", p.stem).group()),
    )
    if step_files:
        return step_files
    # Fallback: sort all clips alphabetically
    return sorted(files)


def _load_captions(raw_dir: Path) -> List[str]:
    """Load captions from captions.json if present, else use defaults."""
    cap_file = raw_dir / "captions.json"
    if cap_file.exists():
        return json.loads(cap_file.read_text(encoding="utf-8"))
    return DEFAULT_CAPTIONS


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="给合规三角录屏自动加字幕")
    parser.add_argument(
        "--raw-dir", type=Path,
        default=repo_root / "demo" / "raw",
        help="存放 step1.mov / step2.mov ... 的目录 (default: demo/raw)",
    )
    parser.add_argument(
        "--output", type=Path,
        default=repo_root / "demo" / "screencast_subtitled.mp4",
        help="输出文件路径",
    )
    parser.add_argument(
        "--title-duration", type=float, default=5.0,
        help="片头时长（秒）",
    )
    parser.add_argument(
        "--end-duration", type=float, default=5.0,
        help="片尾时长（秒）",
    )
    args = parser.parse_args()

    ffmpeg = _find_ffmpeg()
    print(f"[make_screencast] ffmpeg: {ffmpeg}")

    if not args.raw_dir.exists():
        print(f"[ERROR] 原始录屏目录不存在: {args.raw_dir}\n"
              f"        请先按 docs/SCREENCAST_SCRIPT.md 录屏，并把 step1.mov/step2.mov/... 放进去。")
        return 1

    clips = _collect_clips(args.raw_dir)
    if not clips:
        print(f"[ERROR] {args.raw_dir} 下没有 .mov/.mp4 文件。")
        return 1

    captions = _load_captions(args.raw_dir)
    if len(captions) < len(clips):
        print(f"[WARN]  片段有 {len(clips)} 个，但字幕只有 {len(captions)} 条，"
              f"多出的片段会用默认说明。")
        captions = captions + [f"步骤 {i+1}" for i in range(len(clips) - len(captions))]

    # Use the first clip's resolution for all generated cards/overlays
    w, h = _probe_resolution(ffmpeg, str(clips[0]))
    print(f"[make_screencast] 输出分辨率: {w}x{h} | 片段数: {len(clips)}")

    with tempfile.TemporaryDirectory(prefix="ct_screencast_") as tmp:
        tmp = Path(tmp)
        segments: List[Path] = []

        # 1. Title card
        title_path = tmp / "title.mp4"
        _make_title_card(ffmpeg, str(title_path), w, h, duration=args.title_duration)
        segments.append(title_path)

        # 2. Captioned clips
        for idx, clip in enumerate(clips, start=1):
            out = tmp / f"step{idx}_sub.mp4"
            cap = captions[idx - 1]
            print(f"[make_screencast] 加字幕 step{idx}: {clip.name}")
            _burn_caption(ffmpeg, str(clip), str(out), cap, w, h)
            segments.append(out)

        # 3. End card
        end_path = tmp / "end.mp4"
        _make_end_card(ffmpeg, str(end_path), w, h, duration=args.end_duration)
        segments.append(end_path)

        # 4. Concatenate with concat demuxer
        concat_list = tmp / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{seg.resolve()}'" for seg in segments),
            encoding="utf-8",
        )
        print(f"[make_screencast] 合成最终视频 -> {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        _run([
            ffmpeg, "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy",
            "-movflags", "+faststart", str(args.output),
        ])

    print(f"[make_screencast] 完成: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
