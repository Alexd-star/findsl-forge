from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

from .common import (
    BLUE,
    BLUE_LIGHT,
    DOUBLE_IN,
    GOLD,
    GREEN,
    INK,
    MUTED,
    ORANGE,
    RED,
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
    wrap_label,
)


def stage_row(ax, labels: list[str], y: float, x0: float = 0.08, x1: float = 0.92, highlights: set[int] | None = None) -> None:
    highlights = highlights or set()
    xs = [x0 + i * (x1 - x0) / (len(labels) - 1) for i in range(len(labels))]
    ax.plot([x0, x1], [y, y], color=INK, lw=0.7)
    for i, (x, label) in enumerate(zip(xs, labels)):
        ax.plot([x, x], [y - 0.04, y + 0.04], color=INK, lw=0.45)
        ax.add_patch(Circle((x, y), 0.012, facecolor=BLUE if i in highlights else WHITE, edgecolor=INK, lw=0.55, zorder=3))
        ax.text(x, y + 0.065, wrap_label(label, 12), ha="center", va="bottom", fontsize=5.8)


def fig_01(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig = plt.figure(figsize=(DOUBLE_IN, 3.55))
    gs = fig.add_gridspec(1, 2, left=0.06, right=0.98, top=0.83, bottom=0.16, width_ratios=[1.35, 0.85], wspace=0.28)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    stage_row(ax_a, ["input", "DSL/AST", "Doris SQL", "reference", "performance", "evidence"], 0.62, highlights={1, 2, 4})
    ax_a.plot([0.08, 0.92], [0.32, 0.32], color=RULE, lw=0.55)
    ax_a.text(0.08, 0.39, "claim-to-evidence chain", fontsize=5.8, fontweight="bold")
    ax_a.text(0.08, 0.25, "Every figure and report must map to code, tests, or frozen evidence.", fontsize=5.4, color=MUTED)
    panel_label(ax_b, "b")
    summary = metrics["topic_summary"]
    labels = ["implemented", "partial", "needs evidence"]
    values = [summary.get("implemented", 0), summary.get("partial", 0), summary.get("needs_evidence", 0)]
    colors = [BLUE, MUTED, RED]
    y = range(len(labels))
    ax_b.barh(list(y), values, color=colors, edgecolor=INK, lw=0.35, height=0.42)
    ax_b.set_yticks(list(y), labels)
    ax_b.set_xlabel("requirement count")
    ax_b.set_xlim(0, max(values) + 1)
    ax_b.invert_yaxis()
    ax_b.tick_params(axis="y", length=0)
    ax_b.spines["left"].set_visible(False)
    for pos, value in enumerate(values):
        ax_b.text(value + 0.08, pos, str(value), va="center", fontsize=5.8)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_02(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 3.25))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.82, bottom=0.14)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    nodes = [
        (0.10, 0.58, "Chinese request"),
        (0.27, 0.58, "candidate DSL"),
        (0.45, 0.58, "typed compiler"),
        (0.64, 0.58, "reference check"),
        (0.84, 0.58, "Doris SQL"),
    ]
    for i, (x, y, label) in enumerate(nodes):
        ax.add_patch(Circle((x, y), 0.017, facecolor=BLUE if i in {2, 4} else WHITE, edgecolor=INK, lw=0.55))
        ax.text(x, y + 0.07, wrap_label(label, 13), ha="center", fontsize=5.7)
        if i:
            thin_arrow(ax, (nodes[i - 1][0] + 0.025, y), (x - 0.025, y))
    ax.plot([0.35, 0.35], [0.25, 0.78], color=RED, lw=0.65, ls=(0, (4, 2)))
    ax.text(0.35, 0.21, "trust boundary", ha="center", fontsize=5.2, color=RED)
    thin_arrow(ax, (0.45, 0.52), (0.45, 0.36), color=RED)
    ax.text(0.48, 0.36, "reject invalid /\nunsafe DSL", va="center", fontsize=5.2, color=TEXT)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_05(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 3.9))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.83, bottom=0.12)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    steps = [
        ("environment", "python, pytest, project path"),
        ("run gates", "pytest + readiness + metadata"),
        ("inspect outputs", "reports, evidence snapshots"),
        ("capture visuals", "terminal, web, figures"),
        ("submit", "git HEAD + checksum"),
    ]
    xs = [0.12, 0.31, 0.50, 0.69, 0.88]
    ax.plot([xs[0], xs[-1]], [0.56, 0.56], color=INK, lw=0.7)
    for i, ((title, body), x) in enumerate(zip(steps, xs)):
        ax.add_patch(Circle((x, 0.56), 0.014, facecolor=BLUE if i in {1, 4} else WHITE, edgecolor=INK, lw=0.55))
        ax.text(x, 0.68, title, ha="center", fontsize=5.9, fontweight="bold")
        ax.text(x, 0.43, wrap_label(body, 16), ha="center", va="top", fontsize=5.2, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_06(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 3.7))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.83, bottom=0.13)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    boxes = [
        (0.11, 0.61, "lexer\nparser"),
        (0.30, 0.61, "typed\nAST"),
        (0.49, 0.61, "semantic\ngates"),
        (0.69, 0.61, "SQL\nemitter"),
        (0.88, 0.61, "Doris-safe\nSQL"),
    ]
    for i, (x, y, label) in enumerate(boxes):
        ax.add_patch(Rectangle((x - 0.055, y - 0.045), 0.11, 0.09, facecolor=BLUE_LIGHT if i in {1, 3} else WHITE, edgecolor=INK, lw=0.55))
        ax.text(x, y, label, ha="center", va="center", fontsize=5.7)
        if i:
            thin_arrow(ax, (boxes[i - 1][0] + 0.06, y), (x - 0.06, y))
    thin_arrow(ax, (0.49, 0.55), (0.49, 0.34), color=RED)
    ax.text(0.52, 0.34, "stable diagnostic\ncode + repair hint", va="center", fontsize=5.4, color=TEXT)
    ax.text(0.11, 0.26, "No SQL is emitted before the typed and semantic gates pass.", fontsize=5.3, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_07(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    doris = metrics["doris"]
    fig = plt.figure(figsize=(DOUBLE_IN, 3.65))
    gs = fig.add_gridspec(1, 2, left=0.07, right=0.98, top=0.82, bottom=0.16, width_ratios=[1.25, 0.8], wspace=0.30)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    ax_a.text(0.08, 0.72, "rolling SUM(volume, w)", fontsize=6.2, fontweight="bold")
    thin_arrow(ax_a, (0.33, 0.70), (0.54, 0.70))
    ax_a.text(0.57, 0.72, "prefix(t) - prefix(t-w)", fontsize=6.2, fontweight="bold", color=BLUE)
    ax_a.plot([0.08, 0.90], [0.50, 0.50], color=RULE, lw=0.55)
    ax_a.text(0.08, 0.42, "rewrite only when table, window and indicator metadata prove the path is safe", fontsize=5.4, color=MUTED)
    ax_a.text(0.08, 0.25, "fallback: Doris window SQL", fontsize=5.5, color=TEXT)
    panel_label(ax_b, "b")
    values = [doris["baseline"]["avg_execute_ms"], doris["optimized"]["avg_execute_ms"]]
    ax_b.plot([values[1], values[0]], [0, 0], color=RULE, lw=1.0)
    ax_b.scatter([values[0]], [0], facecolor=WHITE, edgecolor=INK, s=50, zorder=3, label="baseline")
    ax_b.scatter([values[1]], [0], facecolor=BLUE, edgecolor=INK, s=50, zorder=3, label="prefix")
    ax_b.set_xscale("log")
    ax_b.set_yticks([0], ["mean execute"])
    ax_b.set_xlabel("latency (ms, log scale)")
    ax_b.legend(loc="upper left", frameon=False, ncol=2)
    ax_b.spines["left"].set_visible(False)
    ax_b.tick_params(axis="y", length=0)
    ax_b.text(values[1] * 1.15, 0.06, f"{values[1]:.1f}", fontsize=5.4)
    ax_b.text(values[0] * 1.02, 0.06, f"{values[0]:.0f}", fontsize=5.4)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_12(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 3.45))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.83, bottom=0.14)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    left = [("user text", 0.72), ("LLM proposal", 0.55), ("candidate DSL", 0.38)]
    right = [("compiler", 0.72), ("reference oracle", 0.55), ("safe SQL", 0.38)]
    for title, y in left:
        ax.add_patch(Circle((0.20, y), 0.013, facecolor=WHITE, edgecolor=INK, lw=0.55))
        ax.text(0.24, y, title, va="center", fontsize=5.8)
    for title, y in right:
        ax.add_patch(Circle((0.68, y), 0.013, facecolor=BLUE if title == "safe SQL" else WHITE, edgecolor=INK, lw=0.55))
        ax.text(0.72, y, title, va="center", fontsize=5.8)
    for y in [0.72, 0.55, 0.38]:
        thin_arrow(ax, (0.36, y), (0.64, y))
    ax.plot([0.50, 0.50], [0.26, 0.82], color=RED, lw=0.65, ls=(0, (4, 2)))
    ax.text(0.50, 0.22, "model output is untrusted", ha="center", fontsize=5.2, color=RED)
    ax.text(0.12, 0.13, "direct SQL and unknown indicators are rejected before execution.", fontsize=5.3, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_14(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    fig, ax = plt.subplots(figsize=(DOUBLE_IN, 3.45))
    fig.subplots_adjust(left=0.06, right=0.98, top=0.83, bottom=0.14)
    figure_header(fig, spec)
    panel_label(ax, "a")
    axis_off(ax)
    stages = [
        ("Docker Doris", "FE/BE runtime"),
        ("DDL + data", "schema, stream load"),
        ("prefix tables", "materialized evidence path"),
        ("collect", "EXPLAIN + latency"),
        ("snapshot", "MD/JSON frozen proof"),
    ]
    xs = [0.10, 0.29, 0.48, 0.67, 0.86]
    for i, ((title, body), x) in enumerate(zip(stages, xs)):
        ax.add_patch(Rectangle((x - 0.06, 0.50), 0.12, 0.10, facecolor=BLUE_LIGHT if i == 2 else WHITE, edgecolor=INK, lw=0.55))
        ax.text(x, 0.57, title, ha="center", va="center", fontsize=5.6, fontweight="bold" if i == 2 else "normal")
        ax.text(x, 0.44, wrap_label(body, 16), ha="center", va="top", fontsize=5.0, color=MUTED)
        if i:
            thin_arrow(ax, (xs[i - 1] + 0.065, 0.55), (x - 0.065, 0.55))
    ax.text(0.10, 0.22, "The figure uses frozen evidence snapshots; it does not claim Doris was rerun during plotting.", fontsize=5.3, color=MUTED)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


BUILDERS = {
    "FIG-01": fig_01,
    "FIG-02": fig_02,
    "FIG-05": fig_05,
    "FIG-06": fig_06,
    "FIG-07": fig_07,
    "FIG-12": fig_12,
    "FIG-14": fig_14,
}

