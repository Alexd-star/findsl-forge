from pathlib import Path

from findsl.official.performance_evidence import (
    validate_performance_evidence_registry,
    write_performance_evidence_report,
)


def main() -> int:
    report = validate_performance_evidence_registry(
        Path("configs/official/performance_evidence_registry.json")
    )
    write_performance_evidence_report(
        report,
        Path("reports/performance_evidence_registry.json"),
        Path("reports/performance_evidence_registry.md"),
    )
    print(f"status={report['status']} metrics={len(report['metrics'])}")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
