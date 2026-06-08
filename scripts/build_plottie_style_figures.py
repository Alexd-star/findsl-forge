from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.plottie_figures.common import SPECS, latest_metrics, reset_output, setup_style, write_outputs
from scripts.plottie_figures.flow import BUILDERS as FLOW_BUILDERS
from scripts.plottie_figures.image_plates import BUILDERS as IMAGE_PLATE_BUILDERS
from scripts.plottie_figures.matrices import BUILDERS as MATRIX_BUILDERS
from scripts.plottie_figures.network import BUILDERS as NETWORK_BUILDERS
from scripts.plottie_figures.performance import BUILDERS as PERFORMANCE_BUILDERS


def main() -> int:
    setup_style()
    metrics = latest_metrics()
    reset_output()

    builders = {}
    for group in [FLOW_BUILDERS, NETWORK_BUILDERS, MATRIX_BUILDERS, PERFORMANCE_BUILDERS, IMAGE_PLATE_BUILDERS]:
        overlap = set(builders).intersection(group)
        if overlap:
            raise RuntimeError(f"Duplicate figure builders: {sorted(overlap)}")
        builders.update(group)

    expected = {spec.fig_id for spec in SPECS}
    missing = sorted(expected.difference(builders))
    extra = sorted(set(builders).difference(expected))
    if missing or extra:
        raise RuntimeError(f"Figure builder mismatch; missing={missing}; extra={extra}")

    rows = []
    for spec in SPECS:
        paths = builders[spec.fig_id](spec, metrics)
        rows.append({"spec": spec, "paths": paths})
        print(f"{spec.fig_id} {spec.title} -> {paths['png']}")

    write_outputs(metrics, rows)
    print("Plottie-style figure package generated: outputs/可视化证据包_plottie_style")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
