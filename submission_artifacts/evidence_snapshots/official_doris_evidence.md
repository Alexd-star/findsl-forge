# Official Doris Real-Data Evidence

## Summary

- Evidence source: official Topic 19 CSV package
- Generated at: 2026-08-12T19:34:35Z
- Git HEAD: `a323d96ca63728b4ac9dbba3d5599c56a6cd135d`
- Doris version: `VERSION()
5.7.99`
- Doris host: `127.0.0.1`
- Query port: 9030
- FE HTTP port: 8030
- Stream Load endpoint: `127.0.0.1:8040`
- Iterations per query: 3
- Technical feature bucket count: 16
- Official row-count parity: True
- Official feature tables rebuilt in this run: False
- Official feature tables available: True
- Baseline/prefix row-count match: True
- Baseline vs prefix speedup: 15.46x

## Row Counts

| Table | Expected | Actual |
|---|---:|---:|
| hsj_stock_code_info | 5686 | 5686 |
| hsj_stock_hq_basic | 13650347 | 13650347 |
| hsj_stock_hq_ext | 6170822 | 6170822 |

## Feature Table Row Counts

| Table | Expected | Actual |
|---|---:|---:|
| hsj_stock_hq_basic_prefix | 13650347 | 13650347 |
| hsj_stock_hq_ext_prefix | 13650347 | 13650347 |
| hsj_stock_hq_basic_technical | 13650347 | 13650347 |
| hsj_stock_hq_basic_rollup | 13650347 | 13650347 |

## Date Ranges

```text
first_basic_date	last_basic_date
2006-01-04	2026-04-14
first_ext_date	last_ext_date
2018-08-20	2026-04-14
```

## Query Evidence

| Query | Rows | Avg ms | P95 ms | Prefix plan | Window plan |
|---|---:|---:|---:|---:|---:|
| simple_close_price_filter | 3836 | 62.23 | 73.884 | False | False |
| rank_volume_top10 | 10 | 71.323 | 88.148 | False | True |
| technical_long_window_feature_filter | 5614 | 120.879 | 167.581 | False | False |
| ext_main_net_inflow_filter | 2247 | 93.614 | 114.214 | False | False |
| baseline_window_volume_sum_20 | 5487 | 884.034 | 931.297 | False | True |
| prefix_optimized_volume_sum_20 | 5487 | 57.181 | 68.287 | True | False |

## Stream Load Results

## SQL and EXPLAIN

### simple_close_price_filter

```sql
SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (base.closePx / 10000.0) > 10 AND base.bizdate = DATE '2026-04-14'
```

```text
Explain String(Nereids Planner)
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    mktcode[#89]
    tgtcode[#90]
    bizdate[#91]
    name[#92]
  PARTITION: HASH_PARTITIONED: mktcode[#22], tgtcode[#23]

  HAS_COLO_PLAN_NODE: false

  VRESULT SINK
     MYSQL_PROTOCOL

  3:VHASH JOIN(285)
  |  join op: LEFT OUTER JOIN(BROADCAST)[]
  |  equal join conjunct: (mktcode[#80] = mktcode[#19])
  |  equal join conjunct: (tgtcode[#81] = tgtcode[#20])
  |  cardinality=3,412,586
  |  vec output tuple id: 5
  |  output tuple id: 5
  |  vIntermediate tuple ids: 4 
  |  hash output slot ids: 80 81 82 21 
  |  final projections: mktcode[#83], tgtcode[#84], bizdate[#85], name[#88]
  |  final project output tuple id: 5
  |  distribute expr lists: mktcode[#80], tgtcode[#81]
  |  distribute expr lists: 
  |  
  |----1:VEXCHANGE
  |       offset: 0
  |       distribute expr lists: mktcode[#19], tgtcode[#20]
  |    
  2:VOlapScanNode(260)
     TABLE: newzl.hsj_stock_hq_basic(hsj_stock_hq_basic), PREAGGREGATION: ON
     PREDICATES: (((closePx[#30] > 100000) AND (bizdate[#24] = '2026-04-14')) AND (__DORIS_DELETE_SIGN__[#78] = 0))
     partitions=1/1 (hsj_stock_hq_basic)
     tablets=16/16, tabletList=1785410008724,1785410008726,1785410008728 ...
     cardinality=13650347, avgRowSize=150.01868, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#22], tgtcode[#23], bizdate[#24]
     final project output tuple id: 3

PLAN FRAGMENT 1

  PARTITION: HASH_PARTITIONED: mktcode[#0], tgtcode[#1]

  HAS_COLO_PLAN_NODE: false

  STREAM DATA SINK
    EXCHANGE ID: 01
    UNPARTITIONED

  0:VOlapScanNode(269)
     TABLE: newzl.hsj_stock_code_info(hsj_stock_code_info), PREAGGREGATION: ON
     PREDICATES: (__DORIS_DELETE_SIGN__[#17] = 0)
     partitions=1/1 (hsj_stock_code_info)
     tablets=16/16, tabletList=1785410008689,1785410008691,1785410008693 ...
     cardinality=5686, avgRowSize=267.0515, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#0], tgtcode[#1], name[#2]
     final project output tuple id: 1



========== STATISTICS ==========
planned with unknown column statistics
```

### rank_volume_top10

```sql
SELECT * FROM (SELECT base.mktcode, base.tgtcode, base.bizdate, code.name, ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY base.volume DESC, base.tgtcode ASC) AS rank_no FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE base.bizdate = DATE '2026-04-14') AS ranked WHERE rank_no <= 10
```

```text
Explain String(Nereids Planner)
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    mktcode[#107]
    tgtcode[#108]
    bizdate[#109]
    name[#110]
    rank_no[#111]
  PARTITION: HASH_PARTITIONED: bizdate[#98]

  HAS_COLO_PLAN_NODE: false

  VRESULT SINK
     MYSQL_PROTOCOL

  7:VANALYTIC(557)
  |  functions: [row_number()]
  |  partition by: bizdate[#103]
  |  order by: volume[#105] DESC NULLS LAST, tgtcode[#102] ASC NULLS FIRST
  |  window: ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  |  predicates: (rank_no[#106] <= 10)
  |  final projections: mktcode[#101], tgtcode[#102], bizdate[#103], name[#104], rank_no[#106]
  |  final project output tuple id: 9
  |  distribute expr lists: bizdate[#103]
  |  
  6:VSORT(553)
  |  order by: bizdate[#103] ASC, volume[#105] DESC, tgtcode[#102] ASC
  |  algorithm: full sort
  |  offset: 0
  |  distribute expr lists: bizdate[#98]
  |  
  5:VEXCHANGE
     offset: 0
     distribute expr lists: mktcode[#96], tgtcode[#97]

PLAN FRAGMENT 1

  PARTITION: HASH_PARTITIONED: mktcode[#22], tgtcode[#23]

  HAS_COLO_PLAN_NODE: false

  STREAM DATA SINK
    EXCHANGE ID: 05
    HASH_PARTITIONED: bizdate[#98]

  4:VPartitionTopN(545)
  |  functions: row_number
  |  partition by: bizdate[#93]
  |  order by: volume[#100] DESC, tgtcode[#97] ASC
  |  has global limit: false
  |  partition limit: 10
  |  partition topn phase: TWO_PHASE_LOCAL_PTOPN
  |  distribute expr lists: mktcode[#91], tgtcode[#92]
  |  
  3:VHASH JOIN(537)
  |  join op: LEFT OUTER JOIN(BROADCAST)[]
  |  equal join conjunct: (mktcode[#80] = mktcode[#19])
  |  equal join conjunct: (tgtcode[#81] = tgtcode[#20])
  |  cardinality=6,825,173
  |  vec output tuple id: 5
  |  output tuple id: 5
  |  vIntermediate tuple ids: 4 
  |  hash output slot ids: 80 81 82 83 21 
  |  final projections: mktcode[#84], tgtcode[#85], bizdate[#86], name[#90], volume[#87]
  |  final project output tuple id: 5
  |  distribute expr lists: mktcode[#80], tgtcode[#81]
  |  distribute expr lists: 
  |  
  |----1:VEXCHANGE
  |       offset: 0
  |       distribute expr lists: mktcode[#19], tgtcode[#20]
  |    
  2:VOlapScanNode(512)
     TABLE: newzl.hsj_stock_hq_basic(hsj_stock_hq_basic), PREAGGREGATION: ON
     PREDICATES: ((bizdate[#24] = '2026-04-14') AND (__DORIS_DELETE_SIGN__[#78] = 0))
     partitions=1/1 (hsj_stock_hq_basic)
     tablets=16/16, tabletList=1785410008724,1785410008726,1785410008728 ...
     cardinality=13650347, avgRowSize=150.01868, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#22], tgtcode[#23], bizdate[#24], volume[#31]
     final project output tuple id: 3

PLAN FRAGMENT 2

  PARTITION: HASH_PARTITIONED: mktcode[#0], tgtcode[#1]

  HAS_COLO_PLAN_NODE: false

  STREAM DATA SINK
    EXCHANGE ID: 01
    UNPARTITIONED

  0:VOlapScanNode(521)
     TABLE: newzl.hsj_stock_code_info(hsj_stock_code_info), PREAGGREGATION: ON
     PREDICATES: (__DORIS_DELETE_SIGN__[#17] = 0)
     partitions=1/1 (hsj_stock_code_info)
     tablets=16/16, tabletList=1785410008689,1785410008691,1785410008693 ...
     cardinality=5686, avgRowSize=267.0515, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#0], tgtcode[#1], name[#2]
     final project output tuple id: 1



========== STATISTICS ==========
planned with unknown column statistics
```

### technical_long_window_feature_filter

```sql
SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_hq_basic_technical AS tech ON tech.mktcode = base.mktcode AND tech.tgtcode = base.tgtcode AND tech.bizdate = base.bizdate LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE base.bizdate = DATE '2026-04-14' AND tech.ma250 > 0 AND tech.volume_avg_60 > 0
```

```text
Explain String(Nereids Planner)
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    mktcode[#137]
    tgtcode[#138]
    bizdate[#139]
    name[#140]
  PARTITION: HASH_PARTITIONED: mktcode[#60], tgtcode[#61]

  HAS_COLO_PLAN_NODE: false

  VRESULT SINK
     MYSQL_PROTOCOL

  6:VHASH JOIN(678)
  |  join op: INNER JOIN(BUCKET_SHUFFLE)[]
  |  equal join conjunct: (mktcode[#127] = mktcode[#36])
  |  equal join conjunct: (tgtcode[#128] = tgtcode[#37])
  |  cardinality=6,825,173
  |  vec output tuple id: 9
  |  output tuple id: 9
  |  vIntermediate tuple ids: 8 
  |  hash output slot ids: 128 129 130 127 
  |  runtime filters: RF000[min_max] <- mktcode[#36](1706293/2097152/2097152), RF001[in_or_bloom] <- mktcode[#36](1706293/2097152/2097152), RF002[min_max] <- tgtcode[#37](1706293/2097152/2097152), RF003[in_or_bloom] <- tgtcode[#37](1706293/2097152/2097152)
  |  final projections: mktcode[#131], tgtcode[#132], bizdate[#133], name[#134]
  |  final project output tuple id: 9
  |  distribute expr lists: mktcode[#127], tgtcode[#128]
  |  distribute expr lists: mktcode[#36], tgtcode[#37]
  |  
  |----1:VEXCHANGE
  |       offset: 0
  |       distribute expr lists: mktcode[#36], tgtcode[#37]
  |    
  5:VHASH JOIN(657)
  |  join op: LEFT OUTER JOIN(BROADCAST)[]
  |  equal join conjunct: (mktcode[#118] = mktcode[#57])
  |  equal join conjunct: (tgtcode[#119] = tgtcode[#58])
  |  cardinality=6,825,173
  |  vec output tuple id: 7
  |  output tuple id: 7
  |  vIntermediate tuple ids: 6 
  |  hash output slot ids: 118 119 120 59 
  |  final projections: mktcode[#121], tgtcode[#122], bizdate[#123], name[#126]
  |  final project output tuple id: 7
  |  distribute expr lists: mktcode[#118], tgtcode[#119]
  |  distribute expr lists: 
  |  
  |----3:VEXCHANGE
  |       offset: 0
  |       distribute expr lists: mktcode[#57], tgtcode[#58]
  |    
  4:VOlapScanNode(632)
     TABLE: newzl.hsj_stock_hq_basic(hsj_stock_hq_basic), PREAGGREGATION: ON
     PREDICATES: ((bizdate[#62] = '2026-04-14') AND (__DORIS_DELETE_SIGN__[#116] = 0))
     partitions=1/1 (hsj_stock_hq_basic)
     tablets=16/16, tabletList=1785410008724,1785410008726,1785410008728 ...
     cardinality=13650347, avgRowSize=150.01868, numNodes=1
     pushAggOp=NONE
     runtime filters: RF000[min_max] -> mktcode[#60], RF001[in_or_bloom] -> mktcode[#60], RF002[min_max] -> tgtcode[#61], RF003[in_or_bloom] -> tgtcode[#61]
     final projections: mktcode[#60], tgtcode[#61], bizdate[#62]
     final project output tuple id: 5

PLAN FRAGMENT 1

  PARTITION: HASH_PARTITIONED: mktcode[#38], tgtcode[#39]

  HAS_COLO_PLAN_NODE: false

  STREAM DATA SINK
    EXCHANGE ID: 03
    UNPARTITIONED

  2:VOlapScanNode(641)
     TABLE: newzl.hsj_stock_code_info(hsj_stock_code_info), PREAGGREGATION: ON
     PREDICATES: (__DORIS_DELETE_SIGN__[#55] = 0)
     partitions=1/1 (hsj_stock_code_info)
     tablets=16/16, tabletList=1785410008689,1785410008691,1785410008693 ...
     cardinality=5686, avgRowSize=267.0515, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#38], tgtcode[#39], name[#40]
     final project output tuple id: 3

PLAN FRAGMENT 2

  PARTITION: HASH_PARTITIONED: mktcode[#0], tgtcode[#1]

  HAS_COLO_PLAN_NODE: false

  STREAM DATA SINK
    EXCHANGE ID: 01
    BUCKET_SHFFULE_HASH_PARTITIONED: mktcode[#36], tgtcode[#37]

  0:VOlapScanNode(662)
     TABLE: newzl.hsj_stock_hq_basic_technical(hsj_stock_hq_basic_technical), PREAGGREGATION: ON
     PREDICATES: (((bizdate[#2] = '2026-04-14') AND (ma250[#19] > 0)) AND ((volume_avg_60[#24] > 0) AND (__DORIS_DELETE_SIGN__[#34] = 0)))
     partitions=1/1 (hsj_stock_hq_basic_technical)
     tablets=16/16, tabletList=1785410008975,1785410008977,1785410008979 ...
     cardinality=13650347, avgRowSize=515.9676, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#0], tgtcode[#1]
     final project output tuple id: 1



========== STATISTICS ==========
planned with unknown column statistics
```

### ext_main_net_inflow_filter

```sql
SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_hq_ext AS ext ON ext.mktcode = base.mktcode AND ext.tgtcode = base.tgtcode AND ext.bizdate = base.bizdate LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE base.bizdate = DATE '2026-04-14' AND ext.ZJLXMainNetTur > 0
```

```text
Explain String(Nereids Planner)
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    mktcode[#167]
    tgtcode[#168]
    bizdate[#169]
    name[#170]
  PARTITION: HASH_PARTITIONED: mktcode[#90], tgtcode[#91]

  HAS_COLO_PLAN_NODE: false

  VRESULT SINK
     MYSQL_PROTOCOL

  6:VHASH JOIN(678)
  |  join op: INNER JOIN(BUCKET_SHUFFLE)[]
  |  equal join conjunct: (mktcode[#157] = mktcode[#66])
  |  equal join conjunct: (tgtcode[#158] = tgtcode[#67])
  |  cardinality=6,825,173
  |  vec output tuple id: 9
  |  output tuple id: 9
  |  vIntermediate tuple ids: 8 
  |  hash output slot ids: 160 157 158 159 
  |  runtime filters: RF000[min_max] <- mktcode[#66](1542705/2097152/2097152), RF001[in_or_bloom] <- mktcode[#66](1542705/2097152/2097152), RF002[min_max] <- tgtcode[#67](1542705/2097152/2097152), RF003[in_or_bloom] <- tgtcode[#67](1542705/2097152/2097152)
  |  final projections: mktcode[#161], tgtcode[#162], bizdate[#163], name[#164]
  |  final project output tuple id: 9
  |  distribute expr lists: mktcode[#157], tgtcode[#158]
  |  distribute expr lists: mktcode[#66], tgtcode[#67]
  |  
  |----1:VEXCHANGE
  |       offset: 0
  |       distribute expr lists: mktcode[#66], tgtcode[#67]
  |    
  5:VHASH JOIN(657)
  |  join op: LEFT OUTER JOIN(BROADCAST)[]
  |  equal join conjunct: (mktcode[#148] = mktcode[#87])
  |  equal join conjunct: (tgtcode[#149] = tgtcode[#88])
  |  cardinality=6,825,173
  |  vec output tuple id: 7
  |  output tuple id: 7
  |  vIntermediate tuple ids: 6 
  |  hash output slot ids: 148 149 150 89 
  |  final projections: mktcode[#151], tgtcode[#152], bizdate[#153], name[#156]
  |  final project output tuple id: 7
  |  distribute expr lists: mktcode[#148], tgtcode[#149]
  |  distribute expr lists: 
  |  
  |----3:VEXCHANGE
  |       offset: 0
  |       distribute expr lists: mktcode[#87], tgtcode[#88]
  |    
  4:VOlapScanNode(632)
     TABLE: newzl.hsj_stock_hq_basic(hsj_stock_hq_basic), PREAGGREGATION: ON
     PREDICATES: ((bizdate[#92] = '2026-04-14') AND (__DORIS_DELETE_SIGN__[#146] = 0))
     partitions=1/1 (hsj_stock_hq_basic)
     tablets=16/16, tabletList=1785410008724,1785410008726,1785410008728 ...
     cardinality=13650347, avgRowSize=150.01868, numNodes=1
     pushAggOp=NONE
     runtime filters: RF000[min_max] -> mktcode[#90], RF001[in_or_bloom] -> mktcode[#90], RF002[min_max] -> tgtcode[#91], RF003[in_or_bloom] -> tgtcode[#91]
     final projections: mktcode[#90], tgtcode[#91], bizdate[#92]
     final project output tuple id: 5

PLAN FRAGMENT 1

  PARTITION: HASH_PARTITIONED: mktcode[#68], tgtcode[#69]

  HAS_COLO_PLAN_NODE: false

  STREAM DATA SINK
    EXCHANGE ID: 03
    UNPARTITIONED

  2:VOlapScanNode(641)
     TABLE: newzl.hsj_stock_code_info(hsj_stock_code_info), PREAGGREGATION: ON
     PREDICATES: (__DORIS_DELETE_SIGN__[#85] = 0)
     partitions=1/1 (hsj_stock_code_info)
     tablets=16/16, tabletList=1785410008689,1785410008691,1785410008693 ...
     cardinality=5686, avgRowSize=267.0515, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#68], tgtcode[#69], name[#70]
     final project output tuple id: 3

PLAN FRAGMENT 2

  PARTITION: HASH_PARTITIONED: mktcode[#0], tgtcode[#1]

  HAS_COLO_PLAN_NODE: false

  STREAM DATA SINK
    EXCHANGE ID: 01
    BUCKET_SHFFULE_HASH_PARTITIONED: mktcode[#66], tgtcode[#67]

  0:VOlapScanNode(662)
     TABLE: newzl.hsj_stock_hq_ext(hsj_stock_hq_ext), PREAGGREGATION: ON
     PREDICATES: (((bizdate[#2] = '2026-04-14') AND (ZJLXMainNetTur[#14] > 0)) AND (__DORIS_DELETE_SIGN__[#64] = 0))
     partitions=1/1 (hsj_stock_hq_ext)
     tablets=16/16, tabletList=1785410008759,1785410008761,1785410008763 ...
     cardinality=6170822, avgRowSize=247.86974, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#0], tgtcode[#1]
     final project output tuple id: 1



========== STATISTICS ==========
planned with unknown column statistics
```

### baseline_window_volume_sum_20

```sql
SELECT w.mktcode, w.tgtcode, w.bizdate FROM (SELECT base.mktcode, base.tgtcode, base.bizdate, SUM(base.volume) OVER (PARTITION BY base.mktcode, base.tgtcode ORDER BY base.bizdate ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS volume_sum_20 FROM newzl.hsj_stock_hq_basic AS base) AS w WHERE w.bizdate = DATE '2026-04-14' AND w.volume_sum_20 > 10000000
```

```text
Explain String(Nereids Planner)
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    mktcode[#67]
    tgtcode[#68]
    bizdate[#69]
  PARTITION: HASH_PARTITIONED: mktcode[#0], tgtcode[#1]

  HAS_COLO_PLAN_NODE: true

  VRESULT SINK
     MYSQL_PROTOCOL

  2:VANALYTIC(271)
  |  functions: [sum(volume[#65])]
  |  partition by: mktcode[#62], tgtcode[#63]
  |  order by: bizdate[#64] ASC NULLS FIRST
  |  window: ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
  |  predicates: (bizdate[#64] = '2026-04-14'), (volume_sum_20[#66] > 10000000)
  |  final projections: mktcode[#62], tgtcode[#63], bizdate[#64]
  |  final project output tuple id: 4
  |  distribute expr lists: mktcode[#62], tgtcode[#63]
  |  
  1:VSORT(267)
  |  order by: mktcode[#62] ASC, tgtcode[#63] ASC, bizdate[#64] ASC
  |  algorithm: full sort
  |  offset: 0
  |  distribute expr lists: mktcode[#58], tgtcode[#59]
  |  
  0:VOlapScanNode(255)
     TABLE: newzl.hsj_stock_hq_basic(hsj_stock_hq_basic), PREAGGREGATION: ON
     PREDICATES: (__DORIS_DELETE_SIGN__[#56] = 0)
     partitions=1/1 (hsj_stock_hq_basic)
     tablets=16/16, tabletList=1785410008724,1785410008726,1785410008728 ...
     cardinality=13650347, avgRowSize=150.01868, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#0], tgtcode[#1], bizdate[#2], volume[#9]
     final project output tuple id: 1



========== STATISTICS ==========
planned with unknown column statistics
```

### prefix_optimized_volume_sum_20

```sql
SELECT p.mktcode, p.tgtcode, p.bizdate FROM newzl.hsj_stock_hq_basic_rollup AS p WHERE p.bizdate = DATE '2026-04-14' AND p.volume_sum_20 > 10000000
```

```text
Explain String(Nereids Planner)
PLAN FRAGMENT 0
  OUTPUT EXPRS:
    mktcode[#14]
    tgtcode[#15]
    bizdate[#16]
  PARTITION: HASH_PARTITIONED: mktcode[#1], tgtcode[#2]

  HAS_COLO_PLAN_NODE: false

  VRESULT SINK
     MYSQL_PROTOCOL

  0:VOlapScanNode(114)
     TABLE: newzl.hsj_stock_hq_basic_rollup(hsj_stock_hq_basic_rollup), PREAGGREGATION: ON
     PREDICATES: (((bizdate[#0] = '2026-04-14') AND (volume_sum_20[#10] > 10000000)) AND (__DORIS_DELETE_SIGN__[#12] = 0))
     partitions=1/244 (p20260401000000)
     tablets=16/16, tabletList=1786254383850,1786254383852,1786254383854 ...
     cardinality=50446, avgRowSize=192.33081, numNodes=1
     pushAggOp=NONE
     final projections: mktcode[#1], tgtcode[#2], bizdate[#0]
     final project output tuple id: 1



========== STATISTICS ==========
planned with unknown column statistics
```

