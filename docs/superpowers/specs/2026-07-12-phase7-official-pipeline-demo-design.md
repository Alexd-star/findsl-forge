# Phase 7 官方编译管线与 Demo 接入设计

## 1. 目标

把已经完成的 ANTLR4、Typed AST、Logical/Domain IR、Physical IR、代价决策和 SQLGlot Doris 后端组合成一个稳定、可复用、可审计的正式编译服务，并让 Web Demo 能直接调用该服务。任何无法物理落地的官方 DSL 都必须返回准确的阶段、错误码和解释，不允许静默回退到旧编译器后伪装为新架构结果。

## 2. 方案选择

本阶段采用“并行正式入口”方案：保留现有 `/api/analyze` 及旧演示样例，新增 `/api/official/analyze` 和真实官方提槽样例。这样既不破坏已有功能，又能让评委直接验证新架构。待新物理后端覆盖率达到迁移门槛后，再把官方入口提升为默认入口。

未采用立即替换方案，因为新物理后端当前只覆盖 33 条官方问句，直接替换会造成明显功能回退。未采用自动回退方案，因为自动回退会掩盖新后端缺口，破坏证据可审计性。

## 3. 组件边界

### 3.1 `findsl.official.pipeline`

提供单一入口 `compile_official(source, options)`。该模块只负责编排，不复制解析、语义、lowering、规划或 SQL 生成逻辑。

成功结果必须包含：

- 输入 DSL 与总耗时；
- frontend、AST、Typed AST；
- Logical/Domain IR；
- 优化前后节点标识；
- Physical IR；
- 物理资源、策略和所有候选决策；
- SQLGlot 生成的 Doris SQL；
- SQLGlot round-trip 和安全校验状态。

失败结果通过 `OfficialPipelineError` 暴露：

- `stage`：失败所在阶段；
- `code`：稳定错误码；
- `message`：面向开发者的准确原因；
- `diagnostics`：解析诊断或物理候选证据；
- `partial`：失败前已经成功生成的中间表示。

### 3.2 Demo API

新增 `analyze_official_dsl`，调用统一管线并返回 JSON 可序列化结构。HTTP 接口 `/api/official/analyze` 不执行旧编译器回退。输入为空返回 400；语法、类型、数据域和物理计划错误均返回结构化 400；成功返回 200。

### 3.3 官方演示样例

新增版本化 JSONL 文件，样例直接来自官方提槽语法，至少覆盖：基础表过滤、证券信息 Join、衍生表 Join、排名、市场/日期约束、技术指标，以及一个明确不可落地的数据域案例。样例必须标注预期状态和错误码。

### 3.4 迁移覆盖漏斗

新增机器可读审计工具，对官方 5,799 条数据逐行记录：严格解析、类型、Logical/Domain、Physical、SQLGlot、安全校验和失败码。报告额外计算旧严格后端成功集到新后端成功集的迁移覆盖率，并按错误码、函数族和数据资源聚合，以此决定下一阶段开发顺序。

## 4. 数据流

```text
official DSL
  -> ANTLR strict frontend
  -> semantic analyzer / Typed AST
  -> logical + domain lowering
  -> deterministic optimizer
  -> statistics-aware physical planner
  -> SQLGlot Doris AST renderer
  -> Doris parse/render/parse + safety lint
  -> structured success payload
```

任一阶段失败时立即停止，返回该阶段已经掌握的事实。缺失数据域、缺失物理映射和不支持的复合语义不能生成 SQL。

## 5. 兼容与回退政策

- `/api/analyze`：保留旧内部 DSL 行为。
- `/api/official/analyze`：只运行新官方管线。
- 不允许请求参数开启静默旧后端回退。
- 后续如需迁移对比，必须以 `legacy_sql` 和 `shadow_sql` 两个显式字段并列展示。

## 6. 测试与验收

1. 单元测试证明基础问句经过全部阶段并生成可解析、安全的 Doris SQL。
2. 单元测试证明缺失数据域、语法错误、物理映射缺失能保留阶段和错误码。
3. API 测试证明新接口不会调用旧 `Compiler`。
4. 样例测试证明每个官方演示样例符合声明的预期。
5. 漏斗报告在同一输入和 Git HEAD 下确定性一致。
6. 完整 pytest、ANTLR 生成物检查、`git diff --check` 和官方静态审计通过。

## 7. 本阶段不做的内容

- 不在本阶段实现所有 Window/Aggregate/CONS/EXIST 物理算子；漏斗报告将为后续实现排序。
- 不启用 Phase 6C 策略；动态窗口集合式计划需要独立真实 Doris 性能门禁。
- 不删除旧编译器或旧 Demo，以免破坏已有验收能力。
