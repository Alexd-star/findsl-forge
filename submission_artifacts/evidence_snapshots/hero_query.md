# Hero Query 端到端证据

- 查询：`HERO-TEMPORAL-STAGE-RANK-001`
- Git HEAD：`5bde41c87fa3769b73f4abc5188b0fc2a81f5e82`
- 编译耗时：`238.7230 ms`
- 选择路由：`PARTITION`
- 选择策略：`stage_rank`
- 编译/特征门禁：`PASS`
- Doris 运行门禁：`PASS`

## DSL

```text
(indicator('沪|深', '', '成交量', '近10日', '', '', 'CONS>=3日') > 0 and indicator('沪&^科创板', '', '成交额', '近10日', '', '', 'EXIST>=2日') > 0) then rank('沪|深', '', '成交额', 'desc', '今日', '', '', '') between '[1,20]'
```

## 语义说明

市场槽中的 & 是集合交运算符，不是数值按位运算；该查询要求沪深范围、排除科创板的沪市子范围、CONS/EXIST 双时间量词、then 阶段屏障以及闭区间排名。

## 复杂能力核验

| 能力 | 通过 |
|---|---:|
| `has_rank` | True |
| `has_temporal` | True |
| `has_stage` | True |
| `has_interval` | True |
| `has_bitwise_alias` | True |
| `CONS + EXIST` | True |
| `and + then` | True |

## Doris 实测

- 完整结果集一致：`True`
- Generated rows / Reference rows：`20 / 20`
- Generated latency：`891.488 ms`
- 执行时间不超过 10 秒：`True`
