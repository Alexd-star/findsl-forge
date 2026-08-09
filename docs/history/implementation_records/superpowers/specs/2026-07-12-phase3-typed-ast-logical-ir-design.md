# Phase 3：Typed AST 独立化与 Calcite 风格 Logical IR 设计

## 1. 阶段目标

Phase 3 在 ANTLR/手写双前端已经证明 AST 等价的基础上，建立稳定的编译器中间边界。该阶段完成三件事：把官方 AST 类型从 `official_slot.py` 中独立出来；把语义分析结果表示成不可变、可审计的 Typed AST；把语义明确的官方查询降低为与 Doris 物理表无关的 Logical IR。

本阶段不替换现有 SQL 生成器，也不宣称已经完成 Calcite、CBO 或 Doris 物理优化。新 IR 先以影子模式运行，旧编译路径继续产生用户可见 SQL。只有 AST 兼容、类型一致和 IR 不变量门禁全部通过，后续阶段才能在 IR 上实现等价重写和 Doris 后端。

## 2. 核心分层

```text
Official DSL
  -> Handwritten/ANTLR frontend
  -> Syntax AST
  -> Binder + Type Analyzer
  -> Typed AST
  -> Logical Lowering
  -> Validated Logical IR
  -> future rule optimizer / physical planner / Doris backend
```

Syntax AST 忠实保存用户写下的结构，不包含数据库表、SQL 片段或优化决定。Typed AST 在不改变语法树形状的前提下，为每个节点绑定确定的类型、函数签名和槽位角色。Logical IR 使用关系运算表达查询意图，不保存原始 parser 对象，也不拼接 SQL。

## 3. AST 独立化

新建 `src/findsl/official/ast.py`，承载 `OfficialNode`、`OfficialLiteral`、`OfficialIdentifier`、`OfficialFunctionCall`、`OfficialBinaryOp`、`OfficialComparison`、`OfficialLimit` 和 `OfficialRangeLiteral`。所有节点继续使用 frozen dataclass，并维持现有构造参数、字段名称、`to_dict()` 结果和相等性。

`official_slot.py` 从新模块导入并重新导出原类名。因此现有调用方执行 `from findsl.official_slot import OfficialLiteral` 时不会中断，历史 pickle 不作为兼容目标。ANTLR 适配器、语义分析器和新 IR 代码应直接依赖 `official.ast`，逐步消除对四千行兼容门面的反向导入。

AST 基类提供显式 visitor 协议和无递归副作用的深度遍历辅助函数。源码位置继续保存在 Phase 2 的旁路 `SourceMap` 中，不加入 dataclass 比较字段，避免改变 AST JSON 和差分证据。

## 4. 类型系统

新建 `src/findsl/official/types.py`。类型不再使用散落字符串，定义不可变 `OfficialType` 及以下单例：

- `BOOLEAN`：筛选谓词和事件条件；
- `NUMERIC`：价格、数量、比率、排名和算术结果；
- `STRING`：名称、枚举和文本结果；
- `TIME`：可比较的时刻值；
- `UNKNOWN`：数据域或指标类型尚无法解析；
- `RangeType(element_type)`：显式范围，要求上下界兼容。

类型系统只表达语义类别，不混入 Doris `DECIMAL` 精度或物理列类型。`UNKNOWN` 允许语义分析继续收集信息，但 strict lowering 不允许依赖未知类型生成可执行 IR。类型兼容规则集中定义：算术只接受 numeric；有序比较接受同类 numeric/time；逻辑运算只接受 boolean；范围上下界必须兼容；近似比较仅接受项目明确支持的 numeric/string。

## 5. Typed AST

新建 `src/findsl/official/typed_ast.py`。Typed AST 不复制一套语法节点类，而使用 `TypedNode` 包装语法节点：

- `node`：原始不可变 Syntax AST 节点；
- `type`：`OfficialType`；
- `children`：与语法节点子项一一对应的 TypedNode；
- `binding`：函数节点的 `FunctionBinding`，非函数节点为空；
- `span`：可选源码位置，不参与语义相等性；
- `annotations`：只允许定义好的不可变元数据项，不接受任意可变字典。

`FunctionBinding` 保存规范函数名、精确签名和按槽位名称组织的字面量。它不解析日期、市场或 count expression 的业务含义；这些属于后续领域绑定。Typed AST 序列化必须稳定，不包含对象地址。

现有 `OfficialSemanticAnalyzer.validate()` 继续返回兼容字符串，新增 `analyze()` 返回 TypedNode。`validate()` 由 `analyze().type.legacy_name` 实现，确保只有一套类型推断逻辑。

## 6. Logical Expression IR

新建 `src/findsl/official/ir/expressions.py`，定义与关系节点解耦的不可变表达式：

- `LiteralExpr(value, type)`；
- `FieldRef(name, type, qualifier=None)`；
- `CallExpr(name, args, type, binding=None)`；
- `BinaryExpr(op, left, right, type)`；
- `ComparisonExpr(op, left, right)`；
- `RangeExpr(lower, upper, lower_inclusive, upper_inclusive, element_type)`。

表达式 IR 不携带 SQL 文本。函数调用保留官方函数名和槽位绑定，以便后续领域 lowering 将 `indicator`、`rank`、事件函数和周期函数转换为更专门的逻辑节点。

## 7. Relational Logical IR

新建 `src/findsl/official/ir/relational.py`，定义：

- `LogicalScan(entity, schema)`：逻辑证券-交易日数据源，不绑定具体 Doris 表；
- `LogicalFilter(input, predicate)`：布尔过滤；
- `LogicalProject(input, expressions, schema)`：投影；
- `LogicalAggregate(input, group_keys, measures, schema)`：聚合；
- `LogicalWindow(input, expressions, schema)`：窗口特征；
- `LogicalRank(input, order_by, direction, bound, schema)`：排名约束；
- `LogicalStage(input, stage_index, operation, schema)`：`then` 的有序阶段；
- `LogicalLimit(input, offset, count, schema)`：输出数量合同。

`Schema` 由有序 `Field` 元组构成，字段具有名称、类型和 nullability。关系节点必须显式保存输出 schema。逻辑实体默认命名为 `market_observation`，不出现 `newzl.hsj_stock_hq_basic` 等物理表名。

## 8. Lowering 范围

新建 `src/findsl/official/lowering.py`。Phase 3 只对能够明确表示的结构完成 lowering：普通 boolean filter、算术和比较、`between`、顶层 `limit`、单阶段和链式 `then`、标准 `rank` 比较，以及官方函数的通用 `CallExpr` 绑定。

Lowering 不试图在本阶段把 12 类函数全部翻译为物理关系算子。对 `indicator` 等标量函数先生成有绑定的 `CallExpr`；对 rank/then/limit 建立专门关系节点。需要窗口事件、连续区间、bucket count 或数据域解析但尚未领域 lowering 的结构，返回稳定的 `UNSUPPORTED_LOGICAL_LOWERING` 诊断，不生成半真半假的计划。

输入顶层必须是 boolean 查询或带 limit 的 boolean 查询。裸 numeric/string 表达式不能成为 `LogicalFilter`。lowering 默认创建逻辑扫描，并保留必需函数集合、未知类型和未降低能力清单供审计。

## 9. IR 验证器

新建 `src/findsl/official/ir/validate.py`。验证器在构造后和序列化前检查：

1. Filter predicate 必须为 boolean；
2. Limit offset/count 必须为非负整数，count 大于零；
3. Rank direction 只能是 asc/desc，bound 必须为正 numeric literal 或合法百分比；
4. Stage index 单调递增；
5. 每个 FieldRef 必须能在输入 schema 中解析，函数槽位字面量除外；
6. 输出 schema 字段名唯一；
7. Range 上下界类型兼容；
8. 节点树无循环，共享子树允许但必须是不可变对象；
9. strict 计划不得包含 UNKNOWN 类型；
10. Logical IR 中不得出现 SQL 关键片段或物理表限定名。

验证失败返回结构化 `OfficialIrError(code, message, path)`，path 使用稳定节点路径，不依赖 Python 对象地址。

## 10. 影子审计

新增 `official-ir-evidence` 命令。它读取官方工作簿，在 strict 解析和语义分析成功的集合上运行 lowering，统计：

- typed 成功/失败及错误码；
- logical lowering 成功/失败及能力分类；
- IR validator 通过数；
- 节点类型分布和函数绑定覆盖；
- 单问句 lowering P50/P95；
- 输入 SHA-256、Git HEAD 和工具版本。

Phase 3 不以 lowering 覆盖率替代 SQL 正确率。门禁要求：AST JSON 与 Phase 2 完全兼容；当前 strict/recovery 解析数不下降；既有 strict compile 数不下降；所有声明为 lowering 成功的计划必须通过 validator；重复运行的规范 JSON 哈希一致。

## 11. 序列化和可观测性

AST、Typed AST、表达式 IR、关系 IR 和诊断均提供显式 `to_dict()`。规范 JSON 使用 UTF-8、排序键和固定分隔符；集合在序列化前排序，禁止输出 `repr()`、对象地址或非确定顺序。IR 节点提供 `node_id`，由节点规范内容哈希截取生成，不使用随机 UUID。

CLI 增加单问句 `official-slot-ir`，支持 JSON 输出 Typed AST、Logical IR、验证结果和 lowering 耗时。默认不改变 `official-slot-compile` 的 SQL 输出。

## 12. 测试策略

1. AST 迁移测试验证旧新导入是同一类对象、构造器和 JSON 完全一致。
2. 类型测试覆盖 literal、算术、逻辑、比较、range、unknown 和全部 12 类函数签名。
3. Typed AST 测试核对 children 顺序、binding 槽位和稳定序列化。
4. IR 单元测试逐节点检查不可变性、schema 和 validator 错误路径。
5. Lowering 金样测试覆盖 filter、between、limit、rank 和多 stage。
6. 负例测试确认未知类型、裸表达式、非法 rank 和 unsupported 结构不会形成可执行计划。
7. 变形测试检查 `A and B` 仍为单个 boolean predicate，limit 不改变内部查询语义，重复 lowering 哈希一致。
8. 官方全量证据确认 Phase 2 解析指标和既有 strict compile 指标不回归。
9. 完整 pytest、ANTLR 生成物检查、`git diff --check` 和跨平台 CI 必须通过。

## 13. 实施顺序

1. 独立 AST 模块并建立兼容导出门禁。
2. 建立 OfficialType 与集中兼容规则。
3. 将语义分析改为生成 Typed AST，保留 validate 兼容接口。
4. 建立 expression/relational IR 和规范序列化。
5. 建立 IR validator。
6. 实现基础表达式 lowering。
7. 实现 filter/limit/rank/stage lowering。
8. 增加 CLI、官方影子证据和性能统计。
9. 刷新中文文档、README、测试和 Git 证据。

## 14. 本阶段非目标

- 不删除现有 SQL 编译路径，不切换默认输出。
- 不实现规则优化器、Volcano 搜索或代价模型。
- 不选择 Doris 基础表、前缀表、特征表或物化视图。
- 不用字符串拼接代替 IR 表达式。
- 不把 UNKNOWN 或 unsupported 结构包装成成功计划。
- 不把 Typed/IR 覆盖率宣传为金融语义正确率、SQL 正确率或比赛满分。
