from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from PIL import Image

from .common import (
    DOUBLE_IN,
    INK,
    MUTED,
    ROOT,
    FigureSpec,
    figure_header,
    save_figure,
)


def _find_screenshot(ev_id: str) -> Path | None:
    screenshot_dir = ROOT / "submission_artifacts" / "visual_evidence" / "screenshots"
    found = sorted(screenshot_dir.glob(f"{ev_id}_*.png"))
    if found:
        return found[0]
    fallback = ROOT / "submission_artifacts" / "demo_screenshots"
    name_map = {
        "EV-043": "02_positive_sql.png",
        "EV-044": "03_positive_ast.png",
        "EV-045": "04_positive_explain.png",
        "EV-046": "05_positive_rows.png",
        "EV-047": "06_positive_evidence.png",
        "EV-048": "07_negative_unknown_indicator.png",
    }
    if ev_id in name_map:
        path = fallback / name_map[ev_id]
        if path.exists():
            return path
    return None


def fig_15(spec: FigureSpec, metrics: dict) -> dict[str, str]:
    panel_ids = [
        ("EV-041", "main"),
        ("EV-042", "params"),
        ("EV-043", "SQL"),
        ("EV-044", "AST"),
        ("EV-045", "EXPLAIN"),
        ("EV-046", "rows"),
        ("EV-047", "evidence"),
        ("EV-048", "diagnostic"),
    ]
    paths = [(ev_id, label, _find_screenshot(ev_id)) for ev_id, label in panel_ids]

    fig = plt.figure(figsize=(DOUBLE_IN, 4.85))
    fig.subplots_adjust(left=0.04, right=0.98, top=0.86, bottom=0.08)
    figure_header(fig, spec, left=0.05)

    x0, y0 = 0.055, 0.60
    panel_w, panel_h = 0.205, 0.305
    x_gap, y_gap = 0.030, 0.35
    for i, (ev_id, label, path) in enumerate(paths):
        row, col = divmod(i, 4)
        ax = fig.add_axes([x0 + col * (panel_w + x_gap), y0 - row * y_gap, panel_w, panel_h])
        if path is None:
            ax.text(0.5, 0.5, f"{ev_id}\nmissing", ha="center", va="center", fontsize=6.0, color=MUTED)
        else:
            with Image.open(path) as img:
                ax.imshow(img.convert("RGB"))
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color(INK)
            spine.set_linewidth(0.35)
        ax.text(-0.02, 1.045, chr(ord("a") + i), transform=ax.transAxes, ha="left", va="bottom", fontsize=8.0, fontweight="bold")
        ax.text(0.10, 1.045, f"{ev_id} {label}", transform=ax.transAxes, ha="left", va="bottom", fontsize=5.0, color=MUTED)

    fig.text(
        0.05,
        0.025,
        "Source: actual Web Demo screenshots EV-041 to EV-048; screenshots are placed as an image plate without synthetic UI reconstruction.",
        fontsize=5.0,
        color=MUTED,
        ha="left",
        va="bottom",
    )
    return save_figure(fig, spec)


BUILDERS = {
    "FIG-15": fig_15,
}
