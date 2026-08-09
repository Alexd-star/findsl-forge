# Typed AST 与 Logical IR 实现说明

## 1. 本阶段解决的问题

Phase 2 已经证明手写前端与 ANTLR 前端在官方 5,799 条 recovery 输入上生成相同 AST，但 AST 类型仍定义在 `official_slot.py` 中，语法、语义和 SQL 代码之间存在反向依赖。Phase 3 将语法树、类型分析和逻辑计划拆成独立层，使后续优化器可以面向稳定 IR 工作，而不是继续匹配 parser 节点或修改 SQL 字符串。

这次调整没有替换现有 SQL 编译器。`official-slot-compile` 的默认行为和证据口径保持不变，新流水线通过 `official-slot-ir` 和 `official-ir-evidence` 显式调用。

## 2. 三层模型的区别

Syntax AST 位于 `src/findsl/official/ast.py`，回答“用户写了什么”。节点字段和 JSON 与旧版本一致，`official_slot.py` 重新导出同一类对象，现有调用方无需改动。

Typed AST 位于 `typed_ast.py`，回答“每个表达式是什么类型、函数参数分别属于哪个槽位”。类型系统不再使用分散字符串，而是使用 `BOOLEAN`、`NUMERIC`、`STRING`、`TIME`、`UNKNOWN` 和 `RangeType`。函数节点绑定官方精确签名，保存 `indicator_name`、`direction`、`date` 等槽位名称与值。

Logical IR 位于 `official/ir/`，回答“查询在逻辑上要执行什么关系操作”。它使用逻辑扫描、过滤、排名、阶段和限制节点，不包含 Doris 表名，不拼接 SQL，也不选择前缀表或物化视图。

## 3. 不变量和失败策略

每个成功计划都必须经过 `validate_plan()`。验证器拒绝非布尔过滤、非法 limit、错误 rank 方向或边界、UNKNOWN 类型、未绑定字段、重复 schema 字段、循环计划和物理表名。strict lowering 无法证明类型或结构时返回 `UNSUPPORTED_LOGICAL_LOWERING`，不会生成降级计划。

IR 的 `node_id` 由规范 JSON 的 SHA-256 截取得到。同一 AST 重复 lowering 应产生相同 ID，不使用 UUID、对象地址或无序集合。官方证据对前 100 个成功计划执行重复 lowering，当前哈希差异为 0。

## 4. 使用方法

生成单问句 IR：

```powershell
python -m pip install -e ".[dev]"
python -m findsl.cli official-slot-ir "indicator('', '', '涨幅', '今日', '', '', '') > 5%" --mode strict --frontend antlr --json
```

输出包含 Typed AST、Logical IR、计划 ID、依赖函数、验证状态和 lowering 耗时。该命令只构造逻辑计划，不执行 Doris SQL。

生成官方工作簿证据：

```powershell
python -m findsl.cli official-ir-evidence --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" --json-output reports/phase3_official_ir_evidence.json --report-output reports/phase3_official_ir_evidence.md
```

## 5. 当前真实结果

本轮官方证据读取 5,799 条问句。strict 解析成功 5,792 条；其中 5,695 条通过 Typed AST 分析，2,034 条能够生成并通过严格验证的 Logical IR。现有 strict SQL 编译成功数仍为 1,097，没有低于 Phase 1 基线。成功计划的 lowering P95 约为 0.1 ms 以内，100 次重复计划哈希没有差异。

2,034 不能解释成“2,034 条 SQL 已经正确执行”。逻辑层允许保存部分类型明确、但尚未选择物理数据域的函数意图，因此 IR 数量可以高于 strict SQL 数量。只有 SQL 后端完成、Doris 实际执行并与独立参考结果比较后，才可以统计结果正确率。

## 6. 当前支持范围

Phase 3 可以表示普通布尔过滤、算术和比较、`between`、顶层 `limit`、标准 rank 比较以及链式 `then`。12 类官方函数均可形成带签名和槽位的 `CallExpr`；其中 rank 和 then 已提升为专门关系节点。

连续区间、事件窗口、bucket count、交易日语义和数据域选择尚未全部提升为专门关系节点。旧 SQL 编译器仍处理这些能力。新 lowering 对 UNKNOWN 类型或无法严格表达的结构明确失败，不把物理 SQL 逻辑偷偷塞进通用 CallExpr。

## 7. 回滚和兼容

默认编译入口未切换，回滚只需停止调用 IR 命令。旧 AST 导入路径仍然有效，旧 JSON、测试和 SQL 输出不受 AST 文件迁移影响。Phase 3 分支保留完整 Git 历史，可逐提交定位 AST、类型、IR、验证器和 lowering 的变化。

## 8. 下一阶段边界

Phase 4 应在现有 Logical IR 上加入领域节点和规则优化器，优先处理 indicator 数据域绑定、日期约束下推、窗口事件、CONS/EXIST、rank stage 合并和 predicate normalization。之后再引入物理候选与 Doris backend。不得跳过等价性测试直接把 Logical IR 序列化成 SQL，也不应在 Python 中复制完整 Calcite Volcano 或 Doris Nereids CBO。
