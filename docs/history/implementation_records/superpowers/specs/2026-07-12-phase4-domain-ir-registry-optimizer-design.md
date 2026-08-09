# Phase 4：领域 IR、声明式注册表与可审计规则优化器设计

## 1. 阶段目标

Phase 4 将 Phase 3 中仍以通用 `CallExpr` 表示的官方金融函数提升为可分析的领域语义，并建立第一套可关闭、可追踪、可证明适用条件的逻辑优化规则。该阶段同时把官方指标元数据从 `official_slot.py` 的大型硬编码字典迁入声明式注册表，使新增同类指标不再要求修改 parser、semantic analyzer 或 optimizer 核心代码。

本阶段仍不生成新的 Doris SQL，不选择基础表、前缀表、技术特征表或物化视图。领域 IR 表达业务意图；规则优化器只执行关系代数和官方 DSL 层面的等价规范化。物理绑定和 SQLGlot Doris backend 属于 Phase 5。

## 2. 当前事实基线

- 官方工作簿共 5,799 条，strict 解析成功 5,792 条。
- Typed AST 成功 5,695 条，严格验证的 Logical IR 为 2,034 条。
- 既有 grounded strict SQL 编译成功 1,097 条。
- 当前 lowering 失败 3,661 条，统一使用 `UNSUPPORTED_LOGICAL_LOWERING`，无法直接说明数据域、类型、函数或槽位根因。
- `official_slot.py` 内部 `INDICATORS` 同时保存逻辑类型、物理表、列、SQL expression 和布尔条件，职责混杂。
- 根目录 `configs/indicators.json` 仅服务内部英文 DSL，不能替代官方中文指标元数据。

## 3. 目标流水线

```text
Typed AST
  -> slot/domain binder
  -> Domain Expression IR
  -> Logical Relational IR
  -> invariant validator
  -> rule batches
  -> optimized Logical IR + rewrite trace
  -> future physical binder / Doris backend
```

Binder 负责把字符串槽位转换为结构化业务对象；Optimizer 只接收已经验证的领域/关系 IR，不解析中文字符串，不访问配置文件，也不生成 SQL。

## 4. 官方指标注册表

新增 `configs/official/indicators.json` 和 `configs/official/indicators.schema.json`，由 `official/registry.py` 加载为不可变对象。每个规范指标条目包含：

- `canonical_name`：规范中文名称；
- `aliases`：同义词和历史写法；
- `value_type`：numeric/boolean/string/time；
- `domain`：quote、order_book、technical、security_master、financial、fund、concept、account 等逻辑数据域；
- `logical_field`：逻辑字段标识，不是 Doris 列名；
- `unit`：price、ratio_percent、shares、amount、count、text 等；
- `scale`：原始值到业务值的精确倍率或 `null`；
- `nullable`：空值能力；
- `availability`：official_provided、derived、missing；
- `capabilities`：ordered、approximate、aggregate、window、prefix_candidate 等集合；
- `physical_hint`：可选迁移提示，只允许逻辑资源 ID，不允许 SQL 片段。

JSON Schema 禁止未知字段并校验枚举、别名唯一性、scale 类型和 capability 组合。注册表加载时执行第二层语义校验：规范名与别名全局不冲突；`missing` 数据域不得声明 physical hint；boolean/string 不得声明数值缩放；可聚合类型必须与 aggregate capability 相容。

现有 `INDICATORS` 分批迁移。Phase 4 至少迁移所有当前 strict SQL 可落地指标和 Phase 3 IR 证据中出现的已知指标。旧 `_resolve_indicator_meta()` 改为注册表适配器，继续返回兼容 `IndicatorMeta`，以保证旧 SQL 编译基线不下降。复杂 derived expression 暂时以受控策略 ID 表示，禁止把任意 SQL 放进 JSON。

## 5. 领域表达式 IR

新增 `official/domain/expressions.py`，定义不可变节点：

- `IndicatorRef(indicator_id, value_type, unit, domain, availability)`；
- `MarketScope(markets)`；
- `DateConstraint(kind, start, end, anchor, trading_day_based)`；
- `AggregateSpec(function, expression, window)`；
- `EventSpec(kind, left, right, tolerance)`；
- `ConsecutiveSpec(predicate, count, unit)`；
- `ExistSpec(predicate, minimum, maximum, bucket)`；
- `RankSpec(expression, direction, bound, partition)`；
- `DataRequirement(domains, capabilities)`。

领域节点不保存原始 SQL、物理别名或表名。每个节点提供规范 JSON 和内容哈希。原始槽位文本可作为审计注解保存，但不参与语义比较。

## 6. 槽位与领域 Binder

新增 `official/domain/binder.py`。Binder 接收 Typed AST 函数绑定，并完成：

1. 规范化 market/filter_scope/date/select_type/agg_func/count_exp；
2. 通过注册表将指标名和别名绑定为 `IndicatorRef`；
3. 将 rank 方向、上下界和百分比转换为 `RankSpec`；
4. 将 cross/reset/close_together/golden_cross 转换为 `EventSpec`；
5. 将 count_exp 转换为 `ConsecutiveSpec`、`ExistSpec` 或结构化计数约束；
6. 输出精确 `DataRequirement`；
7. 对缺失数据域返回 `DOMAIN_DATA_UNAVAILABLE`，不生成伪谓词；
8. 对语法有效但当前能力未实现的结构返回 `DOMAIN_CAPABILITY_UNSUPPORTED`。

Binder 诊断至少区分：未知指标、缺失数据域、非法枚举、日期无法解释、count_exp 无法解释、函数槽位组合不支持、类型不兼容。诊断包含函数名、槽位名、规范化值和源码 span（可用时）。

## 7. 领域关系节点

在现有 Logical IR 上增加：

- `LogicalDomainScan(entity, requirements, schema)`；
- `LogicalEvent(input, event, schema)`；
- `LogicalConsecutive(input, spec, schema)`；
- `LogicalExist(input, spec, schema)`；
- `LogicalDomainRank(input, spec, schema)`；
- `LogicalConstraint(input, market_scope, date_constraint, schema)`。

普通 `LogicalFilter` 继续承载布尔组合。领域节点只在 binder 能完整解释槽位时生成；否则保持失败诊断，不回退到不透明 SQL 字符串。

## 8. 规则优化器

新增 `official/optimizer/`，采用确定性批处理规则，而非复制 Calcite Volcano。接口为：

```text
optimize(plan, rule_set, context) -> OptimizedPlan(plan, trace)
```

首批规则：

1. `BOOL_FLATTEN`：将同操作符嵌套布尔树展平后按原顺序重建；
2. `CONST_FOLD`：计算纯字面量算术、比较和布尔表达式；
3. `PREDICATE_DEDUP`：按规范哈希删除同一 AND/OR 链中的重复谓词；
4. `CONSTRAINT_MERGE`：合并可证明兼容的 market/date 约束，冲突约束变为显式 empty relation；
5. `FILTER_PUSH_DOWN`：在不跨越 rank/window/stage 语义边界时下推 filter；
6. `FILTER_MERGE`：相邻 filter 合并为 AND；
7. `STAGE_NORMALIZE`：修正连续 stage index，合并无语义操作的 stage；
8. `LIMIT_NORMALIZE`：合并相邻 limit 合同；
9. `RANK_CONTRACT_NORMALIZE`：规范 `< N`、`<= N` 和百分比边界，不改变并列排名协议。

规则必须声明 `rule_id`、版本、适用节点、前置条件和 proof obligation。每次命中生成 `RewriteEvent`：before hash、after hash、节点路径、耗时、理由和是否改变计划。规则未命中不产生噪声事件。

## 9. 等价与安全门禁

规则安全性分四层验证：

1. 单元金样：精确 before/after IR；
2. 变形不变量：幂等、确定性、类型/schema 不变；
3. 独立小数据解释器：优化前后结果集合一致；
4. 对已 grounded 的 strict SQL 集合，旧 SQL 路径结果与优化前后逻辑解释结果保持一致。

任何规则若缺少可执行等价证据，默认不进入 production rule set。规则可以通过配置逐项关闭；优化失败返回原验证计划和结构化诊断，不能返回部分修改对象。

## 10. Empty Relation 语义

冲突的日期或市场约束不得降级为 SQL `1=0` 字符串。新增 `LogicalEmpty(schema, reason)`，明确表达查询结果在逻辑上为空。只有能证明约束交集为空时才允许生成；数据域缺失、未知指标或日期解析失败不能转换为 Empty。

## 11. 官方差距审计

新增 `official-domain-evidence`，重新分析 5,799 条官方问句并输出：

- 注册表命中率、别名命中率和未知指标分布；
- 领域绑定成功数；
- 缺失数据域数量与域分类；
- unsupported capability 分类；
- date/count_exp/enum/type 诊断分类；
- 各领域节点数量；
- 优化规则命中次数、计划缩减量、P50/P95；
- 优化前后 validator 通过数；
- 幂等和确定性差异；
- 既有 strict parse、strict compile 和 Phase 3 lowering 基线。

Phase 4 门禁要求：strict parse 不低于 5,792；strict compile 不低于 1,097；Phase 3 validated IR 不低于 2,034；所有优化后计划重新验证；规则幂等差异为 0；注册表适配器与旧 resolver 在已迁移指标上的逻辑类型和可用性一致。

## 12. 性能预算

- 注册表加载一次并缓存，正常请求不读取磁盘；
- 单问句 domain bind + rule optimize P95 小于 5 ms；
- 完整 parse + type + bind + optimize 继续以 50 ms 为预算；
- 规则顺序固定，不进行无界搜索；
- trace 使用有界事件数，防止异常计划产生日志爆炸。

## 13. 迁移和回滚

Phase 4 默认作为 shadow pipeline，不改变 `official-slot-compile`。注册表适配器替换旧 resolver 前，必须运行逐指标 parity 测试；复杂 SQL expression 未迁移完成时保留受控 legacy adapter。规则优化器默认只在新 IR 命令启用，可通过空 rule set 完全关闭。

每个迁移批次独立提交：注册表模型、基础指标、技术指标、领域 binder、各规则批次、官方证据。出现回归时可以回退单一批次，不需要撤销整个 ANTLR/Typed AST/IR 架构。

## 14. 测试策略

1. JSON Schema 正负例和注册表语义校验；
2. 旧 resolver 与注册表逐指标 parity；
3. 别名冲突、未知指标和 missing domain 测试；
4. 12 类函数 binder 金样与槽位负例；
5. 领域节点规范 JSON、哈希和 validator；
6. 每条优化规则 RED/GREEN 金样；
7. optimizer 幂等、确定性、规则关闭和 trace 测试；
8. 小数据解释器等价测试；
9. 官方 5,799 条差距审计；
10. 完整 pytest、ANTLR 生成物、Git diff 和 CI。

## 15. 非目标

- 不把物理 Doris 表名或 SQL expression 批量搬入领域注册表。
- 不实现 Volcano/Cascades 搜索和代价模型。
- 不在本阶段生成或替换 Doris SQL。
- 不把缺失数据域转换成 Empty 或成功计划。
- 不对 rank/window/stage 执行未经证明的下推。
- 不用规则命中数、注册表命中率或领域 IR 覆盖率替代结果正确率。
