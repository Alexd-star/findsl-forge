# Phase 13 Typed Market Set IR 真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`583cb49df3368149f237a1dcd1c335821d66371b`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- 运算优先级：`^ > & > |`
- 行集哈希一致：`5/5`
- 代码表：`5686` 行；kcb/gem/B-share flag 真值：`0/0/0`

## 代码区间画像

| 受控集合 | 代码表数量 |
|---|---:|
| star_688 | 608 |
| chinext_300_301 | 1402 |
| sh_main_600_601_603_605 | 1726 |
| sz_main_000_001_002_003 | 1503 |
| beijing_920 | 307 |

## 行集等价

| 场景 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |
|---|---:|---:|---|---:|
| star_market | 606 | 606 | 是 | 307.3386 |
| chinext_market | 1392 | 1392 | 是 | 262.6255 |
| main_board_union | 3190 | 3190 | 是 | 355.5174 |
| precedence_union_intersection_not | 3875 | 3875 | 是 | 242.4644 |
| double_exclusion_beijing | 306 | 306 | 是 | 189.7851 |

> 官方 schema 将板块标识注明为需要通过代码表计算，但原始数据中的三个相关 flag 全为 false。本阶段不改写官方原始文件，而是以 mktcode 与六位 tgtcode 的受控区间生成集合谓词；reference SQL 独立书写相同集合定义并比较完整结果行集。境外市场和缺失市场仍返回 DATA_UNAVAILABLE，不生成空结果占位 SQL。
