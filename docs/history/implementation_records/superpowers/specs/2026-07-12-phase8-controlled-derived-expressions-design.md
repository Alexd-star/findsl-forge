# Phase 8 受控派生指标物理表达式设计

## 1. 背景与目标

Phase 7 迁移漏斗显示，旧严格后端成功但新后端失败的 1,064 条问句中，`PHYSICAL_PLAN_UNAVAILABLE` 占 305 条。主要指标包括最新价、涨幅、涨跌幅、涨停、总市值、开盘价、收盘价、市盈率、换手率、最高价、量比、跌幅和跌停。这些指标在官方三表中具备原始列，但旧后端使用内嵌 SQL expression 或 true/false condition 表达，未进入独立物理目录。

本阶段建立受控、强类型、SQL 无关的派生表达式注册表，使这些指标进入 Physical IR 和 SQLGlot 后端，同时保持“缺失数据域不可伪造 SQL”的边界。

## 2. 权威约束

- SQLGlot 官方 API 将每个 SQL AST 节点建模为 `Expr` 子类，并支持程序化构造表达式树；本项目继续只使用类型化节点，不使用 Raw/Command 或任意 SQL 文本。
- Apache Doris 官方文档规定除零返回 NULL，`NULLIF(a, 0)` 等价于条件表达式。本项目仍显式使用 safe-divide 节点，避免依赖隐式行为并使语义可审计。
- 物理表达式注册表只负责 FinDSL 指标到物理表达式的映射，不替代 Doris Nereids 的通用查询优化。

## 3. 配置协议

新增 `configs/official/physical_expressions.json` 与 JSON Schema。每个策略包含：

- `indicator_id`；
- `resource_id`；
- `value_type`；
- `nullable`；
- `expression`：受限表达式树。

允许的节点仅包括：

- `column(name, type)`；
- `literal(value, type)`；
- `add/subtract/multiply/divide/safe_divide`；
- `negate`；
- `equal/not_equal/greater/...`；
- `and/or`；
- `coalesce`。

所有节点加载时进行递归类型检查。列名必须满足物理标识符规则；算术节点只能接受 numeric；逻辑节点只能接受 boolean；比较节点要求类型兼容；根类型必须等于策略 `value_type`。配置中不允许出现 SQL、模板、函数名、数据库名或表名。

## 4. Physical IR

新增：

- `PhysicalUnary`：受控 `negate`；
- `PhysicalNullIf`：safe-divide 分母保护；
- `PhysicalCoalesce`：明确空值回退。

其余算术、比较和布尔组合复用现有 `PhysicalBinary`、`PhysicalComparison`、`PhysicalLiteral` 与 `PhysicalColumn`。每个节点继续支持规范 JSON 和内容哈希。

## 5. 规划器接入

规划器解析指标时按以下顺序：

1. 直接物理字段目录；
2. 受控派生表达式注册表；
3. 无映射则返回 `PHYSICAL_PLAN_UNAVAILABLE`。

派生表达式声明的所有列进入 `PhysicalScan.columns`，资源参与现有统计成本计算。一个表达式不得跨多个资源；问句中多个指标仍遵循当前单主资源边界。前缀策略继续通过独立策略注册表工作，不与派生表达式混合。

## 6. 首批指标

首批覆盖高频且公式可由官方三表原始列严格确定的指标：

- 缩放列：最新价、开盘价、收盘价、最高价、最低价、市盈率、动态市盈率、市净率、换手率、量比；
- 安全比例：涨幅、涨跌幅、跌幅；
- 算术组合：总市值、主力净流出；
- 常量：每手股数；
- 布尔条件：涨停、跌停、首板涨停、上涨趋势。

公式必须与旧后端现有业务口径逐项比对，并通过真实 Doris 行集哈希门禁后才能标记 verified。

## 7. 失败与安全边界

- 未知操作符、错误类型、非法列名、重复指标、未知资源在加载时失败。
- 派生配置不能引用 SQL 字符串。
- safe-divide 必须生成显式 `NULLIF(denominator, 0)`。
- nullable 信息不用于擅自补零；只有配置中的显式 coalesce 才改变 NULL 语义。
- 不为缺失财务、基金、账户等数据域增加策略。

## 8. 验收

1. 配置与表达式类型负例全部有测试。
2. 每类新 Physical IR 节点通过 validator 与 SQLGlot round-trip。
3. 首批指标生成 SQL 不含旧字符串片段。
4. 新后端覆盖率高于 Phase 7 的 33 条，且所有新增成功均来自旧严格成功集或明确的新真值案例。
5. 对新增可执行问句采集新旧 Doris 结果 hash；不一致时策略保持不可用。
6. 全量 pytest、ANTLR 检查、静态后端审计和 Git 审计通过。
