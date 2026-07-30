# Evidence Summary

This summary is generated from `evidence_metadata.json`. Use the snapshot files listed below as the audit source.

## Headline Gates

| Item | Value |
|---|---|
| Blocking gates | PASS |
| Warning count | 0 |
| Pytest regression | 1016 passed in 153.70s |
| Official positive cases | 37/37 |
| Official negative diagnostics | 37/37 |
| Official slot coverage | 1830/5799 compiled |
| ANTLR/IR legacy migration | 1016/1097 (92.62%) |
| Phase 18 dynamic date evidence | PASS, 9/9, max P95 181.0921 ms |
| Phase 19 security scope evidence | PASS, 7/7, catalog PASS, max P95 194.0904 ms |
| Phase 20 mapping/event evidence | PASS, 13/13, non-empty 13/13, max P95 3046.7137 ms |
| Phase 21 aggregate/rank evidence | PASS, 6/6, non-empty 6/6, max P95 527.1584 ms |
| Phase 22 stage/rank evidence | PASS, 7/7, non-empty 7/7, max P95 411.3313 ms |
| Phase 23 temporal/relation evidence | PASS, 6/6, non-empty 6/6, max P95 1122.9697 ms |
| Phase 24 period-scalar evidence | PASS, 4/4, non-empty 4/4, max P95 472.0212 ms |
| Phase 25 event-candidate evidence | PASS, 5/5, non-empty 5/5, max P95 2163.5640 ms |
| Phase 26 date/limit evidence | PASS, 6/6, non-empty 6/6, max P95 732.5326 ms |
| Phase 27 event-semantics evidence | PASS, 4/4, non-empty 4/4, max P95 2090.4077 ms |
| Phase 28 default-price event evidence | PASS, 6/6, non-empty 6/6, max P95 3177.3871 ms |
| Phase 29 generalized event projection evidence | PASS, 4/4, non-empty 4/4, max P95 1512.6686 ms |
| Phase 30 grounded event evidence | PASS, 6/6, non-empty 6/6, max P95 1024.4798 ms |
| Phase 31 final grounded evidence | PASS, 2/2, non-empty 2/2, max P95 64.6454 ms |
| Phase 6C set-prefix evidence | PASS, hash 14/14, faster 14/14, median 1.393x |
| Latest phase new-success audit | PASS, 18/18, failed 0 |
| Official per-query 10s target | PASS, 6 queries, max P95 61.269 ms |
| Official Doris real data | AVAILABLE |
| Official Doris feature tables | PASS |
| Official Doris prefix speedup | 13.99x |
| Official 20-year long-horizon speedup | PASS, 40.52x, median 932 -> 23 ms |
| Defense package checks | 13/13 |
| Doris evidence | PASS |
| Doris cluster speedup | 36.24x |
| Doris row parity | PASS |
| Git HEAD at report generation | 0a9307b |
| Git HEAD at export | 0a9307b |

## Source Files

| Source | Path |
|---|---|
| submission_readiness | `submission_artifacts\evidence_snapshots\submission_readiness.md` |
| official_suite_report | `submission_artifacts\evidence_snapshots\official_suite_report.md` |
| official_doris_evidence_json | `submission_artifacts\evidence_snapshots\official_doris_evidence.json` |
| official_slot_coverage_json | `submission_artifacts\evidence_snapshots\official_slot_coverage.json` |
| official_query_performance_matrix_json | `submission_artifacts\evidence_snapshots\official_query_performance_matrix.json` |
| phase42_long_horizon_doris_json | `submission_artifacts\evidence_snapshots\phase42_long_horizon_doris.json` |
| phase18_dynamic_date_funnel_json | `submission_artifacts\evidence_snapshots\phase18_dynamic_date_funnel.json` |
| phase18_dynamic_date_doris_json | `submission_artifacts\evidence_snapshots\phase18_dynamic_date_doris.json` |
| phase19_security_scope_funnel_json | `submission_artifacts\evidence_snapshots\phase19_security_scope_funnel.json` |
| phase19_security_scope_doris_json | `submission_artifacts\evidence_snapshots\phase19_security_scope_doris.json` |
| phase20_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase20_capability_funnel.json` |
| phase20_mapping_event_doris_json | `submission_artifacts\evidence_snapshots\phase20_mapping_event_doris.json` |
| phase21_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase21_capability_funnel.json` |
| phase21_aggregate_rank_doris_json | `submission_artifacts\evidence_snapshots\phase21_aggregate_rank_doris.json` |
| phase21_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase21_new_success_audit.json` |
| phase22_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase22_capability_funnel.json` |
| phase22_stage_rank_doris_json | `submission_artifacts\evidence_snapshots\phase22_stage_rank_doris.json` |
| phase22_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase22_new_success_audit.json` |
| phase23_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase23_capability_funnel.json` |
| phase23_relational_doris_json | `submission_artifacts\evidence_snapshots\phase23_relational_doris.json` |
| phase23_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase23_new_success_audit.json` |
| phase24_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase24_capability_funnel.json` |
| phase24_period_scalar_doris_json | `submission_artifacts\evidence_snapshots\phase24_period_scalar_doris.json` |
| phase24_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase24_new_success_audit.json` |
| phase25_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase25_capability_funnel.json` |
| phase25_event_candidate_doris_json | `submission_artifacts\evidence_snapshots\phase25_event_candidate_doris.json` |
| phase25_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase25_new_success_audit.json` |
| phase26_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase26_capability_funnel.json` |
| phase26_date_limit_doris_json | `submission_artifacts\evidence_snapshots\phase26_date_limit_doris.json` |
| phase26_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase26_new_success_audit.json` |
| phase27_capability_funnel_json | `submission_artifacts\evidence_snapshots\phase27_capability_funnel.json` |
| phase27_event_semantics_doris_json | `submission_artifacts\evidence_snapshots\phase27_event_semantics_doris.json` |
| phase27_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase27_new_success_audit.json` |
| phase28_default_price_funnel_json | `submission_artifacts\evidence_snapshots\phase28_default_price_funnel.json` |
| phase28_default_price_doris_json | `submission_artifacts\evidence_snapshots\phase28_default_price_doris.json` |
| phase28_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase28_new_success_audit.json` |
| phase29_event_projection_funnel_json | `submission_artifacts\evidence_snapshots\phase29_event_projection_funnel.json` |
| phase29_event_projection_doris_json | `submission_artifacts\evidence_snapshots\phase29_event_projection_doris.json` |
| phase29_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase29_new_success_audit.json` |
| phase30_grounded_event_funnel_json | `submission_artifacts\evidence_snapshots\phase30_grounded_event_funnel.json` |
| phase30_grounded_event_doris_json | `submission_artifacts\evidence_snapshots\phase30_grounded_event_doris.json` |
| phase30_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase30_new_success_audit.json` |
| phase31_final_grounded_funnel_json | `submission_artifacts\evidence_snapshots\phase31_final_grounded_funnel.json` |
| phase31_final_grounded_doris_json | `submission_artifacts\evidence_snapshots\phase31_final_grounded_doris.json` |
| phase31_new_success_audit_json | `submission_artifacts\evidence_snapshots\phase31_new_success_audit.json` |
| phase41_external_scope_funnel_json | `submission_artifacts\evidence_snapshots\phase41_external_scope_funnel.json` |
| phase41_external_scope_delta_doris_audit_json | `submission_artifacts\evidence_snapshots\phase41_external_scope_delta_doris_audit.json` |
| phase43_external_scope_funnel_json | `submission_artifacts\evidence_snapshots\phase43_external_scope_funnel.json` |
| phase43_external_scope_delta_doris_audit_json | `submission_artifacts\evidence_snapshots\phase43_external_scope_delta_doris_audit.json` |
| phase43_true_remaining_scope_targets_json | `submission_artifacts\evidence_snapshots\phase43_true_remaining_scope_targets.json` |
| phase44_composite_scope_funnel_json | `submission_artifacts\evidence_snapshots\phase44_composite_scope_funnel.json` |
| phase44_composite_scope_delta_doris_audit_json | `submission_artifacts\evidence_snapshots\phase44_composite_scope_delta_doris_audit.json` |
| phase44_true_remaining_scope_targets_json | `submission_artifacts\evidence_snapshots\phase44_true_remaining_scope_targets.json` |
| phase45_scope_governance_funnel_json | `submission_artifacts\evidence_snapshots\phase45_scope_governance_funnel.json` |
| phase45_scope_governance_delta_doris_audit_json | `submission_artifacts\evidence_snapshots\phase45_scope_governance_delta_doris_audit.json` |
| phase45_true_remaining_scope_targets_json | `submission_artifacts\evidence_snapshots\phase45_true_remaining_scope_targets.json` |
| phase6c_set_prefix_doris_json | `submission_artifacts\evidence_snapshots\phase6c_set_prefix_doris.json` |
| doris_cluster_evidence_json | `submission_artifacts\evidence_snapshots\doris_cluster_evidence.json` |
| evidence_manifest | `submission_artifacts\evidence_manifest.md` |

## Metadata Warnings

- <none>
