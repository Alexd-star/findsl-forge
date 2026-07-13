from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

from .common import (
    BLUE,
    BLUE_LIGHT,
    DOUBLE_IN,
    GREEN,
    INK,
    MUTED,
    RULE,
    TEXT,
    WHITE,
    FigureSpec,
    add_source,
    axis_off,
    figure_header,
    panel_label,
    save_figure,
    thin_arrow,
)


def fig_03(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 4.15))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.12)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    layers = [
        ("interface", "cli.py / demo.py"),
        ("adapter", "llm_adapter.py / nl2dsl.py"),
        ("compiler", "parser.py / semantic.py / sqlgen.py"),
        ("registry", "configs/*.json"),
        ("oracle", "reference.py / evaluator.py"),
        ("evidence", "reports / submission_artifacts / outputs"),
    ]
    y0 = 0.91
    for i, (name, detail) in enumerate(layers):
        y = y0 - i * 0.125
        ax.plot([0.10, 0.88], [y, y], color=RULE, lw=0.45)
        ax.add_patch(Rectangle((0.12, y - 0.035), 0.14, 0.07, facecolor=BLUE_LIGHT if name == "compiler" else WHITE, edgecolor=INK, lw=0.55))
        ax.text(0.19, y, name, ha="center", va="center", fontsize=5.8, fontweight="bold" if name == "compiler" else "normal")
        ax.text(0.31, y, detail, ha="left", va="center", fontsize=5.5, color=TEXT)
    for i in range(len(layers) - 1):
        y = y0 - i * 0.125
        thin_arrow(ax, (0.19, y - 0.038), (0.19, y - 0.087))
    ax.text(0.10, 0.08, "Plottie mapping: layered architecture as a dependency schematic, not a dashboard block layout.", fontsize=5.2, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_04(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 3.95))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.83, bottom=0.12)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    nodes = {
        "cli": (0.15, 0.58),
        "compiler": (0.36, 0.72),
        "sqlgen": (0.57, 0.72),
        "reference": (0.57, 0.44),
        "official": (0.78, 0.62),
        "evidence": (0.78, 0.34),
        "demo": (0.36, 0.34),
    }
    labels = {
        "cli": "cli.py",
        "compiler": "compiler\nparser\nsemantic",
        "sqlgen": "sqlgen.py",
        "reference": "reference\noracle",
        "official": "official\nsuite",
        "evidence": "evidence\nmetadata",
        "demo": "web demo",
    }
    edges = [
        ("cli", "compiler"),
        ("compiler", "sqlgen"),
        ("compiler", "reference"),
        ("sqlgen", "official"),
        ("reference", "official"),
        ("official", "evidence"),
        ("cli", "demo"),
        ("demo", "reference"),
    ]
    for a, b in edges:
        thin_arrow(ax, nodes[a], nodes[b])
    for key, (x, y) in nodes.items():
        ax.add_patch(Circle((x, y), 0.026, facecolor=BLUE if key == "cli" else WHITE, edgecolor=INK, lw=0.65, zorder=3))
        ax.text(x, y - 0.055, labels[key], ha="center", va="top", fontsize=5.4)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_13(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 3.85))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.83, bottom=0.12)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    left = [("indicators.json", 0.72), ("tables.json", 0.55), ("functions.json", 0.38)]
    right = [("semantic", 0.76), ("sqlgen", 0.62), ("reference", 0.48), ("tests", 0.34)]
    for label, y in left:
        ax.add_patch(Rectangle((0.10, y - 0.035), 0.16, 0.07, facecolor=WHITE, edgecolor=INK, lw=0.55))
        ax.text(0.18, y, label, ha="center", va="center", fontsize=5.4)
    for label, y in right:
        ax.add_patch(Rectangle((0.73, y - 0.035), 0.14, 0.07, facecolor=BLUE_LIGHT if label == "sqlgen" else WHITE, edgecolor=INK, lw=0.55))
        ax.text(0.80, y, label, ha="center", va="center", fontsize=5.4)
    for _, ly in left:
        for _, ry in right:
            thin_arrow(ax, (0.27, ly), (0.72, ry), color=RULE)
    ax.text(0.10, 0.18, "Config-only extension means new metadata can reach validation, SQL and tests without editing core compiler logic.", fontsize=5.3, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_16(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 4.35))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.83, bottom=0.10)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    root_x = 0.12
    ax.plot([root_x, root_x], [0.18, 0.82], color=INK, lw=0.65)
    ax.text(root_x, 0.86, "project root", ha="center", fontsize=5.9, fontweight="bold")
    items = [
        ("README.md / PROJECT_INDEX.md", "orientation"),
        ("src/findsl/", "compiler + validation"),
        ("configs/", "business metadata"),
        ("data/", "sample and real data"),
        ("tests/", "regression suite"),
        ("deploy/doris/", "Doris assets"),
        ("docs/", "Chinese documentation"),
        ("submission_artifacts/", "snapshots and evidence"),
        ("outputs/可视化证据包_plottie_style/", "Plottie-style figures"),
    ]
    for i, (name, desc) in enumerate(items):
        y = 0.80 - i * 0.073
        ax.plot([root_x, 0.26], [y, y], color=RULE, lw=0.45)
        ax.add_patch(Circle((0.26, y), 0.0075, facecolor=BLUE if "plottie" in name else WHITE, edgecolor=INK, lw=0.45))
        ax.text(0.29, y + 0.012, name, ha="left", va="center", fontsize=5.5, fontweight="bold" if "plottie" in name else "normal")
        ax.text(0.68, y + 0.012, desc, ha="left", va="center", fontsize=5.1, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_17(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    doris = metrics["doris"]
    fig = plt.figure(figsize=(DOUBLE_IN, 3.85))
    gs = fig.add_gridspec(1, 2, left=0.07, right=0.98, top=0.82, bottom=0.16, width_ratios=[1.20, 0.86], wspace=0.32)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    lanes = [
        (0.66, "real-market sample", "semantic realism\n3/3 SQL-reference cases", GREEN),
        (0.39, "Doris scale evidence", f"5M cardinality\nrow parity: {doris['row_counts_match']}\nspeedup: {doris['speedup']:.2f}x", BLUE),
    ]
    for y, title, body, color in lanes:
        ax_a.plot([0.12, 0.88], [y, y], color=INK, lw=0.65)
        ax_a.add_patch(Circle((0.12, y), 0.012, facecolor=color, edgecolor=INK, lw=0.5))
        ax_a.add_patch(Circle((0.88, y), 0.012, facecolor=WHITE, edgecolor=INK, lw=0.5))
        ax_a.text(0.15, y + 0.055, title, fontsize=5.8, fontweight="bold")
        ax_a.text(0.15, y - 0.035, body, va="top", fontsize=5.3, color=TEXT)
    ax_a.text(0.12, 0.14, "Claim boundary: realism and scale performance are complementary evidence lanes.", fontsize=5.1, color=MUTED)
    panel_label(ax_b, "b")
    cols = ["semantic", "scale", "latency"]
    rows = ["real sample", "Doris evidence"]
    data = [[1, 0, 0], [0, 1, 1]]
    ax_b.imshow(data, cmap=mpl.colors.ListedColormap([WHITE, BLUE_LIGHT]), vmin=0, vmax=1, aspect="auto")
    ax_b.set_xticks(range(len(cols)), cols, rotation=28, ha="right")
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


BUILDERS = {
    "FIG-03": fig_03,
    "FIG-04": fig_04,
    "FIG-13": fig_13,
    "FIG-16": fig_16,
    "FIG-17": fig_17,
}
