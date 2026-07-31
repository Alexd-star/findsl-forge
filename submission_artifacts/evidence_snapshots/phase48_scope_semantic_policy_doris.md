# Phase 48 范围语义政策独立 Doris 证据

- 状态：`PASS`
- Git HEAD：`7825c458aaa740f94440d938e1f8bebc6bfacea1`
- 政策集：`official-competition-scope-policy-v1`
- 数据锚点：`2026-04-14`
- 源成员与物化成员完整集合一致：`7/7`
- 独立参考 SQL 与生成 SQL 完整行集一致：`7/7`
- 编译 P95 < 50 ms：`7/7`
- 执行 P95 < 10000 ms：`7/7`
- Physical IR 与 SQL 溯源合同：`7/7`

| 政策 | 源成员 | 物化成员 | 查询行数 | 编译P95/ms | 执行P95/ms | 状态 |
|---|---:|---:|---:|---:|---:|---|
| `exchange-s-board-name-rule-v1` | 1 | 1 | 1 | 12.4201 | 183.9040 | PASS |
| `deep-sea-economy-to-technology-v1` | 140 | 140 | 140 | 13.3154 | 234.4579 | PASS |
| `broad-technology-to-tmt-v1` | 1220 | 1220 | 1220 | 16.4243 | 213.0261 | PASS |
| `data-center-truncated-name-correction-v1` | 613 | 613 | 612 | 12.7001 | 123.3211 | PASS |
| `laser-ranging-to-lidar-correction-v1` | 89 | 89 | 88 | 10.1459 | 110.7303 | PASS |
| `guzi-cop-to-guzi-economy-correction-v1` | 121 | 121 | 121 | 11.5543 | 138.0345 | PASS |
| `shanghai-water-conservancy-intersection-v1` | 11 | 11 | 11 | 12.1220 | 145.9707 | PASS |

> 参考 SQL 直接读取原始来源快照：精确范围按源快照与源代码筛选，S 板按证券简称规则筛选，上海水利工程按两个完整集合求交。参考 SQL 未复用编译器生成 SQL，也未以行数相同替代完整稳定键集合比较。

> 中等风险政策是比赛配置中的可替换业务口径，不冒充赛题方唯一语义；Physical IR 保留 policy_id、依据类型、风险等级和依据链接，SQL 只消费版本化成员快照。
