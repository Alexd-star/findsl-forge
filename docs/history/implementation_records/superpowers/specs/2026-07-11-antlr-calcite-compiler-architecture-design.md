# FinDSL Forge ANTLR/Calcite 风格编译器架构设计

## 1. 设计目标

本设计将当前的双编译链逐步收敛为一套可审计、可扩展、可在 Apache Doris 真实执行的编译系统。目标不是简单地把现有 Python 代码换成 ANTLR，而是建立与成熟数据库编译器一致的分层：标准语法前端、强类型 AST、逻辑关系 IR、等价重写、代价感知物理规划和 Doris SQL 后端。

赛题硬指标作为架构验收条件：官方 12 类函数及 `then/CONS/EXIST/|&^` 必须有明确语义；符合数据域的测试集 SQL 结果正确率不低于 95%；19 年长周期优化路径较基线提速不低于 10 倍；编译 P95 低于 50 ms；已支持的 SQL 执行不超过 10 s；同类指标和函数通过声明式注册表接入，核心编译代码不改动。

## 2. 当前事实基线

- 通用编译器使用 `parser.py -> semantic.py -> sqlgen.py`，官方 5799 条槽位 DSL 主要使用独立的 `official_slot.py`。
- 官方语料当前语法可容错解析 5799/5799，编译不抛异常 1882/5799，其中 742 条有 warning。
- 已确认的风险包括：额外函数参数被忽略、数值与字符串类型不匹配仍生成 SQL、交叉函数在 `WHERE` 中直接使用窗口函数、未识别日期降级为 `1=1`、缺失数据域降级为 `1=0`、范围集合运算未实现、前复权配置未参与 SQL 生成。
- 真实 Doris 官方数据六类查询均低于 10 s，但官方基线/前缀表提速只有 1.173x，当前表是单分区且 EXPLAIN 显示缺少列统计信息。

## 3. 目标编译流水线

```text
Official DSL
  -> ANTLR4 lexer/parser
  -> parse tree + recovery diagnostics
  -> typed AST
  -> semantic and data-domain analyzer
  -> logical relational IR
  -> semantics-preserving rule optimizer
  -> cost-aware physical planner
  -> Doris SQL AST
  -> SQLGlot Doris validation + project semantic lints
  -> Apache Doris EXPLAIN/Profile/execution
```

ANTLR 仅负责语法识别和错误位置，不承担金融语义。Typed AST 保留 DSL 原始含义；Logical IR 使用 `Scan/Filter/Project/Aggregate/Window/Rank/Stage/LimitContract` 等节点表达与数据库物理表无关的逻辑。Physical Planner 再在普通扫描、分区裁剪、前缀表、技术特征表、快照表和物化视图之间选择路径。

## 4. 模块边界

```text
src/findsl/official/
  diagnostics.py       诊断级别、错误码和容错修复记录
  policy.py            strict/recovery 编译策略
  signatures.py        12 类函数精确签名和槽位角色
  semantics.py         类型、运算符、数据域和业务规则检查
  ir.py                强类型逻辑/物理 IR
  registry.py          指标、函数、数据表、单位和空值协议
  optimizer.py         等价重写与物理候选路径
  cost_model.py        基于缓存统计信息的轻量代价模型
  doris_backend.py     Doris SQL AST 构造与方言约束
```

现有 `official_slot.py` 在迁移期间作为兼容门面，不再继续承载新的核心语义。每迁移一类函数，新旧链路都要生成结果，并在可执行样例上比较行集或结果哈希。

## 5. 严格与容错模式

- `strict`：不自动修改输入；参数数量、参数类型、枚举值、时间、数据域和 SQL 结构任一不确定时失败。赛题正确率和上传准入只认 strict 结果。
- `recovery`：允许修复官方语料中已知的引号、前置连接词和多余括号，但必须返回 `normalized_source` 和逐项 `repairs`；不得将修复后的结果计入 strict 正确率。
- 数据域缺失不再生成伪 SQL。可在审计报告中生成“不可执行的结构化诊断”，但不把 `1=0` 或 `1=1` 视为成功。

## 6. 语义准则

- `cross_above/cross_down/golden_cross`：先在特征层计算当前值与 `LAG`，再由外层过滤，窗口函数不得出现在同级 `WHERE`。
- `CONS`：使用交易日序号和 gaps-and-islands 算法计算最长连续段，不用“区间内真值总数”代替连续性。
- `EXIST`：按规定的日/周/月/季度/年 bucket 计数，区分事件次数和满足条件的 bucket 数。
- `~=`：数值采用 `abs(a-b) <= abs_tol + rel_tol*max(abs(a),abs(b))`，容差由指标注册表配置；字符串和未定义相似度的业务对象必须显式拒绝或路由到专用特征。
- `period/date`：以官方基础行情表的 distinct `bizdate` 建立交易日维表；N 日默认指 N 个交易日，自然日必须显式标注。
- 价格复权、缩放因子、哨兵值、字段回退和可用日期范围必须位于注册表，不散落在 SQL 生成代码中。

## 7. 物理规划与 Doris 边界

编译器不重新实现 Doris Nereids CBO。它只处理金融 DSL 特有的候选路径：普通扫描、分区扫描、前缀表、技术特征表、最新快照表和可用物化视图。代价模型使用离线缓存的行数、分区数、NDV、NULL 数、预估选择率、特征新鲜度和历史 Profile 系数，不在正常编译路径上实时调用 `EXPLAIN`，以保证 P95 < 50 ms。

Doris 物理表按 `bizdate` 自动月分区，基础/扩展/前缀/特征表使用可兼容的分桶键；全量导入或特征刷新后执行 `ANALYZE`。竞赛证据同时保存 EXPLAIN 与 Query Profile，记录分区裁剪、扫描行数、窗口/排序节点、内存峰值和操作符耗时。

## 8. 正确性证据

测试体系分为五层：

1. 语法和语义单元测试，覆盖精确错误码、位置和修复建议。
2. Hypothesis 生成满足文法的 DSL，验证解析-序列化往返、类型不变式和不崩溃。
3. 独立 Polars 解释器与 Doris SQL 行集差分，解释器不复用 SQL 生成器的表达式模板。
4. 变形测试：`A and B` 结果必为 A 子集，`A or B` 必包含 A，前缀/基线计划结果哈希相同，等价日期表达结果相同。
5. mutation testing 验证测试能捕获比较符、窗口边界、排名方向、NULL 规则和布尔运算符的错误变异。

95% 正确率只在“数据域完整、strict 编译成功、Doris 真实执行、独立参考结果可比较”的 eligible 测试集上统计，不用编译成功率代替。

## 9. 迁移阶段

1. 建立 strict/recovery 基线、函数签名和数据质量审计。
2. 修复已确认的语义错误：类型、交叉、范围、交易日、近似、CONS、哨兵值和复权。
3. 引入 ANTLR4 生成前端与 Typed AST，与旧 parser 差分测试。
4. 引入 Logical IR 和声明式注册表，迁移 12 类官方函数。
5. 引入物理候选和缓存代价模型，将官方 basic/ext 前缀表接入编译器。
6. 完成 Doris 分区、统计信息、快照特征和 19 年性能矩阵。
7. 刷新 Web Demo、文档、图表、截图、metadata、校验和和 Git 交付证据。

## 10. 权威实现依据

- Apache Doris Auto Partitioning：<https://github.com/apache/doris-website/blob/master/docs/table-design/data-partitioning/auto-partitioning.md>
- Apache Doris Statistics/CBO：<https://github.com/apache/doris-website/blob/master/docs/query-acceleration/optimization-technology-principle/statistics.md>
- Apache Doris Window Function Processing Order：<https://github.com/apache/doris-website/blob/master/docs/query-data/window-function.md>
- Apache Doris Materialized View：<https://github.com/apache/doris-website/blob/master/docs/query-acceleration/materialized-view/overview.md>
- Apache Doris Query Profile：<https://github.com/apache/doris-website/blob/master/docs/query-acceleration/query-profile.md>
- Apache Calcite Volcano Planner：<https://github.com/apache/calcite/tree/main/core/src/main/java/org/apache/calcite/plan/volcano>
- SQLGlot Doris Dialect：<https://github.com/tobymao/sqlglot/blob/main/sqlglot/dialects/doris.py>
- ANTLR grammars-v4：<https://github.com/antlr/grammars-v4>
- Hypothesis：<https://github.com/HypothesisWorks/hypothesis>
- SQLancer：<https://github.com/sqlancer/sqlancer>

## 11. 非目标

- 不在 Python 项目中复制完整 Apache Calcite 或 Doris Nereids 优化器。
- 不为官方未提供的财务、基金持仓、用户账户、概念成分和龙虎榜数据伪造 SQL。
- 不为追求文档中的“100%”而把 warning、容错修复或空结果计为语义成功。

