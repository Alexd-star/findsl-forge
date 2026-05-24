# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "submission_artifacts" / "demo_screenshots"
OUTPUT_DIR = ROOT / "submission_artifacts" / "defense_video"
DEFAULT_OUTPUT = OUTPUT_DIR / "findsl_forge_one_minute_demo.mp4"


@dataclass(frozen=True)
class Segment:
    filename: str
    duration: int
    title: str
    narration: str
    evidence: str


SEGMENTS = [
    Segment(
        "01_nl_to_dsl_overview.png",
        7,
        "1. 中文请求进入受控 DSL",
        "用户先用中文描述选股意图，系统只生成候选 DSL；候选必须通过编译器和参考验证，不能直接越过审计。",
        "NL2DSL validated candidate, verification PASS",
    ),
    Segment(
        "02_positive_sql.png",
        9,
        "2. 确定性编译生成 Doris SQL",
        "同一条请求被编译成可读、可审计的 Doris SQL，页面同步显示 PASS、编译延迟和结果行数。",
        "Doris SQL, stable CTE/window/rank plan, SQL rows",
    ),
    Segment(
        "03_positive_ast.png",
        7,
        "3. AST 证明系统理解表达结构",
        "AST 展示 filter、CONS、indicator、rank 等节点，说明系统不是字符串拼接，而是在结构层处理金融语义。",
        "Standard AST exposed in Web Demo",
    ),
    Segment(
        "04_positive_explain.png",
        8,
        "4. 优化与裁剪过程可解释",
        "Explain 记录编译和优化规则，让日期裁剪、窗口处理、prefix-sum 选择都能被复核。",
        "Structured optimizer explain records",
    ),
    Segment(
        "05_positive_rows.png",
        7,
        "5. 结果经过独立语义校验",
        "生成 SQL 后，系统用 SQL 执行结果和 Pandas reference 对照，确认 key 集合一致。",
        "SQL/reference equivalence, result rows",
    ),
    Segment(
        "06_positive_evidence.png",
        10,
        "6. Doris 规模证据支撑性能结论",
        "5,000,000 行 Doris 证据显示 baseline 与 optimized 行数一致，prefix 路径达到 36.24x 加速。",
        "Doris evidence: row parity, prefix plan, 36.24x speedup",
    ),
    Segment(
        "07_negative_unknown_indicator.png",
        12,
        "7. 错误输入可诊断、可修复",
        "负例不会抛出不可控异常；系统给出稳定诊断码 UNKNOWN_INDICATOR，并提示修复为 indicator(\"close\")。",
        "Expected/actual diagnostic match, repair hints",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the one-minute FinDSL Forge defense video.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output MP4 path.")
    parser.add_argument("--keep-frames", action="store_true", help="Keep generated slide frames.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slide_dir = OUTPUT_DIR / "slides"
    frame_dir = OUTPUT_DIR / "frames"
    slide_dir.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    for old in slide_dir.glob("slide_*.png"):
        old.unlink()
    for old in frame_dir.glob("frame_*.png"):
        old.unlink()

    font_regular, font_bold = load_fonts()
    frame_paths = []
    for index, segment in enumerate(SEGMENTS, 1):
        screenshot = SCREENSHOT_DIR / segment.filename
        if not screenshot.exists():
            raise FileNotFoundError(f"Missing screenshot: {screenshot}")
        frame = compose_frame(index, segment, screenshot, font_regular, font_bold)
        frame_path = slide_dir / f"slide_{index:02d}.png"
        frame.save(frame_path)
        frame_paths.append((frame_path, segment.duration))

    total_seconds = write_frame_sequence(frame_dir, frame_paths)
    build_mp4(frame_dir, args.output)
    if not args.keep_frames:
        shutil.rmtree(slide_dir, ignore_errors=True)
        shutil.rmtree(frame_dir, ignore_errors=True)

    print(f"Wrote {args.output} ({total_seconds} seconds)")


def load_fonts() -> tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
    ]
    regular_path = next((item for item in candidates if item.exists()), None)
    bold_path = next((item for item in bold_candidates if item.exists()), regular_path)
    if regular_path is None:
        return ImageFont.load_default(), ImageFont.load_default()
    return ImageFont.truetype(str(regular_path), 26), ImageFont.truetype(str(bold_path), 34)


def compose_frame(
    index: int,
    segment: Segment,
    screenshot_path: Path,
    font_regular: ImageFont.FreeTypeFont,
    font_bold: ImageFont.FreeTypeFont,
) -> Image.Image:
    width, height = 1280, 720
    canvas = Image.new("RGB", (width, height), "#f6f7f9")
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, width, 68), fill="#ffffff")
    draw.text((34, 18), "FinDSL Forge | 一分钟答辩演示", fill="#0b1f3a", font=font_bold)
    draw.text((1120, 22), f"{index:02d}/{len(SEGMENTS):02d}", fill="#0f766e", font=font_regular)

    screenshot = Image.open(screenshot_path).convert("RGB")
    screenshot.thumbnail((1210, 450), Image.Resampling.LANCZOS)
    shot_x = (width - screenshot.width) // 2
    shot_y = 86
    draw.rounded_rectangle(
        (shot_x - 8, shot_y - 8, shot_x + screenshot.width + 8, shot_y + screenshot.height + 8),
        radius=12,
        fill="#ffffff",
        outline="#d8dee4",
        width=2,
    )
    canvas.paste(screenshot, (shot_x, shot_y))

    band_y = 560
    draw.rectangle((0, band_y, width, height), fill="#101827")
    draw.text((44, band_y + 24), segment.title, fill="#ffffff", font=font_bold)
    y = band_y + 74
    for line in wrap(segment.narration, width=44):
        draw.text((44, y), line, fill="#e5edf5", font=font_regular)
        y += 34
    draw.rounded_rectangle((835, band_y + 31, 1238, band_y + 150), radius=10, fill="#173b37")
    draw.text((858, band_y + 46), "可见证据", fill="#bff3e8", font=font_regular)
    evidence_y = band_y + 82
    for line in wrap(segment.evidence, width=30)[:2]:
        draw.text((858, evidence_y), line, fill="#ffffff", font=font_regular)
        evidence_y += 32
    return canvas


def write_frame_sequence(frame_dir: Path, frame_paths: list[tuple[Path, int]]) -> int:
    frame_index = 0
    for slide_path, duration in frame_paths:
        slide = Image.open(slide_path).convert("RGB")
        for _ in range(duration):
            slide.save(frame_dir / f"frame_{frame_index:03d}.png")
            frame_index += 1
    return frame_index


def build_mp4(frame_dir: Path, output: Path) -> None:
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to build the defense video.")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        "1",
        "-start_number",
        "0",
        "-i",
        str(frame_dir / "frame_%03d.png"),
        "-vf",
        "scale=1280:720,fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-movflags",
        "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
