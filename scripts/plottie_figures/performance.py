from __future__ import annotations

import matplotlib.pyplot as plt

from .common import (
    BLUE,
    DOUBLE_IN,
    GREEN,
    INK,
    MUTED,
    ORANGE,
    RULE,
    TEXT,
    FigureSpec,
    add_source,
    axis_off,
    clean_axes,
    figure_header,
    panel_label,
    save_figure,
)


def _format_ms(value: float) -> str:
    if value >= 1000:
        return f"{value / 1000:.2f} s"
    return f"{value:.1f} ms"


def fig_09(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    doris = metrics["doris"]
    baseline = doris["baseline"]
    optimized = doris["optimized"]
    rows = [
        ("mean execute", baseline["avg_execute_ms"], optimized["avg_execute_ms"]),
        ("P95 execute", baseline["p95_execute_ms"], optimized["p95_execute_ms"]),
    ]

    fig = plt.figure(figsize=(DOUBLE_IN, 4.2))
    gs = fig.add_gridspec(
        1,
        3,
        left=0.075,
        right=0.98,
        top=0.81,
        bottom=0.18,
        width_ratios=[1.45, 0.72, 0.82],
        wspace=0.38,
    )
    figure_header(fig, spec)

    ax_a = fig.add_subplot(gs[0, 0])
    panel_label(ax_a, "a")
    y_positions = [1, 0]
    for y, (label, base, opt) in zip(y_positions, rows):
        ax_a.hlines(y, opt, base, color=RULE, lw=1.0, zorder=1)
        ax_a.scatter(base, y, s=42, facecolor="white", edgecolor=INK, lw=0.7, zorder=3)
        ax_a.scatter(opt, y, s=42, facecolor=BLUE, edgecolor=INK, lw=0.7, zorder=3)
        ax_a.text(base * 1.04, y + 0.09, _format_ms(base), ha="left", va="bottom", fontsize=5.2, color=TEXT)
        ax_a.text(opt * 0.95, y - 0.13, _format_ms(opt), ha="right", va="top", fontsize=5.2, color=TEXT)
    ax_a.axvline(10_000, color=ORANGE, lw=0.65, ls=(0, (3, 2)))
    ax_a.text(10_000, 1.34, "10 s requirement", rotation=90, va="top", ha="right", fontsize=5.0, color=ORANGE)
    ax_a.set_xscale("log")
    ax_a.set_xlim(80, 14_000)
    ax_a.set_ylim(-0.45, 1.45)
    ax_a.set_yticks(y_positions, [row[0] for row in rows])
    ax_a.set_xlabel("Doris latency (ms, log scale)")
    ax_a.spines["left"].set_visible(False)
    ax_a.tick_params(axis="y", length=0)
    ax_a.grid(axis="x", which="major", color=RULE, lw=0.32, alpha=0.65)
    clean_axes(ax_a)
    ax_a.scatter([], [], s=42, facecolor="white", edgecolor=INK, lw=0.7, label="baseline window")
    ax_a.scatter([], [], s=42, facecolor=BLUE, edgecolor=INK, lw=0.7, label="prefix-sum")
    ax_a.legend(loc="lower right", frameon=False, handletextpad=0.25, borderaxespad=0.0)

    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_b, "b")
    speedup = float(doris["speedup"])
    min_speedup = float(doris["min_speedup"])
    ax_b.hlines([0], min_speedup, speedup, color=RULE, lw=1.0)
    ax_b.scatter([min_speedup], [0], s=38, facecolor="white", edgecolor=INK, lw=0.7, zorder=3)
    ax_b.scatter([speedup], [0], s=46, facecolor=GREEN, edgecolor=INK, lw=0.7, zorder=3)
    ax_b.set_xscale("log")
    ax_b.set_xlim(7, 55)
    ax_b.set_ylim(-0.42, 0.42)
    ax_b.set_yticks([0], ["speedup"])
    ax_b.set_xticks([min_speedup, speedup], [f"{min_speedup:.0f}x", f"{speedup:.2f}x"])
    ax_b.minorticks_off()
    ax_b.set_xlabel("fold change")
    ax_b.text(min_speedup, 0.15, "target", ha="center", va="bottom", fontsize=5.1, color=MUTED)
    ax_b.text(speedup, -0.15, "observed", ha="center", va="top", fontsize=5.1, color=TEXT)
    ax_b.spines["left"].set_visible(False)
    ax_b.tick_params(axis="y", length=0)
    ax_b.grid(axis="x", which="major", color=RULE, lw=0.32, alpha=0.65)
    clean_axes(ax_b)

    ax_c = fig.add_subplot(gs[0, 2])
    panel_label(ax_c, "c")
    axis_off(ax_c)
    table_rows = [
        ("iterations", str(doris["iterations"])),
        ("row parity", "PASS" if doris["row_counts_match"] else "FAIL"),
        ("baseline rows", f"{baseline['row_count']:,}"),
        ("optimized rows", f"{optimized['row_count']:,}"),
        ("snapshot", doris["generated_at"][:10]),
    ]
    ax_c.plot([0.03, 0.97], [0.88, 0.88], color=INK, lw=0.65)
    for i, (key, value) in enumerate(table_rows):
        y = 0.78 - i * 0.135
        ax_c.text(0.03, y, key, ha="left", va="center", fontsize=5.5, fontweight="bold")
        ax_c.text(0.97, y, value, ha="right", va="center", fontsize=5.5, color=TEXT)
        ax_c.plot([0.03, 0.97], [y - 0.065, y - 0.065], color=RULE, lw=0.35)
    ax_c.text(
        0.03,
        0.08,
        "Frozen Doris snapshot reused for plotting; this run did not re-measure live Doris latency.",
        ha="left",
        va="bottom",
        fontsize=4.9,
        color=MUTED,
        wrap=True,
    )
    add_source(fig, spec.source)
    return save_figure(fig, spec)


BUILDERS = {
    "FIG-09": fig_09,
}
