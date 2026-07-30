from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from findsl.official.external.runtime import default_external_scope_catalog
from findsl.official.frontend.antlr_frontend import AntlrOfficialFrontend
from findsl.official.physical.scopes import default_security_scope_catalog


SCOPE_SLOT_FUNCTIONS = {
    "indicator",
    "rank",
    "cross_above",
    "cross_down",
    "close_together",
    "reset",
    "golden_cross",
    "record_high",
    "record_low",
    "position",
    "belong_industry",
    "queryData",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--funnel", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--include-resolved",
        action="store_true",
        help="include atoms already available in the current runtime catalogs",
    )
    args = parser.parse_args()
    report = json.loads(Path(args.funnel).read_text(encoding="utf-8"))
    all_counts = Counter()
    for row in report["rows"]:
        if not (
            row["legacy_strict_success"]
            and not row["new_backend_success"]
            and row["terminal_code"] == "PHYSICAL_SCOPE_DATA_UNAVAILABLE"
        ):
            continue
        parsed = AntlrOfficialFrontend().parse(row["source"])
        _collect_scope_atoms(parsed.ast, all_counts)
    counts = (
        all_counts
        if args.include_resolved
        else _unresolved_counts(
            all_counts,
            default_security_scope_catalog(),
            default_external_scope_catalog(),
        )
    )
    payload = {
        "schema_version": 1,
        "source_sha256": report["source_sha256"],
        "all_target_count": len(all_counts),
        "all_occurrences": sum(all_counts.values()),
        "resolved_target_count": len(all_counts) - len(counts),
        "resolved_occurrences": sum(all_counts.values()) - sum(counts.values()),
        "target_count": len(counts),
        "occurrences": sum(counts.values()),
        "targets": [
            {"name": name, "occurrences": count}
            for name, count in counts.most_common()
        ],
        "aliases": {},
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"targets={len(counts)} occurrences={sum(counts.values())} output={output}")


def _collect_scope_atoms(node, counts: Counter) -> None:
    if node.__class__.__name__ == "OfficialFunctionCall" and node.name in SCOPE_SLOT_FUNCTIONS:
        value = getattr(node.args[1], "value", "") if len(node.args) > 1 else ""
        for atom in re.split(r"[|&^]", str(value or "")):
            if atom.strip():
                counts[atom.strip()] += 1
    for attribute in ("left", "right", "expr"):
        child = getattr(node, attribute, None)
        if child is not None:
            _collect_scope_atoms(child, counts)


def _unresolved_counts(counts: Counter, security_catalog, external_catalog) -> Counter:
    unresolved = Counter()
    for atom, occurrences in counts.items():
        for catalog in (security_catalog, external_catalog):
            try:
                catalog.resolve(atom)
                break
            except KeyError:
                continue
        else:
            unresolved[atom] = occurrences
    return unresolved


if __name__ == "__main__":
    main()
