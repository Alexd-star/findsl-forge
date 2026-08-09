# Phase 5：Doris 物理规划、SQL AST 后端与真实行集差分设计

## 1. 阶段目标

Phase 5 为已经验证的 Domain/Logical IR 建立第一条不依赖旧字符串模板的新 Doris 后端。新链路采用独立物理目录、有限候选规划器、Physical IR 和 SQLGlot Doris AST，先在 grounded strict 子集上影子运行，并通过旧后端结构差分、SQL 安全检查和真实 Doris 行集差分证明正确性。

本阶段不立即替换 `official-slot-compile`。旧后端继续作为当前用户可见路径和迁移对照；新后端只对能够完成数据域绑定、物理映射和 SQL 验证的计划返回成功。无数据、无物理字段或尚未实现的窗口语义返回结构化失败，不生成 `1=0`、`1=1` 或空表占位 SQL。

## 2. 当前事实基线

- official strict 解析成功 5,792，grounded strict SQL 编译成功 1,097。
- Phase 4 领域 lowering 成功 1,322，全部通过优化后验证。
- 官方注册表包含 1,177 个指标，其中 101 个直供、96 个可推导、980 个数据域缺失。
- 旧官方 SQL 后端主要位于 `official_slot.py`，混合物理映射、SQL expression、日期、窗口和查询拼接。
- 项目已有真实 Doris 三表、技术特征表、前缀表、EXPLAIN/Profile 和性能采集脚本。
- SQLGlot 当前未安装，现有 `doris_sql.py` 使用自研词法级安全检查，不是完整 SQL parser。

## 3. 目标流水线

```text
Optimized Logical/Domain IR
  -> physical capability check
  -> physical candidate enumeration
  -> project cost comparison
  -> selected Physical IR
  -> SQLGlot expression tree
  -> Doris dialect render
  -> SQLGlot round-trip parse
  -> project semantic/safety lint
  -> shadow old/new comparison
  -> Apache Doris EXPLAIN / execute / result hash
```

SQL 字符串只在 SQLGlot AST 完整构造后渲染。Backend 不允许接收预拼 SQL fragment，也不从旧编译结果截取 WHERE、JOIN 或 CTE。

## 4. 依赖与版本

`pyproject.toml` 固定 SQLGlot 小版本，生产和 CI 使用相同版本。启动测试确认该版本包含 Doris dialect，能够解析和渲染 SELECT、CTE、窗口函数、QUALIFY 替代结构、LIMIT、日期字面量和标识符转义。

SQLGlot 是 AST 构造与方言校验工具，不承担金融语义、数据域判断和物理代价选择。项目仍保留 `validate_doris_select_sql()` 的安全策略，但其表提取和语法判断逐步改为基于 SQLGlot AST；文本扫描仅保留纵深防御。

## 5. 独立物理目录

新增 `configs/official/physical_catalog.json` 与 schema，由 `official/physical/catalog.py` 加载。逻辑指标注册表与物理目录分离，避免缺失数据域被误认为可查询字段。

物理目录包含：

- resource ID 与 Doris database/table；
- logical entity 和字段映射；
- column type、scale、nullable、sentinel/null protocol；
- partition key、distribution key 和 colocate group；
- date/code/name 主键角色；
- availability range 和 freshness；
- capabilities：scan、aggregate、window、prefix、snapshot、technical；
- candidate priority；
- 可选统计缓存：row count、partition count、NDV、null count、updated_at；
- derived strategy ID，不允许任意 SQL expression。

目录加载时校验：物理标识符合法；同一 resource 字段唯一；logical field 类型与官方指标注册表兼容；missing 指标没有映射；prefix candidate 必须声明 source 与 row-number protocol；技术特征必须声明刷新依赖。

## 6. Physical IR

新增 `official/physical/ir.py`：

- `PhysicalScan(resource, columns, partition_predicate, schema)`；
- `PhysicalFilter(input, predicate, schema)`；
- `PhysicalJoin(left, right, join_type, keys, schema)`；
- `PhysicalAggregate(input, group_keys, measures, schema)`；
- `PhysicalWindow(input, expressions, partition_by, order_by, schema)`；
- `PhysicalRank(input, expression, direction, bound, schema)`；
- `PhysicalLimit(input, offset, count, schema)`；
- `PhysicalPrefixLookup(input, resource, value_column, window, schema)`；
- `PhysicalEmpty(schema, proven_reason)`。

Physical IR 可以引用物理 resource/column ID，但不保存 SQL 文本。每个节点有规范 JSON、内容哈希、输出 schema 和估算属性。

## 7. 候选规划器

候选规划器只处理 FinDSL 特有选择：

1. 基础/扩展字段直接扫描；
2. 技术特征预计算表与运行时窗口；
3. 普通窗口累计与 prefix lookup；
4. 最新快照与全历史扫描；
5. 可用物化视图候选。

不复制 Doris Nereids 对 join order、operator implementation 和 distributed execution 的优化。项目代价模型使用离线目录统计：预估扫描行数、分区数、是否需要排序/窗口、自连接次数、特征新鲜度和历史 Profile 系数。

每次选择输出 `PhysicalDecision`：候选 ID、可行性、拒绝原因、估算 cost、所需资源、新鲜度和最终选择。统计缺失时使用保守启发式并标记 `estimated`，不能伪造精确成本。

## 8. 首批后端覆盖

首批 production-shadow backend 覆盖：

- 官方 provided 指标的数值/布尔/字符串比较；
- arithmetic、AND、OR、between；
- market 和可确定 date constraint；
- LogicalFilter、LogicalConstraint、LogicalLimit；
- 无 count_exp 的普通 rank；
- 目录中有直接字段的技术特征；
- 已证明的 LogicalEmpty。

Event、CONS、EXIST、复杂 count_exp、窗口交叉和多 stage 只有在 Physical IR 与 SQL AST 能完整表达、并具有真实 Doris 差分后才进入成功集合。否则返回 `PHYSICAL_CAPABILITY_UNSUPPORTED`。

## 9. SQLGlot Doris Backend

新增 `official/backend/doris.py`。Backend 通过 SQLGlot expression API 构造：

- quoted table/column identifiers；
- SELECT projection；
- FROM/JOIN；
- WHERE；
- CTE；
- GROUP BY/HAVING；
- window expression；
- rank 外层过滤；
- deterministic ORDER/LIMIT。

所有字面量使用 SQLGlot literal，不手动加引号。`CallExpr` 未被物理绑定时禁止进入 backend。窗口函数不得出现在同级 WHERE；rank/window 先在 CTE/子查询计算，再由外层过滤。

生成结果包含 SQL、SQLGlot AST 规范结构、resources、columns、physical decision trace、backend elapsed 和 validation result。

## 10. SQL 验证

每条新 SQL 必须通过：

1. SQLGlot `read=doris` parse；
2. render 后再次 parse，AST 关键结构一致；
3. 单 SELECT/CTE，禁止 DDL/DML/command；
4. 表资源全部来自 Physical Catalog；
5. 禁止注释、多 statement 和不受控 identifier；
6. 窗口函数不在同级 WHERE；
7. projection 至少包含稳定股票键；
8. limit/rank 边界合法；
9. 项目旧安全 lint 通过。

SQLGlot parse 成功只能证明语法和方言结构，不证明金融结果正确。

## 11. 新旧后端差分

对双方都成功的 grounded strict 问句记录：

- normalized SQL AST hash；
- resource/table 集合；
- projection key；
- predicate operator tree；
- date/market constraint；
- rank/limit contract；
- warning/degraded 状态。

文本 SQL 不要求完全相同。结构差异按语义类别分类，不能把格式、别名和 CTE 名称差异当作错误，也不能忽略比较符、scale、日期、NULL 和窗口边界差异。

## 12. 真实 Doris 行集差分

新建 `official-backend-evidence`：

1. 选择新旧双方成功且物理数据完整的 eligible 集合；
2. 在同一 Doris snapshot、session variables 和 anchor date 下执行；
3. 强制稳定投影 `(mktcode,tgtcode,bizdate)`；
4. 对无序查询排序后计算 row count 与 SHA-256；
5. 对 rank/limit 保留顺序合同并比较有序结果；
6. 保存 SQL、EXPLAIN、Profile ID、耗时、结果 hash 和差异样本；
7. 超时、资源缺失和执行错误单独计数，不计为一致。

eligible 集合要求 100% 行集一致后，新后端能力才能标记 verified。95% 赛题正确率仍需独立参考解释器，不用新旧后端互相一致代替真值。

## 13. 性能证据

- parse + type + bind + optimize + physical + backend P95 < 50 ms；
- 单条 eligible SQL P95 < 10 s；
- 19 年长周期候选单独比较 baseline/window、technical 和 prefix；
- 性能矩阵逐问句记录 compile、EXPLAIN、execution、rows、partitions 和 hash；
- speedup 只在结果 hash 相同、同一 snapshot 和重复测量下报告。

## 14. 迁移门禁

Phase 5 完成要求：

- Phase 1–4 全部基线不下降；
- 所有 backend 成功 SQL 通过 SQLGlot round trip 和项目安全 lint；
- backend 成功计划全部通过 Physical IR validator；
- 新后端不接受 missing 数据域；
- eligible Doris 行集一致率 100%；
- backend 输出确定性和幂等差异为 0；
- 编译 P95 < 50 ms；
- 失败均有精确 error domain；
- 默认旧后端保持不变，shadow 可以关闭。

## 15. 测试策略

1. SQLGlot Doris dialect smoke 与版本测试；
2. Physical Catalog schema/semantic validation；
3. 每类 Physical IR 构造与 validator 负例；
4. candidate feasibility/cost/trace 金样；
5. SQL AST literal、identifier、join、window、rank 和 limit 测试；
6. SQL round-trip 和安全负例；
7. 新旧 AST 结构差分测试；
8. mock Doris executor 协议测试；
9. 真实 Doris eligible 行集/hash 差分；
10. 官方全量 coverage/performance evidence；
11. 完整 pytest、CI、ANTLR 生成和 Git 审计。

## 16. 非目标

- 不把旧 SQL 字符串包装进 SQLGlot Raw/Command 节点。
- 不为提高覆盖率映射 missing 数据域。
- 不在 Python 中复制 Doris Nereids CBO。
- 不把 SQLGlot parse success 当作结果正确。
- 不在无结果 hash 一致证据时报告 speedup。
- 不在本阶段切换默认官方编译后端。
