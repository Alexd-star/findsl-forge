# 性能证据口径注册表

- 校验状态：`PASS`
- 当前打包 HEAD：`10b7af790420e2727fa654e84128de24b1f8992f`
- 全部证据源与当前 HEAD 一致：`True`
- 每项指标绑定独立工作负载、单位、比较符和阈值；不同实验结果不得互相替代。

| 指标 | 工作负载 | 实测值 | 门槛 | 赛题门禁 | HEAD一致 | 结论 | 可证明范围 |
|---|---|---:|---:|---|---|---|---|
| official_routine_prefix_speedup | 官方真实行情常规20日成交量窗口：窗口基线与前缀表路径 | 18.013000x | `gte 1.0x` | 否 | PASS | PASS | 证明常规窗口工作负载的前缀路径没有性能退化，不代表全部查询的加速倍数 |
| official_long_horizon_min_speedup | 五类官方真实行情5000交易日聚合工作负载中的最低加速比 | 14.666667x | `gte 10.0x` | 是 | PASS | PASS | 用于赛题长周期查询相对全表扫描不低于10倍的保守门禁，取五类工作负载中的最小值 |
| synthetic_5m_scalability_speedup | 500万行确定性合成数据的120日滑窗与前缀路径 | 16.862107x | `gte 1.0x` | 否 | PASS | PASS | 证明扩展性实验中的优化潜力，不替代官方真实数据门禁 |
| official_full_matrix_max_p95 | 覆盖12类官方函数族和主要物理计划的48条分层Doris执行矩阵 | 2865.055500ms | `lte 10000.0ms` | 是 | PASS | PASS | 用于赛题SQL执行时间不超过10秒的分层工作负载门禁 |
| official_compile_p95 | 48条分层官方有效问句的正式编译器预热服务请求 | 29.902600ms | `lt 50.0ms` | 是 | PASS | PASS | 用于赛题正式编译P95低于50毫秒门禁 |
| hero_query_execution | then、CONS、EXIST、跨市场集合运算和分阶段排名复合Hero Query | 767.926100ms | `lte 10000.0ms` | 否 | PASS | PASS | 证明高复杂度组合问句在真实Doris上的完整结果等价和现场可执行性 |
