from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

from .common import (
    BLUE,
    BLUE_LIGHT,
    DOUBLE_IN,
    GREEN,
    INK,
    MUTED,
    RED,
    RULE,
    WHITE,
    FigureSpec,
    add_source,
    axis_off,
    clean_axes,
    figure_header,
    panel_label,
    save_figure,
)


def fig_08(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    md = metrics["metadata"]
    fig = plt.figure(figsize=(DOUBLE_IN, 3.75))
    gs = fig.add_gridspec(1, 2, left=0.07, right=0.98, top=0.82, bottom=0.17, width_ratios=[1.05, 0.95], wspace=0.28)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    axis_off(ax_a)
    levels = [("scan quote_ohlcv", 0.76), ("window SUM(volume,120)", 0.58), ("filter threshold", 0.40)]
    for text, y in levels:
        ax_a.plot([0.20, 0.72], [y, y], color=INK, lw=0.55)
        ax_a.text(0.18, y, text, ha="right", va="center", fontsize=5.5)
    ax_a.text(0.20, 0.86, "baseline plan", fontsize=5.8, fontweight="bold")
    ax_a.text(0.20, 0.22, "optimized plan: prefix table predicate + join", fontsize=5.3, color=BLUE)
    panel_label(ax_b, "b")
    rows = ["window path", "prefix table", "row parity", "target met"]
    cols = ["baseline", "optimized"]
    data = [
        [int(md["doris_cluster"]["baseline_plan_contains_window"]), 0],
        [0, int(md["doris_cluster"]["optimized_plan_contains_prefix"])],
        [int(md["doris_cluster"]["row_counts_match"]), int(md["doris_cluster"]["row_counts_match"])],
        [0, int(md["doris_cluster"]["speedup_target_met"])],
    ]
    ax_b.imshow(data, cmap=mpl.colors.ListedColormap([WHITE, BLUE_LIGHT]), vmin=0, vmax=1, aspect="auto")
    ax_b.set_xticks(range(len(cols)), cols)
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


def fig_10(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    md = metrics["metadata"]
    r = md["readiness"]
    labels = ["blocking gates", "warning count", "official +", "official -", "defense checks", "Doris evidence", "metadata warnings"]
    values = [
        1.0 if r["blocking_gates_passed"] else 0.0,
        1.0 if r["warning_count"] == 0 else 0.0,
        md["official_suite"]["positive"]["passed"] / md["official_suite"]["positive"]["total"],
        md["official_suite"]["negative"]["passed"] / md["official_suite"]["negative"]["total"],
        r["defense_package_checks"]["passed"] / r["defense_package_checks"]["total"],
        1.0 if md["doris_cluster"]["passed"] else 0.0,
        1.0 if not md.get("warnings") else 0.0,
    ]
    fig = plt.figure(figsize=(DOUBLE_IN, 4.2))
    gs = fig.add_gridspec(1, 2, left=0.08, right=0.98, top=0.82, bottom=0.16, width_ratios=[1.15, 0.9], wspace=0.34)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    ys = list(range(len(labels)))
    ax_a.hlines(ys, 0, values, color=RULE, lw=0.9)
    ax_a.scatter(values, ys, s=38, facecolor=BLUE, edgecolor=INK, zorder=3)
    ax_a.set_yticks(ys, labels)
    ax_a.set_xlim(0, 1.05)
    ax_a.set_xlabel("pass fraction")
    ax_a.invert_yaxis()
    ax_a.spines["left"].set_visible(False)
    ax_a.tick_params(axis="y", length=0)
    clean_axes(ax_a)
    panel_label(ax_b, "b")
    axis_off(ax_b)
    rows = [
        ("pytest", f"{r['pytest']['passed']} passed", f"{r['pytest']['elapsed_seconds']:.2f}s"),
        ("compile P95", f"{r['compile_p95_latency_ms']:.3f} ms", "<50 ms"),
        ("official", "37/37 + 37/37", "pos/neg"),
        ("Doris", md["doris_cluster"]["speedup_display"], "prefix path"),
        ("Git HEAD", md["git"]["head_at_export"], "export"),
    ]
    y0 = 0.82
    ax_b.plot([0.05, 0.95], [0.90, 0.90], color=INK, lw=0.65)
    for i, (a, b, c) in enumerate(rows):
        y = y0 - i * 0.15
        ax_b.text(0.05, y, a, ha="left", va="center", fontsize=5.7, fontweight="bold")
        ax_b.text(0.43, y, b, ha="left", va="center", fontsize=5.7)
        ax_b.text(0.82, y, c, ha="left", va="center", fontsize=5.2, color=MUTED)
        ax_b.plot([0.05, 0.95], [y - 0.065, y - 0.065], color=RULE, lw=0.35)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


def fig_11(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    items = metrics["topic_items"]
    status_order = ["implemented", "partial", "needs_evidence"]
    colors = mpl.colors.ListedColormap([BLUE_LIGHT, "#E8E8E8", "#F0D5D2"])
    status_to_code = {status: i for i, status in enumerate(status_order)}
    data = [[1 if status_to_code[item["status"]] == c else 0 for c in range(3)] for item in items]
    fig = plt.figure(figsize=(DOUBLE_IN, 4.75))
    gs = fig.add_gridspec(1, 2, left=0.08, right=0.98, top=0.83, bottom=0.19, width_ratios=[1.25, 0.65], wspace=0.32)
    figure_header(fig, spec)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_a, "a")
    ax_a.imshow(data, cmap=colors, vmin=0, vmax=1, aspect="auto")
    ax_a.set_yticks(range(len(items)), [item["id"] for item in items])
    ax_a.set_xticks(range(3), status_order, rotation=28, ha="right")
    ax_a.tick_params(length=0)
    for x in range(4):
        ax_a.axvline(x - 0.5, color=RULE, lw=0.35)
    for y in range(len(items) + 1):
        ax_a.axhline(y - 0.5, color=RULE, lw=0.35)
    for r_i, item in enumerate(items):
        ax_a.text(status_to_code[item["status"]], r_i, "1", ha="center", va="center", fontsize=5.2)
    for spine in ax_a.spines.values():
        spine.set_visible(False)
    panel_label(ax_b, "b")
    summary = metrics["topic_summary"]
    labels = ["implemented", "partial", "needs evidence"]
    values = [summary["implemented"], summary["partial"], summary["needs_evidence"]]
    ax_b.barh(range(3), values, color=[BLUE, MUTED, RED], edgecolor=INK, lw=0.35, height=0.44)
    ax_b.set_yticks(range(3), labels)
    ax_b.invert_yaxis()
    ax_b.set_xlabel("count")
    ax_b.spines["left"].set_visible(False)
    ax_b.tick_params(axis="y", length=0)
    for i, value in enumerate(values):
        ax_b.text(value + 0.08, i, str(value), va="center", fontsize=5.7)
    clean_axes(ax_b)
    add_source(fig, spec.source)
    return save_figure(fig, spec)


BUILDERS = {
    "FIG-08": fig_08,
    "FIG-10": fig_10,
    "FIG-11": fig_11,
}

