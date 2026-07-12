# Phase 19 证券名称范围真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`e39fbacb21ca57fbb51f4a581b56b200d4811e62`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- 最新数据日期：`2026-04-14`
- 证券目录行数：`5686`
- 目录与实时 Doris 源哈希一致：`True`
- 完整行集哈希一致：`7/7`

| 场景 | 预期行数 | 实际行数 | 哈希一致 | Security Join | Cross Join | P95 ms |
|---|---:|---:|---|---|---|---:|
| exact_name_universe | 3675 | 3675 | 是 | True | False | 175.7458 |
| market_and_exact_name | 3681 | 3681 | 是 | True | False | 189.0478 |
| explicit_name_and_code | 1958 | 1958 | 是 | True | False | 108.0098 |
| direct_querydata_scalar | 1896 | 1896 | 是 | True | True | 92.8522 |
| global_querydata_aggregate | 1872 | 1872 | 是 | True | True | 65.8193 |
| rank_with_exact_name_scope | 1 | 1 | 是 | True | False | 45.9619 |
| exact_name_union | 6290 | 6290 | 是 | True | False | 194.0904 |

> 只有能在版本化官方证券主数据目录中精确解析的名称或“名称(六位代码)”才会进入 Physical IR。概念、行业、指数和自定义板块缺少成员关系时返回 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`，不会退化为全市场或空结果假成功。

> `queryData` 的直接值和全局聚合值均以独立命名关系执行，再通过 Cross Join 进入候选证券谓词；它们不会把名称过滤错误施加到候选全集，也不会按候选证券键关联全局基准。
