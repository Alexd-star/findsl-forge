# FinDSL Forge

FinDSL Forge is an enterprise-grade prototype for the 2026 Graduate FinTech Innovation Competition topic:

> Topic 19: Compile stock-screening DSL into high-performance Apache Doris SQL.

The project goal is not to let an LLM freely hallucinate SQL. The core path is deterministic:

```text
DSL -> Lexer/Parser -> Typed AST -> Semantic Validation -> SQL Plan -> Doris SQL
```

AI/NL2DSL is implemented as an assistant layer that proposes DSL candidates. Every candidate still flows through the deterministic compiler and SQL/reference equivalence check, so the core remains auditable, reproducible, and testable.

## ANTLR/IR Migration Status

The production-hardening branch now contains a second, strictly typed compiler path:

```text
ANTLR4 -> Typed AST -> Domain/Logical IR -> Rule Optimizer
       -> Physical IR -> SQLGlot Doris AST -> Doris validation/execution
```

On the official 5,799-row workbook, the strict baseline remains 1,097 grounded legacy-backend queries. The new Physical IR/SQLGlot backend now compiles 1,016 of that strict success set (`92.62%`) and succeeds on 1,047 workbook rows in total. This is a migration metric, not an overall SQL accuracy claim. The remaining 81 strict-baseline gaps are 78 unavailable scope-membership cases and three ambiguous non-aggregate `queryData` scalar cases; missing or non-singleton data still produces a structured diagnostic rather than placeholder SQL.

Phase 9 introduces typed trading-sequence semantics, typed date windows, relational set algebra, and gap-aware year/quarter/month/week buckets for `CONS/EXIST` predicates. The generated Doris plan is set based and uses CTE/window islands instead of correlated scalar subqueries or calendar-day `DATEDIFF`; independent `AND` branches become intersections and `OR` branches become distinct unions. On the official `13,650,347`-row basic quote table, an independent raw-row oracle matches Doris result hashes in all ten cases (`10/10`): six daily/set cases over the latest full stock universe and four calendar-bucket cases over a deterministic 200-stock sample. The highest measured P95 is about 1.30 seconds in the current five-run snapshot. See `submission_artifacts/evidence_snapshots/phase9_temporal_doris.md` and `phase9_temporal_funnel.md` for the versioned evidence, scope boundaries, and remaining migration gaps.

Phase 10 adds a same-entity multi-resource join planner. It derives a deterministic `official_basic` anchor, constructs a left-deep `PhysicalJoin` tree, and obtains every join key from the catalog-declared stable-key intersection. Static security metadata joins on `(mktcode,tgtcode)` while dated quote, flow, and technical resources also require `bizdate`. Five independently written reference joins match generated Doris result hashes (`5/5`) across two- and three-resource cases. Multi-resource temporal, aggregate, and cross-entity plans remain explicit failures until their own contracts are implemented. See `submission_artifacts/evidence_snapshots/phase10_join_doris.md` and `phase10_join_funnel.md`.

Phase 11 carries normalized `DateConstraint` values on Logical IR calls and materializes explicit years, months, dates, and trading-session offsets. `PhysicalNthLatestValue` resolves yesterday or two sessions ago from the distinct Doris trading calendar, so weekends and exchange holidays are not treated as trading days. Five reference-date cases match complete Doris result hashes (`5/5`), and the physical-date migration gap falls from 95 to 68. Dynamic periods and recent-session ranges remain explicit work items. See `submission_artifacts/evidence_snapshots/phase11_date_doris.md` and `phase11_date_funnel.md`.

Phase 12 adds scalar recent-session membership for phrases such as `近5日`, `最近十个交易日`, and `30个交易日内`. The backend selects the latest N distinct exchange dates and applies them as a typed calendar membership predicate; it does not subtract N calendar days or reuse the per-stock temporal-record contract. Independent 5/10/30-session date sets match complete Doris result hashes (`3/3`), lifting migration coverage to `183/1097`. See `submission_artifacts/evidence_snapshots/phase12_session_doris.md` and `phase12_session_funnel.md`.

Phase 13 introduces Typed Market Set IR with conventional precedence `^` (complement) before `&` (intersection) before `|` (union). Because the supplied security-code file leaves `kcbFlag`, `gemFlag`, and `bShareFlag` uncomputed, A-share board membership is derived from controlled `(mktcode,tgtcode)` ranges without mutating official source data. Five union/intersection/complement cases match complete Doris result hashes (`5/5`); unavailable overseas markets remain structured failures. Migration coverage rises to `218/1097`. See `submission_artifacts/evidence_snapshots/phase13_market_doris.md` and `phase13_market_funnel.md`.

Phase 14 lowers one `SUM/AVG/MAX/MIN` indicator contract into a set-based grouped qualification plan: constrained source rows are grouped by stable security keys, qualified measures are filtered in a derived relation, and matching securities are joined to the latest quote snapshot. Four independently written `GROUP BY/HAVING` references match complete Doris result hashes (`4/4`), and all generated plans are verified non-correlated. Growth aggregates and multi-measure arithmetic remain separately classified. Migration coverage rises to `231/1097`. See `submission_artifacts/evidence_snapshots/phase14_aggregate_doris.md` and `phase14_aggregate_funnel.md`.

Phase 15 introduces a typed `UniverseSpec` for the official empty-indicator contract. Only direct `indicator(...) = 'all'` comparisons are accepted; empty `rank`/`queryData`, other literals, and unmaterialized concept or industry scopes remain deterministic failures. Universe plans scan `official_basic` without inventing a metric column, while typed market and date constraints still lower normally. Full-market, Shanghai main-board, ChiNext-complement, and recent-five-session cases match independently written Doris reference SQL by complete row-set hash (`4/4`) with no `1=0/1=1` placeholders. Migration coverage rises to `258/1097`; the new backend succeeds on 260 workbook rows. See `submission_artifacts/evidence_snapshots/phase15_universe_doris.md` and `phase15_universe_funnel.md`.

Phase 16 adds named composite aggregate relations. Each aggregate call receives an independent typed input scope, grouped measure alias, and stable-key relation; compatible securities are joined on `(mktcode,tgtcode)` before the outer arithmetic or boolean predicate is evaluated. This prevents different date windows from being collapsed into contradictory row predicates and protects aggregate division with `NULLIF`. Four real Doris cases, including cross-resource AVG division and two non-empty result sets, match independent reference SQL by complete row-set hash (`4/4`); the highest five-run P95 is about 1.23 seconds. The same audit fixes numeric percentage literals that were previously emitted as SQL strings. Eleven historical false positives that ignored non-scalar `agg_func` contracts are now explicit failures, so audited migration coverage is `250/1097`, not the less trustworthy Phase 15 count. See `submission_artifacts/evidence_snapshots/phase16_composite_doris.md` and `phase16_composite_funnel.md`.

Phase 17 treats rank as a relational operator rather than a scalar function. Boolean `and/or` expressions containing rank conditions lower to stable-key set intersection/union, while `then rank(...)` retains filter-then-rank stage semantics. Percentage bounds use `COUNT(*) OVER (...)` and `CEIL(population * percent / 100)`; aggregate rank first groups a typed measure by security, then applies `ROW_NUMBER`. Ties are deterministic on `(mktcode,tgtcode)`. Five real Doris cases cover direct and aggregate Top N, direct and aggregate Top N%, and rank/scalar set intersection; all complete row-set hashes match independent reference SQL (`5/5`), with a highest five-run P95 of about 0.54 seconds. Migration coverage rises to `317/1097`, with 319 total backend successes. See `submission_artifacts/evidence_snapshots/phase17_rank_doris.md` and `phase17_rank_funnel.md`.

Phase 18 adds typed dynamic calendar contracts anchored to `MAX(bizdate)` rather than the workstation clock. Current and previous week/month/quarter/year ranges, rolling calendar windows, anchor-year month/day forms, relative trading-session slices, and session sets before or after a calendar boundary all reach dedicated Physical IR. Natural periods use SQLGlot date arithmetic; trading-day expressions select distinct exchange sessions and never subtract calendar days. The official migration date gap falls from 82 to zero, migration coverage rises to `393/1097` (`35.83%`), and the new backend succeeds on 400 workbook rows. Nine independently resolved Doris date sets match complete generated result hashes (`9/9`); the highest five-run P95 is about 0.59 seconds. See `submission_artifacts/evidence_snapshots/phase18_dynamic_date_doris.md` and `phase18_dynamic_date_funnel.md`.

Phase 19 separates grounded security-name scopes from unavailable concept, industry, index, and custom-block membership. A versioned 5,686-row catalog is generated from the official security master and fingerprinted against live Doris data. Exact names and `name(code)` forms lower through typed scope set algebra and a stable-key security-master join; unknown scope atoms return `PHYSICAL_SCOPE_DATA_UNAVAILABLE`. Direct `queryData` values and global `queryData` aggregates use independent named relations and cross joins, so their filters never leak into the candidate universe. Migration coverage rises to `406/1097` (`37.01%`) with 413 total backend successes; seven non-empty Doris cases match independent complete result hashes (`7/7`) and the catalog source hash matches live Doris. See `submission_artifacts/evidence_snapshots/phase19_security_scope_doris.md` and `phase19_security_scope_funnel.md`.

Phase 20 adds 29 controlled direct/derived mappings across the official basic, extension, and deterministic technical-feature resources, including market value, order imbalance, auction/rate fields, capital-flow ratios, candlestick flags, volume breakout, and moving-average alignment. Crossing, record-extreme, technical-pattern, and five-bucket position functions now lower to explicit window/event relations; `LAG`, rolling `MIN/MAX`, configurable `ABS/GREATEST/NULLIF` pattern predicates, and scalar projections are evaluated in a derived relation before outer filtering. A real Doris audit exposed and fixed a general boolean-precedence defect that had allowed an inner `OR` to escape its comparison/date scope. Migration coverage rises to `534/1097` (`48.68%`) with 548 total backend successes; all 13 non-empty mapping/event cases match independently written complete result hashes (`13/13`). The original 95 mapping-plan gaps fall to three genuine unavailable mappings, and the original 81 generic expression gaps fall to zero; 15 industry-relative rows are now classified as `PHYSICAL_INDUSTRY_DATA_UNAVAILABLE` because the supplied industry membership column is entirely empty. See `submission_artifacts/evidence_snapshots/phase20_mapping_event_doris.md` and `phase20_capability_funnel.md`.

Phase 21 adds configured numeric approximation, first/last-value growth aggregates, grouped temporal aggregates, and temporal cross-sectional rank. `GROWTH_RISE/FALL` use `MIN_BY/MAX_BY` with explicit arithmetic parentheses and zero-denominator protection; `CONS/EXIST` use typed bucket relations and gaps-and-islands rather than string SQL fragments. Migration coverage rises to `631/1097` (`57.52%`) with 647 total backend successes. All 99 newly accepted rows pass a slot-materialization and placeholder audit, and six non-empty Doris cases match independent complete result hashes (`6/6`). See `submission_artifacts/evidence_snapshots/phase21_aggregate_rank_doris.md`, `phase21_new_success_audit.md`, and `phase21_capability_funnel.md`.

Phase 22 treats rank arithmetic and `then rank` as named relational stages. Independent rank calls materialize once and join on stable security keys; chained rank recursively materializes the complete prior candidate plan before ranking only that candidate population. Period-valued rank measures collapse to one end-of-period value per security with `MAX_BY(value,bizdate)`, percentage stages count the stage population, and parenthesized stage branches remain relational set operations. Migration coverage rises to `647/1097` (`58.98%`) with 663 total backend successes, eliminating the remaining rank-expression and chained-rank error categories. All 16 new successes pass the false-positive audit; seven non-empty Doris cases match independently written complete result hashes (`7/7`) with a highest observed P95 below 0.55 seconds. See `submission_artifacts/evidence_snapshots/phase22_stage_rank_doris.md`, `phase22_new_success_audit.md`, and `phase22_capability_funnel.md`.

Phase 23 generalizes temporal and rank relations instead of adding query-specific branches. Multiple calls governed by one identical `CONS/EXIST` contract now form one composite per-bucket predicate; differing quantifiers or scopes remain explicit failures. Temporal predicates can consume catalog-validated same-entity joins across quote and technical resources on `(mktcode,tgtcode,bizdate)`. Rank ranges carry lower/upper bounds and open/closed flags through Logical IR, Physical IR, direct rank, aggregate rank, and candidate-stage rank. Recursive field discovery now traverses set-operation trees, allowing a complete prior intersection/union to become the population of a later rank stage. Migration coverage reaches `660/1097` (`60.16%`) with 677 total backend successes. All 14 newly accepted backend rows pass the materialization audit; six non-empty Doris cases match independent complete result hashes (`6/6`). See `submission_artifacts/evidence_snapshots/phase23_relational_doris.md`, `phase23_new_success_audit.md`, and `phase23_capability_funnel.md`.

Phase 24 introduces named period-end scalar relations. A non-aggregate indicator over a multi-row date window is materialized independently and collapsed with `MAX_BY(value,bizdate)` before it participates beside grouped aggregates or rank arithmetic. Ordinary indicators retain `(mktcode,tgtcode)` and join by security; exact-security `queryData` produces one scalar row and cross joins. This prevents period rows from multiplying the anchor relation or silently selecting an arbitrary row. Migration coverage reaches `667/1097` (`60.80%`) with 687 total backend successes, eliminating the legacy-success `PHYSICAL_SCALAR_SCOPE_UNBOUNDED` category. All 10 newly accepted backend rows pass the materialization audit; four non-empty Doris cases match independent complete result hashes (`4/4`). See `submission_artifacts/evidence_snapshots/phase24_period_scalar_doris.md`, `phase24_new_success_audit.md`, and `phase24_capability_funnel.md`.

Phase 25 introduces keyed event-candidate relations. Event branches and aggregate, scalar, or cross-date branches execute independently, project distinct `(mktcode,tgtcode)` candidates, apply set `INTERSECT/UNION/EXCEPT`, and finally join the latest anchor snapshot. A period event compared with `False` is compiled as the decidable event universe minus securities with any true occurrence; SQL `NULL` is never treated as false. Undated events now evaluate at the latest session, and the normalized `position` formula explicitly preserves `(value-min)/(max-min)` parentheses. Migration coverage reaches `675/1097` (`61.53%`) with 695 total backend successes. All eight newly accepted strict-baseline rows use explicit candidate-set contracts; five non-empty Doris cases match independent complete result hashes (`5/5`) below the 10-second target. See `submission_artifacts/evidence_snapshots/phase25_event_candidate_doris.md`, `phase25_new_success_audit.md`, and `phase25_capability_funnel.md`.

Phase 26 extends typed date algebra and open-ended pagination. Fixed-year following ranges, anchor-day trading sessions, `今天的前N日`, half-year windows, and exact fractional year/quarter-to-month conversions now survive from Typed AST through Physical IR. `limit offset,-1` becomes an optional-count relational slice; Doris lowering adds stable output-key ordering and uses `INT64_MAX-offset`, avoiding nondeterministic pages and signed overflow. Migration coverage reaches `686/1097` (`62.53%`) with 709 total backend successes, eliminating the strict-baseline date, open-limit lowering, and fractional-period error categories. All 14 new backend successes pass contract auditing; six non-empty Doris cases match independent complete result hashes (`6/6`). See `submission_artifacts/evidence_snapshots/phase26_date_limit_doris.md`, `phase26_new_success_audit.md`, and `phase26_capability_funnel.md`.

Phase 27 adds typed event projection before temporal quantification and date-signature decomposition for cross-date event conjunctions. Monthly event buckets preserve `LAG` context before date filtering; consecutive event runs retain false rows for gaps-and-islands analysis; undated direct scalars use the latest data snapshot. `80内` becomes an 80-session frame, and one-session extrema use Doris-valid `CURRENT ROW` boundaries. Migration coverage reaches `690/1097` (`62.90%`) with 713 total backend successes and zero historical regressions. All four new successes pass materialization auditing; four non-empty real-Doris cases match independent complete result hashes (`4/4`) and structural contracts (`4/4`). See `submission_artifacts/evidence_snapshots/phase27_event_semantics_doris.md`, `phase27_new_success_audit.md`, and `phase27_capability_funnel.md`.

Phase 28 restores the official workbook's documented-by-example default price semantics in the typed pipeline. Empty left indicators in price-versus-line crossing, reset, and close-together functions, and empty indicators in record-high, record-low, and position functions, normalize to `最新价` before Logical IR construction. Empty right operands and empty rank measures remain deterministic failures. Migration coverage rises to `729/1097` (`66.45%`) with 752 total backend successes; all 39 newly accepted strict-baseline rows pass slot-materialization, event-plan, backend-safety, and no-placeholder auditing. Six non-empty real-Doris cases match independently written complete result hashes (`6/6`), pass structural contracts (`6/6`), and remain below the 10-second execution target. See `submission_artifacts/evidence_snapshots/phase28_default_price_doris.md`, `phase28_new_success_audit.md`, and `phase28_default_price_funnel.md`.

Phase 29 generalizes `PhysicalEventProjection` from crossing-only events to typed Crossing, Extreme, Position, and Pattern features, with optional scalar projections carried in the same relation. Temporal quantification now consumes those projected columns after their required `LAG`, rolling `MIN/MAX`, position CASE, or configured pattern expression has been materialized; date-window slicing no longer forces these event families into separate ad hoc paths. Migration coverage reaches `734/1097` (`66.91%`) with 758 total backend successes. All six newly accepted backend rows pass recursive event-materialization auditing. Four bounded, non-empty real-Doris scenarios match independent complete result hashes (`4/4`), satisfy structural contracts (`4/4`), and have a highest three-run P95 of about 1.37 seconds. See `submission_artifacts/evidence_snapshots/phase29_event_projection_doris.md`, `phase29_new_success_audit.md`, and `phase29_event_projection_funnel.md`.

Phase 30 closes six grounded event gaps without weakening unavailable-data diagnostics. Exact security-scoped events now join the versioned official security catalog; natural event periods normalize `半个月` and `上个月` to 10 and 20 per-security trading observations; `半年内` reaches typed calendar date algebra; support/pressure and unsealed-limit predicates use verified official fields. The unsealed-limit mapping explicitly requires `upSealPx > 0`, preventing the official zero sentinel from producing 5,445 false positives. Migration coverage reaches `740/1097` (`67.46%`) with 764 total backend successes. All six new successes pass event-materialization auditing, and six non-empty real-Doris scenarios match independent complete result hashes (`6/6`), satisfy structural contracts (`6/6`), and remain below the 10-second target with a highest three-run P95 of about 1.03 seconds. See `submission_artifacts/evidence_snapshots/phase30_grounded_event_doris.md`, `phase30_new_success_audit.md`, and `phase30_grounded_event_funnel.md`.

Phase 31 implements the final two migration gaps that can be proved from the supplied data. A fixed-date-since event period now filters the source relation before its unbounded event window, while the latest-date predicate remains outside the projection; this preserves the intended range instead of computing all-history extrema first. Top-level `then rank` is planned before generic event dispatch, allowing a fully materialized event candidate relation to feed deterministic stage ranking. Migration coverage reaches `742/1097` (`67.64%`) with 766 total backend successes. The two exact official workbook questions return 34 and 2 non-empty rows on Doris, match independently written complete result hashes (`2/2`), pass structural contracts (`2/2`), and have a highest three-run P95 below 0.09 seconds. The remaining 355 strict-baseline gaps require unavailable membership/data domains, undefined empty-rank semantics, or T+0 data absent from the supplied daily tables. See `submission_artifacts/evidence_snapshots/phase31_final_grounded_doris.md`, `phase31_new_success_audit.md`, and `phase31_final_grounded_funnel.md`.

Phase 32 turns the local Web Demo into a two-pipeline audit workbench. The existing internal FinDSL path retains Chinese NL2DSL candidates, reference execution, optimizer explain, and sample rows. A separate official path now invokes the real `ANTLR4 -> Typed AST -> Logical IR -> Physical IR -> SQLGlot Doris AST` pipeline and exposes each intermediate representation, selected physical strategy, deterministic diagnostics, and versioned delivery evidence. Expected negative cases use a preview endpoint that preserves structured compiler rejection without browser network errors; the programmatic `/api/official/analyze` endpoint keeps its HTTP 400 contract. Browser QA covers 360, 390, 768, and 1440 pixel widths, long IR uses an internal audit viewport, and keyboard users can traverse pipeline and result tabs with arrow, Home, and End keys. See `docs/superpowers/specs/2026-07-13-phase32-dual-pipeline-audit-workbench.md`.

Phase 36 adds versioned public and third-party data boundaries without disguising them as official tables. CSI/CNI index definitions, AKShare/Eastmoney constituents, BaoStock CSRC industry classification, exchange trading rules, AKShare/Sina index quotes, exact A-share identities, and audited scope aliases are stored as source-attributed snapshots. Doris currently holds 35,421 scope-membership rows, 23,226 industry rows, 5,686 instrument-rule rows, and 14,533 index-quote rows with zero filtered Stream Load records. Index scalar plans are anchored to the official quote table's `2026-04-14` evaluation date rather than the external feed's later date. Dynamic moving averages, empty-rank stable ordering, calendar event periods, independent dated scalars, and cross-scope temporal aggregate thresholds now use typed Physical IR. All 36 rows newly accepted since Phase 35 execute successfully on Doris; see `submission_artifacts/evidence_snapshots/phase36_external_data_summary.md` and `phase36_new_success_doris_audit.json`.

Phase 38 adds a complete Sina public-sector snapshot (`290/290` sectors), a general AKShare public-index provider, resumable raw-response caches, explicit proxy control, and a reusable funnel-delta Doris auditor. Doris now contains 61,862 source-attributed scope memberships, 28,386 industry memberships, 5,686 instrument rules, and 14,533 index quotes with zero filtered Stream Load rows. Reliable migration coverage is `947/1097` (`86.33%`) with 976 total backend successes. Nine newly enabled index queries pass repeated real-Doris execution (`9/9`); the highest three-run P95 in the Git-aligned refreshed audit is about 1.61 seconds. The audit also withdrew seven earlier suffix-based false positives, including mappings that had treated `金融公司` as `金融指数`. A prefix-join renderer defect exposed by `上证周期` crossing a dynamic 24-day moving average was fixed by preserving input columns through the prefix CTE and retargeting outer event constraints. See `docs/41_公开外部数据接入与Phase38语义审计.md` and the Phase 38 evidence snapshots.

Phase 39 refreshes the versioned Eastmoney catalog and hardens the provider with raw-response resume caches, shard failover, explicit retry controls, proxy-aware system-curl fallback, and offline-safe dependency injection. Doris now contains 68,975 scope memberships, 29,727 industry memberships, 5,686 instrument rules, and 14,533 index quotes. Reliable migration coverage reaches `954/1097` (`86.96%`) with 983 total backend successes. All seven newly enabled queries pass repeated real-Doris execution (`7/7`), with a highest three-run P95 of about 1.47 seconds. The delta auditor now canonicalizes unordered set results by every projected column and rejects unordered `LIMIT`, so independent runs produce identical full-result hashes instead of confusing database row order with semantic change. See `docs/42_Phase39外部目录刷新与结果集排序审计.md` and the Phase 39 evidence snapshots.

Phase 40 completes the missing `上证指数` scalar path by adding code `000001` to the versioned public index-quote snapshot and normalizing `上个交易日` as a typed relative-session contract. Reliable migration coverage reaches `956/1097` (`87.15%`) with 985 total backend successes. Both newly enabled scalar queries execute on real Doris and return non-empty stable results (`2/2`).

Phase 41 adds a complete security-side public classification provider. The Baidu related-block source returns verified classifications for `5529/5529` versioned A-share identities, producing 117,908 scope memberships and 11,057 industry-level memberships. Combined Doris catalog counts reach 193,168 scope memberships, 40,784 industry memberships, and 5,686 instrument rules with zero filtered load rows. Same-source/date snapshots are atomically superseded, premature provider pagination is rejected, and only reviewed aliases enter runtime resolution. Reliable migration coverage reaches `971/1097` (`88.51%`) with 1,000 total backend successes. All 15 Phase 41 additions pass repeated real-Doris execution and canonical result hashing (`15/15`), with a highest three-run P95 of about 2.00 seconds. See `docs/43_Phase41全市场公开分类接入与完整性审计.md` and the Phase 41 evidence snapshots.

Phase 42 corrects a benchmark-method defect and closes the competition's long-horizon performance target on the official Doris data. The old preparation script did not actually disable Doris SQL Cache, so repeated runs understated the window baseline. A narrow rolling-feature serving table now preserves all 13,650,347 rows from `2006-01-04` to `2026-04-14` and uses 244 automatic monthly partitions. Seven alternating, uncached Query Profile runs produce identical complete 5,487-row SHA-256 hashes: the window baseline has a `932 ms` median and the partition-pruned path a `23 ms` median, for `40.52x` server-side speedup. The general official evidence script independently reports `13.99x` end-to-end speedup after its cache setting is fixed. See `docs/44_Phase42官方20年长周期加速与基准口径修复.md` and `submission_artifacts/evidence_snapshots/phase42_long_horizon_doris.json`.

Phase 43 extends the versioned public scope catalog without weakening fail-closed behavior. Complete Eastmoney board pages and reviewed aliases add exact or policy-explicit support for ByteDance, DeepSeek, HBM, brain-computer interface, AIGC, white liquor, low-altitude economy, IPv6, solid-state batteries, utilities, SHEIN-related A-share suppliers, and other grounded ranges. Exact source names now take precedence over canonical aliases, preventing `白酒` from being rewritten to `白酒Ⅱ`; THS synchronization refuses partial pagination by default and exits non-zero. Doris contains 203,181 scope memberships, 40,907 industry memberships, and 5,686 instrument rules with zero filtered rows. Reliable migration coverage reaches `990/1097` (`90.25%`) with 1,021 total backend successes. All 21 additions since Phase 41 pass three-run real-Doris execution and complete-result hashing (`21/21`), with a highest P95 of `2.389 s`. See `docs/45_Phase43公开范围补齐与别名语义治理.md` and the Phase 43 evidence snapshots.

Phase 44 adds provenance-preserving composite scopes and current CSI workbook compatibility. Curated ranges may now derive an intersection or union from multiple versioned membership snapshots; `宁夏算力概念` is the one-security intersection of 16 Ningxia securities and 205 computing-concept securities, while `银行保险` is an auditable 47-security union. Six-digit DSL atoms resolve only when the official security master contains exactly one matching security. The CSI parser accepts the current bilingual workbook headers, validates the expected member count, and recognizes the official Shenzhen `302xxx` code range; the rebuilt CSI 300 snapshot contains exactly `300/300` members instead of the stale one-row parse. Reliable migration coverage reaches `998/1097` (`90.98%`) with 1,029 total backend successes. The eight Phase 44 additions pass repeated real-Doris hashing (`8/8`) with a highest P95 below `0.79 s`. See `docs/46_Phase44组合范围与中证官方成员修复.md` and the Phase 44 evidence snapshots.

Phase 45 adds a conservative semantic-scope governance layer and one previously hidden event-period capability. Reviewed public mappings cover high-confidence spelling repairs (`msic` -> MSCI, `豆包概率` -> 豆包概念), standard shorthand (`低价`, `标普概念`, `消费`, `医疗`, `饮料`, `金融`), unique securities, and auditable intersections such as 华为概念∩AI眼镜 and 字节概念∩算力. Every direct source has a minimum-member-count gate; composite sources validate both component and result cardinality. A bare `季度` record-extreme period is normalized to one quarter of trading observations (60 sessions), then lowered through the existing typed window path. Strict migration reaches `1016/1097` (`92.62%`) with 1,047 total backend successes. The Phase 45 delta has `18/18` repeated real-Doris hash-stable cases, 11 non-empty cases, and a highest P95 of about `1.18 s`. The remaining strict gaps are still explicit: 78 unresolved scope atoms and three non-singleton scalar `queryData` cases. Unknown custom boards, noisy strategy names, overseas/fund domains, and ambiguous broad words remain rejected rather than guessed. See `docs/47_Phase45语义范围治理与季度事件补强.md` and the Phase 45 evidence snapshots.

## Implemented Scope

- Parse nested stock-screening DSL expressions.
- Validate indicators, functions, named parameters, duplicate named arguments, and window arguments from configuration.
- Compile `filter`, `then`, `rank` with top/bottom/percent cutoffs, `date_between`, `CONS`, `EXIST`, `MA`, `SUM`, `MAX`, `MIN`, and `RET` into SQL.
- Generate trace metadata explaining the selected rewrite path.
- Emit structured optimizer explain steps for machine-readable rewrite evidence.
- Validate generated SQL against a Doris-safe single-query shape before returning it.
- Return structured compile diagnostics and repair hints for invalid DSL/API requests.
- Prove config-only indicator extension through defense-package evidence.
- Execute generated SQL against local SQLite fixtures for regression checks.
- Compare SQL output with an independent Pandas semantic reference evaluator.
- Push safe date ranges and window-safe date upper bounds into base table scans for partition-pruning-friendly Doris SQL.
- Support signed numeric thresholds for net-flow and other negative-valued financial indicators.
- Normalize mixed-case indicator names and market codes for official-style input robustness.
- Preserve sparse auxiliary-table rows by anchoring stock-date semantics on `daily_quote` and left-joining optional tables.
- Rewrite eligible rolling `SUM` expressions to prefix-sum table joins for long-window acceleration.
- Use configured hot-window prefix columns such as `volume_sum_120` to avoid query-time prefix self-joins on competition-scale Doris evidence paths.
- Build auxiliary prefix tables from the daily quote trading-calendar skeleton so sparse money-flow data cannot shift rolling windows.
- Produce baseline-window versus prefix-sum benchmark reports.
- Generate deterministic synthetic A-share-style data for reproducible long-window scale benchmarks.
- Generate Doris DDL with trade-date auto partitions, colocated stock-code distribution, sample load, prefix-table build, and smoke-query assets.
- Collect Doris-cluster `EXPLAIN` and latency evidence for baseline-window versus prefix-sum SQL.
- Serve a local Web Demo/API for DSL, AST, Doris SQL, optimizer explain, and SQL/reference verification.
- Suggest DSL candidates from Chinese natural-language stock-screening requests, then validate them through the compiler and reference oracle.
- Cover official-style NL2DSL prompts for low-price bottom picks, turnover percent cuts, B-market average-volume thresholds, high-turnover close ranking, date-window moving-average filters, rolling minimum thresholds, return-rate thresholds, date-prefix-sum pruning, and signed net-outflow thresholds.
- Validate optional LLM-proposed DSL candidates while rejecting direct SQL and invalid DSL before execution.
- Call an optional OpenAI-compatible LLM provider as a DSL-candidate source, then force every returned candidate through the same deterministic safety loop.
- Run an official-style coverage suite with representative positive cases and negative diagnostic cases.
- Generate a defense package that maps live demo steps to competition scoring evidence.
- Generate a submission readiness report covering tests, accuracy, equivalence, optimizer evidence, real-market sample evidence, Doris assets, and git rollback state.
- Pin runtime dependencies, including the generated ANTLR4 frontend runtime, for reproducible installation.
- Provide pytest coverage for parser, semantic validation, SQL generation, and SQL/reference equivalence.

Current readiness passes required gates and the Doris-scale performance proof. The recorded Doris evidence uses 5,000,000 synthetic daily quote rows, disables Doris SQL cache during timing, and shows a 36.24x cluster speedup for a 120-day rolling-volume prefix path.

The repository also includes a versioned public A-share quote sample under `data/real_samples/eastmoney_a_share_sample/`. It uses Eastmoney historical K-line rows for 贵州茅台 and 平安银行 so the demo can show real market fields without mixing that small business sample with the 5M-row Doris performance claim.

The official Topic 19 real-data adapter is tracked separately from the staged internal DSL path. It reads the official `选股提槽实例.xlsx` workbook and the three `newzl` Doris CSV tables (`hsj_stock_code_info`, `hsj_stock_hq_basic`, `hsj_stock_hq_ext`), reports parse/compile coverage, and emits SQL only for indicators that can be grounded in the provided A-share tables or deterministic OHLCV-derived feature tables. On the current 5,799-row workbook, strict parsing succeeds for 5,792 rows and recovery parsing succeeds for all 5,799; strict compilation produces 1,097 grounded, non-degraded results, while recovery compilation produces 1,830 results. These are different evidence populations and must not be merged into a single success rate. The remaining strict failures are primarily unsupported indicators from data domains absent in the official three tables; `UNSUPPORTED_OFFICIAL_COUNT_EXP` is down to 3 and remains an explicit no-fake-SQL boundary. The official Doris path has also completed real CSV ingestion and feature-table construction on local Apache Doris: `hsj_stock_code_info=5,686`, `hsj_stock_hq_basic=13,650,347`, `hsj_stock_hq_ext=6,170,822`, and each official derived feature table has `13,650,347` rows. `scripts/prepare_official_doris_evidence.ps1` records row-count parity, feature-table parity, SQL/EXPLAIN evidence, and baseline/prefix row-count equivalence before writing `reports/official_doris_evidence.md/json`.

This count reflects real `agg_func/count_exp`, cross-date, rank-count, aggregate rank-count, crossed-line event count, aggregate count expressions inside arithmetic, punctuation-noise repair for documented workbook defects, bounded `count_exp` ranges, chained-rank, industry-aggregate, period-position, official alias, and string-wildcard semantics instead of treating unsupported intent as ordinary field filters. The adapter now normalizes official date slots, including explicit year ranges such as `2006年-12年`, month/day forms such as `2024年8月` and `9号`, colloquial recent windows such as `过去20天` and `三个月之内`, and composite relative forms such as `本月的前一周`, `2018年的第五年`, and `最近的第二天`, scales official integer price/rate fields into human units, preserves branch-local `OR` constraints, localizes incompatible `AND` date slots with correlated `EXISTS`, compiles AVG/SUM/MAX/MIN/GROWTH and EXIST/CONS windows for ordinary indicators, compiles grounded `rank(..., count_exp)` and `rank(..., agg_func, count_exp)` as bucketed rank counting, compiles `cross_above/cross_down/golden_cross(..., count_exp)` as daily event rows using `LAG()` while keeping pre-window source rows for first-day event correctness, maps moving-average/candlestick/volume-breakout indicators through `newzl.hsj_stock_hq_basic_technical`, supports monotonic `then rank(...) then rank(...)` pipelines as CTE stages, uses official `pxMkTopDays/pxMkBotDays` for price new-high/new-low predicates, maps grounded official aliases such as `涨停天数`、`涨停价`、`跌停价`、`沪港通标识`、`委比`、`委差`、`涨停炸板`、`涨停未封板`, long-window MA/volume-average aliases, and big-order amount aliases, emits valid `LIKE` SQL for `%...%` string wildcards, classifies unsupported official samples by missing data domain, and supports `belong_industry` for numeric indicators via `hyBlkRefName` aggregates. See `docs/20_官方真实数据适配分析与开发计划.md`, `docs/21_官方真实数据冲刺计划与验收闭环.md`, `docs/22_官方真实数据落库复盘与满分冲刺计划.md`, `docs/31_官方真实数据第六轮复核与后续计划.md`, `docs/32_官方真实数据第七轮窗口语义复核与后续开发计划.md`, `docs/33_官方真实数据第八轮表达式级聚合count_exp补强说明.md`, `docs/34_官方槽位DSL_BNF与ANTLR形式化说明.md`, `docs/35_官方三表缺失数据域不可伪造SQL审计报告.md`, `docs/superpowers/plans/2026-06-09-official-real-data-hardening.md`, `docs/superpowers/plans/2026-06-10-official-real-data-second-pass.md`, `docs/superpowers/plans/2026-06-10-official-doris-evidence-automation.md`, and `deploy/doris/official/` for the current official-data plan, schema, Stream Load runbook, smoke queries, feature-table SQL, grammar/audit materials, and evidence automation.

## Comprehensive Chinese Manual

The repository includes a long-form Chinese Word manual for competition submission and defense:

- `docs/FinDSL_Forge_中文综合操作指南.docx`
- `docs/FinDSL_Forge_中文综合操作指南.md`

The manual is written as a combined product introduction, project overview, architecture whitepaper, algorithm explanation, operation guide, deployment guide, validation report guide, and defense reference. Its source Markdown contains more than 30,000 Chinese characters and is generated by `scripts/build_chinese_manual_docx.py` for reproducibility.

## 中文文档与文件索引

为便于比赛提交、答辩复核、后续维护和代码回溯，项目根目录提供中文文件索引与分册式文档体系：

- `PROJECT_INDEX.md`: 当前项目文件、文件夹、运行入口、历史文件和维护建议总索引。
- `CHANGELOG.md`: 面向提交和维护的版本更新记录。
- `docs/README.md`: `docs/` 目录文档导航。
- `docs/01_项目简介.md`: 项目定位、目标用户、核心能力和交付价值说明。
- `docs/03_操作手册.md`: 命令行、Web Demo、验证脚本和 Doris 证据采集操作说明。
- `docs/12_环境依赖与部署.md`: Python、Doris、PowerShell 脚本和可选 LLM Provider 的环境说明。
- `docs/17_项目交付说明.md`: 提交物、验收顺序、答辩材料和人工复核事项说明。

## Quick Start

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m findsl.cli compile 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))'
python -m findsl.cli evaluate --input data/samples/queries.jsonl --output reports/evaluation_report.md
python -m findsl.cli reference 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3))' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(RET(indicator("close"), 2) > 0.05)' --data-dir data/samples --json
python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)' --json
python -m findsl.cli suggest-dsl '筛选A股连续三天主力净流入为正并按换手率排名前一百' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'A股存在资金流入后按低价取每日2只' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'A股每日换手率前50%' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'B股近2日均量不低于80' --data-dir data/samples --json
python -m findsl.cli suggest-dsl '主力净流出低于-1.5' --data-dir data/samples --json
python -m findsl.cli suggest-dsl 'A股近2日收盘价涨幅超过5%' --data-dir data/samples --json
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --text '近3日成交量累计大于300' --data-dir data/samples --json
python -m findsl.cli llm-suggest-dsl '近3日成交量累计大于300' --model '<provider-model>' --json
python -m findsl.cli official-suite --output reports/official_suite_report.md --json
python -m findsl.cli official-slot-coverage --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/official_slot_coverage.json --report-output reports/official_slot_coverage.md
python -m findsl.cli official-performance-matrix --evidence reports/official_doris_evidence.json --json-output reports/official_query_performance_matrix.json --report-output reports/official_query_performance_matrix.md --json
python -m findsl.cli defense-package --output reports/defense_package.md --json
python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 20 --output reports/prefix_sum_benchmark.md
python -m findsl.cli scale-benchmark --stocks 300 --days 260 --window 120 --iterations 5 --output reports/prefix_sum_scale_benchmark.md
python -m findsl.cli collect-doris-evidence --host 127.0.0.1 --port 9030 --user root --database findsl_demo --dsl 'filter(SUM(indicator("volume"), 120) > 1000000)' --output reports/doris_cluster_evidence.md
python -m findsl.cli serve-demo --host 127.0.0.1 --port 8765
python -m findsl.cli readiness-report --output reports/submission_readiness.md
python -m findsl.cli evidence-metadata --snapshots-dir submission_artifacts/evidence_snapshots --output submission_artifacts/evidence_metadata.json --summary-output submission_artifacts/evidence_summary.md
```

The official parser also has a pinned ANTLR4 shadow frontend. Verify generated sources with `python scripts/generate_antlr.py --check` and run official parity evidence with `python -m findsl.cli official-frontend-evidence ...`. See `docs/37_ANTLR影子前端与迁移证据.md` for commands and interpretation boundaries.

The official compiler now exposes an immutable Typed AST and a SQL-free logical IR shadow pipeline. `python -m findsl.cli official-slot-ir ... --json` shows function-slot bindings, explicit types, validated logical operators, and a deterministic content-derived plan ID without changing the existing SQL compiler. On the current official workbook, 5,695 strict inputs produce Typed ASTs and 2,034 produce validated logical plans; the separate grounded strict SQL baseline remains 1,097. See `docs/38_Typed_AST与Logical_IR实现说明.md` and `reports/phase3_official_ir_evidence.md` for the evidence boundary.

Phase 4 adds a schema-validated official indicator registry, domain binding, SQL-free financial-domain nodes, and a deterministic rule optimizer. The registry distinguishes 197 provided/derived static indicators from workbook indicators whose required data domains are absent, so missing financial/fund/index data reports `DOMAIN_DATA_UNAVAILABLE` instead of becoming fake SQL. `official-slot-optimize` exposes the domain requirements and rewrite trace; `official-domain-evidence` audits all 5,799 official rows. See `docs/39_领域IR注册表与规则优化器说明.md`.

Phase 5 adds a schema-validated physical catalog, bounded Doris candidate planner, validated Physical IR, and a SQLGlot-only Doris AST backend. The shadow backend currently produces 33 grounded plans on the 5,799 official rows; all 33 preserve supported market/latest-date constraints, round-trip in the Doris dialect, and pass the SELECT safety lint. On real Apache Doris data, 30 deterministic candidates match the legacy compiler exactly by row count and streaming SHA-256 (`30/30`, zero execution errors); three top-level LIMIT queries without ORDER BY are recorded as `NONDETERMINISTIC_LIMIT` and excluded rather than being counted as passes. Direct numeric rank uses a `ROW_NUMBER()` window partitioned by trading date, a stable `tgtcode` tie-breaker, and an outer rank filter. Catalog-declared anchor resources preserve the basic-market universe for extension, security, and technical tables. Missing domains, derived expressions without controlled strategies, unsupported constraints, and approximate comparisons without catalog tolerances remain explicit failures rather than fake SQL. Use `official-slot-physical`, `official-slot-backend`, and `official-backend-evidence`; see `docs/40_Doris物理规划与SQL_AST后端说明.md`.

Phase 6A replaces the shadow planner's fixed priority cost with a versioned Doris statistics snapshot. `official-physical-stats` collects real row counts, stored sizes, and the FE version through controlled metadata commands; the snapshot is bound to the physical catalog fingerprint. Complete statistics produce an auditable primary-plus-anchor scan-byte cost with `estimated=false`, while missing statistics fall back explicitly to catalog priority. The model does not invent selectivity or equate stored bytes with latency. Prefix and hot-materialization alternatives will enter the same interface as multiple candidates in Phase 6B.

Phase 6B adds 14 schema-validated prefix-average strategies for fixed moving-price and moving-volume averages. The planner now enumerates direct materialized columns and controlled prefix-difference expressions, records both decisions, and keeps uncalibrated alternatives in `shadow` mode. SQLGlot renders the prefix path from typed AST nodes using current/previous prefix rows; no legacy SQL fragments enter the backend. Real Doris evidence matches both representative result sets exactly (`2/2`, zero errors), but the correlated prefix path is currently slower than the technical feature table (`0.795x` and `0.734x` legacy-over-prefix ratios in the implementation-bound run), so the default remains `direct_column`. Use `official-prefix-evidence` to reproduce the result hashes and timing before changing any strategy to `active`.

Phase 6C replaces the correlated prefix scalar with a typed `PhysicalPrefixJoin`: `prefix_anchor_rows` first applies the market/date snapshot, and `prefix_values` computes current-minus-previous cumulative values through stable-key CTE/joins. All 14 fixed moving-price and moving-volume filters match technical-column result hashes and are faster on real Doris (`14/14`, median about `1.55x`, range about `1.23x-2.00x`), so filter-shaped candidates are now `active`. Prefix-fed rank remains a validated shadow plan because warm-cache rank timing is effectively tied and can regress slightly; direct technical rank stays the default. The evidence also records EXPLAIN scan nodes and conservative projected-column logical-byte costs without presenting modeled bytes as measured I/O. See `submission_artifacts/evidence_snapshots/phase6c_set_prefix_doris.md`.

Repository-wide static quality is now a required CI gate. ANTLR-generated sources are excluded by exact path, package `__init__.py` files retain narrowly scoped re-export exceptions, and all maintained source, test, documentation, and plotting modules pass Ruff 0.15.13. GitHub Actions verifies generated ANTLR sources, runs `python -m ruff check .`, and then executes the full pytest suite. See `docs/superpowers/plans/2026-07-13-repository-ruff-quality-gate.md`.

Phase 7 exposes the ANTLR-to-SQLGlot path through one `compile_official` orchestration service and a dedicated `/api/official/analyze` Demo endpoint. The endpoint never silently falls back to the legacy compiler: unsupported data domains, constraints, expressions, or physical mappings return the exact terminal stage, stable code, partial IR evidence, and candidate decisions. Versioned official-slot examples are available from `/api/official/examples`. The migration funnel measures the new backend against the 1,097-query legacy strict success set; the current result is `33/1,097` (`3.01%`), with the largest actionable gaps classified as physical constraints, mappings, domain capabilities, and expressions. See `reports/phase7_official_pipeline_funnel.md`; this migration percentage is not presented as SQL correctness.

Phase 8 replaces 20 high-frequency legacy SQL expression strings with a closed, recursively type-checked physical expression algebra. Configuration may declare only typed columns, literals, arithmetic, explicit safe division, comparisons, boolean composition, negation, and coalesce; arbitrary SQL text and function escape hatches are rejected. The planner lowers these declarations into Physical IR and SQLGlot nodes, with explicit parentheses preserving arithmetic tree semantics and `NULLIF(denominator, 0)` protecting ratio formulas. Official migration coverage rises from `33/1,097` to `72/1,097` (`6.56%`) while compile P95 remains `5.2387 ms`. Six representative newly eligible strategies match the legacy backend on real Doris data by row count and SHA-256 (`6/6`, zero errors); their shadow P95 is `1,025.2171 ms`, below the 10-second execution target but slower than the legacy comparison path, so Phase 8 claims correctness expansion rather than speedup. See `reports/phase8_derived_expression_funnel.md` and `reports/phase8_derived_expression_doris.md`.

If running from the repository root without installing the package:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli compile 'filter(indicator("close") >= MAX(indicator("close"), 250))'
python -m findsl.cli compile 'filter(RET(indicator("close"), 2) > 0.05)'
python -m findsl.cli diagnose 'filter(indicator("clos") > 10)'
python -m findsl.cli suggest-dsl '今日收盘价创二百五十日新高'
python -m findsl.cli validate-llm-candidates --response-file data/samples/llm_candidate_response.json --json
python -m findsl.cli llm-suggest-dsl '近3日成交量累计大于300' --model '<provider-model>' --json
python -m findsl.cli official-suite --json
python -m findsl.cli official-slot-coverage --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/official_slot_coverage.json --report-output reports/official_slot_coverage.md
python -m findsl.cli official-coverage-funnel --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/phase7_official_pipeline_funnel.json --report-output reports/phase7_official_pipeline_funnel.md
python -m findsl.cli official-performance-matrix --json
python -m findsl.cli defense-package --json
powershell -ExecutionPolicy Bypass -File .\scripts\evaluate.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\reference_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\verify_sql_sample.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\official_suite.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\validate_llm_candidates.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\defense_package.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\benchmark_prefix_sum.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\scale_benchmark.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\generate_doris_assets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_doris_scale_evidence.ps1 -ProxyUrl "http://127.0.0.1:7897"
python .\scripts\fetch_real_market_sample.py
powershell -ExecutionPolicy Bypass -File .\scripts\export_submission_artifacts.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\serve_demo.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\submission_readiness.ps1
```

## Semantic Reference Evaluation

The repository includes a small sample A-share-style dataset under `data/samples/`.
`PandasReferenceEvaluator` interprets DSL directly over those CSV tables. It is intentionally independent from the SQL generator, so it can serve as a slow but trustworthy semantic oracle.

This is the foundation for later SQL equivalence tests:

```text
DSL -> Pandas reference result
DSL -> compiler -> SQLite/Doris SQL result
compare result sets
```

The current implementation already runs the generated SQL over in-memory SQLite tables loaded from CSV fixtures. SQLite is used as a lightweight local execution harness, while the generated SQL remains Doris-oriented and window-safe. This gives every compiler change a fast semantic regression gate before the Doris execution path is introduced.

## Real Market Sample

`scripts/fetch_real_market_sample.py` produces a small, versioned Eastmoney A-share sample in `data/real_samples/eastmoney_a_share_sample/`. The sample includes `daily_quote.csv`, `stock_universe.csv`, cached raw JSON payloads, metadata, and ready-to-run DSL cases for turnover, return rate, and rolling volume. `money_flow.csv` is a neutral zero-valued placeholder only so the existing three-table sample loader can run quote-only DSLs; it is not used as real money-flow evidence.

Use the sample for business credibility in the demo:

```powershell
$env:PYTHONPATH="src"
python -m findsl.cli verify-sql 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample
```

Refresh the raw Eastmoney JSON only when needed:

```powershell
python .\scripts\fetch_real_market_sample.py --refresh --proxy "http://127.0.0.1:7897"
```

## Prefix-Sum Optimization

Indicators can declare prefix-sum support in `configs/indicators.json`. When the compiler sees an eligible `SUM(indicator(...), window)` expression, it rewrites the rolling window aggregate into prefix table joins:

```text
window_sum = current_prefix - prefix_at_row_no_minus_window
```

This is the optimizer path aimed at the competition's long-range query acceleration requirement. Unsupported indicators still use ordinary SQL window functions, so the optimization is safe and configuration-driven. For sparse auxiliary sources, generated prefix tables are built from the daily quote trading calendar with a left join back to the auxiliary values, preserving the same stock-date universe used by the reference oracle.

The `benchmark-prefix-sum` command compiles the same DSL twice: once with prefix-sum disabled as a baseline window query, and once with prefix-sum enabled. It then checks both SQL outputs against the Pandas reference result and writes a Markdown report with timing and plan-shape evidence. Local SQLite timings are treated as regression signals; the competition-scale acceleration claim is backed separately by Doris data, `EXPLAIN`, row-count parity, and latency evidence.

`scripts/scale_benchmark.ps1` goes one step further: it generates deterministic synthetic market data under `data/generated/scale/`, runs a 120-day rolling `SUM` query against baseline-window and prefix-sum SQL, and writes `reports/prefix_sum_scale_benchmark.md`. The report records correctness gates, local timing, plan shape, and a long-window feature-access reduction estimate. It is designed as reproducible pre-Doris evidence and complements, rather than replaces, the committed Doris cluster proof.

After the Doris schema, data, and prefix tables are loaded, `scripts/collect_doris_evidence.ps1` captures real-cluster `EXPLAIN`, repeated `COUNT(*)` latency, row-count equivalence, plan-shape markers, and the default 10x speedup target into `reports/doris_cluster_evidence.md` plus a JSON sidecar. The readiness report consumes this file and closes the `Doris-scale performance proof` warning only when baseline and optimized SQL both succeed, row counts match, the baseline contains a window plan, the optimized query uses a prefix table, and measured Doris speedup meets the 10x target.

For the repeatable local 5M-row path, `scripts/prepare_doris_scale_evidence.ps1` starts the Docker Doris cluster, generates deterministic CSV data, Stream Loads the base tables, rebuilds prefix tables, collects Doris evidence, and reruns readiness. Use `-ProxyUrl "http://127.0.0.1:7897"` when Docker image pulls need the local VPN proxy.

## Structured Explain

Compiler JSON output includes both human-readable `trace` text and machine-readable `explain` steps. Each explain step records a rule name, status, message, and evidence dictionary. This lets evaluation reports, future UI panels, and answer-defense materials show why an optimization was applied or skipped.

## Web Demo

`scripts/serve_demo.ps1` starts a local Web Demo at `http://127.0.0.1:8765`. The first segmented control selects one of two deliberately separate compiler identities:

- **Internal validation pipeline** accepts a Chinese stock-screening request, proposes compiler-validated FinDSL candidates, runs the deterministic internal compiler, and can compare SQL output with an independent reference executor. Baseline cases, official-style positive/negative presets, and a small whitelisted Eastmoney real-market sample remain available here.
- **Official competition pipeline** accepts the official seven-slot DSL and invokes the real ANTLR frontend, Typed AST construction, Logical IR, Physical IR, and SQLGlot Doris backend. The result tabs expose Doris SQL, frontend/Typed AST, Logical IR, Physical IR, stage trace, delivery evidence, and structured diagnostics. Examples include ordinary mappings, multi-resource joins, stage rank, event windows, exact-security scopes, unavailable finance data, and T+0 rejection.

The browser compiles and audits official plans but does not directly query the production Doris cluster. Real execution, complete result hashes, EXPLAIN summaries, and latency evidence remain versioned under `submission_artifacts/evidence_snapshots/`. Expected negative examples display the failed stage, expected and actual diagnostic codes, and the partial pipeline generated before rejection; they do not emit placeholder SQL. Long SQL and IR are contained in a keyboard-focusable result viewport, while result tabs and the pipeline selector support standard arrow-key navigation. Browser QA is performed at 360, 390, 768, and 1440 pixel widths with zero page-level horizontal overflow.

The same server exposes JSON APIs:

- `GET /api/examples`
- `POST /api/suggest`
- `POST /api/analyze`
- `GET /api/official/examples`
- `POST /api/official/analyze`

The first three endpoints preserve the original internal FinDSL demonstration and its local reference verifier. The `/api/official/*` endpoints use the official seven-slot syntax and the new ANTLR/Typed AST/Logical IR/Physical IR/SQLGlot pipeline. They are intentionally separate until the migration funnel shows that replacing the legacy path will not regress supported official behavior.

## Safe LLM Candidate Adapter

`validate-llm-candidates` is an offline safety adapter for model-proposed DSL. It accepts a structured or markdown-style LLM response file, extracts candidate FinDSL expressions, rejects direct SQL-looking output, compiles remaining DSL through the deterministic compiler, and requires SQL/reference equivalence when verification is enabled.

The bundled `data/samples/llm_candidate_response.json` intentionally contains one valid DSL candidate, one misspelled indicator, and one unsafe direct SQL candidate. This gives the defense package concrete evidence that LLM assistance is useful but cannot bypass parser, semantic validation, diagnostics, optimizer explain, or reference-oracle checks.

`llm-suggest-dsl` adds a real-provider entry point without changing that boundary. It posts a JSON-only FinDSL prompt to an OpenAI-compatible `/chat/completions` endpoint, extracts candidates from the response, and immediately reuses `validate_llm_candidates`. The command reads `FINDSL_LLM_MODEL` or `--model`, `FINDSL_LLM_API_KEY` by default, and optionally `FINDSL_LLM_BASE_URL` for local or domestic-compatible providers:

```powershell
$env:FINDSL_LLM_API_KEY="<your key>"
$env:FINDSL_LLM_MODEL="<provider-model>"
$env:FINDSL_LLM_BASE_URL="https://api.openai.com/v1"
python -m findsl.cli llm-suggest-dsl "近3日成交量累计大于300" --json
```

For a local provider that does not require authentication, pass `--no-api-key --base-url http://127.0.0.1:8000/v1 --model <local-model>`. Provider access is optional; the offline adapter and deterministic NL2DSL templates remain the reproducible competition path.

## Doris Assets

`scripts/generate_doris_assets.ps1` creates the SQL files under `deploy/doris/`:

```text
01_schema.sql
02_sample_data.sql
03_build_prefix_tables.sql
04_smoke_queries.sql
```

These files are a smoke-test deployment path for Doris. The schema generator emits monthly `trade_date` auto partitions plus a shared `colocate_with` group on `ts_code`, so the date-range pushdown and prefix-table joins have visible physical-design support. See `docs/doris_runbook.md` for execution order and production notes.

To capture cluster evidence for the submission gate:

```powershell
$env:DORIS_HOST="127.0.0.1"
$env:DORIS_PORT="9030"
$env:DORIS_USER="root"
powershell -ExecutionPolicy Bypass -File .\scripts\collect_doris_evidence.ps1
```

The script defaults `DORIS_EVIDENCE_MIN_SPEEDUP` to `10.0`, matching the competition acceleration target. Keep the default for final submission evidence so `submission_readiness.ps1` can validate the 10x marker.

For password-protected private clusters, set `DORIS_PASSWORD` and `DORIS_PASSWORD_MODE=inline`, or use `DORIS_PASSWORD_MODE=prompt` in an interactive shell. The generated report redacts inline passwords from the command template.

## Submission Readiness

`scripts/submission_readiness.ps1` generates `reports/submission_readiness.md` and companion evidence reports. The readiness report is designed as a pre-submission gate: it runs pytest, compiler evaluation, SQL/reference equivalence, prefix-sum benchmark checks, Demo API smoke checks, NL2DSL validated-candidate checks, structured diagnostics checks, Doris SQL validation evidence, public real-market sample verification, config-only indicator extension evidence, Doris asset integrity checks, Doris cluster evidence marker checks, and git rollback-state inspection.

The readiness report also runs `official-suite`, which currently covers 37 positive official-style cases and 37 negative diagnostic cases across staged filters, top-N ranking, percent-cutoff ranking, date-range pushdown, window-safe date pruning, rolling boolean conditions, moving averages, rolling extrema, prefix-sum aggregates, hot-window materialized columns, market joins, cross-market boolean `&/^/|` logic, arithmetic predicates, signed numeric thresholds, sparse auxiliary joins, repeated rank stages, case-insensitive inputs, inequality predicates, parenthesized OR predicates, return-rate drawdown thresholds, duplicate named arguments, invalid dates, invalid rank directions, invalid windows, mutually exclusive rank cutoffs, and invalid-DSL repair diagnostics. Each positive case must compile, expose expected SQL/trace/explain evidence, and match the independent SQL/reference result. Each negative case must fail with a stable diagnostic code and actionable suggestions.

It also validates the safe LLM candidate loop and generates `reports/defense_package.md`, a live-defense walkthrough that maps NL2DSL validation, official NL2DSL template coverage, LLM guardrails, the OpenAI-compatible provider contract, prefix-sum positive presets, diagnostic negative presets, public real-market quote samples, official coverage, compiler latency, Doris asset integrity, and the exported Doris proof to concrete scoring evidence.

Required gates fail the command when correctness or asset integrity breaks. Warning gates highlight competition risks such as missing Doris-cluster scale proof or uncommitted local changes.

Because `reports/` is generated and ignored by Git, run `scripts/export_submission_artifacts.ps1` before the final commit. It copies lightweight evidence reports into `submission_artifacts/evidence_snapshots/` so the submitted repository contains a reviewable evidence snapshot without committing large CSV data.

The same export step also writes `submission_artifacts/evidence_metadata.json`, a machine-readable summary of readiness gates, pytest count, official-suite counts, and Doris cluster speedup. It also renders `submission_artifacts/evidence_summary.md`, a short human-readable evidence page for reviewers. Treat both files as consistency indexes for reports, PPT, and Demo indicators; the original snapshot files remain the audit source.

## Competition-Oriented Design

This repository is built around the topic's quantitative requirements:

- SQL correctness target: `>= 95%`
- Compile P95 target: `< 50ms`
- Long-range acceleration target: `10x+`
- New indicator/function target: core compiler code change `0 lines`

The current implementation establishes a reliable compiler kernel, correctness oracle, optimizer evidence, Doris assets, real Doris-cluster execution proof, a public real-market quote sample, NL2DSL templates, safe LLM candidate validation, an optional OpenAI-compatible provider entry point, official-style coverage evidence, and a local demo. Provider output is still treated as untrusted DSL-candidate text, so it cannot bypass compiler validation or SQL/reference equivalence.
