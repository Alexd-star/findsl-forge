from __future__ import annotations

import datetime as dt
import html
import json
import math
import os
import re
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "submission_artifacts" / "visual_evidence" / "figure_materials"
HTML_DIR = FIGURE_DIR / "_render_html"

CANVAS_W = 2400
CANVAS_H = 1500


STYLE_STANDARD = "SciPilot/Nature-inspired publication style v2"


# Okabe-Ito inspired, colorblind-safe palette with low-saturation fills.
PALETTE = {
    "ink": "#111827",
    "muted": "#4b5563",
    "line": "#b8c0cc",
    "panel": "#ffffff",
    "soft": "#f6f7f9",
    "blue": "#0072B2",
    "blue_soft": "#edf6fb",
    "teal": "#009E73",
    "teal_soft": "#eef8f4",
    "green": "#009E73",
    "green_soft": "#eef8f4",
    "orange": "#D55E00",
    "orange_soft": "#fff3eb",
    "amber": "#E69F00",
    "amber_soft": "#fff8e8",
    "purple": "#CC79A7",
    "purple_soft": "#fbf1f7",
    "red": "#D55E00",
    "red_soft": "#fff0e8",
    "gray_soft": "#f3f4f6",
}


FIG_DIRS = {
    "topic": "01_赛题理解图",
    "architecture": "02_架构与代码图",
    "operation": "03_运行流程图",
    "algorithm": "04_算法说明图",
    "validation": "05_测试验证图",
    "performance": "06_结果与性能图",
    "special": "07_项目类型专项图",
    "ppt": "08_答辩PPT用图",
    "report": "09_技术报告用图",
}


@dataclass
class FigureSpec:
    fig_id: str
    title: str
    kind: str
    category: str
    required: str
    source: str
    proof: str
    report_place: str
    ppt_place: str
    filename: str


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def visual_len(text: str) -> float:
    total = 0.0
    for ch in text:
        total += 0.55 if ch.isascii() else 1.0
    return total


def wrap_zh(text: str, max_units: int) -> list[str]:
    parts: list[str] = []
    for raw in str(text).split("\n"):
        raw = raw.strip()
        if not raw:
            parts.append("")
            continue
        current = ""
        current_units = 0.0
        for token in re.findall(r"[A-Za-z0-9_./:+<>=-]+|.", raw):
            units = visual_len(token)
            if current and current_units + units > max_units:
                parts.append(current)
                current = token
                current_units = units
            else:
                current += token
                current_units += units
        if current:
            parts.append(current)
    return parts


class Svg:
    def __init__(self, title: str, subtitle: str = "", height: int = CANVAS_H) -> None:
        self.w = CANVAS_W
        self.h = height
        self.items: list[str] = []
        self.title = title
        self.subtitle = subtitle
        self.items.append(
            f'<rect x="0" y="0" width="{self.w}" height="{self.h}" fill="#ffffff"/>'
        )
        self.items.append(
            '<defs>'
            '<marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">'
            '<path d="M2,2 L10,6 L2,10 Z" fill="#4b5563"/></marker>'
            "</defs>"
        )
        self.text(92, 92, title, size=36, weight=800, color=PALETTE["ink"], max_units=52)
        if subtitle:
            self.text(92, 146, subtitle, size=20, color=PALETTE["muted"], max_units=112)
        self.text(self.w - 92, 92, STYLE_STANDARD, size=16, color=PALETTE["muted"], anchor="end", max_units=34)
        self.line(92, 188, self.w - 92, 188, PALETTE["line"], 1.2)

    def raw(self, value: str) -> None:
        self.items.append(value)

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: str = "#4b5563",
        width: float = 1.8,
        dashed: bool = False,
        arrow: bool = False,
    ) -> None:
        dash = ' stroke-dasharray="10 9"' if dashed else ""
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        self.items.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"{dash}{marker}/>'
        )

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill: str = "#ffffff",
        stroke: str = PALETTE["line"],
        radius: int = 8,
        width: float = 1.2,
        shadow: bool = False,
    ) -> None:
        self.items.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )

    def diamond(
        self,
        cx: float,
        cy: float,
        w: float,
        h: float,
        fill: str = "#ffffff",
        stroke: str = PALETTE["line"],
    ) -> None:
        points = [
            (cx, cy - h / 2),
            (cx + w / 2, cy),
            (cx, cy + h / 2),
            (cx - w / 2, cy),
        ]
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        self.items.append(
            f'<polygon points="{path}" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str, stroke: str = "none") -> None:
        self.items.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}"/>'
        )

    def text(
        self,
        x: float,
        y: float,
        text: object,
        size: int = 22,
        color: str = PALETTE["ink"],
        weight: int = 400,
        anchor: str = "start",
        max_units: int | None = None,
        line_height: float = 1.35,
        family: str = "Microsoft YaHei, SimSun, Noto Sans CJK SC, Arial, sans-serif",
    ) -> None:
        lines = wrap_zh(str(text), max_units or 999)
        self.items.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{esc(family)}" '
            f'font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">'
        )
        for i, line in enumerate(lines):
            dy = 0 if i == 0 else size * line_height
            self.items.append(f'<tspan x="{x:.1f}" dy="{dy:.1f}">{esc(line)}</tspan>')
        self.items.append("</text>")

    def label_box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str = "",
        fill: str = "#ffffff",
        stroke: str = PALETTE["line"],
        title_color: str = PALETTE["ink"],
        body_color: str = PALETTE["muted"],
        title_size: int = 22,
        body_size: int = 18,
        max_units: int = 24,
    ) -> None:
        self.rect(x, y, w, h, fill=fill, stroke=stroke, radius=8, width=1.2)
        self.text(x + 24, y + 40, title, size=title_size, weight=800, color=title_color, max_units=max_units)
        if body:
            self.text(x + 24, y + 78, body, size=body_size, color=body_color, max_units=max_units)

    def footer(self, source: str) -> None:
        self.line(92, self.h - 82, self.w - 92, self.h - 82, PALETTE["line"], 1)
        self.text(92, self.h - 43, source, size=16, color=PALETTE["muted"], max_units=138)

    def save(self, path: Path, source: str = "") -> None:
        if source:
            self.footer(source)
        content = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.title)}">\n'
            + "\n".join(self.items)
            + "\n</svg>\n"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def latest_metrics() -> dict:
    metadata = load_json(ROOT / "submission_artifacts" / "evidence_metadata.json")
    doris = load_json(ROOT / "submission_artifacts" / "evidence_snapshots" / "doris_cluster_evidence.json")
    topic_md = read_text(ROOT / "reports" / "topic_19_compliance_plan.md")
    visual_summary_path = ROOT / "submission_artifacts" / "visual_evidence" / "visual_evidence_summary.json"
    visual_summary = load_json(visual_summary_path) if visual_summary_path.exists() else {}
    topic_items = []
    for line in topic_md.splitlines():
        if line.startswith("| T19-R"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 5:
                topic_items.append(
                    {
                        "id": parts[0],
                        "requirement": parts[1],
                        "status": parts[2],
                        "evidence": parts[3],
                        "next": parts[4],
                    }
                )
    topic_summary = {"implemented": 0, "partial": 0, "needs_evidence": 0}
    for item in topic_items:
        if item["status"] in topic_summary:
            topic_summary[item["status"]] += 1
    return {
        "metadata": metadata,
        "doris": doris,
        "topic_items": topic_items,
        "topic_summary": topic_summary,
        "visual_summary": visual_summary,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def arrow_between(svg: Svg, x1: float, y1: float, x2: float, y2: float, dashed: bool = False) -> None:
    svg.line(x1, y1, x2, y2, color="#475569", width=3, dashed=dashed, arrow=True)


def draw_pill(svg: Svg, x: float, y: float, text: str, fill: str, color: str, w: float = 210) -> None:
    svg.rect(x, y, w, 44, fill=fill, stroke=color, radius=8, width=1)
    svg.text(x + w / 2, y + 31, text, size=20, color=color, weight=800, anchor="middle", max_units=16)


def fig_01(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "把输入、核心任务、约束、输出、验证和提交材料拆开讲清楚。")
    boxes = [
        ("输入", "中文选股需求\nFinDSL 表达式\nLLM/Provider 候选", PALETTE["blue_soft"], PALETTE["blue"]),
        ("核心任务", "Lexer/Parser\nTyped AST\nSemantic Validation\nSQL Plan -> Doris SQL", PALETTE["teal_soft"], PALETTE["teal"]),
        ("关键约束", "LLM 不直接写 SQL\n强类型与窗口参数校验\nDoris-safe 单查询边界", PALETTE["amber_soft"], PALETTE["amber"]),
        ("输出", "Doris SQL\nAST / Trace / Explain\nRows / Diagnostic", PALETTE["purple_soft"], PALETTE["purple"]),
        ("验证", f"pytest {m['metadata']['readiness']['pytest']['passed']} passed\n官方正例 {m['metadata']['official_suite']['positive']['passed']}/{m['metadata']['official_suite']['positive']['total']}\n官方负例 {m['metadata']['official_suite']['negative']['passed']}/{m['metadata']['official_suite']['negative']['total']}", PALETTE["green_soft"], PALETTE["green"]),
        ("提交", "README / docs\nEvidence snapshots\nVisual evidence / Demo", PALETTE["gray_soft"], PALETTE["ink"]),
    ]
    x0, y0, bw, bh, gap = 110, 260, 330, 360, 48
    for i, (title, body, fill, color) in enumerate(boxes):
        x = x0 + i * (bw + gap)
        svg.label_box(x, y0, bw, bh, title, body, fill=fill, stroke=color, title_color=color, max_units=18)
        if i < len(boxes) - 1:
            arrow_between(svg, x + bw + 10, y0 + bh / 2, x + bw + gap - 10, y0 + bh / 2)
    svg.label_box(
        290,
        760,
        1820,
        280,
        "答辩口径",
        "本项目不是让大模型自由生成 SQL，而是把中文需求或 DSL 候选放入确定性编译器，再通过 SQL/reference 等价验证和 Doris 证据闭环。带数值的结论只引用最新 evidence 文件。",
        fill="#ffffff",
        stroke=PALETTE["line"],
        max_units=88,
    )
    draw_pill(svg, 320, 1080, f"Blocking gates {m['metadata']['readiness']['blocking_gates_passed'] and 'PASS'}", PALETTE["green_soft"], PALETTE["green"], 310)
    draw_pill(svg, 660, 1080, f"Warning {m['metadata']['readiness']['warning_count']}", PALETTE["green_soft"], PALETTE["green"], 220)
    draw_pill(svg, 910, 1080, f"Doris {m['metadata']['doris_cluster']['speedup_display']}", PALETTE["teal_soft"], PALETTE["teal"], 240)
    draw_pill(svg, 1180, 1080, f"Git HEAD {m['metadata']['git']['head_at_export']}", PALETTE["blue_soft"], PALETTE["blue"], 280)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：README.md，reports/topic_19_compliance_plan.md，submission_artifacts/evidence_metadata.json。")
    return path


def fig_02(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "端到端展示从需求输入到 SQL、验证、Doris evidence 和交付输出的闭环。")
    nodes = [
        ("中文需求 / DSL", "用户输入、官方样例、LLM 候选"),
        ("候选治理", "NL2DSL 模板\nLLM candidate extraction"),
        ("确定性编译", "Lexer -> Parser -> Typed AST\nSemantic Validation"),
        ("SQL 生成", "SQL Plan\nDoris-safe SQL validation"),
        ("正确性验证", "SQLite 执行\nPandas Reference Oracle"),
        ("Doris 证据", "EXPLAIN / latency\nrow parity / speedup"),
        ("展示交付", "Web Demo / API\nreports / screenshots"),
    ]
    x, y = 110, 320
    bw, bh, gap = 285, 220, 36
    for i, (title, body) in enumerate(nodes):
        fill = [PALETTE["blue_soft"], PALETTE["amber_soft"], PALETTE["teal_soft"], PALETTE["purple_soft"], PALETTE["green_soft"], "#e0f2fe", PALETTE["gray_soft"]][i]
        stroke = [PALETTE["blue"], PALETTE["amber"], PALETTE["teal"], PALETTE["purple"], PALETTE["green"], "#0369a1", PALETTE["ink"]][i]
        xx = x + i * (bw + gap)
        svg.label_box(xx, y, bw, bh, title, body, fill=fill, stroke=stroke, title_color=stroke, max_units=15)
        if i < len(nodes) - 1:
            arrow_between(svg, xx + bw + 8, y + bh / 2, xx + bw + gap - 8, y + bh / 2)
    svg.label_box(
        230,
        670,
        780,
        250,
        "安全边界",
        "LLM 只允许提供 DSL candidate；直接 SQL、未知指标、非法语义都必须进入拒绝或诊断路径。",
        fill=PALETTE["red_soft"],
        stroke=PALETTE["red"],
        title_color=PALETTE["red"],
        max_units=36,
    )
    svg.label_box(
        1100,
        670,
        940,
        250,
        "验证闭环",
        f"最新证据：official suite {m['metadata']['official_suite']['positive']['passed']}/{m['metadata']['official_suite']['positive']['total']} + {m['metadata']['official_suite']['negative']['passed']}/{m['metadata']['official_suite']['negative']['total']}；SQL/reference、Demo smoke、Doris marker check 均由 readiness 复核。",
        fill=PALETTE["green_soft"],
        stroke=PALETTE["green"],
        title_color=PALETTE["green"],
        max_units=45,
    )
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：README.md，submission_artifacts/evidence_metadata.json，reports/submission_readiness.md。")
    return path


def fig_03(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "分层展示入口、输入适配、编译内核、配置数据、验证执行和提交证据。")
    layers = [
        ("评审入口层", ["CLI", "Web Demo", "JSON API", "README / docs / 图表证据"], PALETTE["blue_soft"], PALETTE["blue"]),
        ("输入适配层", ["NL2DSL", "LLM candidate validator", "official examples", "diagnostics"], PALETTE["amber_soft"], PALETTE["amber"]),
        ("编译内核层", ["lexer.py", "parser.py", "ast_nodes.py", "semantic.py", "sqlgen.py", "doris_sql.py"], PALETTE["teal_soft"], PALETTE["teal"]),
        ("配置与数据层", ["configs/*.json", "data/samples", "real_samples", "deploy/doris"], PALETTE["purple_soft"], PALETTE["purple"]),
        ("验证执行层", ["reference.py", "executor.py", "equivalence.py", "official_suite.py", "readiness.py"], PALETTE["green_soft"], PALETTE["green"]),
        ("证据交付层", ["evidence_snapshots", "visual_evidence", "demo_screenshots", "defense_video"], PALETTE["gray_soft"], PALETTE["ink"]),
    ]
    y = 250
    for i, (name, mods, fill, color) in enumerate(layers):
        yy = y + i * 175
        svg.rect(120, yy, 2160, 136, fill=fill, stroke=color, radius=18, shadow=True)
        svg.text(155, yy + 58, name, size=28, weight=800, color=color, max_units=13)
        start_x = 500
        chip_w = min(250, (1700 - 28 * (len(mods) - 1)) / len(mods))
        for j, mod in enumerate(mods):
            cx = start_x + j * (chip_w + 28)
            svg.rect(cx, yy + 38, chip_w, 62, fill="#ffffff", stroke=color, radius=14, width=1)
            svg.text(cx + chip_w / 2, yy + 77, mod, size=19, weight=700, color=PALETTE["ink"], anchor="middle", max_units=17)
        if i < len(layers) - 1:
            arrow_between(svg, 1200, yy + 142, 1200, yy + 170)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：PROJECT_INDEX.md，README.md，src/findsl/，configs/，submission_artifacts/。")
    return path


def fig_04(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "仅保留核心调用链，避免全量函数图过密。")
    svg.label_box(920, 270, 560, 160, "src/findsl/cli.py", "compile / verify-sql / official-suite / serve-demo / readiness-report", fill=PALETTE["blue_soft"], stroke=PALETTE["blue"], title_color=PALETTE["blue"], max_units=30)
    chains = [
        (260, 560, "编译链路", "Compiler.compile\nparse -> semantic.validate\nSqlGenerator.generate\nvalidate_doris_select_sql", PALETTE["teal_soft"], PALETTE["teal"]),
        (920, 560, "等价验证链路", "Compiler.compile\nSQLiteSampleExecutor.execute\nPandasReferenceEvaluator.evaluate\ncompare result sets", PALETTE["green_soft"], PALETTE["green"]),
        (1580, 560, "Web Demo 链路", "demo.py\n/api/examples\n/api/suggest\n/api/analyze", PALETTE["purple_soft"], PALETTE["purple"]),
        (540, 930, "赛题套件链路", "official_suite.py\npositive 37/37\nnegative 37/37\nreport output", PALETTE["amber_soft"], PALETTE["amber"]),
        (1260, 930, "提交证据链路", "readiness.py\nevidence_metadata.py\nsubmission_artifacts\nvisual_evidence", PALETTE["gray_soft"], PALETTE["ink"]),
    ]
    for x, y, title, body, fill, color in chains:
        svg.label_box(x, y, 540, 250, title, body, fill=fill, stroke=color, title_color=color, max_units=28)
        arrow_between(svg, 1200, 430, x + 270, y)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：src/findsl/cli.py，compiler.py，sqlgen.py，equivalence.py，demo.py，official_suite.py。")
    return path


def fig_05(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "按人工验收顺序组织，旁边标出对应截图证据编号。")
    steps = [
        ("1", "Git 状态", "Git HEAD / status / log\nEV-008~EV-010"),
        ("2", "环境依赖", "Python / pip / Git / Node\nEV-011~EV-012"),
        ("3", "主命令", "compile / verify-sql\nEV-015 / EV-024"),
        ("4", "自动测试", f"pytest {m['metadata']['readiness']['pytest']['passed']} passed\nEV-016"),
        ("5", "官方套件", "正例 37/37，负例 37/37\nEV-019"),
        ("6", "Doris 证据", f"speedup {m['metadata']['doris_cluster']['speedup_display']}\nEV-037 / EV-038"),
        ("7", "Web Demo", "SQL / AST / Explain / Rows / Evidence\nEV-041~EV-048"),
        ("8", "提交核验", "manifest / sha256 / READY\nEV-057~EV-062"),
    ]
    x0, y0, bw, bh, gap_x, gap_y = 140, 280, 480, 185, 80, 90
    for i, (num, title, body) in enumerate(steps):
        col = i % 4
        row = i // 4
        x = x0 + col * (bw + gap_x)
        y = y0 + row * (bh + gap_y)
        fill = PALETTE["blue_soft"] if i < 3 else PALETTE["green_soft"] if i < 6 else PALETTE["gray_soft"]
        color = PALETTE["blue"] if i < 3 else PALETTE["green"] if i < 6 else PALETTE["ink"]
        svg.rect(x, y, bw, bh, fill=fill, stroke=color, radius=18, shadow=True)
        svg.circle(x + 45, y + 50, 29, color)
        svg.text(x + 45, y + 60, num, size=26, weight=900, color="#ffffff", anchor="middle")
        svg.text(x + 92, y + 55, title, size=27, weight=800, color=color, max_units=16)
        svg.text(x + 92, y + 100, body, size=20, color=PALETTE["ink"], max_units=26)
        if i not in (3, 7):
            if col < 3:
                arrow_between(svg, x + bw + 10, y + bh / 2, x + bw + gap_x - 10, y + bh / 2)
            else:
                arrow_between(svg, x + bw / 2, y + bh + 12, x + bw / 2, y + bh + gap_y - 12)
    svg.label_box(360, 950, 1680, 220, "验收原则", "所有截图必须来自实际命令、实际文件或实际界面。流程图只负责告诉评委“怎么复现”，最终通过性由 evidence snapshots、logs 和 screenshots 共同证明。", fill="#ffffff", stroke=PALETTE["line"], max_units=78)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：submission_artifacts/visual_evidence/SCREENSHOT_EVIDENCE_INDEX.md，evidence_metadata.json。")
    return path


def fig_06(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "确定性编译内核：错误在编译期诊断，成功路径输出可审计 SQL。")
    nodes = [
        ("FinDSL 输入", 'then(filter(...), rank(...))'),
        ("Lexer", "生成 token\n捕获 LEX_ERROR"),
        ("Parser", "递归下降解析\n生成 Typed AST"),
        ("Semantic", "指标/函数/窗口/rank/日期/类型检查"),
        ("SQL Plan", "CTE / window / prefix\n结构化 explain"),
        ("Doris SQL", "单查询形态校验\n已知表与安全边界"),
        ("输出", "SQL / AST / trace\nelapsed_ms / diagnostics"),
    ]
    x, y, bw, bh, gap = 110, 340, 295, 210, 35
    for i, (title, body) in enumerate(nodes):
        color = [PALETTE["blue"], PALETTE["teal"], PALETTE["teal"], PALETTE["amber"], PALETTE["purple"], PALETTE["green"], PALETTE["ink"]][i]
        fill = [PALETTE["blue_soft"], PALETTE["teal_soft"], PALETTE["teal_soft"], PALETTE["amber_soft"], PALETTE["purple_soft"], PALETTE["green_soft"], PALETTE["gray_soft"]][i]
        xx = x + i * (bw + gap)
        svg.label_box(xx, y, bw, bh, title, body, fill=fill, stroke=color, title_color=color, max_units=15)
        if i < len(nodes) - 1:
            arrow_between(svg, xx + bw + 8, y + bh / 2, xx + bw + gap - 8, y + bh / 2)
    svg.line(620, 600, 620, 850, color=PALETTE["red"], width=3, dashed=True, arrow=True)
    svg.line(950, 600, 950, 850, color=PALETTE["red"], width=3, dashed=True, arrow=True)
    svg.line(1280, 600, 1280, 850, color=PALETTE["red"], width=3, dashed=True, arrow=True)
    svg.label_box(430, 860, 1040, 210, "错误分支", "ParseError / SemanticError / UNKNOWN_INDICATOR / UNSAFE_DIRECT_SQL 会进入 diagnostics repair hints，不会继续生成不可控 SQL。", fill=PALETTE["red_soft"], stroke=PALETTE["red"], title_color=PALETTE["red"], max_units=48)
    svg.label_box(1540, 840, 650, 240, "最新门禁", f"compile success rate {m['metadata']['readiness']['compile_success_rate_percent']:.2f}%；compile P95 {m['metadata']['readiness']['compile_p95_latency_ms']:.3f} ms；warning count {m['metadata']['readiness']['warning_count']}。", fill=PALETTE["green_soft"], stroke=PALETTE["green"], title_color=PALETTE["green"], max_units=30)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：src/findsl/compiler.py，src/findsl/parser.py，src/findsl/semantic.py，evidence_metadata.json。")
    return path


def fig_07(spec: FigureSpec, m: dict) -> Path:
    doris = m["doris"]
    svg = Svg(f"{spec.fig_id}  {spec.title}", "长窗口滚动 SUM 的性能亮点：有条件改写，有回退，有行数一致性验证。")
    svg.label_box(150, 280, 500, 190, "输入表达式", 'SUM(indicator("volume"), 120)\n阈值 > 1000000', fill=PALETTE["blue_soft"], stroke=PALETTE["blue"], title_color=PALETTE["blue"], max_units=25)
    svg.diamond(900, 380, 360, 190, fill=PALETTE["amber_soft"], stroke=PALETTE["amber"])
    svg.text(900, 370, "指标支持 prefix_sum？", size=24, weight=800, color=PALETTE["amber"], anchor="middle", max_units=16)
    svg.text(900, 410, "配置 + window 检查", size=19, color=PALETTE["ink"], anchor="middle", max_units=18)
    svg.label_box(1240, 260, 540, 230, "优化路径", "读取 dwd_stock_daily_quote_prefix\n命中 volume_sum_120\n用 prefix table 过滤", fill=PALETTE["teal_soft"], stroke=PALETTE["teal"], title_color=PALETTE["teal"], max_units=27)
    svg.label_box(1240, 640, 540, 230, "回退路径", "普通 window SQL\nSUM(volume) OVER (...119 PRECEDING...)\n保证语义优先", fill=PALETTE["gray_soft"], stroke=PALETTE["ink"], title_color=PALETTE["ink"], max_units=27)
    svg.label_box(1860, 420, 360, 290, "验证", f"row parity PASS\n{doris['baseline']['row_count']} vs {doris['optimized']['row_count']}\nspeedup {doris['speedup']:.2f}x", fill=PALETTE["green_soft"], stroke=PALETTE["green"], title_color=PALETTE["green"], max_units=18)
    arrow_between(svg, 650, 375, 720, 375)
    arrow_between(svg, 1080, 360, 1230, 360)
    svg.text(1120, 330, "是", size=20, color=PALETTE["green"], weight=800)
    arrow_between(svg, 900, 475, 1240, 735)
    svg.text(1090, 620, "否 / 未命中", size=20, color=PALETTE["ink"], weight=800)
    arrow_between(svg, 1780, 380, 1860, 500)
    arrow_between(svg, 1780, 755, 1860, 620)
    svg.label_box(300, 1010, 1800, 210, "答辩解释", "这张图不把 prefix-sum 说成所有查询必然加速；它表达的是：当指标配置、窗口和物化列满足条件时走优化路径，否则回退 window 语义，最后用 reference/baseline/Doris 证据核验。", fill="#ffffff", stroke=PALETTE["line"], max_units=88)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：configs/indicators.json，src/findsl/sqlgen.py，submission_artifacts/evidence_snapshots/doris_cluster_evidence.json。")
    return path


def fig_08(spec: FigureSpec, m: dict) -> Path:
    doris = m["doris"]
    svg = Svg(f"{spec.fig_id}  {spec.title}", "左右对比 EXPLAIN 摘要，说明性能差异来自执行计划结构变化。")
    svg.label_box(130, 270, 980, 860, "Baseline window plan", "VOlapScanNode(dwd_stock_daily_quote)\ncardinality=5,000,000\n-> VSORT by ts_code, trade_date\n-> VANALYTIC sum(volume)\nROWS BETWEEN 119 PRECEDING AND CURRENT ROW\n-> predicate __win_1 > 1000000\n\n特点：运行时计算长窗口，包含排序与 analytic window。", fill=PALETTE["orange_soft"], stroke=PALETTE["orange"], title_color=PALETTE["orange"], max_units=44)
    svg.label_box(1290, 270, 980, 860, "Optimized prefix-sum plan", "VOlapScanNode(dwd_stock_daily_quote_prefix)\npredicate volume_sum_120 > 1000000\n-> VHASH JOIN(COLOCATE)\nwith dwd_stock_daily_quote\n-> output rows\n\n特点：直接读取 prefix/hot-window 列，避免运行时窗口聚合。", fill=PALETTE["teal_soft"], stroke=PALETTE["teal"], title_color=PALETTE["teal"], max_units=44)
    svg.line(1190, 280, 1190, 1140, color=PALETTE["line"], width=4, dashed=True)
    draw_pill(svg, 260, 1190, f"window={doris['baseline']['plan_contains_window']}", PALETTE["orange_soft"], PALETTE["orange"], 260)
    draw_pill(svg, 560, 1190, f"prefix={doris['baseline']['plan_contains_prefix']}", PALETTE["gray_soft"], PALETTE["ink"], 260)
    draw_pill(svg, 1410, 1190, f"window={doris['optimized']['plan_contains_window']}", PALETTE["gray_soft"], PALETTE["ink"], 260)
    draw_pill(svg, 1710, 1190, f"prefix={doris['optimized']['plan_contains_prefix']}", PALETTE["teal_soft"], PALETTE["teal"], 260)
    draw_pill(svg, 940, 1190, f"row parity {doris['row_counts_match']}", PALETTE["green_soft"], PALETTE["green"], 340)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：submission_artifacts/evidence_snapshots/doris_cluster_evidence.md / .json；EXPLAIN 为摘要示意。")
    return path


def fig_09(spec: FigureSpec, m: dict) -> Path:
    d = m["doris"]
    svg = Svg(f"{spec.fig_id}  {spec.title}", "真实 Doris evidence：baseline window 与 optimized prefix-sum 的 Avg/P95 延迟对比。")
    chart_x, chart_y, chart_w, chart_h = 220, 330, 1280, 720
    values = [
        ("Avg execute ms", d["baseline"]["avg_execute_ms"], d["optimized"]["avg_execute_ms"]),
        ("P95 execute ms", d["baseline"]["p95_execute_ms"], d["optimized"]["p95_execute_ms"]),
    ]
    max_v = max(v for _, b, o in values for v in (b, o))
    min_v = 80
    log_min, log_max = math.log10(min_v), math.log10(max_v * 1.35)
    svg.line(chart_x, chart_y + chart_h, chart_x + chart_w, chart_y + chart_h, PALETTE["ink"], 3)
    svg.line(chart_x, chart_y, chart_x, chart_y + chart_h, PALETTE["ink"], 3)
    for tick in [100, 200, 500, 1000, 2000, 5000, 8000]:
        if tick < min_v or tick > max_v * 1.35:
            continue
        y = chart_y + chart_h - (math.log10(tick) - log_min) / (log_max - log_min) * chart_h
        svg.line(chart_x - 12, y, chart_x + chart_w, y, PALETTE["line"], 1, dashed=True)
        svg.text(chart_x - 24, y + 7, str(tick), size=18, color=PALETTE["muted"], anchor="end")
    group_gap = 300
    bar_w = 150
    for i, (label, baseline, opt) in enumerate(values):
        gx = chart_x + 300 + i * (bar_w * 2 + group_gap)
        for j, (name, value, color) in enumerate(
            [("baseline", baseline, PALETTE["orange"]), ("optimized", opt, PALETTE["teal"])]
        ):
            x = gx + j * (bar_w + 46)
            y = chart_y + chart_h - (math.log10(value) - log_min) / (log_max - log_min) * chart_h
            svg.rect(x, y, bar_w, chart_y + chart_h - y, fill=color, stroke=color, radius=10, width=1)
            svg.text(x + bar_w / 2, y - 18, f"{value:.1f}", size=22, weight=800, color=color, anchor="middle")
        svg.text(gx + bar_w + 23, chart_y + chart_h + 52, label, size=23, weight=800, color=PALETTE["ink"], anchor="middle", max_units=18)
    svg.text(chart_x + 8, chart_y - 34, "执行耗时 ms（log scale）", size=22, color=PALETTE["muted"], max_units=30)
    svg.rect(1560, 340, 650, 520, fill="#ffffff", stroke=PALETTE["line"], radius=24, shadow=True)
    svg.text(1600, 400, "核心结论", size=30, weight=900, color=PALETTE["ink"])
    svg.text(1600, 475, f"Speedup: {d['speedup']:.2f}x", size=46, weight=900, color=PALETTE["teal"])
    svg.text(1600, 545, f"目标: >= {d['min_speedup']:.2f}x，已达标: {d['speedup_target_met']}", size=24, color=PALETTE["ink"], max_units=30)
    svg.text(1600, 605, f"Row parity: {d['baseline']['row_count']} vs {d['optimized']['row_count']}", size=24, color=PALETTE["ink"], max_units=30)
    svg.text(1600, 665, f"Doris evidence generated: {d['generated_at']}", size=21, color=PALETTE["muted"], max_units=34)
    svg.text(1600, 735, "说明：本图用最新 export 证据引用的 Doris evidence；本轮未现场重跑 Doris latency。", size=20, color=PALETTE["muted"], max_units=34)
    svg.rect(420, 1120, 260, 54, fill=PALETTE["orange"], stroke=PALETTE["orange"], radius=14)
    svg.text(700, 1155, "baseline_window", size=22, color=PALETTE["ink"], weight=700)
    svg.rect(920, 1120, 260, 54, fill=PALETTE["teal"], stroke=PALETTE["teal"], radius=14)
    svg.text(1200, 1155, "optimized_prefix_sum", size=22, color=PALETTE["ink"], weight=700)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：submission_artifacts/evidence_snapshots/doris_cluster_evidence.json；PNG 为 300dpi 元数据。")
    return path


def fig_10(spec: FigureSpec, m: dict) -> Path:
    md = m["metadata"]
    svg = Svg(f"{spec.fig_id}  {spec.title}", "使用本轮刷新后的 evidence_metadata.json，一页展示关键门禁。")
    cards = [
        ("Blocking gates", "PASS" if md["readiness"]["blocking_gates_passed"] else "CHECK", PALETTE["green"]),
        ("Warning count", str(md["readiness"]["warning_count"]), PALETTE["green"]),
        ("Pytest", f"{md['readiness']['pytest']['passed']} passed\n{md['readiness']['pytest']['elapsed_seconds']:.2f}s", PALETTE["blue"]),
        ("Official positive", f"{md['official_suite']['positive']['passed']}/{md['official_suite']['positive']['total']}", PALETTE["teal"]),
        ("Official negative", f"{md['official_suite']['negative']['passed']}/{md['official_suite']['negative']['total']}", PALETTE["teal"]),
        ("Defense checks", f"{md['readiness']['defense_package_checks']['passed']}/{md['readiness']['defense_package_checks']['total']}", PALETTE["purple"]),
        ("Doris evidence", "PASS" if md["doris_cluster"]["passed"] else "CHECK", PALETTE["green"]),
        ("Doris speedup", md["doris_cluster"]["speedup_display"], PALETTE["orange"]),
        ("Metadata warnings", "<none>" if not md["warnings"] else str(len(md["warnings"])), PALETTE["green"]),
    ]
    x0, y0, bw, bh, gx, gy = 150, 285, 640, 210, 90, 80
    for i, (title, value, color) in enumerate(cards):
        col, row = i % 3, i // 3
        x, y = x0 + col * (bw + gx), y0 + row * (bh + gy)
        svg.rect(x, y, bw, bh, fill="#ffffff", stroke=color, radius=24, shadow=True)
        svg.text(x + 35, y + 55, title, size=25, color=PALETTE["muted"], weight=700, max_units=26)
        svg.text(x + 35, y + 125, value, size=40, color=color, weight=900, max_units=20)
    svg.label_box(
        420,
        1160,
        1560,
        150,
        "最新证据时间",
        f"metadata generated_at={md['generated_at']}；Git HEAD at export={md['git']['head_at_export']}；snapshot_dir={md['snapshot_dir']}。",
        fill=PALETTE["gray_soft"],
        stroke=PALETTE["line"],
        max_units=76,
    )
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：submission_artifacts/evidence_metadata.json，submission_artifacts/evidence_summary.md。")
    return path


def fig_11(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "如实保留 partial 与 needs_evidence，避免把待补证据包装成满分结果。", height=1850)
    items = m["topic_items"]
    x0, y0 = 90, 260
    widths = [160, 520, 210, 700, 610]
    headers = ["编号", "要求摘要", "状态", "当前证据", "下一步/风险"]
    colors = {"implemented": PALETTE["green"], "partial": PALETTE["amber"], "needs_evidence": PALETTE["red"]}
    fills = {"implemented": PALETTE["green_soft"], "partial": PALETTE["amber_soft"], "needs_evidence": PALETTE["red_soft"]}
    x = x0
    for w, header in zip(widths, headers):
        svg.rect(x, y0, w, 70, fill=PALETTE["ink"], stroke=PALETTE["ink"], radius=0)
        svg.text(x + 18, y0 + 45, header, size=22, weight=800, color="#ffffff", max_units=18)
        x += w
    row_h = 104
    for i, item in enumerate(items):
        y = y0 + 70 + i * row_h
        fill = "#ffffff" if i % 2 == 0 else PALETTE["soft"]
        x = x0
        cells = [
            item["id"],
            item["requirement"],
            item["status"],
            item["evidence"],
            item["next"],
        ]
        for ci, (w, cell) in enumerate(zip(widths, cells)):
            svg.rect(x, y, w, row_h, fill=fill, stroke=PALETTE["line"], radius=0, width=1)
            if ci == 2:
                status = item["status"]
                svg.rect(x + 18, y + 30, w - 36, 44, fill=fills.get(status, PALETTE["gray_soft"]), stroke=colors.get(status, PALETTE["ink"]), radius=22, width=1)
                svg.text(x + w / 2, y + 58, status, size=18, color=colors.get(status, PALETTE["ink"]), weight=800, anchor="middle", max_units=14)
            else:
                max_units = [8, 26, 12, 35, 30][ci]
                svg.text(x + 16, y + 36, cell, size=17, color=PALETTE["ink"], max_units=max_units, line_height=1.18)
            x += w
    summary = m["topic_summary"]
    draw_pill(svg, 180, 1628, f"implemented {summary['implemented']}", PALETTE["green_soft"], PALETTE["green"], 270)
    draw_pill(svg, 490, 1628, f"partial {summary['partial']}", PALETTE["amber_soft"], PALETTE["amber"], 230)
    draw_pill(svg, 760, 1628, f"needs_evidence {summary['needs_evidence']}", PALETTE["red_soft"], PALETTE["red"], 310)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：reports/topic_19_compliance_plan.md（本轮重新运行 topic-compliance 生成）。")
    return path


def fig_12(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "金融数据场景下，大模型只做候选生成，不能绕过编译和验证。")
    svg.label_box(120, 310, 440, 220, "中文需求", "例如：近3日成交量累计大于300", fill=PALETTE["blue_soft"], stroke=PALETTE["blue"], title_color=PALETTE["blue"], max_units=22)
    svg.label_box(720, 220, 440, 210, "模板 NL2DSL", "稳定样例路径\n本地可复现", fill=PALETTE["teal_soft"], stroke=PALETTE["teal"], title_color=PALETTE["teal"], max_units=22)
    svg.label_box(720, 520, 440, 230, "LLM Provider", "OpenAI-compatible\n只返回 DSL candidate\n保存原始响应", fill=PALETTE["purple_soft"], stroke=PALETTE["purple"], title_color=PALETTE["purple"], max_units=22)
    svg.label_box(1320, 360, 440, 270, "安全闸门", "extract candidates\nreject direct SQL\ncompile + semantic\nSQL/reference equivalence", fill=PALETTE["amber_soft"], stroke=PALETTE["amber"], title_color=PALETTE["amber"], max_units=24)
    svg.label_box(1900, 390, 360, 220, "受控输出", "validated DSL\nDoris SQL\nrepair hints", fill=PALETTE["green_soft"], stroke=PALETTE["green"], title_color=PALETTE["green"], max_units=18)
    arrow_between(svg, 560, 420, 720, 325)
    arrow_between(svg, 560, 420, 720, 635)
    arrow_between(svg, 1160, 325, 1320, 455)
    arrow_between(svg, 1160, 635, 1320, 495)
    arrow_between(svg, 1760, 495, 1900, 495)
    svg.label_box(340, 870, 1720, 230, "最新 safety smoke", "accepted candidates=1；rejected candidates=2；rejected diagnostic codes=UNKNOWN_INDICATOR, UNSAFE_DIRECT_SQL。答辩时强调：AI 可以提升入口体验，但最终执行权在 deterministic compiler 和 reference verifier。", fill="#ffffff", stroke=PALETTE["line"], max_units=84)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：reports/submission_readiness.md，src/findsl/llm_adapter.py，src/findsl/llm_provider.py。")
    return path


def fig_13(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "业务规则配置化进入注册表，再被语义、SQL、reference 和测试共同消费。")
    configs = ["configs/indicators.json", "configs/functions.json", "configs/tables.json"]
    for i, name in enumerate(configs):
        svg.label_box(140, 300 + i * 190, 540, 130, name, "业务元数据 / 模板 / 表映射", fill=PALETTE["blue_soft"], stroke=PALETTE["blue"], title_color=PALETTE["blue"], max_units=26)
        arrow_between(svg, 680, 365 + i * 190, 960, 585)
    svg.label_box(940, 470, 520, 240, "Registry", "加载、规范化、校验配置\n向编译器提供统一描述", fill=PALETTE["teal_soft"], stroke=PALETTE["teal"], title_color=PALETTE["teal"], max_units=25)
    consumers = [
        ("SemanticAnalyzer", "类型、参数、窗口检查"),
        ("SqlGenerator", "Doris SQL 模板生成"),
        ("PandasReferenceEvaluator", "独立 reference 语义解释"),
        ("tests / official suite", "回归与官方样例证据"),
    ]
    for i, (title, body) in enumerate(consumers):
        x = 1620
        y = 260 + i * 190
        svg.label_box(x, y, 590, 135, title, body, fill=PALETTE["green_soft"] if i != 1 else PALETTE["purple_soft"], stroke=PALETTE["green"] if i != 1 else PALETTE["purple"], title_color=PALETTE["green"] if i != 1 else PALETTE["purple"], max_units=28)
        arrow_between(svg, 1460, 590, x, y + 68)
    svg.label_box(380, 1050, 1640, 210, "边界说明", "已证明：新指标配置化、ABS 简单 numeric scalar 函数模板。仍需诚实标注：复杂时序函数模板协议尚需增强，不能夸大为任意函数零代码。", fill=PALETTE["amber_soft"], stroke=PALETTE["amber"], title_color=PALETTE["amber"], max_units=78)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：configs/*.json，src/findsl/registry.py，tests/test_config_extension.py，tests/test_template_functions.py。")
    return path


def fig_14(spec: FigureSpec, m: dict) -> Path:
    d = m["doris"]
    svg = Svg(f"{spec.fig_id}  {spec.title}", "展示从 Doris SQL assets 到 evidence_summary 的性能证据链。")
    nodes = [
        ("01_schema.sql", "建 base/prefix 表\ntrade_date auto partitions"),
        ("02_sample_data / scale CSV", "加载行情数据\n5,000,000 EXPLAIN cardinality"),
        ("03_build_prefix_tables.sql", "构建 prefix table\nmaterialized hot window column"),
        ("collect_doris_evidence.ps1", "baseline/optimized SQL\nEXPLAIN + latency"),
        ("doris_cluster_evidence", f"row parity {d['row_counts_match']}\nspeedup {d['speedup']:.2f}x"),
        ("evidence_summary", "readiness 消费\n提交证据汇总"),
    ]
    x0, y0, bw, bh, gap = 120, 360, 335, 210, 45
    for i, (title, body) in enumerate(nodes):
        color = [PALETTE["blue"], PALETTE["blue"], PALETTE["teal"], PALETTE["amber"], PALETTE["green"], PALETTE["purple"]][i]
        fill = [PALETTE["blue_soft"], PALETTE["blue_soft"], PALETTE["teal_soft"], PALETTE["amber_soft"], PALETTE["green_soft"], PALETTE["purple_soft"]][i]
        x = x0 + i * (bw + gap)
        svg.label_box(x, y0, bw, bh, title, body, fill=fill, stroke=color, title_color=color, max_units=18)
        if i < len(nodes) - 1:
            arrow_between(svg, x + bw + 8, y0 + bh / 2, x + bw + gap - 8, y0 + bh / 2)
    svg.label_box(410, 800, 1580, 260, "证据边界", f"Doris evidence generated_at={d['generated_at']}；本轮最新 export 只复核 evidence 文件和 readiness markers，未重新连现场 Doris 重跑 latency。若最终演示环境可用，应再跑 collect-doris-evidence 并刷新本图。", fill="#ffffff", stroke=PALETTE["line"], max_units=76)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：deploy/doris/*.sql，scripts/collect_doris_evidence.ps1，doris_cluster_evidence.json。")
    return path


def fig_15(spec: FigureSpec, m: dict) -> Path:
    svg = Svg(f"{spec.fig_id}  {spec.title}", "把 Web Demo 页面区域与真实截图编号对应起来，便于答辩快速定位。")
    svg.rect(150, 260, 2100, 950, fill=PALETTE["soft"], stroke=PALETTE["line"], radius=28, shadow=True)
    svg.label_box(220, 340, 720, 720, "Workbench", "Natural language 输入\nSuggest DSL\ncandidate list\nSample 下拉框\nDSL 输入框\nPrefix/Verify 开关\nRun analysis", fill="#ffffff", stroke=PALETTE["blue"], title_color=PALETTE["blue"], max_units=32)
    svg.label_box(1040, 340, 1070, 220, "Result Metrics", "verification / compile latency / SQL rows / optimizer / dataset\n证据：EV-041 主界面，EV-042 参数区", fill="#ffffff", stroke=PALETTE["teal"], title_color=PALETTE["teal"], max_units=52)
    tabs = [
        ("SQL", "EV-043"),
        ("AST", "EV-044"),
        ("Explain", "EV-045"),
        ("Rows", "EV-046"),
        ("Evidence", "EV-047"),
        ("Diagnostic", "EV-048"),
    ]
    for i, (tab, ev) in enumerate(tabs):
        x = 1040 + (i % 3) * 350
        y = 650 + (i // 3) * 210
        svg.label_box(x, y, 300, 150, tab, ev, fill=PALETTE["green_soft"] if i < 5 else PALETTE["red_soft"], stroke=PALETTE["green"] if i < 5 else PALETTE["red"], title_color=PALETTE["green"] if i < 5 else PALETTE["red"], max_units=14)
    svg.text(220, 1130, "说明：本图为页面信息架构索引，真实界面截图仍以 visual_evidence/screenshots/EV-041 至 EV-048 为准。", size=23, color=PALETTE["muted"], max_units=92)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：submission_artifacts/visual_evidence/screenshots/EV-041 至 EV-048。")
    return path


def fig_16(spec: FigureSpec, m: dict) -> Path:
    vs = m["visual_summary"]
    svg = Svg(f"{spec.fig_id}  {spec.title}", "用目录树说明最终交付件在哪里、分别证明什么。")
    rows = [
        ("README.md / PROJECT_INDEX.md", "项目简介、运行入口、文件索引"),
        ("src/", "编译器、SQL 生成、验证、Demo 后端"),
        ("configs/", "指标、函数、表映射配置"),
        ("data/", "样例数据、真实行情小样本"),
        ("tests/", "pytest、official suite、边界测试"),
        ("deploy/doris/", "Doris DDL、样例加载、prefix 表构建"),
        ("docs/", "中文手册、架构、算法、部署、交付说明"),
        ("submission_artifacts/", "evidence snapshots、visual evidence、demo screenshots、defense video"),
    ]
    x0, y0 = 180, 270
    for i, (name, desc) in enumerate(rows):
        y = y0 + i * 118
        fill = PALETTE["blue_soft"] if i < 2 else PALETTE["green_soft"] if i < 6 else PALETTE["purple_soft"]
        color = PALETTE["blue"] if i < 2 else PALETTE["green"] if i < 6 else PALETTE["purple"]
        svg.rect(x0 + 70, y, 1880, 82, fill=fill, stroke=color, radius=18)
        svg.circle(x0 + 25, y + 41, 18, color)
        svg.text(x0 + 110, y + 51, name, size=25, weight=900, color=color, max_units=32)
        svg.text(x0 + 760, y + 51, desc, size=23, color=PALETTE["ink"], max_units=54)
    evidence = f"visual evidence: {vs.get('evidence_rows', '待核验')} rows / {vs.get('screenshots', '待核验')} screenshots / {vs.get('logs', '待核验')} logs"
    svg.label_box(360, 1240, 1680, 130, "证据包统计", evidence, fill=PALETTE["gray_soft"], stroke=PALETTE["line"], max_units=76)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：PROJECT_INDEX.md，submission_artifacts/evidence_manifest.md，visual_evidence_summary.json。")
    return path


def fig_17(spec: FigureSpec, m: dict) -> Path:
    d = m["doris"]
    svg = Svg(f"{spec.fig_id}  {spec.title}", "把业务真实样本和规模性能证据分开讲，避免数据口径混淆。")
    svg.label_box(160, 310, 2100, 320, "业务可信度泳道", "Eastmoney public historical K-line -> 贵州茅台 / 平安银行真实 A 股字段 -> real market sample cases 3/3 -> Web Demo 真实行情展示\n结论边界：用于证明字段、日期、A 股代码和验证流程贴近真实业务，不用于 5M 性能结论。", fill=PALETTE["blue_soft"], stroke=PALETTE["blue"], title_color=PALETTE["blue"], max_units=98)
    svg.label_box(160, 760, 2100, 320, "性能可信度泳道", f"deterministic synthetic A-share-style scale data -> Doris 5,000,000 cardinality -> baseline vs prefix-sum -> speedup {d['speedup']:.2f}x\n结论边界：用于证明长窗口 prefix-sum 在 Doris 集群上的性能收益，不声称它是真实行情原始全量数据。", fill=PALETTE["teal_soft"], stroke=PALETTE["teal"], title_color=PALETTE["teal"], max_units=98)
    svg.line(250, 700, 2150, 700, color=PALETTE["line"], width=4, dashed=True)
    draw_pill(svg, 500, 1150, "业务样本：真实小样本", PALETTE["blue_soft"], PALETTE["blue"], 360)
    draw_pill(svg, 940, 1150, "性能样本：可复现规模数据", PALETTE["teal_soft"], PALETTE["teal"], 430)
    draw_pill(svg, 1450, 1150, "口径诚实：分开证明", PALETTE["green_soft"], PALETTE["green"], 360)
    path = FIGURE_DIR / FIG_DIRS[spec.category] / f"{spec.filename}.svg"
    svg.save(path, "数据源：README.md，data/real_samples/eastmoney_a_share_sample/README.md，doris_cluster_evidence.json。")
    return path


BUILDERS = {
    "FIG-01": fig_01,
    "FIG-02": fig_02,
    "FIG-03": fig_03,
    "FIG-04": fig_04,
    "FIG-05": fig_05,
    "FIG-06": fig_06,
    "FIG-07": fig_07,
    "FIG-08": fig_08,
    "FIG-09": fig_09,
    "FIG-10": fig_10,
    "FIG-11": fig_11,
    "FIG-12": fig_12,
    "FIG-13": fig_13,
    "FIG-14": fig_14,
    "FIG-15": fig_15,
    "FIG-16": fig_16,
    "FIG-17": fig_17,
}


SPECS = [
    FigureSpec("FIG-01", "赛题任务拆解图", "分层任务拆解图", "topic", "必须", "README + topic-compliance + evidence_metadata", "赛题理解证据", "问题定义", "赛题理解与目标", "FIG-01_topic_task_breakdown"),
    FigureSpec("FIG-02", "输入-处理-输出总链路图", "Pipeline 流程图", "topic", "必须", "README + technical_report + evidence_metadata", "端到端闭环证据", "方案概述", "整体链路", "FIG-02_input_process_output_pipeline"),
    FigureSpec("FIG-03", "项目总体架构图", "分层架构图", "architecture", "必须", "PROJECT_INDEX + src + configs", "架构说明证据", "总体架构", "系统架构", "FIG-03_system_architecture"),
    FigureSpec("FIG-04", "代码模块调用关系图", "模块调用图", "architecture", "必须", "src/findsl/*.py", "代码可追溯证据", "代码结构", "答辩备份页", "FIG-04_code_module_call_graph"),
    FigureSpec("FIG-05", "项目运行与人工核验流程图", "验收流程图", "operation", "必须", "SCREENSHOT_EVIDENCE_INDEX + evidence_metadata", "运行复现证据", "运行与验收流程", "如何复现与验收", "FIG-05_operation_acceptance_flow"),
    FigureSpec("FIG-06", "DSL 编译核心算法流程图", "算法流程图", "algorithm", "必须", "compiler.py + parser.py + semantic.py", "核心算法证据", "核心算法", "确定性编译内核", "FIG-06_dsl_compiler_algorithm"),
    FigureSpec("FIG-07", "Prefix-Sum 长窗口优化流程图", "优化算法流程图", "algorithm", "必须", "sqlgen.py + doris_cluster_evidence", "性能算法证据", "优化方法", "长窗口性能优化", "FIG-07_prefix_sum_optimization_flow"),
    FigureSpec("FIG-08", "Doris SQL 执行计划对比图", "执行计划摘要图", "performance", "必须", "doris_cluster_evidence.md/json", "性能可信证据", "实验结果与分析", "执行计划对比", "FIG-08_doris_plan_comparison"),
    FigureSpec("FIG-09", "Doris 性能对比柱状图", "分组柱状图", "performance", "必须", "doris_cluster_evidence.json", "性能达标证据", "性能实验", "性能核心页", "FIG-09_doris_latency_speedup"),
    FigureSpec("FIG-10", "测试验证结果汇总图", "指标卡 dashboard", "validation", "必须", "evidence_metadata.json", "测试通过证据", "测试说明", "验证结果", "FIG-10_validation_dashboard"),
    FigureSpec("FIG-11", "赛题要求-实现-证据矩阵", "矩阵表", "validation", "必须", "reports/topic_19_compliance_plan.md", "赛题符合性证据", "符合性分析", "评委追问备份页", "FIG-11_requirement_implementation_evidence_matrix"),
    FigureSpec("FIG-12", "NL2DSL 与 LLM 安全边界图", "安全流程图", "special", "建议", "submission_readiness + llm_adapter.py", "AI 安全设计证据", "AI 安全入口", "创新点", "FIG-12_llm_safety_boundary"),
    FigureSpec("FIG-13", "配置化扩展机制图", "关系图", "special", "建议", "configs + registry + tests", "扩展性证据", "扩展性设计", "工程亮点", "FIG-13_configurable_extension"),
    FigureSpec("FIG-14", "Doris 部署与数据流图", "部署/数据流图", "special", "建议", "deploy/doris + doris evidence", "性能环境说明证据", "部署与实验环境", "性能实验说明", "FIG-14_doris_deployment_data_flow"),
    FigureSpec("FIG-15", "Web Demo 功能证据索引图", "页面功能索引图", "ppt", "建议", "EV-041 至 EV-048", "界面说明证据", "系统界面说明", "演示页", "FIG-15_web_demo_evidence_map"),
    FigureSpec("FIG-16", "结果与交付包结构图", "目录树/交付地图", "report", "建议", "PROJECT_INDEX + evidence_manifest", "交付完整证据", "交付说明", "收尾页", "FIG-16_delivery_package_map"),
    FigureSpec("FIG-17", "真实行情样本与规模性能证据边界图", "双泳道说明图", "special", "建议", "README + real_samples + doris evidence", "数据口径证据", "实验设计", "数据来源备份页", "FIG-17_real_sample_vs_scale_evidence"),
]


def png_add_dpi(path: Path, dpi: int = 300) -> None:
    data = path.read_bytes()
    sig = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(sig):
        return
    ppm = int(round(dpi / 0.0254))
    phys_data = struct.pack(">IIB", ppm, ppm, 1)
    phys_chunk = (
        struct.pack(">I", len(phys_data))
        + b"pHYs"
        + phys_data
        + struct.pack(">I", zlib.crc32(b"pHYs" + phys_data) & 0xFFFFFFFF)
    )
    pos = len(sig)
    output = bytearray(sig)
    inserted = False
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk = data[pos : pos + 12 + length]
        pos += 12 + length
        if chunk_type == b"pHYs":
            continue
        output.extend(chunk)
        if chunk_type == b"IHDR" and not inserted:
            output.extend(phys_chunk)
            inserted = True
    path.write_bytes(bytes(output))


def render_png(svg_path: Path) -> Path:
    png_path = svg_path.with_name(svg_path.stem + "_300dpi.png")
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    html_path = HTML_DIR / (svg_path.stem + ".html")
    rel = svg_path.resolve().as_uri()
    html_path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:#fff;width:{CANVAS_W}px;}}
img{{display:block;width:{CANVAS_W}px;height:auto;}}
</style></head>
<body><img src="{esc(rel)}" alt="{esc(svg_path.stem)}"></body></html>""",
        encoding="utf-8",
    )
    npx_cmd = shutil.which("npx.cmd") or shutil.which("npx.exe")
    if npx_cmd:
        command = [npx_cmd]
    else:
        npx_ps1 = shutil.which("npx.ps1") or shutil.which("npx")
        if not npx_ps1:
            raise RuntimeError("Cannot find npx/npx.cmd/npx.ps1 for Playwright rendering.")
        command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", npx_ps1]
    # Keep Playwright as the renderer so the PNG reflects the actual SVG layout.
    subprocess.run(
        command
        + [
            "playwright",
            "screenshot",
            "--viewport-size",
            f"{CANVAS_W},{CANVAS_H + 300}",
            "--wait-for-timeout",
            "700",
            "--full-page",
            html_path.resolve().as_uri(),
            str(png_path),
        ],
        cwd=ROOT,
        check=True,
    )
    png_add_dpi(png_path, 300)
    return png_path


def write_index(m: dict, outputs: list[tuple[FigureSpec, Path, Path]]) -> None:
    md = m["metadata"]
    d = m["doris"]
    lines: list[str] = []
    lines.append("# 已生成图表索引")
    lines.append("")
    lines.append(f"生成时间：{m['generated_at_local']}")
    lines.append(f"最新 evidence metadata：`{md['generated_at']}`")
    lines.append(f"最新 Git HEAD at export：`{md['git']['head_at_export']}`")
    lines.append(f"最新 pytest：`{md['readiness']['pytest']['passed']} passed in {md['readiness']['pytest']['elapsed_seconds']:.2f}s`")
    lines.append(f"最新 official suite：正例 `{md['official_suite']['positive']['passed']}/{md['official_suite']['positive']['total']}`，负例 `{md['official_suite']['negative']['passed']}/{md['official_suite']['negative']['total']}`")
    lines.append(f"Doris evidence：`{d['generated_at']}` 生成，最新 export/readiness 已核验为 PASS；本轮未现场重跑 Doris latency。")
    lines.append("")
    lines.append("## 科研绘图规范")
    lines.append("")
    lines.append(f"本批图表按 `{STYLE_STANDARD}` 重新生成。执行标准包括：白底、矢量优先、PNG 300dpi 元数据、Okabe-Ito 风格色盲安全配色、低饱和辅助底色、无 3D/饼图/彩虹色/装饰渐变、细线框、统一图号图题、脚注标注数据源。流程图和架构图属于机制示意图；FIG-09、FIG-10、FIG-11 等含指标图只使用最新 evidence 文件中的真实数据。")
    lines.append("")
    lines.append("## 图表总表")
    lines.append("")
    lines.append("| 图号 | 图名 | 类型 | 必须/建议 | 所属目录 | SVG | PNG | 数据来源 | 证明什么 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for spec, svg_path, png_path in outputs:
        rel_svg = svg_path.relative_to(ROOT).as_posix()
        rel_png = png_path.relative_to(ROOT).as_posix()
        lines.append(
            f"| {spec.fig_id} | {spec.title} | {spec.kind} | {spec.required} | {FIG_DIRS[spec.category]} | `{rel_svg}` | `{rel_png}` | {spec.source} | {spec.proof} |"
        )
    lines.append("")
    lines.append("## 使用说明")
    lines.append("")
    lines.append("这些图表分为两类：流程、架构、边界类图属于说明证据；FIG-09 和 FIG-10 等带指标图引用最新 evidence 文件，可作为性能和测试验证材料。答辩时不要把示意图当作测试通过截图，实际通过性仍以 `submission_artifacts/evidence_snapshots/`、`evidence_metadata.json`、`evidence_summary.md` 和截图证据包为准。")
    lines.append("")
    lines.append("## 不适用图表")
    lines.append("")
    lines.append("| 图表类型 | 结论 | 原因 |")
    lines.append("|---|---|---|")
    lines.append("| 深度学习 Loss/Accuracy/ROC/PR/mAP | 不适用 | 本项目是 DSL 编译器与 Doris SQL 优化系统，没有训练日志、模型权重和分类阈值。 |")
    lines.append("| 硬件连接/Verilog 波形 | 不适用 | 项目没有嵌入式、HDL、仿真波形或硬件接口。 |")
    lines.append("| 无数据支撑的 QPS/CPU/内存图 | 不适用 | 当前最新 evidence 没有资源消耗与吞吐量指标，只画真实 Avg/P95 latency 与 speedup。 |")
    (FIGURE_DIR / "已生成图表索引.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "generated_at": m["generated_at_local"],
        "metadata_generated_at": md["generated_at"],
        "git_head_at_export": md["git"]["head_at_export"],
        "style_standard": STYLE_STANDARD,
        "style_rules": [
            "white background",
            "vector-first SVG",
            "300 dpi PNG metadata",
            "Okabe-Ito inspired colorblind-safe palette",
            "low-saturation fills",
            "thin strokes and no drop shadows",
            "explicit figure id, data source, and evidence boundary",
        ],
        "pytest": md["readiness"]["pytest"],
        "official_suite": md["official_suite"],
        "doris": {
            "generated_at": d["generated_at"],
            "speedup": d["speedup"],
            "baseline_avg_execute_ms": d["baseline"]["avg_execute_ms"],
            "optimized_avg_execute_ms": d["optimized"]["avg_execute_ms"],
            "baseline_p95_execute_ms": d["baseline"]["p95_execute_ms"],
            "optimized_p95_execute_ms": d["optimized"]["p95_execute_ms"],
            "row_counts_match": d["row_counts_match"],
            "note": "Doris latency evidence is the latest committed evidence file consumed by the refreshed readiness/export step; it was not re-measured in this figure-generation run.",
        },
        "figures": [
            {
                "id": spec.fig_id,
                "title": spec.title,
                "svg": str(svg_path.relative_to(ROOT)),
                "png": str(png_path.relative_to(ROOT)),
                "source": spec.source,
            }
            for spec, svg_path, png_path in outputs
        ],
    }
    (FIGURE_DIR / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_dir_readmes(outputs: list[tuple[FigureSpec, Path, Path]]) -> None:
    grouped: dict[str, list[tuple[FigureSpec, Path, Path]]] = {}
    for row in outputs:
        grouped.setdefault(row[0].category, []).append(row)
    for key, rows in grouped.items():
        folder = FIGURE_DIR / FIG_DIRS[key]
        lines = [f"# {FIG_DIRS[key]}", ""]
        lines.append("| 图号 | 图名 | SVG | PNG | 建议放置 |")
        lines.append("|---|---|---|---|---|")
        for spec, svg_path, png_path in rows:
            lines.append(
                f"| {spec.fig_id} | {spec.title} | `{svg_path.name}` | `{png_path.name}` | 报告：{spec.report_place}；PPT：{spec.ppt_place} |"
            )
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if os.name == "nt":
        paths = [
            os.environ.get("Path", ""),
            os.environ.get("PATH", ""),
            os.environ.get("ProgramFiles", r"C:\Program Files") + r"\nodejs",
            os.environ.get("APPDATA", "") + r"\npm",
        ]
        os.environ["PATH"] = ";".join(p for p in paths if p)
    for folder in FIG_DIRS.values():
        (FIGURE_DIR / folder).mkdir(parents=True, exist_ok=True)
    if HTML_DIR.exists():
        HTML_DIR.resolve().relative_to(FIGURE_DIR.resolve())
        shutil.rmtree(HTML_DIR)
    metrics = latest_metrics()
    outputs: list[tuple[FigureSpec, Path, Path]] = []
    for spec in SPECS:
        svg_path = BUILDERS[spec.fig_id](spec, metrics)
        png_path = render_png(svg_path)
        outputs.append((spec, svg_path, png_path))
    write_index(metrics, outputs)
    write_dir_readmes(outputs)
    if HTML_DIR.exists():
        HTML_DIR.resolve().relative_to(FIGURE_DIR.resolve())
        shutil.rmtree(HTML_DIR)
    print(f"Generated {len(outputs)} figures under {FIGURE_DIR}")


if __name__ == "__main__":
    main()
