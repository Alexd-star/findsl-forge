# Doris Cluster Evidence

## Summary

- Evidence source: Apache Doris MySQL-compatible query port
- Generated at: 2026-05-23T15:11:26Z
- Database: `findsl_demo`
- Iterations: 5
- Client command template: `mysql -h 127.0.0.1 -P 9030 -u root --connect-timeout 10 --init-command 'SET enable_sql_cache=false' --batch --raw --skip-column-names findsl_demo -e 'SELECT 1'`
- Evidence passed: True
- Baseline success: True
- Optimized success: True
- Row counts match: True
- Baseline row count: 88586
- Optimized row count: 88586
- Doris cluster speedup: 36.24x
- Minimum Doris speedup target: 10.00x
- Doris speedup target met: True
- Baseline avg execute ms: 5182.042
- Optimized avg execute ms: 142.993
- Baseline P95 execute ms: 5461.011
- Optimized P95 execute ms: 155.716
- Optimized plan contains prefix table: True
- Baseline plan contains window: True

This is the Doris-scale evidence file consumed by `submission_readiness.ps1`.
Only generate it after loading schema, sample or scale data, and prefix tables into a real Doris cluster.

## DSL

```text
filter(SUM(indicator(volume), 120) > 1000000)
```

## Variant Metrics

| Variant | Success | Avg execute ms | P95 execute ms | Rows | Prefix plan | Window plan |
|---|---:|---:|---:|---:|---:|---:|
| baseline_window | True | 5182.042 | 5461.011 | 88586 | False | True |
| optimized_prefix_sum | True | 142.993 | 155.716 | 88586 | True | False |

## EXPLAIN Output

### baseline_window

```text
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    ts_code[#5]
    trade_date[#6]
    close[#7]
    turnover_rate[#8]
    volume[#9]
    __win_1[#10]
  PARTITION: HASH_PARTITIONED: ts_code[#0]

  HAS_COLO_PLAN_NODE: true

  VRESULT SINK
     MYSQL_PROTOCOL

  2:VANALYTIC(169)
  |  functions: [sum(volume[#9])]
  |  partition by: ts_code[#5]
  |  order by: trade_date[#6] ASC NULLS FIRST
  |  window: ROWS BETWEEN 119 PRECEDING AND CURRENT ROW
  |  predicates: (__win_1[#10] > 1000000)
  |  distribute expr lists: ts_code[#5]
  |  
  1:VSORT(165)
  |  order by: ts_code[#5] ASC, trade_date[#6] ASC
  |  algorithm: full sort
  |  offset: 0
  |  distribute expr lists: ts_code[#0]
  |  
  0:VOlapScanNode(161)
     TABLE: findsl_demo.dwd_stock_daily_quote(dwd_stock_daily_quote), PREAGGREGATION: ON
     partitions=33/33 (p20221001000000,p20230201000000,p20230301000000,p20221201000000,p20230401000000,p20240801000000,p20240901000000,p20220701000000,p20240501000000,p20220601000000,p20220901000000,p20240401000000,p20240701000000,p20221101000000,p20220801000000,p20240601000000,p20230101000000,p20220301000000,p20240101000000,p20220401000000,p20240201000000,p20231101000000,p20240301000000,p20230901000000,p20231201000000,p20220501000000,p20230601000000,p20230501000000,p20230801000000,p20220101000000,p20231001000000,p20230701000000,p20220201000000)
     tablets=264/264, tabletList=1779547885136,1779547885138,1779547885140 ...
     cardinality=5000000, avgRowSize=51.994324, numNodes=1
     pushAggOp=NONE



========== STATISTICS ==========
```

SQL:

```sql
SELECT * FROM (SELECT base_features.*, SUM(volume) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 119 PRECEDING AND CURRENT ROW) AS __win_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features) numeric_features_1 WHERE __win_1 > 1000000
```

### optimized_prefix_sum

```text
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    ts_code[#21]
    trade_date[#22]
    close[#23]
    turnover_rate[#24]
    volume[#25]
    __psum_1[#26]
  PARTITION: HASH_PARTITIONED: ts_code[#8]

  HAS_COLO_PLAN_NODE: true

  VRESULT SINK
     MYSQL_PROTOCOL

  2:VHASH JOIN(290)
  |  join op: INNER JOIN(COLOCATE[])[]
  |  equal join conjunct: (ts_code[#8] = ts_code[#5])
  |  equal join conjunct: (trade_date[#9] = trade_date[#6])
  |  cardinality=96,670,723
  |  vec output tuple id: 4
  |  output tuple id: 4
  |  vIntermediate tuple ids: 3 
  |  hash output slot ids: 7 8 9 10 11 12 
  |  runtime filters: RF000[min_max] <- ts_code[#5](5961/8192/1048576), RF001[in_or_bloom] <- ts_code[#5](5961/8192/1048576), RF002[min_max] <- trade_date[#6](1000/1024/1048576), RF003[in_or_bloom] <- trade_date[#6](1000/1024/1048576)
  |  final projections: ts_code[#13], trade_date[#14], close[#15], turnover_rate[#16], volume[#17], __psum_1[#20]
  |  final project output tuple id: 4
  |  distribute expr lists: ts_code[#8]
  |  distribute expr lists: ts_code[#5]
  |  
  |----0:VOlapScanNode(278)
  |       TABLE: findsl_demo.dwd_stock_daily_quote_prefix(dwd_stock_daily_quote_prefix), PREAGGREGATION: ON
  |       PREDICATES: (volume_sum_120[#4] > 1000000)
  |       partitions=33/33 (p20220101000000,p20220201000000,p20220301000000,p20220401000000,p20220501000000,p20220601000000,p20220701000000,p20220801000000,p20220901000000,p20221001000000,p20221101000000,p20221201000000,p20230101000000,p20230201000000,p20230301000000,p20230401000000,p20230501000000,p20230601000000,p20230701000000,p20230801000000,p20230901000000,p20231001000000,p20231101000000,p20231201000000,p20240101000000,p20240201000000,p20240301000000,p20240401000000,p20240501000000,p20240601000000,p20240701000000,p20240801000000,p20240901000000)
  |       tablets=264/264, tabletList=1779547886200,1779547886202,1779547886204 ...
  |       cardinality=5000000, avgRowSize=25.9734, numNodes=1
  |       pushAggOp=NONE
  |       final projections: ts_code[#0], trade_date[#1], volume_sum_120[#4]
  |       final project output tuple id: 1
  |    
  1:VOlapScanNode(277)
     TABLE: findsl_demo.dwd_stock_daily_quote(dwd_stock_daily_quote), PREAGGREGATION: ON
     partitions=33/33 (p20221001000000,p20230201000000,p20230301000000,p20221201000000,p20230401000000,p20240801000000,p20240901000000,p20220701000000,p20240501000000,p20220601000000,p20220901000000,p20240401000000,p20240701000000,p20221101000000,p20220801000000,p20240601000000,p20230101000000,p20220301000000,p20240101000000,p20220401000000,p20240201000000,p20231101000000,p20240301000000,p20230901000000,p20231201000000,p20220501000000,p20230601000000,p20230501000000,p20230801000000,p20220101000000,p20231001000000,p20230701000000,p20220201000000)
     tablets=264/264, tabletList=1779547885136,1779547885138,1779547885140 ...
     cardinality=5000000, avgRowSize=51.994324, numNodes=1
     pushAggOp=NONE
     runtime filters: RF000[min_max] -> ts_code[#8], RF001[in_or_bloom] -> ts_code[#8], RF002[min_max] -> trade_date[#9], RF003[in_or_bloom] -> trade_date[#9]



========== STATISTICS ==========
```

SQL:

```sql
SELECT * FROM (SELECT base_features.*, __pref_curr_1.volume_sum_120 AS __psum_1 FROM (SELECT base.* FROM dwd_stock_daily_quote AS base) base_features LEFT JOIN dwd_stock_daily_quote_prefix AS __pref_curr_1 ON __pref_curr_1.ts_code = base_features.ts_code AND __pref_curr_1.trade_date = base_features.trade_date) numeric_features_1 WHERE __psum_1 > 1000000
```
