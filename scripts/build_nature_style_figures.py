from __future__ import annotations

import datetime as dt
import json
import math
import re
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Rectangle
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "可视化证据包_nature_style"

NATURE_SINGLE_IN = 89 / 25.4
NATURE_DOUBLE_IN = 183 / 25.4
NATURE_MAX_HEIGHT_IN = 170 / 25.4
STYLE_STANDARD = "Nature figure mode v2 - paper-first Python/matplotlib figures"

# Restrained Nature-style palette. Text stays black/grey; colour is used for
# data marks, boundary lines and evidence state, not decorative panels.
INK = "#1F1F1F"
TEXT = "#3E3E3E"
MUTED = "#6D6D6D"
RULE = "#BDBDBD"
PALE = "#F2F2F2"
BLUE = "#0F4D92"
BLUE_SOFT = "#DCE8F5"
ACCENT = "#B64342"
ACCENT_SOFT = "#F0D5D2"
WHITE = "#FFFFFF"


FIG_DIRS = {
    "topic": "01_赛题与方法示意图",
    "architecture": "02_架构与代码示意图",
    "operation": "03_运行核验流程图",
    "algorithm": "04_算法机制图",
    "validation": "05_验证与符合性图",
    "performance": "06_性能证据图",
    "special": "07_专项机制与边界图",
    "image_plate": "08_界面证据图像板",
    "delivery": "09_交付结构图",
}

REFERENCE_LINKS = [
    ("Nature Research Figure Guide: preparing figures",
     "https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/"),
    ("Nature Research Figure Guide: building and exporting figure panels",
     "https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/"),
    ("Matplotlib rcParams and savefig documentation",
     "https://matplotlib.org/stable/users/explain/customizing.html"),
    ("SciencePlots publication styles",
     "https://github.com/garrettj403/SciencePlots"),
    ("cnsplots publication-ready Cell/Nature/Science plotting patterns",
     "https://github.com/faridrashidi/cnsplots"),
    ("figures4papers scientific matplotlib examples",
     "https://github.com/ChenLiu-1996/figures4papers"),
    ("Wong, B. Colour blindness, Nature Methods",
     "https://www.nature.com/articles/nmeth.1618"),
]


@dataclass(frozen=True)
class FigureSpec:
    fig_id: str
    title: str
    category: str
    source: str
    proof: str
    filename: str
    archetype: str
    conclusion: str
    redesign: str
    reference_pattern: str


SPECS = [
    FigureSpec(
        "FIG-01",
        "赛题任务拆解",
        "topic",
        "README + topic compliance + evidence metadata",
        "问题定义与得分点拆解",
        "FIG-01_topic_task_breakdown",
        "schematic-led composite + quantitative summary",
        "赛题能力可以拆成输入、编译、验证、性能和交付五条可审计证据链。",
        "panel a 使用线稿证据链；panel b 使用真实要求状态计数，不做指标卡。",
        "Nature schematic-led composite; cnsplots horizontal bar style",
    ),
    FigureSpec(
        "FIG-02",
        "输入-处理-输出链路",
        "topic",
        "README + technical report + evidence metadata",
        "端到端闭环",
        "FIG-02_input_process_output_pipeline",
        "method schematic",
        "自然语言或 DSL 候选必须经过确定性编译与验证后才进入 Doris SQL。",
        "用 trust-boundary 线稿显示 LLM 候选、编译器门禁和可执行 SQL 的责任边界。",
        "Nature editable method schematic; no decorative icons",
    ),
    FigureSpec(
        "FIG-03",
        "项目总体架构",
        "architecture",
        "PROJECT_INDEX + src + configs",
        "系统分层架构",
        "FIG-03_system_architecture",
        "paper architecture schematic",
        "项目由入口、适配、编译、配置、验证和证据交付六层组成。",
        "以分层表格和跨层调用线呈现工程结构，避免彩色模块卡片。",
        "Nature space-efficient panel arrangement; figures4papers GridSpec",
    ),
    FigureSpec(
        "FIG-04",
        "核心模块调用关系",
        "architecture",
        "src/findsl/*.py",
        "代码可追溯",
        "FIG-04_code_module_call_graph",
        "network schematic",
        "CLI 将编译、验证、官方套件、Demo 与提交证据统一到同一工程链路。",
        "用无填充节点和细线表示调用图，突出核心模块而非界面效果。",
        "method graph / direct labelling",
    ),
    FigureSpec(
        "FIG-05",
        "运行与人工核验流程",
        "operation",
        "SCREENSHOT_EVIDENCE_INDEX + evidence metadata",
        "复现流程",
        "FIG-05_operation_acceptance_flow",
        "acceptance timeline",
        "验收流程从环境、命令、测试、证据到提交状态逐层收口。",
        "改为纵向 checkpoint timeline，并标注证据类型，不使用流程卡片。",
        "clinical timeline / checkpoint strip",
    ),
    FigureSpec(
        "FIG-06",
        "DSL 编译核心算法",
        "algorithm",
        "compiler.py + parser.py + semantic.py",
        "核心算法",
        "FIG-06_dsl_compiler_algorithm",
        "algorithm schematic",
        "FinDSL 先形成 typed AST，再生成可验证的 Doris-safe SQL。",
        "用解析状态机、错误分支和 SQL 输出三部分解释算法，不画装饰型流程。",
        "method schematic + error branch",
    ),
    FigureSpec(
        "FIG-07",
        "Prefix-Sum 长窗口优化",
        "algorithm",
        "sqlgen.py + prefix_sum_benchmark + Doris evidence",
        "性能算法",
        "FIG-07_prefix_sum_optimization_flow",
        "formula + quantitative inset",
        "滚动 SUM 可在满足条件时改写为前缀表访问，并保留窗口函数回退路径。",
        "把核心公式、回退条件和实测加速拆成公式面板与小型证据面板。",
        "formula-led method schematic + dot comparison",
    ),
    FigureSpec(
        "FIG-08",
        "Doris 执行计划差异",
        "performance",
        "doris_cluster_evidence.md/json",
        "执行计划证据",
        "FIG-08_doris_plan_comparison",
        "plan tree + binary matrix",
        "优化路径把运行时窗口聚合替换为 prefix-table predicate 与 join。",
        "左侧为 explain plan tree；右侧为计划特征矩阵，避免把 plan 画成 PPT 模块。",
        "binary heatmap / plan tree",
    ),
    FigureSpec(
        "FIG-09",
        "Doris 延迟与加速比",
        "performance",
        "doris_cluster_evidence.json",
        "性能达标",
        "FIG-09_doris_latency_speedup",
        "quantitative dot-range plot",
        "prefix-sum 优化在已采集 Doris evidence 中达到 36x 级延迟下降。",
        "采用 log-scale paired dot-range 和 speedup inset，保留未重测 Doris 的口径说明。",
        "cnsplots forest/range plot; Matplotlib log axis",
    ),
    FigureSpec(
        "FIG-10",
        "测试验证结果",
        "validation",
        "evidence_metadata.json",
        "门禁通过证据",
        "FIG-10_validation_matrix",
        "lollipop plot + evidence table",
        "最新证据显示 required gates 全通过，warning count 为 0。",
        "pass fraction 用 lollipop 展示，关键数值放小表，不再做 dashboard 指标卡。",
        "lollipop / compact evidence table",
    ),
    FigureSpec(
        "FIG-11",
        "赛题要求-实现-证据矩阵",
        "validation",
        "reports/topic_19_compliance_plan.md",
        "符合性证据",
        "FIG-11_requirement_implementation_evidence_matrix",
        "requirement heatmap",
        "已实现、部分实现和待补证据必须如实分开表达。",
        "以状态热图和计数条形图如实呈现 implemented、partial、needs_evidence。",
        "status heatmap / horizontal summary bar",
    ),
    FigureSpec(
        "FIG-12",
        "NL2DSL 与 LLM 安全边界",
        "special",
        "submission readiness + llm_adapter.py",
        "AI 安全边界",
        "FIG-12_llm_safety_boundary",
        "trust-boundary schematic",
        "LLM 只产生候选 DSL，执行权由编译器和验证器控制。",
        "用垂直边界线和 reject branch 呈现安全控制，不把 AI 能力夸大成直接执行。",
        "trust boundary schematic",
    ),
    FigureSpec(
        "FIG-13",
        "配置化扩展机制",
        "special",
        "configs + registry + tests",
        "扩展机制",
        "FIG-13_configurable_extension",
        "bipartite dependency graph",
        "指标、函数和表配置通过 Registry 同时服务语义、SQL、reference 与测试。",
        "用配置到消费者的二分图表达解耦关系，突出 0 行核心代码改动边界。",
        "dependency graph / direct labelling",
    ),
    FigureSpec(
        "FIG-14",
        "Doris 部署与数据流",
        "special",
        "deploy/doris + Doris evidence",
        "实验环境说明",
        "FIG-14_doris_deployment_data_flow",
        "infrastructure schematic",
        "Doris 证据从 DDL、prefix 表、采集脚本进入 evidence snapshot。",
        "改为实验管线线稿，区分环境准备、SQL 执行和证据冻结。",
        "method/infrastructure schematic",
    ),
    FigureSpec(
        "FIG-15",
        "Web Demo 图像证据板",
        "image_plate",
        "EV-041 to EV-048 screenshots",
        "界面证据",
        "FIG-15_web_demo_image_plate",
        "image plate",
        "Demo 截图应作为真实图像证据板展示，而不是把截图索引画成说明卡。",
        "使用实际截图 image plate，统一 panel 字母、边框和 gutter。",
        "Nature image plate layout",
    ),
    FigureSpec(
        "FIG-16",
        "结果与交付包结构",
        "delivery",
        "PROJECT_INDEX + evidence_manifest",
        "交付完整性",
        "FIG-16_delivery_package_map",
        "delivery tree schematic",
        "最终交付物围绕源码、配置、数据、测试、文档和 evidence snapshots 组织。",
        "用树形线稿表示项目交付结构，不用目录卡片或网页式列表。",
        "tree schematic / direct labels",
    ),
    FigureSpec(
        "FIG-17",
        "真实样本与规模证据边界",
        "special",
        "README + real samples + Doris evidence",
        "数据口径边界",
        "FIG-17_real_sample_vs_scale_evidence",
        "evidence boundary matrix",
        "真实行情样本证明语义可信性，5M Doris evidence 证明规模性能，两者不能混为同一数据集。",
        "用双证据泳道和小矩阵说明口径边界，防止答辩时过度宣称。",
        "claim-boundary figure / evidence matrix",
    ),
]


FIGURE_SEARCH_AUDIT = {
    "FIG-01": {
        "search_queries": "Nature schematic composite, cnsplots horizontal bar, publication-ready requirement evidence bar",
        "best_code_pattern": "GridSpec 双面板；左侧无填充 method timeline，右侧 horizontal barh；不用指标卡。",
        "style_contract": "双栏宽，黑灰线稿为主体，深蓝只标已实现主链路，红色只标需补证据项。",
    },
    "FIG-02": {
        "search_queries": "Nature method schematic trust boundary, editable SVG schematic matplotlib, LLM safety workflow figure",
        "best_code_pattern": "细箭头 pipeline + trust-boundary 竖线 + reject branch；直接标签代替图例。",
        "style_contract": "白底线稿，少量边界虚线，不使用 AI 图标、渐变、发光或卡片。",
    },
    "FIG-03": {
        "search_queries": "Nature system architecture schematic, figures4papers GridSpec architecture, software method schematic",
        "best_code_pattern": "分层结构表 + 跨层调用细线；每层只保留必要术语和依赖方向。",
        "style_contract": "工程架构以论文 method schematic 表达，避免 PPT 模块堆叠。",
    },
    "FIG-04": {
        "search_queries": "scientific call graph figure direct labelling, method network schematic matplotlib",
        "best_code_pattern": "无填充节点、细线边、直接标注；强调核心入口与核心模块。",
        "style_contract": "所有节点同一视觉权重，只用深蓝标主入口，防止变成彩色系统图。",
    },
    "FIG-05": {
        "search_queries": "Nature checklist timeline figure, acceptance workflow timeline, clinical checkpoint strip",
        "best_code_pattern": "纵向 checkpoint timeline + 证据类型小标签；不用流程卡片。",
        "style_contract": "时间线只表达复现顺序和验收门禁，注释短句放图内，细节放文档。",
    },
    "FIG-06": {
        "search_queries": "compiler algorithm schematic typed AST SQL generation figure, Nature method algorithm diagram",
        "best_code_pattern": "解析状态机 + 语义错误分支 + SQL 输出路径；用线条说明算法责任边界。",
        "style_contract": "算法图不做商业宣传式图标，核心是输入、状态、门禁、输出。",
    },
    "FIG-07": {
        "search_queries": "prefix sum optimization formula figure, rolling window optimization schematic, scientific formula inset plot",
        "best_code_pattern": "公式主面板 + fallback 条件 + 小型 paired dot 证据；不用夸张速度仪表盘。",
        "style_contract": "公式与证据共图但分 panel，定量点只来自真实 benchmark/evidence。",
    },
    "FIG-08": {
        "search_queries": "database query plan tree figure, binary heatmap feature matrix, Nature methods plan comparison",
        "best_code_pattern": "左侧 plan tree，右侧 binary feature matrix；计划特征用 0/1 热图表达。",
        "style_contract": "执行计划不画成彩色系统流程，保持可读的数据库证据口径。",
    },
    "FIG-09": {
        "search_queries": "Nature log scale latency dot range plot, forest plot speedup matplotlib, cnsplots range plot",
        "best_code_pattern": "log-scale paired dot-range + speedup inset；baseline 空心点，optimized 实心点。",
        "style_contract": "不画大色块 speedup bar；保留 evidence reused / not rerun 说明。",
    },
    "FIG-10": {
        "search_queries": "validation gate lollipop plot, compact evidence table Nature figure, pass fraction scientific plot",
        "best_code_pattern": "lollipop pass fraction + 小表格 inset；门禁结果按比例和计数分开显示。",
        "style_contract": "PASS 不是 UI 徽章，改成可复核比例图和审计表。",
    },
    "FIG-11": {
        "search_queries": "requirement implementation evidence matrix, status heatmap publication figure, compliance matrix scientific plot",
        "best_code_pattern": "状态 heatmap + 计数条形图；implemented/partial/needs_evidence 如实分色。",
        "style_contract": "矩阵图必须保留部分实现与待证据边界，不把风险项美化成全绿。",
    },
    "FIG-12": {
        "search_queries": "LLM guardrail trust boundary schematic, safe AI workflow scientific figure, reject branch method schematic",
        "best_code_pattern": "候选生成、编译门禁、reference oracle 三段式；reject 分支用虚线。",
        "style_contract": "明确 LLM 不直接执行 SQL，不夸大模型自主决策能力。",
    },
    "FIG-13": {
        "search_queries": "configuration registry dependency graph, extensible software architecture bipartite graph",
        "best_code_pattern": "配置文件到消费者模块的二分图；边线显示解耦关系。",
        "style_contract": "突出配置化扩展的工程机制，不做产品功能卡片。",
    },
    "FIG-14": {
        "search_queries": "Doris deployment data pipeline schematic, database evidence pipeline Nature methods, infrastructure method figure",
        "best_code_pattern": "环境准备、DDL/load、evidence snapshot 三段 pipeline；区别现场环境与冻结证据。",
        "style_contract": "部署图只说明实验链路，不把本地 Doris 状态伪装成实时在线。",
    },
    "FIG-15": {
        "search_queries": "Nature image plate layout, screenshot evidence plate, multi-panel image plate matplotlib",
        "best_code_pattern": "实际截图 image plate；统一 gutters、细边框、panel label；不叠加假 UI。",
        "style_contract": "所有画面来自现有截图文件，不重绘、伪造或遮盖关键状态。",
    },
    "FIG-16": {
        "search_queries": "scientific tree schematic direct labels, software delivery package map figure",
        "best_code_pattern": "树形交付结构线稿；目录说明用短标签和右侧释义列。",
        "style_contract": "交付结构不做目录卡片，按审计树显示源码、数据、测试、文档、证据。",
    },
    "FIG-17": {
        "search_queries": "claim boundary evidence matrix, data provenance lane figure, scientific evidence boundary diagram",
        "best_code_pattern": "双证据泳道 + 0/1 矩阵；真实样本和规模性能分开证明。",
        "style_contract": "防止把小样本业务真实性与 5M Doris 性能混为一类证据。",
    },
}


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def reference_inventory() -> list[dict[str, str]]:
    base = ROOT / "external_references" / "scientific_figure_code"
    inventory: list[dict[str, str]] = []
    for name in ["SciencePlots", "cnsplots", "figures4papers"]:
        repo = base / name
        if not repo.exists():
            inventory.append({"name": name, "local_cache": "missing", "head": "unknown"})
            continue
        try:
            head = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            head = "not-a-git-repo"
        inventory.append({"name": name, "local_cache": "present", "head": head})
    return inventory


def setup_style() -> None:
    cjk_candidates = [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Arial Unicode MS",
    ]
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    cjk_font = next((font for font in cjk_candidates if font in available_fonts), None)
    sans_stack = ([cjk_font] if cjk_font else []) + [
        "Arial",
        "Helvetica",
        "DejaVu Sans",
        "Liberation Sans",
        "sans-serif",
    ]
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": sans_stack,
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "font.size": 6.5,
            "axes.labelsize": 6.5,
            "axes.titlesize": 7.0,
            "xtick.labelsize": 5.8,
            "ytick.labelsize": 5.8,
            "legend.fontsize": 5.8,
            "axes.linewidth": 0.6,
            "lines.linewidth": 0.8,
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
            "savefig.pad_inches": 0.03,
        }
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_topic_items(text: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    items: list[dict[str, str]] = []
    for line in text.splitlines():
        if line.startswith("| T19-R"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 5:
                items.append(
                    {
                        "id": parts[0],
                        "requirement": parts[1],
                        "status": parts[2],
                        "evidence": parts[3],
                        "next": parts[4],
                    }
                )
    summary = {"implemented": 0, "partial": 0, "needs_evidence": 0}
    for item in items:
        if item["status"] in summary:
            summary[item["status"]] += 1
    return items, summary


def parse_eval_latencies(text: str) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for line in text.splitlines():
        if not line.startswith("| ") or "Latency" in line or "---" in line:
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 3 and parts[1] in {"True", "False"}:
            try:
                rows.append((parts[0], float(parts[2])))
            except ValueError:
                pass
    return rows


def latest_metrics() -> dict:
    metadata = load_json(ROOT / "submission_artifacts" / "evidence_metadata.json")
    doris = load_json(ROOT / "submission_artifacts" / "evidence_snapshots" / "doris_cluster_evidence.json")
    topic_items, topic_summary = parse_topic_items(load_text(ROOT / "reports" / "topic_19_compliance_plan.md"))
    eval_path = ROOT / "submission_artifacts" / "evidence_snapshots" / "evaluation_report.md"
    prefix_path = ROOT / "submission_artifacts" / "evidence_snapshots" / "prefix_sum_benchmark.md"
    visual_summary_path = ROOT / "submission_artifacts" / "visual_evidence" / "visual_evidence_summary.json"
    return {
        "metadata": metadata,
        "doris": doris,
        "topic_items": topic_items,
        "topic_summary": topic_summary,
        "eval_rows": parse_eval_latencies(load_text(eval_path)),
        "prefix_report": load_text(prefix_path),
        "visual_summary": load_json(visual_summary_path) if visual_summary_path.exists() else {},
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_head_now": git_head(),
        "reference_inventory": reference_inventory(),
    }


def wrap_label(text: str, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(text), width=width, break_long_words=False, replace_whitespace=False))


def figure_header(fig: Figure, spec: FigureSpec, left: float = 0.06) -> None:
    fig.text(left, 0.975, f"{spec.fig_id} | {spec.title}", ha="left", va="top", fontsize=7.0, fontweight="bold")
    fig.text(left, 0.94, wrap_label(spec.conclusion, 72), ha="left", va="top", fontsize=5.6, color=MUTED)


def add_source(fig: Figure, text: str, left: float = 0.06) -> None:
    fig.text(left, 0.02, f"Source: {text}", ha="left", va="bottom", fontsize=5.0, color=MUTED)


def panel_label(ax: Axes, label: str, x: float = -0.08, y: float = 1.04) -> None:
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="top", fontsize=8.0, fontweight="bold")


def clean_axes(ax: Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=2.5, width=0.6, colors=TEXT)


def axis_off(ax: Axes, xlim: tuple[float, float] = (0, 1), ylim: tuple[float, float] = (0, 1)) -> None:
    ax.set_axis_off()
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)


def thin_arrow(ax: Axes, start: tuple[float, float], end: tuple[float, float], color: str = INK, lw: float = 0.65) -> None:
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={"arrowstyle": "-|>", "lw": lw, "color": color, "shrinkA": 0, "shrinkB": 0, "mutation_scale": 7},
    )


def stage_axis(ax: Axes, labels: list[str], y: float = 0.5, x0: float = 0.08, x1: float = 0.92, emph: set[int] | None = None) -> None:
    emph = emph or set()
    xs = [x0 + i * (x1 - x0) / (len(labels) - 1) for i in range(len(labels))]
    ax.plot([x0, x1], [y, y], color=INK, lw=0.65)
    for i, (x, label) in enumerate(zip(xs, labels)):
        color = BLUE if i in emph else WHITE
        ax.add_patch(Circle((x, y), 0.012, facecolor=color, edgecolor=INK, linewidth=0.55, zorder=3))
        ax.plot([x, x], [y - 0.035, y + 0.035], color=INK, lw=0.45, zorder=2)
        ax.text(x, y + 0.07, wrap_label(label, 12), ha="center", va="bottom", fontsize=5.8)


def text_node(ax: Axes, x: float, y: float, label: str, marker: str = "o", color: str = WHITE, size: float = 0.014) -> None:
    ax.scatter([x], [y], s=(size * 900) ** 2 / 100, marker=marker, facecolor=color, edgecolor=INK, linewidth=0.55, zorder=3)
    ax.text(x, y - 0.05, wrap_label(label, 16), ha="center", va="top", fontsize=5.8)


def horizontal_barh(ax: Axes, labels: list[str], values: list[float], colors: list[str], xlabel: str, xlim: tuple[float, float] | None = None) -> None:
    y = list(range(len(labels)))
    ax.barh(y, values, color=colors, edgecolor=INK, linewidth=0.35, height=0.44)
    ax.set_yticks(y, labels)
    ax.set_xlabel(xlabel)
    if xlim:
        ax.set_xlim(*xlim)
    ax.invert_yaxis()
    clean_axes(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def save_figure(fig: Figure, spec: FigureSpec) -> dict[str, str]:
    folder = OUT_DIR / FIG_DIRS[spec.category]
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
    return {k: str(v.relative_to(ROOT)) for k, v in paths.items()}


def fig_01(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 3.65))
    gs = fig.add_gridspec(1, 2, left=0.06, right=0.98, top=0.83, bottom=0.17, width_ratios=[1.35, 0.9], wspace=0.28)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    stage_axis(ax_a, ["input", "DSL/AST", "Doris SQL", "reference", "performance", "evidence"], y=0.62, emph={1, 2, 4})
    ax_a.plot([0.08, 0.92], [0.31, 0.31], color=RULE, lw=0.5)
    ax_a.text(0.08, 0.38, "audit chain", fontsize=5.8, fontweight="bold")
    ax_a.text(0.08, 0.24, "Every claim is linked to code, tests or evidence snapshots.", fontsize=5.4, color=MUTED)
    panel_label(ax_b, "b")
    summary = m["topic_summary"]
    labels = ["implemented", "partial", "needs evidence"]
    values = [summary["implemented"], summary["partial"], summary["needs_evidence"]]
    horizontal_barh(ax_b, labels, values, [BLUE, "#8E8E8E", ACCENT], "requirement count", (0, max(values) + 1))
    for y, v in enumerate(values):
        ax_b.text(v + 0.08, y, str(v), va="center", fontsize=5.8)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_02(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(NATURE_DOUBLE_IN, 3.35))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.82, bottom=0.16)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    xs = [0.08, 0.25, 0.43, 0.61, 0.80, 0.93]
    labels = ["Chinese\nrequest", "candidate\nDSL", "lexer\nparser", "semantic\ngates", "Doris-safe\nSQL", "evidence\nsnapshot"]
    for i, (x, label) in enumerate(zip(xs, labels)):
        ax.plot([x, x], [0.42, 0.68], color=INK if i != 3 else BLUE, lw=0.65)
        ax.text(x, 0.73, label, ha="center", va="bottom", fontsize=5.8)
        if i < len(xs) - 1:
            thin_arrow(ax, (x + 0.035, 0.55), (xs[i + 1] - 0.035, 0.55), BLUE if i in {2, 3} else INK)
    ax.axvline(0.34, ymin=0.18, ymax=0.88, color=RULE, lw=0.7, ls="--")
    ax.text(0.345, 0.22, "trust boundary", rotation=90, va="bottom", ha="left", fontsize=5.2, color=MUTED)
    thin_arrow(ax, (0.25, 0.43), (0.25, 0.23), ACCENT, lw=0.55)
    ax.text(0.25, 0.16, "reject direct SQL / unknown indicator", ha="center", va="top", fontsize=5.3, color=TEXT)
    ax.text(0.61, 0.25, "Only verified DSL reaches execution path.", ha="center", fontsize=5.5, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_03(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 4.65))
    fig.subplots_adjust(left=0.05, right=0.98, top=0.85, bottom=0.10)
    figure_header(fig, spec)
    ax = fig.add_axes([0.06, 0.14, 0.90, 0.68])
    panel_label(ax, "a")
    axis_off(ax)
    layers = [
        ("entry", ["CLI", "Web Demo", "JSON API", "docs"]),
        ("adapter", ["NL2DSL", "LLM candidate", "diagnostics"]),
        ("compiler", ["lexer", "parser", "typed AST", "semantic", "sqlgen"]),
        ("metadata", ["indicators", "functions", "tables", "samples"]),
        ("validation", ["reference", "official suite", "readiness", "Doris evidence"]),
        ("delivery", ["snapshots", "screenshots", "figures", "defense assets"]),
    ]
    y_positions = [0.86 - i * 0.14 for i in range(len(layers))]
    ax.plot([0.18, 0.18], [0.10, 0.90], color=RULE, lw=0.6)
    ax.plot([0.84, 0.84], [0.10, 0.90], color=RULE, lw=0.6)
    for (name, modules), y in zip(layers, y_positions):
        ax.plot([0.12, 0.90], [y - 0.055, y - 0.055], color=RULE, lw=0.45)
        ax.text(0.13, y, name, ha="left", va="center", fontsize=6.2, fontweight="bold")
        for j, module in enumerate(modules):
            x = 0.30 + j * (0.50 / max(1, len(modules) - 1))
            ax.text(x, y, module, ha="center", va="center", fontsize=5.5, color=TEXT)
            if name == "compiler":
                ax.plot([x - 0.035, x + 0.035], [y - 0.032, y - 0.032], color=BLUE, lw=0.8)
    for y1, y2 in zip(y_positions, y_positions[1:]):
        thin_arrow(ax, (0.86, y1 - 0.035), (0.86, y2 + 0.035), BLUE, lw=0.5)
    ax.text(0.92, 0.48, "compile -> validate -> freeze", rotation=90, ha="center", va="center", fontsize=5.2, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_04(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(NATURE_DOUBLE_IN, 4.0))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.84, bottom=0.14)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    center = (0.50, 0.58)
    ax.add_patch(Circle(center, 0.040, facecolor=WHITE, edgecolor=BLUE, linewidth=0.85))
    ax.text(center[0], center[1] + 0.075, "cli.py", ha="center", fontsize=6.2, fontweight="bold")
    nodes = [
        ("compiler\nparser semantic sqlgen", 0.16, 0.72),
        ("reference\nexecutor", 0.22, 0.32),
        ("official\nsuite", 0.50, 0.20),
        ("web demo\napi", 0.78, 0.32),
        ("readiness\nevidence", 0.84, 0.72),
    ]
    for label, x, y in nodes:
        ax.add_patch(Circle((x, y), 0.025, facecolor=WHITE, edgecolor=INK, linewidth=0.6))
        ax.text(x, y - 0.055, label, ha="center", va="top", fontsize=5.5)
        ax.plot([center[0], x], [center[1], y], color=BLUE if "compiler" in label else RULE, lw=0.65)
    ax.text(0.50, 0.86, "one command surface; multiple evidence-producing paths", ha="center", fontsize=5.6, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_05(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(NATURE_DOUBLE_IN, 4.6))
    fig.subplots_adjust(left=0.11, right=0.96, top=0.84, bottom=0.12)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax, (0, 1), (0, 1))
    steps = [
        ("environment", "Python / MySQL client / optional Doris"),
        ("compile smoke", "CLI compile + SQL output"),
        ("pytest", f"{m['metadata']['readiness']['pytest']['passed']} passed"),
        ("official suite", "37 positive + 37 negative"),
        ("readiness", "blocking gates PASS"),
        ("Doris evidence", m["metadata"]["doris_cluster"]["speedup_display"]),
        ("screenshots", "actual terminal / file / demo evidence"),
        ("submission", "manifest + package review"),
    ]
    xs = [0.12, 0.88]
    ax.plot([xs[0], xs[0]], [0.14, 0.86], color=INK, lw=0.65)
    for i, (step, detail) in enumerate(steps):
        y = 0.84 - i * 0.095
        ax.add_patch(Circle((xs[0], y), 0.012, facecolor=BLUE if i in {2, 3, 4, 5} else WHITE, edgecolor=INK, linewidth=0.55))
        ax.text(0.17, y + 0.012, step, ha="left", va="center", fontsize=5.9, fontweight="bold")
        ax.text(0.40, y + 0.012, detail, ha="left", va="center", fontsize=5.5, color=TEXT)
        ax.plot([0.17, xs[1]], [y - 0.030, y - 0.030], color=RULE, lw=0.35)
    ax.text(0.17, 0.065, "The timeline is a reproducibility checklist, not a decorative process map.", fontsize=5.2, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_06(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 4.15))
    gs = fig.add_gridspec(1, 3, left=0.06, right=0.98, top=0.82, bottom=0.15, wspace=0.26)
    figure_header(fig, spec)
    panels = [
        ("a", "lex / parse", ["FinDSL text", "token stream", "AST nodes"]),
        ("b", "semantic", ["type binding", "window legality", "indicator registry"]),
        ("c", "SQL generation", ["feature layers", "CTE/rank/window", "Doris validation"]),
    ]
    for idx, (letter, title, rows) in enumerate(panels):
        ax = fig.add_subplot(gs[0, idx])
        panel_label(ax, letter)
        axis_off(ax)
        ax.text(0.05, 0.91, title, ha="left", va="top", fontsize=6.4, fontweight="bold")
        y0 = 0.74
        for i, row in enumerate(rows):
            y = y0 - i * 0.20
            ax.plot([0.10, 0.82], [y, y], color=BLUE if idx == 1 and i == 1 else INK, lw=0.7)
            ax.add_patch(Circle((0.10, y), 0.010, facecolor=WHITE, edgecolor=INK, linewidth=0.5))
            ax.text(0.16, y + 0.012, row, ha="left", va="center", fontsize=5.6)
            if i < len(rows) - 1:
                thin_arrow(ax, (0.46, y - 0.025), (0.46, y - 0.155), lw=0.45)
        if idx == 1:
            ax.plot([0.44, 0.78], [0.22, 0.12], color=ACCENT, lw=0.55, ls="--")
            ax.text(0.39, 0.08, "fail fast before SQL", fontsize=5.1, color=TEXT)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def extract_prefix_smoke(prefix_report: str) -> dict[str, float | str | bool]:
    result: dict[str, float | str | bool] = {}
    match = re.search(r"Local SQLite speedup smoke:\s*([0-9.]+)x", prefix_report)
    if match:
        result["sqlite_speedup"] = float(match.group(1))
    for line in prefix_report.splitlines():
        if line.startswith("| baseline_window"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            result["sqlite_baseline"] = float(parts[2])
        if line.startswith("| optimized_prefix_sum"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            result["sqlite_optimized"] = float(parts[2])
    return result


def fig_07(spec: FigureSpec, m: dict) -> dict[str, str]:
    d = m["doris"]
    smoke = extract_prefix_smoke(m["prefix_report"])
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 4.1))
    gs = fig.add_gridspec(1, 2, left=0.07, right=0.97, top=0.82, bottom=0.16, width_ratios=[1.25, 0.95], wspace=0.35)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    ax_a.text(0.04, 0.76, "rolling window", fontsize=6.3, fontweight="bold")
    ax_a.text(0.04, 0.64, "SUM(x, w) = x[t-w+1] + ... + x[t]", fontsize=6.0)
    ax_a.text(0.04, 0.43, "prefix rewrite", fontsize=6.3, fontweight="bold")
    ax_a.text(0.04, 0.31, "SUM(x, w) = prefix[t] - prefix[t-w]", fontsize=6.0)
    ax_a.plot([0.04, 0.88], [0.53, 0.53], color=RULE, lw=0.55)
    thin_arrow(ax_a, (0.50, 0.56), (0.50, 0.47), BLUE)
    ax_a.text(0.04, 0.13, "Guard: use prefix table only when registry metadata and table assets prove the path is available.", fontsize=5.1, color=MUTED)
    panel_label(ax_b, "b")
    y = [1, 0]
    labels = ["Doris evidence", "SQLite smoke"]
    speedups = [d["speedup"], float(smoke.get("sqlite_speedup", 1.0))]
    ax_b.hlines(y, [1, 1], speedups, color=RULE, lw=0.8)
    ax_b.scatter([1, 1], y, s=18, facecolor=WHITE, edgecolor=INK, linewidth=0.6, label="baseline")
    ax_b.scatter(speedups, y, s=24, facecolor=BLUE, edgecolor=INK, linewidth=0.4, label="optimized")
    ax_b.axvline(d["min_speedup"], color=ACCENT, lw=0.7, ls="--")
    ax_b.text(d["min_speedup"] * 1.05, 1.23, "10x target", fontsize=5.1, color=TEXT)
    ax_b.set_xscale("log")
    ax_b.set_xlabel("relative speedup (x, log scale)")
    ax_b.set_yticks(y, labels)
    ax_b.set_xlim(0.8, max(speedups) * 1.5)
    clean_axes(ax_b)
    ax_b.legend(loc="lower right", fontsize=5.2)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_08(spec: FigureSpec, m: dict) -> dict[str, str]:
    d = m["doris"]
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 4.15))
    gs = fig.add_gridspec(1, 2, left=0.06, right=0.98, top=0.82, bottom=0.17, width_ratios=[1.35, 1.0], wspace=0.32)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    x_base, x_opt = 0.25, 0.70
    plan_y = [0.78, 0.56, 0.34]
    base_nodes = ["VOlapScan", "VSORT", "VANALYTIC\nwindow SUM"]
    opt_nodes = ["prefix scan\npredicate", "VHASH JOIN", "base scan\nruntime filters"]
    for nodes, x, color in [(base_nodes, x_base, ACCENT), (opt_nodes, x_opt, BLUE)]:
        ax_a.plot([x, x], [plan_y[-1], plan_y[0]], color=RULE, lw=0.55)
        for y, label in zip(plan_y, nodes):
            ax_a.add_patch(Circle((x, y), 0.012, facecolor=color if y == plan_y[0] else WHITE, edgecolor=INK, linewidth=0.5))
            ax_a.text(x + 0.035, y, label, ha="left", va="center", fontsize=5.4)
    ax_a.text(x_base, 0.89, "baseline", ha="center", fontsize=5.8, fontweight="bold")
    ax_a.text(x_opt, 0.89, "optimized", ha="center", fontsize=5.8, fontweight="bold")
    ax_a.plot([0.48, 0.48], [0.26, 0.86], color=RULE, lw=0.45, ls="--")
    panel_label(ax_b, "b")
    cols = ["window", "prefix", "row parity", ">=10x"]
    data = [
        [1 if d["baseline_plan_contains_window"] else 0, 0, 1 if d["row_counts_match"] else 0, 0],
        [0, 1 if d["optimized_plan_contains_prefix"] else 0, 1 if d["row_counts_match"] else 0, 1 if d["speedup_target_met"] else 0],
    ]
    cmap = mpl.colors.ListedColormap([WHITE, BLUE_SOFT])
    ax_b.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax_b.set_xticks(range(len(cols)), cols, rotation=35, ha="right")
    ax_b.set_yticks([0, 1], ["baseline", "optimized"])
    ax_b.tick_params(length=0)
    for x in range(len(cols) + 1):
        ax_b.axvline(x - 0.5, color=RULE, lw=0.35)
    for y in range(3):
        ax_b.axhline(y - 0.5, color=RULE, lw=0.35)
    for r, row in enumerate(data):
        for c, value in enumerate(row):
            ax_b.text(c, r, str(value), ha="center", va="center", fontsize=5.8)
    for spine in ax_b.spines.values():
        spine.set_visible(False)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_09(spec: FigureSpec, m: dict) -> dict[str, str]:
    d = m["doris"]
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 3.10))
    gs = fig.add_gridspec(1, 2, left=0.08, right=0.98, top=0.78, bottom=0.22, width_ratios=[1.45, 0.75], wspace=0.32)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    metrics = ["mean execute", "P95 execute"]
    baseline = [d["baseline"]["avg_execute_ms"], d["baseline"]["p95_execute_ms"]]
    optimized = [d["optimized"]["avg_execute_ms"], d["optimized"]["p95_execute_ms"]]
    y = list(range(len(metrics)))
    ax_a.hlines(y, optimized, baseline, color=RULE, lw=0.9)
    ax_a.scatter(baseline, y, s=22, facecolor=WHITE, edgecolor=INK, linewidth=0.6, label="window baseline", zorder=3)
    ax_a.scatter(optimized, y, s=24, facecolor=BLUE, edgecolor=INK, linewidth=0.4, label="prefix optimized", zorder=3)
    for yi, b, o in zip(y, baseline, optimized):
        ax_a.text(b * 1.05, yi, f"{b:.0f}", va="center", fontsize=5.2, color=TEXT)
        ax_a.text(o * 1.15, yi, f"{o:.1f}", va="center", fontsize=5.2, color=TEXT)
    ax_a.set_xscale("log")
    ax_a.set_xlabel("latency (ms, log scale)")
    ax_a.set_yticks(y, metrics)
    ax_a.set_xlim(min(optimized) * 0.7, max(baseline) * 1.6)
    clean_axes(ax_a)
    ax_a.legend(loc="upper left", bbox_to_anchor=(0.00, 1.04), ncol=2, fontsize=5.2, borderaxespad=0)
    panel_label(ax_b, "b")
    ax_b.hlines([0], [1], [d["speedup"]], color=RULE, lw=0.9)
    ax_b.scatter([1], [0], s=20, facecolor=WHITE, edgecolor=INK, linewidth=0.6, zorder=3)
    ax_b.scatter([d["speedup"]], [0], s=26, facecolor=BLUE, edgecolor=INK, linewidth=0.4, zorder=3)
    ax_b.axvline(d["min_speedup"], color=ACCENT, lw=0.7, ls="--")
    ax_b.set_xscale("log")
    ax_b.set_xlim(1, d["speedup"] * 1.6)
    ax_b.set_ylim(-0.55, 0.55)
    ax_b.set_yticks([0], ["Doris"])
    ax_b.set_xlabel("relative speedup (x)")
    clean_axes(ax_b)
    ax_b.spines["left"].set_visible(False)
    ax_b.tick_params(axis="y", length=0)
    ax_b.text(d["speedup"] * 1.08, 0, f"{d['speedup']:.2f}x", va="center", fontsize=5.5)
    ax_b.text(1.05, 0.20, "baseline", fontsize=5.0, color=MUTED)
    ax_b.text(0.02, -0.33, "Evidence file was reused;\nDoris latency not rerun.", transform=ax_b.transAxes, fontsize=5.0, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_10(spec: FigureSpec, m: dict) -> dict[str, str]:
    md = m["metadata"]
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 4.05))
    gs = fig.add_gridspec(1, 2, left=0.11, right=0.98, top=0.82, bottom=0.17, width_ratios=[1.25, 1.0], wspace=0.35)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    labels = ["blocking gates", "warning count", "official +", "official -", "defense checks", "Doris evidence", "metadata warnings"]
    values = [
        1 if md["readiness"]["blocking_gates_passed"] else 0,
        1 if md["readiness"]["warning_count"] == 0 else 0,
        md["official_suite"]["positive"]["passed"] / md["official_suite"]["positive"]["total"],
        md["official_suite"]["negative"]["passed"] / md["official_suite"]["negative"]["total"],
        md["readiness"]["defense_package_checks"]["passed"] / md["readiness"]["defense_package_checks"]["total"],
        1 if md["doris_cluster"]["passed"] else 0,
        1 if not md["warnings"] else 0,
    ]
    y = list(range(len(labels)))
    ax_a.hlines(y, [0] * len(values), values, color=RULE, lw=0.8)
    ax_a.scatter(values, y, s=22, facecolor=BLUE, edgecolor=INK, linewidth=0.4)
    ax_a.set_xlim(0, 1.05)
    ax_a.set_xlabel("pass fraction")
    ax_a.set_yticks(y, labels)
    ax_a.invert_yaxis()
    clean_axes(ax_a)
    ax_a.spines["left"].set_visible(False)
    ax_a.tick_params(axis="y", length=0)
    panel_label(ax_b, "b")
    axis_off(ax_b)
    rows = [
        ("pytest", f"{md['readiness']['pytest']['passed']} passed", f"{md['readiness']['pytest']['elapsed_seconds']:.2f}s"),
        ("compile P95", f"{md['readiness']['compile_p95_latency_ms']:.3f} ms", "<50 ms"),
        ("official", "37/37 + 37/37", "pos/neg"),
        ("Doris", md["doris_cluster"]["speedup_display"], "prefix path"),
        ("Git HEAD", md["git"]["head_at_export"], "export"),
    ]
    y0 = 0.82
    ax_b.plot([0.02, 0.98], [0.88, 0.88], color=INK, lw=0.6)
    for i, row in enumerate(rows):
        yv = y0 - i * 0.15
        ax_b.text(0.02, yv, row[0], fontsize=5.5, fontweight="bold", ha="left")
        ax_b.text(0.38, yv, row[1], fontsize=5.5, ha="left")
        ax_b.text(0.78, yv, row[2], fontsize=5.2, color=MUTED, ha="left")
        ax_b.plot([0.02, 0.98], [yv - 0.055, yv - 0.055], color=RULE, lw=0.35)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_11(spec: FigureSpec, m: dict) -> dict[str, str]:
    items = m["topic_items"]
    summary = m["topic_summary"]
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 6.35))
    gs = fig.add_gridspec(2, 1, left=0.11, right=0.98, top=0.86, bottom=0.10, height_ratios=[0.85, 2.7], hspace=0.28)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[1, 0])
    panel_label(ax_a, "a")
    labels = ["implemented", "partial", "needs evidence"]
    values = [summary["implemented"], summary["partial"], summary["needs_evidence"]]
    horizontal_barh(ax_a, labels, values, [BLUE, "#8E8E8E", ACCENT], "requirement count", (0, max(values) + 1))
    panel_label(ax_b, "b")
    status_map = {"implemented": 2, "partial": 1, "needs_evidence": 0}
    data = [[status_map.get(item["status"], 0)] for item in items]
    cmap = mpl.colors.ListedColormap([ACCENT_SOFT, PALE, BLUE_SOFT])
    ax_b.imshow(data, cmap=cmap, vmin=0, vmax=2, aspect="auto")
    ylabels = [item["id"] for item in items]
    ax_b.set_yticks(range(len(items)), ylabels)
    ax_b.set_xticks([0], ["status"])
    ax_b.tick_params(length=0)
    for y, item in enumerate(items):
        ax_b.text(0, y, item["status"], ha="center", va="center", fontsize=5.0)
        ax_b.text(0.72, y, wrap_label(item["requirement"], 64), transform=ax_b.get_yaxis_transform(), ha="left", va="center", fontsize=4.9, color=TEXT)
    for y in range(len(items) + 1):
        ax_b.axhline(y - 0.5, color=RULE, lw=0.3)
    for spine in ax_b.spines.values():
        spine.set_visible(False)
    ax_b.set_xlim(-0.5, 2.2)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_12(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(NATURE_DOUBLE_IN, 3.8))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.82, bottom=0.16)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    ax.axvline(0.43, ymin=0.18, ymax=0.86, color=RULE, lw=0.75, ls="--")
    ax.text(0.445, 0.18, "compiler boundary", rotation=90, va="bottom", fontsize=5.1, color=MUTED)
    xs = [0.10, 0.28, 0.56, 0.76, 0.91]
    labels = ["user\nrequest", "LLM\ncandidate", "deterministic\ncompiler", "reference\nchecks", "accepted\nSQL"]
    for i, (x, label) in enumerate(zip(xs, labels)):
        ax.add_patch(Circle((x, 0.60), 0.013, facecolor=BLUE if i in {2, 3} else WHITE, edgecolor=INK, linewidth=0.55))
        ax.text(x, 0.70, label, ha="center", va="bottom", fontsize=5.7)
        if i < len(xs) - 1:
            thin_arrow(ax, (x + 0.025, 0.60), (xs[i + 1] - 0.025, 0.60), BLUE if i >= 1 else INK)
    thin_arrow(ax, (0.28, 0.56), (0.28, 0.30), ACCENT)
    ax.plot([0.18, 0.58], [0.30, 0.30], color=ACCENT, lw=0.55)
    ax.text(0.18, 0.22, "reject: direct SQL / unknown indicator / unsafe output", ha="left", fontsize=5.3, color=TEXT)
    ax.text(0.57, 0.38, "accepted=1; rejected=2 in smoke evidence", fontsize=5.2, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_13(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(NATURE_DOUBLE_IN, 4.0))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.83, bottom=0.14)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    left = [("indicators.json", 0.78), ("functions.json", 0.58), ("tables.json", 0.38)]
    right = [("semantic\nchecks", 0.80), ("SQL\ngenerator", 0.62), ("reference\noracle", 0.44), ("tests /\nofficial suite", 0.26)]
    ax.text(0.20, 0.91, "configuration", ha="center", fontsize=5.8, fontweight="bold")
    ax.text(0.50, 0.91, "registry", ha="center", fontsize=5.8, fontweight="bold")
    ax.text(0.80, 0.91, "consumers", ha="center", fontsize=5.8, fontweight="bold")
    ax.add_patch(Circle((0.50, 0.58), 0.032, facecolor=BLUE_SOFT, edgecolor=INK, linewidth=0.6))
    ax.text(0.50, 0.50, "normalize\nand bind", ha="center", va="top", fontsize=5.4)
    for label, y in left:
        ax.add_patch(Circle((0.20, y), 0.011, facecolor=WHITE, edgecolor=INK, linewidth=0.5))
        ax.text(0.15, y, label, ha="right", va="center", fontsize=5.4)
        ax.plot([0.215, 0.468], [y, 0.58], color=RULE, lw=0.55)
    for label, y in right:
        ax.add_patch(Circle((0.80, y), 0.011, facecolor=WHITE, edgecolor=INK, linewidth=0.5))
        ax.text(0.83, y, label, ha="left", va="center", fontsize=5.4)
        ax.plot([0.532, 0.785], [0.58, y], color=BLUE, lw=0.55)
    ax.text(0.06, 0.10, "Boundary: simple scalar function templates are configuration-only; complex temporal templates still need protocol expansion.", fontsize=5.1, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_14(spec: FigureSpec, m: dict) -> dict[str, str]:
    d = m["doris"]
    fig, ax = plt.subplots(figsize=(NATURE_DOUBLE_IN, 3.95))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.82, bottom=0.16)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    lanes = [
        (0.74, ["Docker / Doris FE+BE", "DDL", "scale data"]),
        (0.54, ["compiler SQL", "mysql client", "EXPLAIN + timing"]),
        (0.34, ["row parity", "speedup", "evidence snapshot"]),
    ]
    for y, labels in lanes:
        ax.plot([0.09, 0.91], [y, y], color=INK, lw=0.55)
        xs = [0.15, 0.50, 0.85]
        for x, label in zip(xs, labels):
            ax.add_patch(Circle((x, y), 0.011, facecolor=BLUE if label in {"speedup", "evidence snapshot"} else WHITE, edgecolor=INK, linewidth=0.5))
            ax.text(x, y + 0.055, label, ha="center", va="bottom", fontsize=5.5)
        for x1, x2 in zip(xs, xs[1:]):
            thin_arrow(ax, (x1 + 0.02, y), (x2 - 0.02, y), BLUE if y == 0.54 else INK, lw=0.45)
    ax.text(0.13, 0.16, f"row parity: {d['baseline']['row_count']} = {d['optimized']['row_count']}; speedup: {d['speedup']:.2f}x", fontsize=5.3)
    ax.text(0.13, 0.09, "Figure generation reused frozen evidence; live Doris latency was not re-measured.", fontsize=5.0, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_15(spec: FigureSpec, m: dict) -> dict[str, str]:
    screenshot_dir = ROOT / "submission_artifacts" / "visual_evidence" / "screenshots"
    ids = ["EV-041", "EV-042", "EV-043", "EV-044", "EV-045", "EV-046", "EV-047", "EV-048"]
    paths = []
    for ev in ids:
        found = sorted(screenshot_dir.glob(f"{ev}_*.png"))
        if found:
            paths.append((ev, found[0]))
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 4.85))
    fig.subplots_adjust(left=0.04, right=0.98, top=0.86, bottom=0.08)
    figure_header(fig, spec, left=0.05)
    for i, (ev, path) in enumerate(paths[:8]):
        row, col = divmod(i, 4)
        ax = fig.add_axes([0.055 + col * 0.235, 0.54 - row * 0.37, 0.205, 0.30])
        img = Image.open(path).convert("RGB")
        ax.imshow(img)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(INK)
            spine.set_linewidth(0.35)
        ax.text(-0.02, 1.04, chr(ord("a") + i), transform=ax.transAxes, ha="left", va="bottom", fontsize=8.0, fontweight="bold")
        ax.text(0.10, 1.04, ev, transform=ax.transAxes, ha="left", va="bottom", fontsize=5.0, color=MUTED)
    fig.text(0.05, 0.025, "Source: actual screenshots EV-041 to EV-048; no synthetic UI elements were added.", fontsize=5.0, color=MUTED)
    return save_figure(fig, spec)


def fig_16(spec: FigureSpec, m: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(NATURE_DOUBLE_IN, 4.7))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.84, bottom=0.10)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    root_x = 0.10
    ax.plot([root_x, root_x], [0.16, 0.84], color=INK, lw=0.6)
    ax.text(root_x, 0.88, "project root", ha="center", fontsize=5.9, fontweight="bold")
    items = [
        ("README.md / PROJECT_INDEX.md", "orientation"),
        ("src/findsl/", "compiler + validation"),
        ("configs/", "business metadata"),
        ("data/", "sample and real data"),
        ("tests/", "regression suite"),
        ("deploy/doris/", "Doris assets"),
        ("docs/", "Chinese documentation"),
        ("submission_artifacts/", "snapshots and evidence"),
        ("outputs/可视化证据包_nature_style/", "journal figures"),
    ]
    for i, (name, desc) in enumerate(items):
        y = 0.82 - i * 0.075
        ax.plot([root_x, 0.24], [y, y], color=RULE, lw=0.45)
        ax.add_patch(Circle((0.24, y), 0.007, facecolor=BLUE if name.startswith("outputs") else WHITE, edgecolor=INK, linewidth=0.4))
        ax.text(0.27, y + 0.012, name, ha="left", va="center", fontsize=5.5, fontweight="bold" if name.startswith("outputs") else "normal")
        ax.text(0.67, y + 0.012, desc, ha="left", va="center", fontsize=5.1, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_17(spec: FigureSpec, m: dict) -> dict[str, str]:
    d = m["doris"]
    fig = plt.figure(figsize=(NATURE_DOUBLE_IN, 4.0))
    gs = fig.add_gridspec(1, 2, left=0.07, right=0.98, top=0.82, bottom=0.16, width_ratios=[1.2, 0.9], wspace=0.32)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    lanes = [
        (0.67, "real-market sample", "semantic realism\n3/3 SQL-reference cases"),
        (0.39, "Doris scale evidence", f"5M cardinality\nrow parity: {d['row_counts_match']}\nspeedup: {d['speedup']:.2f}x"),
    ]
    for y, title, body in lanes:
        ax_a.plot([0.12, 0.88], [y, y], color=INK, lw=0.65)
        ax_a.add_patch(Circle((0.12, y), 0.012, facecolor=BLUE, edgecolor=INK, linewidth=0.5))
        ax_a.add_patch(Circle((0.88, y), 0.012, facecolor=WHITE, edgecolor=INK, linewidth=0.5))
        ax_a.text(0.15, y + 0.06, title, ha="left", va="bottom", fontsize=5.9, fontweight="bold")
        ax_a.text(0.15, y - 0.04, body, ha="left", va="top", fontsize=5.4, color=TEXT)
    ax_a.text(0.12, 0.13, "Claim boundary: correctness realism and scale performance are complementary evidence lanes.", fontsize=5.1, color=MUTED)
    panel_label(ax_b, "b")
    cols = ["semantic", "scale", "latency"]
    rows = ["real sample", "Doris evidence"]
    data = [[1, 0, 0], [0, 1, 1]]
    ax_b.imshow(data, cmap=mpl.colors.ListedColormap([WHITE, BLUE_SOFT]), vmin=0, vmax=1, aspect="auto")
    ax_b.set_xticks(range(len(cols)), cols, rotation=30, ha="right")
    ax_b.set_yticks(range(len(rows)), rows)
    ax_b.tick_params(length=0)
    for x in range(len(cols) + 1):
        ax_b.axvline(x - 0.5, color=RULE, lw=0.35)
    for y in range(len(rows) + 1):
        ax_b.axhline(y - 0.5, color=RULE, lw=0.35)
    for r in range(len(rows)):
        for c in range(len(cols)):
            ax_b.text(c, r, str(data[r][c]), ha="center", va="center", fontsize=5.8)
    for spine in ax_b.spines.values():
        spine.set_visible(False)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


BUILDERS: dict[str, Callable[[FigureSpec, dict], dict[str, str]]] = {
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


def write_rebuild_plan(metrics: dict, outputs: list[dict]) -> None:
    lines = [
        "# 科研绘图参考与逐图重构方案",
        "",
        f"生成时间：{metrics['generated_at_local']}",
        f"绘图后端：Python / matplotlib。所有图件、预览和灰度 QA 均由同一后端生成。",
        f"目标规格：Nature 双栏宽约 183 mm（{NATURE_DOUBLE_IN:.2f} in），高度不超过 170 mm（{NATURE_MAX_HEIGHT_IN:.2f} in）。",
        f"当前 Git HEAD：`{metrics['git_head_now']}`。",
        "",
        "## 1. 已核对的外部规范与参考代码",
        "",
        "| 来源 | 用途 |",
        "|---|---|",
    ]
    for name, url in REFERENCE_LINKS:
        lines.append(f"| [{name}]({url}) | 尺寸、字体、颜色、导出或代码模式参考 |")
    lines.extend(
        [
            "",
            "本轮重构采用的硬约束如下：文字尽量控制在 5-7 pt，panel label 使用 8 pt 加粗小写字母；主图按最终论文尺寸直接导出，不在报告中二次缩放；SVG 文本保留为可编辑 `<text>`；PDF 字体使用 TrueType Type 42；图表避免背景网格、阴影、装饰图标、彩色文字和大面积 UI 色块；有真实数值数据时才画定量图，没有 source data 的内容只画 method schematic 或 image plate。",
            "",
            "## 2. 参考代码到本项目的映射",
            "",
            "- SciencePlots 的 `science + nature` 思路用于字体、字号和终稿尺寸约束，但本项目需要中文，因此脚本使用 CJK 字体优先、Arial/Helvetica 兜底的字体栈。",
            "- cnsplots 的 publication-ready 图型库用于选择 lollipop、forest/range plot、heatmap matrix、image plate 等图型语法；没有直接复制第三方源码。",
            "- figures4papers 的 GridSpec、多面板和直接标注方式用于版面组织；本项目按实际证据重写为自己的脚本。",
            "- Matplotlib 官方 rcParams 用于固定 `svg.fonttype='none'`、`pdf.fonttype=42`、`savefig.dpi` 与 `bbox_inches='tight'`。",
            "",
            "本地参考代码缓存状态如下。它们只作为绘图语法和期刊风格的审计参考，未直接进入最终交付代码；最终可提交文件仍以本项目脚本为准。",
            "",
            "| 参考仓库 | 本地缓存 | HEAD |",
            "|---|---|---|",
        ]
    )
    for repo in metrics["reference_inventory"]:
        lines.append(f"| {repo['name']} | {repo['local_cache']} | `{repo['head']}` |")
    lines.extend(
        [
            "",
            "## 3. 逐图搜索与最佳绘图代码映射",
            "",
            "每张图在重画前都按“要证明的结论 -> 证据类型 -> 最合适科研图型 -> 期刊导出约束”的顺序确定图型。下面的搜索关键词不是装饰性记录，而是用于复核为什么选这种图，不选 UI 卡片、雷达图、仪表盘、饼图或无来源曲线。",
            "",
            "| 图号 | 搜索关键词 / 参考方向 | 采用的代码模式 | 期刊样式约束 |",
            "|---|---|---|---|",
        ]
    )
    for row in outputs:
        spec = row["spec"]
        audit = FIGURE_SEARCH_AUDIT[spec.fig_id]
        lines.append(
            f"| {spec.fig_id} | {audit['search_queries']} | {audit['best_code_pattern']} | {audit['style_contract']} |"
        )
    lines.extend(
        [
            "",
            "## 4. 逐图重构清单",
            "",
            "| 图号 | 结论 | 证据来源 | 图型语法 | 参考模式 | 主要整改 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in outputs:
        spec = row["spec"]
        lines.append(
            f"| {spec.fig_id} | {spec.conclusion} | {spec.source} | {spec.archetype} | {spec.reference_pattern} | {spec.redesign} |"
        )
    lines.extend(
        [
            "",
            "## 5. 证据诚实边界",
            "",
            "Doris latency 图使用已经冻结在 `submission_artifacts/evidence_snapshots/doris_cluster_evidence.json` 的真实 Doris 证据；本轮只是重画图，没有现场重跑 Doris。项目没有 ROC、PR、loss、mAP、显微图、训练权重等 source data，因此本图包不会编造这些常见科研曲线。",
            "",
            "## 6. 输出与 QA",
            "",
            "每张图输出 SVG、PDF、300 dpi PNG、600 dpi TIFF 和 300 dpi 灰度 PNG。灰度 PNG 用于检查打印和色觉可读性；SVG 用 XML 审计确认文本没有被全部转成 path；PNG/TIFF 用 DPI 审计确认分辨率。",
        ]
    )
    (OUT_DIR / "科研绘图参考与逐图重构方案.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_index(metrics: dict, outputs: list[dict]) -> None:
    md = metrics["metadata"]
    d = metrics["doris"]
    lines = [
        "# Nature Style 科研图表证据包",
        "",
        f"生成时间：{metrics['generated_at_local']}",
        f"样式标准：`{STYLE_STANDARD}`",
        f"当前 Git HEAD：`{metrics['git_head_now']}`",
        f"最新 evidence metadata：`{md['generated_at']}`",
        f"Git HEAD at export：`{md['git']['head_at_export']}`",
        f"Pytest：`{md['readiness']['pytest']['passed']} passed in {md['readiness']['pytest']['elapsed_seconds']:.2f}s`",
        f"Official suite：正例 `{md['official_suite']['positive']['passed']}/{md['official_suite']['positive']['total']}`，负例 `{md['official_suite']['negative']['passed']}/{md['official_suite']['negative']['total']}`",
        f"Doris speedup：`{md['doris_cluster']['speedup_display']}`；Doris evidence generated_at：`{d['generated_at']}`",
        "",
        "## 设计原则",
        "",
        "- 去 UI 化：不使用 dashboard 指标卡、大面积彩色圆角模块、阴影、装饰图标和说明牌。",
        "- 论文图语法：数值证据使用 dot-range、lollipop、matrix、bar；流程和架构使用线稿 method schematic；截图使用 image plate。",
        "- 色彩克制：文本使用黑/灰，深蓝只用于主数据标记或证据线，红色只用于风险边界或阈值。",
        "- 证据诚实：没有真实 source data 的 ROC/PR/loss 等曲线不生成；Doris latency 使用冻结 evidence 文件，本轮未重测 Doris。",
        "- 输出格式：每张图导出 SVG、PDF、300dpi PNG、600dpi TIFF 和灰度 PNG。",
        "",
        "## 图表清单",
        "",
        "| 图号 | 图名 | 类型 | SVG | PDF | PNG | TIFF | 灰度 QA | 数据来源 | 证明什么 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in outputs:
        spec = row["spec"]
        paths = row["paths"]
        lines.append(
            f"| {spec.fig_id} | {spec.title} | {spec.archetype} | `{paths['svg']}` | `{paths['pdf']}` | `{paths['png']}` | `{paths['tiff']}` | `{paths['gray_png']}` | {spec.source} | {spec.proof} |"
        )
    lines.extend(
        [
            "",
            "## 参考说明",
            "",
            "详见 `科研绘图参考与逐图重构方案.md`。该文件记录外部规范、参考代码来源、逐图搜索关键词、最佳绘图代码模式、图型选择和证据边界。",
            "",
            "## 不适用说明",
            "",
            "当前项目没有模型训练、ROC/PR、mAP、loss 曲线、显微图或硬件波形。凡没有真实 source data 的指标，不在 Nature style 图中编造成科研曲线。",
        ]
    )
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "generated_at": metrics["generated_at_local"],
        "style_standard": STYLE_STANDARD,
        "git_head_now": metrics["git_head_now"],
        "target_size": {
            "single_column_in": NATURE_SINGLE_IN,
            "double_column_in": NATURE_DOUBLE_IN,
            "max_height_in": NATURE_MAX_HEIGHT_IN,
        },
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
        "references": [{"name": name, "url": url} for name, url in REFERENCE_LINKS],
        "local_reference_inventory": metrics["reference_inventory"],
        "figures": [
            {
                "id": row["spec"].fig_id,
                "title": row["spec"].title,
                "archetype": row["spec"].archetype,
                "conclusion": row["spec"].conclusion,
                "source": row["spec"].source,
                "redesign": row["spec"].redesign,
                "reference_pattern": row["spec"].reference_pattern,
                "search_audit": FIGURE_SEARCH_AUDIT[row["spec"].fig_id],
                **row["paths"],
            }
            for row in outputs
        ],
    }
    (OUT_DIR / "figure_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for category, folder_name in FIG_DIRS.items():
        rows = [row for row in outputs if row["spec"].category == category]
        if not rows:
            continue
        folder = OUT_DIR / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        folder_lines = [f"# {folder_name}", "", "| 图号 | 图名 | SVG | PDF | PNG | TIFF | 灰度 QA |", "|---|---|---|---|---|---|---|"]
        for row in rows:
            spec = row["spec"]
            paths = {k: Path(v).name for k, v in row["paths"].items()}
            folder_lines.append(
                f"| {spec.fig_id} | {spec.title} | `{paths['svg']}` | `{paths['pdf']}` | `{paths['png']}` | `{paths['tiff']}` | `{paths['gray_png']}` |"
            )
        (folder / "README.md").write_text("\n".join(folder_lines) + "\n", encoding="utf-8")


def main() -> None:
    setup_style()
    if OUT_DIR.exists():
        OUT_DIR.resolve().relative_to(ROOT.resolve())
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for folder in FIG_DIRS.values():
        (OUT_DIR / folder).mkdir(parents=True, exist_ok=True)
    metrics = latest_metrics()
    outputs = []
    for spec in SPECS:
        paths = BUILDERS[spec.fig_id](spec, metrics)
        outputs.append({"spec": spec, "paths": paths})
    write_index(metrics, outputs)
    write_rebuild_plan(metrics, outputs)
    print(f"Generated {len(outputs)} paper-first Nature-style figures under {OUT_DIR}")


if __name__ == "__main__":
    main()
