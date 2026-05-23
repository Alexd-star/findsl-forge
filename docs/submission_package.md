# Submission Package Runbook

This runbook turns local generated reports into a versioned competition package.

## Export Evidence Snapshots

`reports/` is intentionally ignored because it is a generated working directory. Before a final commit or submission bundle, export the current lightweight reports:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
```

The command writes:

- `submission_artifacts/evidence_manifest.md`
- `submission_artifacts/evidence_snapshots/submission_readiness.md`
- `submission_artifacts/evidence_snapshots/doris_cluster_evidence.md`
- `submission_artifacts/evidence_snapshots/official_suite_report.md`
- `submission_artifacts/evidence_snapshots/defense_package.md`

Large CSV files under `data/generated/` remain excluded. Recreate them with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_doris_scale_evidence.ps1
```

## Final Review Checklist

- `git status --short --branch` is clean after exporting artifacts and committing.
- `submission_artifacts/evidence_snapshots/submission_readiness.md` says blocking gates passed and warning count is zero.
- `submission_artifacts/evidence_snapshots/doris_cluster_evidence.md` contains row-count match, prefix-table optimized plan, baseline window plan, and speedup above target.
- `submission_artifacts/demo_script.md` has been rehearsed once on the target machine.
- The final PPT follows `submission_artifacts/defense_ppt_outline.md`.
