from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "outputs" / "可视化证据包_plottie_style"
REFERENCE_GALLERY_DIRNAME = "00_参考样例学习"

DOUBLE_IN = 183 / 25.4
SINGLE_IN = 89 / 25.4
MAX_HEIGHT_IN = 170 / 25.4
STYLE_STANDARD = "Plottie atlas + figures4papers + Show2Know + nature-skills reference mode v2"

# Restrained publication palette: figures4papers semantic blue plus
# Show2Know paper palette 05 as low-saturation secondary roles.
INK = "#1C1C1C"
TEXT = "#404040"
MUTED = "#727272"
RULE = "#C7C7C7"
PALE = "#F5F5F3"
BLUE = "#0F4D92"
BLUE_LIGHT = "#D8E6F3"
TEAL = "#388498"
GREEN = "#779043"
ORANGE = "#BF7334"
RED = "#943C39"
GOLD = "#C9A227"
WHITE = "#FFFFFF"

FIG_DIRS = {
    "flow": "01_流程与机制图",
    "network": "02_架构与依赖图",
    "matrix": "03_矩阵与验证图",
    "performance": "04_性能图",
    "image_plate": "05_界面证据图像板",
}

PLOTTIE_LINKS = [
    ("Plottie scientific plot atlas", "https://plottie.art/"),
    ("Plottie collections", "https://plottie.art/collections"),
    ("Plottie palettes", "https://plottie.art/palette"),
    ("Plottie line plots", "https://plottie.art/plots/line-plots"),
    ("Plottie scatter plots", "https://plottie.art/plots/scatter-plots"),
    ("Plottie heatmaps", "https://plottie.art/plots/heatmaps"),
    ("Plottie volcano plots guide", "https://plottie.art/plots/volcano-plots"),
    ("Nature building and exporting panels", "https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/"),
    ("Nature figure specifications", "https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/"),
    ("Matplotlib customizing and export", "https://matplotlib.org/stable/users/explain/customizing.html"),
]

REFERENCE_PROJECTS = [
    {
        "name": "figures4papers",
        "url": "https://github.com/ChenLiu-1996/figures4papers",
        "relative_path": "external_references/scientific_figure_code/figures4papers",
        "install_mode": "Codex local skill: scientific-figure-making; source templates cached locally",
        "install_check": "scientific-figure-making/SKILL.md and references/api.md copied into Codex skills",
        "used_for": "GridSpec multi-panel composition, direct labelling, semantic palette and vector export helpers",
    },
    {
        "name": "Show2Know",
        "url": "https://github.com/Winn1y/Show2Know",
        "relative_path": "external_references/scientific_figure_code/Show2Know",
        "install_mode": "Source-template library; repository has no pip package metadata",
        "install_check": "selected scatter, line, confidence interval, heatmap, image-plate and violin scripts compile",
        "used_for": "paper color temple, heatmap/matrix recipes, line/range plot patterns and multi-image plate layout",
    },
    {
        "name": "nature-skills",
        "url": "https://github.com/Yuan1z0825/nature-skills",
        "relative_path": "external_references/scientific_figure_code/nature-skills",
        "install_mode": "Codex local skill bundle; all nature-* folders plus _shared copied into Codex skills",
        "install_check": "nature-figure manifest/static/references installed; MCP requirements installed under Python 3.11",
        "used_for": "Nature figure contract, backend exclusivity, QA checklist, editable SVG/PDF and image integrity rules",
    },
]

REFERENCE_EXAMPLES = [
    {
        "id": "REF-01",
        "project": "figures4papers",
        "title": "speed comparison panel",
        "relative_path": "external_references/scientific_figure_code/figures4papers/figure_RNAGenScape/figures/results_comparison_speed.png",
        "learned_pattern": "wide comparison panel, direct numeric annotations, semantic blue for the key method",
        "applied_to": "FIG-09 Doris latency/speedup and matrix/performance panels",
    },
    {
        "id": "REF-02",
        "project": "figures4papers",
        "title": "composition heatmap",
        "relative_path": "external_references/scientific_figure_code/figures4papers/figure_ophthal_review/figures/composition_heatmap.png",
        "learned_pattern": "compact matrix with cell annotations, quiet axes and one continuous color scale",
        "applied_to": "FIG-08 plan comparison, FIG-10 validation matrix, FIG-11 compliance matrix",
    },
    {
        "id": "REF-03",
        "project": "figures4papers",
        "title": "method schematic",
        "relative_path": "external_references/scientific_figure_code/figures4papers/assets/ImmunoStruct_schematic.png",
        "learned_pattern": "schematic-first method panel with small supporting panels and consistent panel labels",
        "applied_to": "FIG-01, FIG-02, FIG-06, FIG-07, FIG-12 and FIG-14",
    },
    {
        "id": "REF-04",
        "project": "Show2Know",
        "title": "confidence interval line",
        "relative_path": "external_references/scientific_figure_code/Show2Know/2 Line Plot/95ConfidenceInterval/draw_95_CI.py",
        "preview_path": "external_references/scientific_figure_code/Show2Know/2 Line Plot/errorbar/errorbar.png",
        "learned_pattern": "line or dot estimates with uncertainty bands instead of isolated metric cards",
        "applied_to": "FIG-09 paired range plot and performance annotation strategy",
    },
    {
        "id": "REF-05",
        "project": "Show2Know",
        "title": "multi-line fill",
        "relative_path": "external_references/scientific_figure_code/Show2Know/15 Multi-Line-With-Fill/run.py",
        "preview_path": "external_references/scientific_figure_code/Show2Know/15 Multi-Line-With-Fill/multi_line_chart_with_fill.png",
        "learned_pattern": "thin line plus low-alpha interval fill, with restrained legend use",
        "applied_to": "performance-family charts where intervals or paired comparisons are needed",
    },
    {
        "id": "REF-06",
        "project": "Show2Know",
        "title": "multi-image plate",
        "relative_path": "external_references/scientific_figure_code/Show2Know/14 Multi-Image-To-One/run.py",
        "preview_path": "external_references/scientific_figure_code/Show2Know/14 Multi-Image-To-One/collage_with_text4.jpg",
        "learned_pattern": "image plate assembly with consistent tile geometry and minimal captions",
        "applied_to": "FIG-15 Web Demo image evidence plate",
    },
    {
        "id": "REF-07",
        "project": "nature-skills",
        "title": "heatmap atlas",
        "relative_path": "external_references/scientific_figure_code/nature-skills/skills/nature-figure/assets/chart-atlas/atlas-03-heatmaps.png",
        "learned_pattern": "multi-panel matrix atlas, tight gutters, no decorative containers",
        "applied_to": "matrix charts and requirement/evidence maps",
    },
    {
        "id": "REF-08",
        "project": "nature-skills",
        "title": "forest and interval atlas",
        "relative_path": "external_references/scientific_figure_code/nature-skills/skills/nature-figure/assets/chart-atlas/atlas-07-forest-interval.png",
        "learned_pattern": "interval/dot estimates as evidence, using the axis rather than dashboard badges",
        "applied_to": "FIG-09 latency and speedup evidence",
    },
    {
        "id": "REF-09",
        "project": "nature-skills",
        "title": "Nature-style mechanism gallery",
        "relative_path": "external_references/scientific_figure_code/nature-skills/skills/nature-figure/assets/gallery/fig1-material-mechanism-rich.png",
        "learned_pattern": "one visual claim per panel, lowercase panel labels, restrained supporting plots",
        "applied_to": "all generated figures as the final QA target",
    },
]


@dataclass(frozen=True)
class FigureSpec:
    fig_id: str
    title: str
    chart_class: str
    filename: str
    source: str
    proof: str
    conclusion: str


SPECS = [
    FigureSpec("FIG-01", "赛题任务拆解", "flow", "FIG-01_topic_task_breakdown", "README + topic compliance", "赛题任务证据链", "赛题任务可以被拆成输入、编译、验证、性能和交付五条证据线。"),
    FigureSpec("FIG-02", "输入-处理-输出链路", "flow", "FIG-02_input_process_output_pipeline", "README + compiler reports", "端到端闭环", "自然语言候选必须被确定性编译器和 reference oracle 复核后才能形成 Doris SQL。"),
    FigureSpec("FIG-03", "项目总体架构", "network", "FIG-03_system_architecture", "PROJECT_INDEX + src", "系统分层架构", "项目由入口、适配、编译、配置、验证和证据交付六层组成。"),
    FigureSpec("FIG-04", "核心模块调用关系", "network", "FIG-04_code_module_call_graph", "src/findsl", "代码可追溯", "CLI 把编译、验证、官方套件、Demo 和证据导出统一到同一链路。"),
    FigureSpec("FIG-05", "运行与人工核验流程", "flow", "FIG-05_operation_acceptance_flow", "SCREENSHOT_EVIDENCE_INDEX", "复现流程", "验收应从环境、命令、测试、证据到提交状态逐层收口。"),
    FigureSpec("FIG-06", "DSL 编译核心算法", "flow", "FIG-06_dsl_compiler_algorithm", "compiler.py + parser.py + semantic.py", "核心算法", "FinDSL 先形成 typed AST，再生成可验证的 Doris-safe SQL。"),
    FigureSpec("FIG-07", "Prefix-Sum 长窗口优化", "flow", "FIG-07_prefix_sum_optimization_flow", "sqlgen.py + Doris evidence", "性能算法", "滚动 SUM 在满足条件时可改写为 prefix-table 访问，并保留窗口函数回退路径。"),
    FigureSpec("FIG-08", "Doris 执行计划差异", "matrix", "FIG-08_doris_plan_comparison", "doris_cluster_evidence", "执行计划证据", "优化路径把运行时窗口聚合替换为 prefix-table predicate 与 join。"),
    FigureSpec("FIG-09", "Doris 延迟与加速比", "performance", "FIG-09_doris_latency_speedup", "doris_cluster_evidence.json", "性能达标", "冻结 Doris evidence 显示 prefix-sum 路径达到 36x 级延迟下降。"),
    FigureSpec("FIG-10", "测试验证结果", "matrix", "FIG-10_validation_matrix", "evidence_metadata.json", "门禁通过证据", "最新证据显示 required gates 全通过，warning count 为 0。"),
    FigureSpec("FIG-11", "赛题要求-实现-证据矩阵", "matrix", "FIG-11_requirement_implementation_evidence_matrix", "topic_19_compliance_plan.md", "符合性证据", "已实现、部分实现和待补证据必须如实分开表达。"),
    FigureSpec("FIG-12", "NL2DSL 与 LLM 安全边界", "flow", "FIG-12_llm_safety_boundary", "llm_adapter.py + readiness", "AI 安全边界", "LLM 只产生候选 DSL，执行权由编译器和验证器控制。"),
    FigureSpec("FIG-13", "配置化扩展机制", "network", "FIG-13_configurable_extension", "configs + registry", "扩展机制", "指标、函数和表配置通过 Registry 同时服务语义、SQL、reference 与测试。"),
    FigureSpec("FIG-14", "Doris 部署与数据流", "flow", "FIG-14_doris_deployment_data_flow", "deploy/doris + evidence", "实验环境说明", "Doris 证据从 DDL、prefix 表、采集脚本进入 evidence snapshot。"),
    FigureSpec("FIG-15", "Web Demo 图像证据板", "image_plate", "FIG-15_web_demo_image_plate", "actual screenshots", "界面证据", "Demo 截图应作为真实图像证据板展示，不重绘、不伪造、不遮挡状态。"),
    FigureSpec("FIG-16", "结果与交付包结构", "network", "FIG-16_delivery_package_map", "PROJECT_INDEX + evidence_manifest", "交付完整性", "最终交付物围绕源码、配置、数据、测试、文档和 evidence snapshots 组织。"),
    FigureSpec("FIG-17", "真实样本与规模证据边界", "network", "FIG-17_real_sample_vs_scale_evidence", "real samples + Doris evidence", "数据口径边界", "真实行情样本证明语义可信性，5M Doris evidence 证明规模性能，两者不能混为同一数据集。"),
]
SPEC_BY_ID = {spec.fig_id: spec for spec in SPECS}

PLOTTIE_AUDIT = {
    "flow": {
        "plottie_reference": "Flowchart / schematic examples in Plottie collections",
        "code_file": "scripts/plottie_figures/flow.py",
        "rule": "用 nature-skills 的 method schematic 约束和 figures4papers 的 GridSpec/直接标注方式表达过程，不用 UI 卡片、阴影或图标堆叠。",
    },
    "network": {
        "plottie_reference": "Network and mechanism-style atlas examples",
        "code_file": "scripts/plottie_figures/network.py",
        "rule": "用 figures4papers 的分层/网络示意写法表达依赖关系，采用 Show2Know 低饱和配色作极少量强调，避免彩色系统大屏风格。",
    },
    "matrix": {
        "plottie_reference": "Heatmap and matrix plot examples",
        "code_file": "scripts/plottie_figures/matrices.py",
        "rule": "参考 Show2Know heatmap 和 figures4papers validation panel，把状态、门禁和要求对应关系画成矩阵/棒棒糖/紧凑表格，不做仪表盘。",
    },
    "performance": {
        "plottie_reference": "Line/scatter/range plot examples",
        "code_file": "scripts/plottie_figures/performance.py",
        "rule": "结合 Show2Know line/errorbar 思路和 figures4papers comparison panel，把延迟和加速比画成 log-scale range/dot plot，保留未重测边界。",
    },
    "image_plate": {
        "plottie_reference": "Image panel / multi-panel evidence layouts",
        "code_file": "scripts/plottie_figures/image_plates.py",
        "rule": "参考 Show2Know Multi-Image-To-One 与 nature-skills image integrity，实际截图只做 image plate 排版，不合成假界面。",
    },
}


def setup_style() -> None:
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
    candidates = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Arial Unicode MS",
    ]
    available = {font.name for font in font_manager.fontManager.ttflist}
    cjk = next((name for name in candidates if name in available), None)
    sans_stack = ([cjk] if cjk else []) + ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "sans-serif"]
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": sans_stack,
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 6.6,
            "axes.labelsize": 6.6,
            "axes.titlesize": 7.2,
            "xtick.labelsize": 5.8,
            "ytick.labelsize": 5.8,
            "legend.fontsize": 5.8,
            "axes.linewidth": 0.65,
            "lines.linewidth": 0.9,
            "patch.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "axes.edgecolor": INK,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "text.color": INK,
            "figure.facecolor": WHITE,
            "axes.facecolor": WHITE,
            "savefig.facecolor": WHITE,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.035,
        }
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _git_value(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def _skill_root() -> Path:
    return Path.home() / ".codex" / "skills"


def _reference_checks(name: str) -> list[dict[str, str | bool]]:
    skill_root = _skill_root()
    if name == "figures4papers":
        checks = [
            ("local skill", skill_root / "scientific-figure-making" / "SKILL.md"),
            ("palette API", skill_root / "scientific-figure-making" / "references" / "api.md"),
            ("common patterns", skill_root / "scientific-figure-making" / "references" / "common-patterns.md"),
        ]
    elif name == "Show2Know":
        checks = [
            ("line script", ROOT / "external_references" / "scientific_figure_code" / "Show2Know" / "2 Line Plot" / "line.py"),
            ("confidence interval script", ROOT / "external_references" / "scientific_figure_code" / "Show2Know" / "2 Line Plot" / "95ConfidenceInterval" / "draw_95_CI.py"),
            ("heatmap script", ROOT / "external_references" / "scientific_figure_code" / "Show2Know" / "4 HeatMap Plot" / "heatmap.py"),
            ("image plate script", ROOT / "external_references" / "scientific_figure_code" / "Show2Know" / "14 Multi-Image-To-One" / "run.py"),
            ("paper palette", ROOT / "external_references" / "scientific_figure_code" / "Show2Know" / "0 Collection and Color" / "Color" / "PaperColorTemple.md"),
        ]
    elif name == "nature-skills":
        checks = [
            ("nature-figure skill", skill_root / "nature-figure" / "SKILL.md"),
            ("nature-figure manifest", skill_root / "nature-figure" / "manifest.yaml"),
            ("QA contract", skill_root / "nature-figure" / "references" / "qa-contract.md"),
            ("shared skill assets", skill_root / "_shared"),
        ]
    else:
        checks = []
    return [{"name": label, "path": str(path), "exists": path.exists()} for label, path in checks]


def reference_project_inventory() -> list[dict]:
    inventory: list[dict] = []
    for project in REFERENCE_PROJECTS:
        repo_path = ROOT / project["relative_path"]
        checks = _reference_checks(project["name"])
        inventory.append(
            {
                **project,
                "local_exists": repo_path.exists(),
                "git_head": _git_value(["rev-parse", "--short", "HEAD"], repo_path) if repo_path.exists() else "missing",
                "origin_url": _git_value(["remote", "get-url", "origin"], repo_path) if repo_path.exists() else "missing",
                "install_checks": checks,
                "install_checks_passed": bool(checks) and all(bool(check["exists"]) for check in checks),
            }
        )
    return inventory


def reference_examples_inventory() -> list[dict]:
    rows: list[dict] = []
    for example in REFERENCE_EXAMPLES:
        preview_rel = example.get("preview_path", example["relative_path"])
        preview_path = ROOT / preview_rel
        source_path = ROOT / example["relative_path"]
        rows.append(
            {
                **example,
                "source_exists": source_path.exists(),
                "preview_path": preview_rel,
                "preview_exists": preview_path.exists(),
            }
        )
    return rows


def parse_topic_items(text: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    items: list[dict[str, str]] = []
    for line in text.splitlines():
        if line.startswith("| T19-R"):
            parts = [part.strip() for part in line.strip("|").split("|")]
            if len(parts) >= 5:
                items.append({"id": parts[0], "requirement": parts[1], "status": parts[2], "evidence": parts[3]})
    summary = {"implemented": 0, "partial": 0, "needs_evidence": 0}
    for item in items:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    return items, summary


def latest_metrics() -> dict:
    metadata = load_json(ROOT / "submission_artifacts" / "evidence_metadata.json")
    doris = load_json(ROOT / "submission_artifacts" / "evidence_snapshots" / "doris_cluster_evidence.json")
    topic_items, topic_summary = parse_topic_items(load_text(ROOT / "reports" / "topic_19_compliance_plan.md"))
    return {
        "metadata": metadata,
        "doris": doris,
        "topic_items": topic_items,
        "topic_summary": topic_summary,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_head_now": git_head(),
        "reference_projects": reference_project_inventory(),
        "reference_examples": reference_examples_inventory(),
    }


def wrap_label(text: str, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(text), width=width, break_long_words=False, replace_whitespace=False))


def figure_header(fig: Figure, spec: FigureSpec, left: float = 0.06) -> None:
    fig.text(left, 0.975, f"{spec.fig_id} | {spec.title}", ha="left", va="top", fontsize=7.2, fontweight="bold")
    fig.text(left, 0.94, wrap_label(spec.conclusion, 78), ha="left", va="top", fontsize=5.7, color=MUTED)


def add_source(fig: Figure, source: str, left: float = 0.06) -> None:
    fig.text(left, 0.02, f"Source: {source}", ha="left", va="bottom", fontsize=5.0, color=MUTED)


def panel_label(ax: Axes, label: str, x: float = -0.075, y: float = 1.045) -> None:
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="top", fontsize=8.0, fontweight="bold")


def clean_axes(ax: Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=2.5, width=0.6, colors=TEXT)


def axis_off(ax: Axes, xlim: tuple[float, float] = (0, 1), ylim: tuple[float, float] = (0, 1)) -> None:
    ax.set_axis_off()
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)


def thin_arrow(ax: Axes, start: tuple[float, float], end: tuple[float, float], color: str = INK) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={"arrowstyle": "-|>", "lw": 0.65, "color": color, "mutation_scale": 7, "shrinkA": 0, "shrinkB": 0},
    )


def reset_output() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / REFERENCE_GALLERY_DIRNAME).mkdir(parents=True, exist_ok=True)
    for dirname in FIG_DIRS.values():
        (OUT_DIR / dirname).mkdir(parents=True, exist_ok=True)


def save_figure(fig: Figure, spec: FigureSpec) -> dict[str, str]:
    folder = OUT_DIR / FIG_DIRS[spec.chart_class]
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / spec.filename
    paths = {
        "svg": base.with_suffix(".svg"),
        "pdf": base.with_suffix(".pdf"),
        "png": base.with_name(base.name + "_300dpi.png"),
        "tiff": base.with_name(base.name + "_600dpi.tiff"),
        "gray_png": base.with_name(base.name + "_gray_300dpi.png"),
    }
    fig.savefig(paths["svg"])
    fig.savefig(paths["pdf"])
    fig.savefig(paths["png"], dpi=300)
    fig.savefig(paths["tiff"], dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    Image.open(paths["png"]).convert("L").save(paths["gray_png"], dpi=(300, 300))
    plt.close(fig)
    return {key: str(value.relative_to(ROOT)) for key, value in paths.items()}


def _load_gallery_font(size: int) -> ImageFont.ImageFont:
    for font_name in ["arial.ttf", "DejaVuSans.ttf", "simhei.ttf"]:
        try:
            return ImageFont.truetype(font_name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _paste_fit(canvas: Image.Image, image_path: Path, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        img.thumbnail((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
        x = x0 + (x1 - x0 - img.width) // 2
        y = y0 + (y1 - y0 - img.height) // 2
        canvas.paste(img, (x, y))


def write_reference_gallery(metrics: dict) -> dict[str, object]:
    gallery = OUT_DIR / REFERENCE_GALLERY_DIRNAME
    gallery.mkdir(parents=True, exist_ok=True)
    examples = metrics["reference_examples"]

    title_font = _load_gallery_font(18)
    small_font = _load_gallery_font(13)
    thumb_w, thumb_h = 390, 235
    label_h = 50
    pad = 20
    cols = 3
    rows = (len(examples) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (thumb_w + pad) + pad, rows * (thumb_h + label_h + pad) + pad), "white")
    draw = ImageDraw.Draw(sheet)

    thumbnails: dict[str, str] = {}
    for i, example in enumerate(examples):
        row, col = divmod(i, cols)
        x = pad + col * (thumb_w + pad)
        y = pad + row * (thumb_h + label_h + pad)
        preview_path = ROOT / example["preview_path"]
        thumb_path = gallery / f"{example['id']}_{example['project']}_preview.png"

        if preview_path.exists():
            thumb = Image.new("RGB", (thumb_w, thumb_h), "white")
            _paste_fit(thumb, preview_path, (0, 0, thumb_w, thumb_h))
            thumb.save(thumb_path, dpi=(300, 300))
            _paste_fit(sheet, preview_path, (x, y + label_h, x + thumb_w, y + label_h + thumb_h))
            thumbnails[example["id"]] = str(thumb_path.relative_to(ROOT))
        else:
            draw.text((x + 120, y + label_h + 95), "preview missing", fill=(120, 120, 120), font=small_font)

        draw.text((x, y), f"{example['id']} {example['project']}", fill=(28, 28, 28), font=title_font)
        draw.text((x, y + 25), example["title"], fill=(86, 86, 86), font=small_font)
        draw.rectangle([x, y + label_h, x + thumb_w, y + label_h + thumb_h], outline=(190, 190, 190), width=1)

    contact_sheet = gallery / "reference_examples_contact_sheet.png"
    sheet.save(contact_sheet, dpi=(300, 300))

    lines = [
        "# 参考样例学习包",
        "",
        "本目录用于记录本轮重画前实际查看过的参考项目样例。它不是项目成果图，也不建议作为最终提交图件；作用是说明本项目图表的版式、配色、线宽、图例和导出规则来自哪些已安装参考项目。",
        "",
        f"样例接触表：`{contact_sheet.relative_to(ROOT)}`",
        "",
        "## 参考样例",
        "",
        "| 编号 | 项目 | 样例 | 源文件/脚本 | 预览 | 学到的绘图规则 | 应用到本项目 |",
        "|---|---|---|---|---|---|---|",
    ]
    for example in examples:
        preview = thumbnails.get(example["id"], "预览缺失")
        lines.append(
            f"| {example['id']} | {example['project']} | {example['title']} | `{example['relative_path']}` | `{preview}` | {example['learned_pattern']} | {example['applied_to']} |"
        )
    lines.extend(
        [
            "",
            "## 抽取后的统一规则",
            "",
            "1. 采用最终论文尺寸绘制，不做网页大屏比例。",
            "2. 定量图优先使用点图、区间图、矩阵图和 log-scale range plot，不使用指标卡、饼图、3D 图或无来源曲线。",
            "3. 主色采用 figures4papers 的深蓝，辅助色采用 Show2Know 低饱和论文配色，红/橙仅用于风险、阈值或边界。",
            "4. SVG/PDF 保持文字可编辑；PNG 用于预览；TIFF 用于高分辨率归档；灰度版用于检查脱离颜色后仍可阅读。",
            "5. 真实截图只做 image plate 编排，不重绘、不美化成虚假界面。",
        ]
    )
    (gallery / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "directory": str(gallery.relative_to(ROOT)),
        "contact_sheet": str(contact_sheet.relative_to(ROOT)),
        "thumbnails": thumbnails,
    }


def write_outputs(metrics: dict, rows: list[dict]) -> None:
    md = metrics["metadata"]
    d = metrics["doris"]
    reference_gallery = write_reference_gallery(metrics)
    reference_projects = metrics["reference_projects"]
    readme = [
        "# Plottie Style 科研图表证据包",
        "",
        f"生成时间：{metrics['generated_at_local']}",
        f"样式标准：`{STYLE_STANDARD}`",
        f"图包渲染时 Git HEAD：`{metrics['git_head_now']}`",
        f"Evidence metadata：`{md['generated_at']}`",
        f"Pytest：`{md['readiness']['pytest']['passed']} passed in {md['readiness']['pytest']['elapsed_seconds']:.2f}s`",
        f"Official suite：正例 `{md['official_suite']['positive']['passed']}/{md['official_suite']['positive']['total']}`，负例 `{md['official_suite']['negative']['passed']}/{md['official_suite']['negative']['total']}`",
        f"Doris speedup：`{md['doris_cluster']['speedup_display']}`；Doris evidence generated_at：`{d['generated_at']}`",
        f"参考样例接触表：`{reference_gallery['contact_sheet']}`",
        "",
        "## 已安装参考项目",
        "",
        "| 项目 | 本地 HEAD | 安装/接入状态 | 本轮用于 |",
        "|---|---|---|---|",
    ]
    for project in reference_projects:
        status = "PASS" if project["local_exists"] and project["install_checks_passed"] else "待核验"
        readme.append(
            f"| [{project['name']}]({project['url']}) | `{project['git_head']}` | {status}：{project['install_mode']} | {project['used_for']} |"
        )
    readme.extend(
        [
        "",
        "## 代码结构",
        "",
        "| 图类 | 代码文件 | Plottie 参考方式 |",
        "|---|---|---|",
        ]
    )
    for chart_class, info in PLOTTIE_AUDIT.items():
        readme.append(f"| {chart_class} | `{info['code_file']}` | {info['rule']} |")
    readme.extend(
        [
            "",
            "## 图表清单",
            "",
            "| 图号 | 图名 | 图类 | SVG | PDF | PNG | TIFF | 灰度 QA | 数据来源 |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        spec = row["spec"]
        paths = row["paths"]
        readme.append(
            f"| {spec.fig_id} | {spec.title} | {spec.chart_class} | `{paths['svg']}` | `{paths['pdf']}` | `{paths['png']}` | `{paths['tiff']}` | `{paths['gray_png']}` | {spec.source} |"
        )
    readme.extend(["", "## 证据边界", "", "Doris 性能图使用已经冻结的 Doris evidence snapshot，本轮只重画图，不现场重测 Doris。没有真实 source data 的 ROC、PR、loss、mAP 或训练曲线不生成。"])
    (OUT_DIR / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    notes = [
        "# Plottie 绘图依据与逐图说明",
        "",
        "本轮重写删除了旧单体绘图脚本，改为按图类拆分代码。Plottie 的作用是提供论文图型检索和视觉语法参考：不同证据类型对应不同图型，而不是把所有内容塞进同一种 dashboard 模板。",
        "",
        f"本轮同时安装并核验 figures4papers、Show2Know 和 nature-skills；参考样例接触表见：`{reference_gallery['contact_sheet']}`。",
        "",
        "## 外部参考",
        "",
        "| 来源 | 用途 |",
        "|---|---|",
    ]
    for name, url in PLOTTIE_LINKS:
        notes.append(f"| [{name}]({url}) | 图型分类、配色、尺寸或导出参考 |")
    notes.extend(["", "## 已安装 GitHub 参考项目", "", "| 项目 | 本地路径 | HEAD | 安装核验 | 应用方式 |", "|---|---|---|---|---|"])
    for project in reference_projects:
        status = "PASS" if project["local_exists"] and project["install_checks_passed"] else "待核验"
        notes.append(
            f"| [{project['name']}]({project['url']}) | `{project['relative_path']}` | `{project['git_head']}` | {status} | {project['used_for']} |"
        )
    notes.extend(["", "## 已查看参考样例", "", "| 编号 | 项目 | 样例 | 学到的规则 | 应用到本项目 |", "|---|---|---|---|---|"])
    for example in metrics["reference_examples"]:
        notes.append(
            f"| {example['id']} | {example['project']} | {example['title']} | {example['learned_pattern']} | {example['applied_to']} |"
        )
    notes.extend(["", "## 图类规则", "", "| 图类 | 代码文件 | 采用规则 |", "|---|---|---|"])
    for chart_class, info in PLOTTIE_AUDIT.items():
        notes.append(f"| {chart_class} | `{info['code_file']}` | {info['rule']} |")
    notes.extend(["", "## 逐图结论", "", "| 图号 | 结论 | 证据来源 |", "|---|---|---|"])
    for row in rows:
        spec = row["spec"]
        notes.append(f"| {spec.fig_id} | {spec.conclusion} | {spec.source} |")
    (OUT_DIR / "Plottie绘图依据与逐图说明.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    manifest = {
        "generated_at": metrics["generated_at_local"],
        "style_standard": STYLE_STANDARD,
        "git_head_at_render": metrics["git_head_now"],
        "metadata_generated_at": md["generated_at"],
        "git_head_at_export": md["git"]["head_at_export"],
        "pytest": md["readiness"]["pytest"],
        "official_suite": md["official_suite"],
        "doris": {
            "generated_at": d["generated_at"],
            "speedup": d["speedup"],
            "speedup_display": md["doris_cluster"]["speedup_display"],
            "baseline_avg_execute_ms": d["baseline"]["avg_execute_ms"],
            "optimized_avg_execute_ms": d["optimized"]["avg_execute_ms"],
            "baseline_p95_execute_ms": d["baseline"]["p95_execute_ms"],
            "optimized_p95_execute_ms": d["optimized"]["p95_execute_ms"],
            "row_counts_match": d["row_counts_match"],
            "note": "Doris latency was not re-measured in this figure generation run.",
        },
        "references": [{"name": name, "url": url} for name, url in PLOTTIE_LINKS],
        "reference_projects": reference_projects,
        "reference_examples": metrics["reference_examples"],
        "reference_gallery": reference_gallery,
        "chart_class_audit": PLOTTIE_AUDIT,
        "figures": [
            {
                "id": row["spec"].fig_id,
                "title": row["spec"].title,
                "chart_class": row["spec"].chart_class,
                "source": row["spec"].source,
                "proof": row["spec"].proof,
                "conclusion": row["spec"].conclusion,
                **row["paths"],
            }
            for row in rows
        ],
    }
    (OUT_DIR / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for chart_class, dirname in FIG_DIRS.items():
        info = PLOTTIE_AUDIT[chart_class]
        lines = [
            f"# {dirname}",
            "",
            f"代码文件：`{info['code_file']}`",
            f"绘图规则：{info['rule']}",
            "",
            "| 图号 | 文件名 |",
            "|---|---|",
        ]
        for row in rows:
            if row["spec"].chart_class == chart_class:
                lines.append(f"| {row['spec'].fig_id} | `{row['spec'].filename}` |")
        (OUT_DIR / dirname / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
