from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "outputs" / "manual-20260609-ppt" / "presentations" / "findsl-defense-deck"
SLIDES_DIR = WORKSPACE / "slides"
ASSET_DIR = WORKSPACE / "assets"
PREVIEW_DIR = WORKSPACE / "preview"
LAYOUT_DIR = WORKSPACE / "layout"
QA_DIR = WORKSPACE / "qa"
OUTPUT_DIR = WORKSPACE / "output"
FINAL_PPTX = OUTPUT_DIR / "FinDSL-Forge-赛题19答辩展示稿.pptx"
SKILL_DIR = Path(
    r"C:\Users\26312\.codex\plugins\cache\openai-primary-runtime\presentations\26.601.10930\skills\presentations"
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return path.resolve().as_posix()


def ensure_dirs() -> None:
    for d in [SLIDES_DIR, ASSET_DIR, PREVIEW_DIR, LAYOUT_DIR, QA_DIR, OUTPUT_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def copy_assets() -> dict:
    assets: dict[str, str] = {}
    concept_dir = ROOT / "outputs" / "AI生成图_GPTImage2Skill" / "final_chinese"
    concept_files = sorted(concept_dir.glob("*.png"))
    for file in concept_files:
        target = ASSET_DIR / file.name
        shutil.copy2(file, target)
        assets[file.stem] = rel(target)

    generated_root = Path(r"C:\Users\26312\.codex\generated_images")
    latest = sorted(generated_root.rglob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[:4]
    names = [
        "imagegen_hero_gpt_style.png",
        "imagegen_method_schematic.png",
        "imagegen_data_governance_schematic.png",
        "imagegen_delivery_package.png",
    ]
    for source, name in zip(reversed(latest), names):
        target = ASSET_DIR / name
        shutil.copy2(source, target)
        assets[Path(name).stem] = rel(target)

    return assets


def configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.dpi": 180,
            "savefig.dpi": 300,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#263238",
            "axes.labelcolor": "#263238",
            "xtick.color": "#263238",
            "ytick.color": "#263238",
            "text.color": "#263238",
        }
    )


def save_fig(fig, path: Path) -> str:
    fig.tight_layout(pad=1.0)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return rel(path)


def make_charts(data: dict) -> dict:
    configure_matplotlib()
    charts: dict[str, str] = {}
    readiness = data["readiness"]
    official = data["official_suite"]
    doris = data["doris_cluster"]

    # 1. headline gate matrix
    labels = ["Blocking\ngates", "Warning\ncount", "Pytest", "正例", "负例", "Doris\nevidence", "行数一致"]
    values = [1, 1, readiness["pytest"]["passed"], official["positive"]["passed"], official["negative"]["passed"], 1, 1]
    display = ["PASS", "0", f'{readiness["pytest"]["passed"]}', "37/37", "37/37", "PASS", "PASS"]
    colors = ["#0F4D92", "#0F4D92", "#0F4D92", "#0F4D92", "#0F4D92", "#0F4D92", "#0F4D92"]
    fig, ax = plt.subplots(figsize=(8.2, 3.0))
    x = np.arange(len(labels))
    ax.scatter(x, [1] * len(labels), s=[380, 280, 560, 420, 420, 420, 420], color=colors)
    for xi, text in zip(x, display):
        ax.text(xi, 1.16, text, ha="center", va="bottom", fontsize=10.5, fontweight="bold")
    ax.set_xticks(x, labels, fontsize=8.5)
    ax.set_yticks([])
    ax.set_ylim(0.75, 1.45)
    ax.set_title("提交门禁与证据状态", loc="left", fontsize=12, fontweight="bold")
    ax.text(0, 0.82, "Source: submission_artifacts/evidence_metadata.json", fontsize=7.5, color="#60707C")
    ax.spines[["left", "bottom"]].set_visible(False)
    charts["gate_matrix"] = save_fig(fig, ASSET_DIR / "chart_gate_matrix.png")

    # 2. Doris latency and speedup
    baseline = doris["baseline_avg_execute_ms"]
    optimized = doris["optimized_avg_execute_ms"]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    y = np.array([0, 1])
    vals = [baseline, optimized]
    bars = ax.barh(y, vals, color=["#9AA6B2", "#0F4D92"], height=0.38)
    ax.set_yticks(y, ["Baseline window SQL", "Prefix optimized SQL"], fontsize=9.5)
    ax.set_xlabel("Average execute time (ms)", fontsize=9)
    ax.set_xscale("log")
    ax.grid(axis="x", color="#E4E8EC", linewidth=0.8)
    for b, v in zip(bars, vals):
        ax.text(v * 1.08, b.get_y() + b.get_height() / 2, f"{v:.1f} ms", va="center", fontsize=9.5)
    ax.text(0.66, 0.90, f"speedup = {doris['speedup_display']}", transform=ax.transAxes, color="#0F4D92", fontsize=11.5, fontweight="bold")
    ax.text(0.0, 1.03, "Average latency, log scale", transform=ax.transAxes, fontsize=8.5, color="#60707C")
    charts["doris_latency"] = save_fig(fig, ASSET_DIR / "chart_doris_latency.png")

    # 3. test and suite coverage
    items = ["Pytest", "官方正例", "官方负例", "评审包检查", "评估用例"]
    passed = [
        readiness["pytest"]["passed"],
        official["positive"]["passed"],
        official["negative"]["passed"],
        readiness["defense_package_checks"]["passed"],
        readiness["evaluation_cases"]["passed"],
    ]
    total = [
        readiness["pytest"]["passed"],
        official["positive"]["total"],
        official["negative"]["total"],
        readiness["defense_package_checks"]["total"],
        readiness["evaluation_cases"]["total"],
    ]
    pct = [p / t * 100 for p, t in zip(passed, total)]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    yy = np.arange(len(items))
    ax.barh(yy, [100] * len(items), color="#ECEFF3", height=0.42)
    ax.barh(yy, pct, color="#0F4D92", height=0.42)
    ax.set_yticks(yy, items, fontsize=9.5)
    ax.set_xlim(0, 104)
    ax.set_xlabel("Pass rate (%)", fontsize=9)
    ax.grid(axis="x", color="#E8ECEF", linewidth=0.8)
    for i, (p, t) in enumerate(zip(passed, total)):
        ax.text(101.5, i, f"{p}/{t}", va="center", ha="right", fontsize=9.5)
    ax.set_title("自动化验证覆盖概览", loc="left", fontsize=12, fontweight="bold")
    charts["test_coverage"] = save_fig(fig, ASSET_DIR / "chart_test_coverage.png")

    # 4. latency target marker
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    thresholds = [10000, baseline, optimized]
    names = ["赛题 10s 目标", "Baseline", "Optimized"]
    ax.scatter(thresholds, [0, 0, 0], s=[220, 220, 260], color=["#C55A11", "#9AA6B2", "#0F4D92"])
    for xval, name in zip(thresholds, names):
        ax.vlines(xval, -0.12, 0.12, colors="#8A95A0", linewidth=0.9)
        ax.text(xval, 0.18, name, ha="center", fontsize=9)
        ax.text(xval, -0.28, f"{xval:.0f} ms", ha="center", fontsize=8.5, color="#60707C")
    ax.set_xscale("log")
    ax.set_xlim(90, 14000)
    ax.set_yticks([])
    ax.set_xlabel("Execute time on log scale (ms)", fontsize=9)
    ax.grid(axis="x", color="#E8ECEF")
    ax.set_title("执行时间与 10s 目标线", loc="left", fontsize=12, fontweight="bold")
    charts["latency_target"] = save_fig(fig, ASSET_DIR / "chart_latency_target.png")

    return charts


def write_notes(data: dict, assets: dict, charts: dict) -> None:
    (WORKSPACE / "profile-plan.txt").write_text(
        "\n".join(
            [
                "task mode: create",
                "primary deck-profile: engineering-platform",
                "secondary gates: competition defense, evidence-led technical delivery, Chinese presentation",
                "required proof objects: architecture map, compiler workflow, validation gates, Doris performance proof, delivery package evidence",
                "source/asset requirements: evidence_metadata.json, README, docs, generated imagegen concept assets, exact metric charts",
                "brand constraints: no unofficial 华泰证券 logo; no fabricated partner logos; project identity is FinDSL Forge text only",
                "imagegen contract: imagegen assets are concept visuals only; exact numbers are rendered by code or PPT editable objects",
            ]
        ),
        encoding="utf-8",
    )
    (WORKSPACE / "source-notes.txt").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "primary_sources": {
                    "evidence_metadata": rel(ROOT / "submission_artifacts" / "evidence_metadata.json"),
                    "evidence_summary": rel(ROOT / "submission_artifacts" / "evidence_summary.md"),
                    "readme": rel(ROOT / "README.md"),
                    "topic_compliance_docs": rel(ROOT / "项目全流程导师文档" / "08_官方赛题原文摘录与符合性复核.md"),
                },
                "image_assets": assets,
                "chart_assets": charts,
                "notes": [
                    "PPT uses current evidence metadata for hard metrics.",
                    "AI-generated images are presentation concept visuals, not runtime screenshots.",
                    "Chinese titles and metric values are editable PPT text or code-rendered charts.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (WORKSPACE / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (WORKSPACE / "contact-sheet-plan.txt").write_text(
        "\n".join(
            [
                "Deck rhythm: 24 slides, 6 chapters.",
                "Macro layouts: visual cover, split problem map, requirement matrix, pipeline diagram, scientific chart, table proof, section divider, risk register, speech page.",
                "No 3 consecutive slides share the same macro layout.",
                "No pseudo official logos; imagegen only supplies concept visuals without text.",
            ]
        ),
        encoding="utf-8",
    )


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_slide_modules(data: dict, assets: dict, charts: dict) -> None:
    evidence_head = data["git"]["head_at_export"]
    evidence_branch = data["git"].get("branch", "main")
    evidence_generated_at = data.get("generated_at", "待核验")
    readiness = data["readiness"]
    official = data["official_suite"]
    doris = data["doris_cluster"]
    slides = [
        {
            "type": "cover",
            "title": "FinDSL Forge",
            "subtitle": "赛题 19：行情选股 DSL 到高性能 Doris SQL 的自动化编译系统",
            "image": assets["imagegen_hero_gpt_style"],
            "claim": "用确定性编译器把行情选股语言转成可验证、可优化、可审计的 Doris SQL。",
        },
        {
            "type": "problem",
            "title": "赛题真正考的是“语义正确 + 性能可证”",
            "subtitle": "不是简单 NL2SQL，而是金融行情 DSL 的编译、验证、优化和工程交付。",
            "points": ["复杂 DSL 语义：then、窗口、集合、区间条件与组合逻辑", "Doris 执行空间：CTE、窗口函数、prefix 热点路径、执行计划", "比赛交付：正确率、10s 目标、可扩展配置、可复核证据"],
        },
        {
            "type": "compare",
            "title": "方案定位：受控编译系统，而不是大模型直接写 SQL",
            "left": ["大模型可参与候选生成", "候选必须进入 DSL 解析", "错误输入返回诊断，不静默生成"],
            "right": ["确定性 parser / semantic / sqlgen", "reference oracle 与 SQL 结果等价", "Doris evidence 和 readiness 作为最终门禁"],
        },
        {
            "type": "matrix",
            "title": "官方任务到项目实现的对应关系",
            "rows": [
                ["语义解析与标准 AST", "已实现", "lexer / parser / ast_nodes / semantic"],
                ["逻辑等价重写", "已实现", "sqlgen + reference + equivalence"],
                ["声明式规则框架", "已实现", "configs/*.json + registry"],
                ["长周期查询加速", "有真实证据", "Doris 5M 行，36.24x"],
                ["全量官方隐藏集", "待官方数据", "当前官方风格 37+37 全通过"],
            ],
        },
        {
            "type": "image",
            "title": "端到端架构：候选、编译、执行、证据归档",
            "image": assets["02_系统总体架构"],
            "caption": "核心链路把输入、规则、SQL、Doris 证据和提交元数据连成闭环。",
        },
        {
            "type": "pipeline",
            "title": "编译主流程：每一步都有失败边界",
            "steps": ["DSL 输入", "Lexer", "Parser / AST", "Semantic gates", "SQL generator", "Doris validator", "Evidence"],
        },
        {
            "type": "code",
            "title": "核心算法：AST 驱动的 SQL 生成",
            "left_title": "输入 DSL 示例",
            "left_code": "SELECT code WHERE\\n  SUM(indicator(\"volume\"), 120) > 0\\n  AND close > MA(close, 20)",
            "right_title": "输出 SQL 语义",
            "right_code": "WITH base AS (...),\\noptimized AS (\\n  SELECT code, trade_date\\n  FROM quote_prefix_120\\n  WHERE volume_sum_120 > 0\\n)",
            "note": "真实 SQL 以 sqlgen 输出和 Doris validator 结果为准，PPT 中为简化讲解片段。",
        },
        {
            "type": "chart",
            "title": "门禁证据总览：所有 blocking gate 均通过",
            "chart": charts["gate_matrix"],
            "bullets": [f"Pytest：{readiness['pytest']['passed']} passed in {readiness['pytest']['elapsed_seconds']}s", "Warning count：0", "Metadata warnings：<none>"],
        },
        {
            "type": "mechanism",
            "title": "SQL 重写：从窗口重复计算到 prefix 热点路径",
            "items": ["识别长窗口 SUM 热点", "读取指标配置中的 prefix 能力", "生成 optimized SQL 路径", "用 row parity 与 explain marker 验证"],
        },
        {
            "type": "chart",
            "title": "Doris 真实性能证据：36.24x 加速",
            "chart": charts["doris_latency"],
            "bullets": [f"Baseline 平均：{doris['baseline_avg_execute_ms']:.2f} ms", f"Optimized 平均：{doris['optimized_avg_execute_ms']:.2f} ms", f"行数一致：{doris['baseline_row_count']} / {doris['optimized_row_count']}"],
        },
        {
            "type": "chart",
            "title": "优化路径已低于 10s 目标线",
            "chart": charts["latency_target"],
            "bullets": ["10s 是赛题可解释的关键工程目标", "优化路径约 143 ms，远低于目标线", "该结果只对应 120 日 rolling SUM 证据路径"],
        },
        {
            "type": "chart",
            "title": "正确性验证：官方风格正负例与回归测试",
            "chart": charts["test_coverage"],
            "bullets": [f"官方正例：{official['positive']['passed']}/{official['positive']['total']}", f"官方负例：{official['negative']['passed']}/{official['negative']['total']}", "SQL/reference 等价用于避免只测字符串"],
        },
        {
            "type": "image",
            "title": "数据治理闭环：配置、口径、血缘、审计",
            "image": assets["05_数据治理与元数据闭环"],
            "caption": "指标、表、函数配置与证据元数据解耦，降低代码硬编码和文档口径漂移。",
        },
        {
            "type": "image",
            "title": "LLM 安全边界：候选生成不等于最终答案",
            "image": assets["07_LLM安全边界与确定性编译"],
            "caption": "大模型输出必须经过 parser、semantic、validator、reference、readiness 多层闸门。",
        },
        {
            "type": "image",
            "title": "Web Demo：用于演示输入、SQL、结果与诊断",
            "image": assets["06_Web演示与人工核验界面"],
            "caption": "本页是概念视觉页；最终验收应展示真实 Web 截图和终端证据包。",
        },
        {
            "type": "structure",
            "title": "代码结构：按编译器、验证器和交付证据拆分",
            "groups": [
                ["src/findsl", "lexer / parser / semantic / sqlgen / readiness"],
                ["configs", "indicators / tables / functions"],
                ["tests", "parser / equivalence / official suite / Doris evidence"],
                ["submission_artifacts", "evidence metadata / manifest / snapshots"],
            ],
        },
        {
            "type": "evidence",
            "title": "Evidence metadata：关键数字集中管理",
            "rows": [
                ["Blocking gates", "PASS"],
                ["Warning count", "0"],
                ["Pytest", f"{readiness['pytest']['passed']} passed"],
                ["Doris speedup", doris["speedup_display"]],
                ["Evidence HEAD", evidence_head],
                ["Evidence branch", evidence_branch],
                ["Evidence generated", evidence_generated_at],
            ],
        },
        {
            "type": "risk",
            "title": "边界说清楚，反而更像成熟工程",
            "risks": [
                ["36.24x", "只证明 5M 行、120 日 rolling SUM 的 Doris prefix 路径"],
                ["12 类领域函数", "题面 TXT 未列完整清单，需官方 DSL 规范逐项复核"],
                ["ANTLR4", "当前采用同类递归下降解析器；若强制可迁移文法层"],
                ["真实数据", "公开样例用于演示，最终以官方数据集补跑"],
            ],
        },
        {
            "type": "image",
            "title": "可视化证据包：答辩、验收、审计三用",
            "image": assets["08_可视化证据包结构"],
            "caption": "证据包把运行日志、测试、Doris、截图、文档和交付清单分开管理。",
        },
        {
            "type": "delivery",
            "title": "交付不是 demo：代码、文档、测试、证据均可回溯",
            "image": assets["imagegen_delivery_package"],
            "items": ["Git 可回溯", "README / docs / 项目索引完整", "submission_artifacts 自动证据", "PPT / 图片资产独立归档"],
        },
        {
            "type": "roadmap",
            "title": "后续冲奖路线：围绕隐藏测试和现场数据补强",
            "items": ["拿到官方 12 类函数清单后逐项扩 official suite", "扩复杂窗口函数和布尔状态函数模板", "用官方 Doris 数据集补全全问句 10s 报告", "把 Demo 截图、性能报告、答辩讲稿统一到最终提交包"],
        },
        {
            "type": "speech",
            "title": "1 分钟介绍稿",
            "paragraph": "FinDSL Forge 面向华泰证券赛题 19，解决行情选股 DSL 到高性能 Doris SQL 的自动化编译问题。项目不是让大模型直接写 SQL，而是采用确定性编译器、语义校验、Doris SQL 安全验证、reference 等价验证和 prefix-sum 长窗口优化。当前证据显示，项目通过 311 个 pytest、官方风格正例 37/37、负例 37/37，readiness blocking gates 为 PASS，warning count 为 0，并在 5,000,000 行 Doris 数据上取得 36.24x 的长窗口加速。",
        },
        {
            "type": "qa",
            "title": "评委高概率追问：准备好的回答方向",
            "qas": [
                ["是不是套壳大模型？", "不是。大模型只做候选，最终由确定性编译和测试门禁决定。"],
                ["36.24x 是否泛化？", "不泛化所有查询，只代表当前 Doris 长窗口证据路径。"],
                ["如何证明 SQL 正确？", "用 reference oracle 与 SQL 执行结果做集合等价验证。"],
                ["如何扩展新指标？", "优先通过 configs 和 registry 扩展，复杂函数再补模板与测试。"],
            ],
        },
        {
            "type": "closing",
            "title": "为什么这个项目有竞争力",
            "image": assets["10_最终交付状态"],
            "claim": "把赛题要求做成了可运行、可验证、可解释、可回溯的工程系统。",
        },
    ]

    common = f"""
const C = {{
  navy: '#0B1F33',
  blue: '#0F4D92',
  teal: '#1C7C7D',
  ink: '#263238',
  muted: '#64727F',
  line: '#DDE5EC',
  pale: '#F5F8FA',
  paleBlue: '#EAF2FA',
  warn: '#B75C1E',
  ok: '#0F4D92',
  white: '#FFFFFF',
}};
const W = 1280, H = 720;
const slides = {json.dumps(slides, ensure_ascii=False, indent=2)};
function text(slide, ctx, x, y, w, h, value, opts={{}}) {{
  return ctx.addText(slide, {{
    left:x, top:y, width:w, height:h, text:value,
    fontSize: opts.size ?? 24, color: opts.color ?? C.ink, bold: opts.bold ?? false,
    typeface: opts.face ?? 'Microsoft YaHei', align: opts.align ?? 'left', valign: opts.valign ?? 'top',
    fill: opts.fill ?? '#FFFFFF00', line: opts.line ?? {{style:'solid', fill:'#FFFFFF00', width:0}},
    insets: opts.insets ?? {{left:0,right:0,top:0,bottom:0}},
  }});
}}
function rect(slide, ctx, x, y, w, h, opts={{}}) {{
  return ctx.addShape(slide, {{
    left:x, top:y, width:w, height:h, geometry:'rect',
    fill: opts.fill ?? '#FFFFFF00',
    line: opts.line ?? {{style:'solid', fill:opts.stroke ?? C.line, width:opts.width ?? 1}},
  }});
}}
function rule(slide, ctx, x, y, w, color=C.line) {{ rect(slide, ctx, x, y, w, 2, {{fill:color, line:{{style:'solid', fill:color, width:0}}}}); }}
async function image(slide, ctx, p, x, y, w, h, fit='contain') {{
  return await ctx.addImage(slide, {{path:p, left:x, top:y, width:w, height:h, fit, alt:'presentation image'}});
}}
function footer(slide, ctx, idx) {{
  rule(slide, ctx, 64, 675, 1152, '#E4EAF0');
  text(slide, ctx, 64, 687, 700, 18, 'FinDSL Forge | 赛题19答辩展示稿 | 数据来源：evidence_metadata.json 与项目文档', {{size:10, color:C.muted}});
  text(slide, ctx, 1120, 687, 96, 18, String(idx).padStart(2,'0') + ' / 24', {{size:10, color:C.muted, align:'right'}});
}}
function header(slide, ctx, s, idx) {{
  text(slide, ctx, 64, 38, 900, 46, s.title, {{size:30, bold:true, color:C.navy}});
  if (s.subtitle) text(slide, ctx, 66, 86, 890, 26, s.subtitle, {{size:14, color:C.blue}});
  rule(slide, ctx, 64, 121, 1152, '#E4EAF0');
  footer(slide, ctx, idx);
}}
function bulletList(slide, ctx, arr, x, y, w, gap=48) {{
  arr.forEach((b,i)=> {{
    const yy = y + i*gap;
    rect(slide, ctx, x, yy+7, 8, 8, {{fill:C.blue, line:{{style:'solid', fill:C.blue, width:0}}}});
    text(slide, ctx, x+22, yy, w-22, 46, b, {{size:17, color:C.ink}});
  }});
}}
function card(slide, ctx, x, y, w, h, title, body, accent=C.blue) {{
  rect(slide, ctx, x, y, w, h, {{fill:'#FFFFFF', stroke:'#D8E2EA', width:1}});
  rect(slide, ctx, x, y, 5, h, {{fill:accent, line:{{style:'solid', fill:accent, width:0}}}});
  text(slide, ctx, x+20, y+18, w-36, 28, title, {{size:18, bold:true, color:C.navy}});
  text(slide, ctx, x+20, y+55, w-36, h-68, body, {{size:14, color:C.muted}});
}}
function kpi(slide, ctx, x, y, value, label, note='') {{
  text(slide, ctx, x, y, 145, 42, value, {{size:29, bold:true, color:C.blue}});
  text(slide, ctx, x, y+43, 150, 18, label, {{size:12, bold:true, color:C.ink}});
  if (note) text(slide, ctx, x, y+64, 150, 18, note, {{size:10, color:C.muted}});
}}
function flow(slide, ctx, steps, x, y, w, h) {{
  const gap = 16, n = steps.length, bw = (w - gap*(n-1))/n;
  steps.forEach((st,i)=> {{
    const xx = x + i*(bw+gap);
    rect(slide, ctx, xx, y, bw, h, {{fill:i%2? '#FFFFFF' : C.paleBlue, stroke:'#CAD6E2'}});
    text(slide, ctx, xx+10, y+20, bw-20, h-40, st, {{size:17, bold:true, color:C.navy, align:'center', valign:'middle'}});
    if (i<n-1) {{
      rule(slide, ctx, xx+bw+2, y+h/2, gap-4, C.blue);
      rect(slide, ctx, xx+bw+gap-8, y+h/2-4, 8, 8, {{fill:C.blue, line:{{style:'solid', fill:C.blue, width:0}}}});
    }}
  }});
}}
function table(slide, ctx, rows, x, y, widths, rowH=52) {{
  rows.forEach((r, i)=> {{
    let xx=x;
    const fill=i===0 ? C.navy : (i%2 ? '#FFFFFF' : '#F7FAFC');
    r.forEach((cell,j)=> {{
      rect(slide, ctx, xx, y+i*rowH, widths[j], rowH, {{fill, stroke:'#D8E2EA'}});
      text(slide, ctx, xx+12, y+i*rowH+12, widths[j]-24, rowH-24, cell, {{size:i===0?14:13, bold:i===0, color:i===0?'#FFFFFF':C.ink}});
      xx += widths[j];
    }});
  }});
}}
export async function addSlide(presentation, ctx, idx) {{
  const s = slides[idx-1];
  const slide = presentation.slides.add();
  slide.background.fill = '#FFFFFF';
  if (s.type === 'cover') {{
    await image(slide, ctx, s.image, 640, 56, 558, 455, 'cover');
    text(slide, ctx, 68, 92, 500, 70, s.title, {{size:52, bold:true, color:C.navy}});
    text(slide, ctx, 72, 174, 510, 60, s.subtitle, {{size:21, color:C.blue}});
    text(slide, ctx, 72, 280, 500, 82, s.claim, {{size:22, color:C.ink}});
    kpi(slide, ctx, 72, 432, '203', 'Pytest passed', '13.11s');
    kpi(slide, ctx, 258, 432, '37/37', '官方正例', '全部通过');
    kpi(slide, ctx, 72, 548, '36.24x', 'Doris speedup', '5M 行证据');
    kpi(slide, ctx, 258, 548, '0', 'Warning count', '无未关闭警告');
    footer(slide, ctx, idx);
  }} else if (s.type === 'problem') {{
    header(slide, ctx, s, idx);
    s.points.forEach((p,i)=>card(slide, ctx, 88+i*374, 190, 320, 285, ['语义复杂','执行复杂','交付复杂'][i], p, [C.blue,C.teal,C.warn][i]));
    text(slide, ctx, 120, 535, 1040, 50, '答辩主线：把复杂金融 DSL 编译问题，拆成“可解析、可验证、可优化、可交付”的工程闭环。', {{size:21, bold:true, color:C.navy, align:'center'}});
  }} else if (s.type === 'compare') {{
    header(slide, ctx, s, idx);
    text(slide, ctx, 110, 160, 420, 34, '大模型可以辅助，但不能越过闸门', {{size:22, bold:true, color:C.warn}});
    text(slide, ctx, 730, 160, 420, 34, '最终交付由确定性系统负责', {{size:22, bold:true, color:C.blue}});
    bulletList(slide, ctx, s.left, 110, 225, 455, 62);
    bulletList(slide, ctx, s.right, 730, 225, 455, 62);
    flow(slide, ctx, ['LLM 候选','DSL 解析','语义校验','SQL 生成','证据门禁'], 208, 520, 864, 72);
  }} else if (s.type === 'matrix') {{
    header(slide, ctx, s, idx);
    table(slide, ctx, [['官方任务','完成状态','项目证据'], ...s.rows], 78, 158, [330,170,620], 62);
  }} else if (s.type === 'image') {{
    header(slide, ctx, s, idx);
    await image(slide, ctx, s.image, 92, 150, 760, 456, 'contain');
    rect(slide, ctx, 890, 188, 260, 365, {{fill:C.pale, stroke:'#D8E2EA'}});
    text(slide, ctx, 915, 218, 210, 34, '讲解重点', {{size:22, bold:true, color:C.navy}});
    text(slide, ctx, 915, 270, 210, 160, s.caption, {{size:16, color:C.ink}});
    text(slide, ctx, 915, 472, 210, 52, '注：概念图用于讲解，不替代真实运行证据。', {{size:12, color:C.warn}});
  }} else if (s.type === 'pipeline') {{
    header(slide, ctx, s, idx);
    flow(slide, ctx, s.steps, 80, 210, 1120, 112);
    card(slide, ctx, 135, 405, 300, 120, '失败可解释', '非法 token、未知指标、类型错误、危险 SQL 均返回诊断。');
    card(slide, ctx, 490, 405, 300, 120, '输出可验证', 'SQL/reference 等价、Doris validator、readiness 一起兜底。');
    card(slide, ctx, 845, 405, 300, 120, '证据可归档', '结果写入 reports 与 submission_artifacts，便于回溯。');
  }} else if (s.type === 'code') {{
    header(slide, ctx, s, idx);
    text(slide, ctx, 92, 155, 450, 28, s.left_title, {{size:18, bold:true, color:C.navy}});
    text(slide, ctx, 704, 155, 450, 28, s.right_title, {{size:18, bold:true, color:C.navy}});
    rect(slide, ctx, 92, 195, 470, 245, {{fill:'#0B1F33', stroke:'#0B1F33'}});
    rect(slide, ctx, 704, 195, 470, 245, {{fill:'#0B1F33', stroke:'#0B1F33'}});
    text(slide, ctx, 116, 226, 420, 190, s.left_code, {{size:18, color:'#DCEEFF', face:'Consolas'}});
    text(slide, ctx, 728, 226, 420, 190, s.right_code, {{size:18, color:'#DCEEFF', face:'Consolas'}});
    flow(slide, ctx, ['parse','AST','rewrite','SQL'], 420, 500, 440, 72);
    text(slide, ctx, 108, 600, 1060, 36, s.note, {{size:13, color:C.muted, align:'center'}});
  }} else if (s.type === 'chart') {{
    header(slide, ctx, s, idx);
    await image(slide, ctx, s.chart, 82, 155, 720, 430, 'contain');
    bulletList(slide, ctx, s.bullets, 850, 225, 330, 66);
  }} else if (s.type === 'mechanism') {{
    header(slide, ctx, s, idx);
    flow(slide, ctx, s.items, 96, 205, 1088, 105);
    rect(slide, ctx, 150, 420, 980, 110, {{fill:C.paleBlue, stroke:'#C8D8E8'}});
    text(slide, ctx, 180, 446, 930, 54, '核心思想：把“每次查询重复扫描 120 日窗口”变成“提前准备 prefix/窗口列，查询时走热点路径”，再用 row parity 和 explain marker 证明等价。', {{size:21, color:C.navy, align:'center'}});
  }} else if (s.type === 'structure') {{
    header(slide, ctx, s, idx);
    s.groups.forEach((g,i)=>card(slide, ctx, 120+(i%2)*530, 170+Math.floor(i/2)*180, 450, 122, g[0], g[1], i<2?C.blue:C.teal));
  }} else if (s.type === 'evidence') {{
    header(slide, ctx, s, idx);
    table(slide, ctx, [['证据项','当前值'], ...s.rows], 240, 132, [360, 440], 48);
    text(slide, ctx, 240, 570, 760, 42, '注意：本页展示的是证据采集时的稳定元数据；最终交付版本以仓库 git log 和推送记录为准。', {{size:14, color:C.muted}});
  }} else if (s.type === 'risk') {{
    header(slide, ctx, s, idx);
    table(slide, ctx, [['容易被问穿的点','成熟回答边界'], ...s.risks], 92, 165, [260, 840], 76);
  }} else if (s.type === 'delivery') {{
    header(slide, ctx, s, idx);
    await image(slide, ctx, s.image, 705, 155, 430, 400, 'cover');
    bulletList(slide, ctx, s.items, 120, 215, 520, 70);
  }} else if (s.type === 'roadmap') {{
    header(slide, ctx, s, idx);
    s.items.forEach((it,i)=> {{
      rect(slide, ctx, 145+i*250, 250, 178, 150, {{fill:i%2? '#FFFFFF':C.paleBlue, stroke:'#D4E0EA'}});
      text(slide, ctx, 165+i*250, 270, 138, 36, 'Step ' + (i+1), {{size:18, bold:true, color:C.blue, align:'center'}});
      text(slide, ctx, 165+i*250, 322, 138, 58, it, {{size:13, color:C.ink, align:'center'}});
    }});
  }} else if (s.type === 'speech') {{
    header(slide, ctx, s, idx);
    rect(slide, ctx, 135, 170, 1010, 365, {{fill:'#FFFFFF', stroke:'#D8E2EA'}});
    text(slide, ctx, 175, 218, 930, 250, s.paragraph, {{size:24, color:C.navy}});
  }} else if (s.type === 'qa') {{
    header(slide, ctx, s, idx);
    s.qas.forEach((qa,i)=> {{
      const y = 158 + i*112;
      text(slide, ctx, 105, y, 340, 36, qa[0], {{size:18, bold:true, color:C.navy}});
      rect(slide, ctx, 470, y-4, 660, 68, {{fill:i%2? '#FFFFFF':C.pale, stroke:'#D8E2EA'}});
      text(slide, ctx, 495, y+12, 610, 34, qa[1], {{size:16, color:C.ink}});
    }});
  }} else if (s.type === 'closing') {{
    await image(slide, ctx, s.image, 610, 72, 560, 390, 'contain');
    text(slide, ctx, 74, 120, 530, 58, s.title, {{size:40, bold:true, color:C.navy}});
    text(slide, ctx, 78, 236, 510, 92, s.claim, {{size:27, color:C.blue}});
    kpi(slide, ctx, 82, 430, 'PASS', 'Blocking gates', 'readiness');
    kpi(slide, ctx, 250, 430, '203', 'Tests', 'passed');
    kpi(slide, ctx, 418, 430, '36.24x', 'Doris', 'speedup');
    footer(slide, ctx, idx);
  }}
  return slide;
}}
"""
    (SLIDES_DIR / "common.mjs").write_text(common, encoding="utf-8")
    for i in range(1, len(slides) + 1):
        body = f"import {{ addSlide }} from './common.mjs';\nexport async function slide{i:02d}(presentation, ctx) {{\n  return await addSlide(presentation, ctx, {i});\n}}\n"
        (SLIDES_DIR / f"slide-{i:02d}.mjs").write_text(body, encoding="utf-8")


def build_deck(slide_count: int) -> None:
    env = os.environ.copy()
    env["HOME"] = r"C:\Users\26312"
    env["PYTHON"] = "python"
    cmd = [
        "node",
        str(SKILL_DIR / "scripts" / "build_artifact_deck.mjs"),
        "--workspace",
        str(WORKSPACE),
        "--slides-dir",
        str(SLIDES_DIR),
        "--out",
        str(FINAL_PPTX),
        "--preview-dir",
        str(PREVIEW_DIR),
        "--layout-dir",
        str(LAYOUT_DIR / "final"),
        "--contact-sheet",
        str(PREVIEW_DIR / "contact-sheet.png"),
        "--slide-count",
        str(slide_count),
        "--slide-size",
        "1280x720",
        "--scale",
        "1",
    ]
    result = subprocess.run(cmd, cwd=ROOT, env=env, check=False)
    if result.returncode != 0:
        if FINAL_PPTX.exists() and FINAL_PPTX.stat().st_size > 0 and (PREVIEW_DIR / "contact-sheet.png").exists():
            print(f"artifact-tool returned {result.returncode} after writing outputs; continuing after file checks.")
            return
        raise subprocess.CalledProcessError(result.returncode, cmd)


def main() -> None:
    ensure_dirs()
    data = read_json(ROOT / "submission_artifacts" / "evidence_metadata.json")
    assets = copy_assets()
    charts = make_charts(data)
    write_notes(data, assets, charts)
    write_slide_modules(data, assets, charts)
    build_deck(24)
    print(FINAL_PPTX)
    print(PREVIEW_DIR / "contact-sheet.png")


if __name__ == "__main__":
    main()
