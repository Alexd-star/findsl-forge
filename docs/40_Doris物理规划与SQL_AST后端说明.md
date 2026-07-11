# Doris 物理规划与 SQL AST 后端说明

## 1. 建设目的

Phase 5 在既有 ANTLR 前端、Typed AST、Logical IR 和领域绑定层之后增加受控 Doris 物理后端。它解决的不是“把旧 SQL 换一种方式打印”，而是建立明确的编译边界：逻辑计划只有在物理目录中找到真实资源、字段和类型后，才能形成 Physical IR；Physical IR 通过验证后，只能由 SQLGlot AST 生成 Doris SQL。任何缺失数据域、派生公式、未配置容差或暂未支持的跨资源计划都返回结构化错误，不允许拼出看似完整但无法证明语义的 SQL。

当前后端仍以影子模式运行，不替换比赛期间已经充分验证的旧编译链。这样可以比较两条路径的结构和结果，同时保留稳定回滚入口。

## 2. 分层结构

物理目录位于 `configs/official/physical_catalog.json`，JSON Schema 位于同目录。目录只保存数据库、表、列、逻辑类型、资源能力和优先级，不保存可执行 SQL 片段。当前受控资源包括行情基础表、行情扩展表、证券信息表和技术特征表，共映射 125 个直接字段。

`src/findsl/official/physical/planner.py` 负责候选选择。首版规划器只接受单资源、直接指标、标量运算、比较、布尔条件、范围条件和 limit。代价使用物理目录优先级；由于目录尚未接入 Doris 统计信息，决策记录会明确写出 `estimated=True`，不会虚构行数或选择率。

`src/findsl/official/backend/doris.py` 将 Physical IR 转成 SQLGlot 表达式。表名、列名和字面量分别使用 SQLGlot 的标识符与 literal 节点，不接收旧后端 SQL 字符串。生成结果必须经过 Doris 方言 parse-render-parse、单条 SELECT 检查、物理资源白名单和既有安全 lint。

`diff.py` 提供别名无关的结构签名以及有序、无序结果哈希；`executor.py` 通过 Doris MySQL 兼容端口执行单条 SELECT，密码只进入子进程环境变量，不进入 argv 或错误日志。

## 3. 官方数据结果

在官方 `选股提槽实例.xlsx` 的 5,799 条问句上，本阶段静态审计结果如下：

| 阶段 | 通过数量 | 含义 |
|---|---:|---|
| Typed AST | 5,695 | 严格 ANTLR 输入完成类型分析 |
| Logical IR | 1,322 | 完成数据域绑定和逻辑 lowering |
| Physical IR | 34 | 能由当前受控物理目录和首版单资源规划器准确落地 |
| SQLGlot round-trip | 34 | 生成 SQL 可由 Doris 方言稳定解析和重绘 |
| 安全 lint | 34 | 全部生成 SQL 为单条受控 SELECT |

静态门禁为 PASS，因为所有进入 Physical IR 的计划都完整通过 SQLGlot 与安全检查。`34/5799` 不是赛题整体正确率，也不是旧编译器覆盖率，更不代表只有 34 条业务需求可处理；它表示新影子后端当前已经建立端到端、无语义降级的最小可信集合。

首轮审计曾记录 151 条，但复核发现其中多数问句含市场、日期、行业或聚合槽位，而早期规划器没有把这些约束写入 Physical IR。该口径已作废。当前实现会物理化受支持的沪深京市场集合和“今日/当前/最新”最大交易日约束，其他非空槽位统一返回结构化错误。覆盖数字因此下降，但消除了漏条件生成 SQL 的语义风险。

直接数值排名已进入受控子集。Logical IR 会保留原始排名比较符，Physical IR 使用显式 Rank 节点；SQLGlot 后端在子查询中按 `bizdate` 分区生成 `ROW_NUMBER()`，并在外层查询过滤名次，避免窗口函数进入 WHERE。百分位、聚合排名和 count_exp 尚未纳入该子集。

主要拒绝项包括 3,819 条 `DOMAIN_DATA_UNAVAILABLE`、747 条缺少受控直接物理映射、430 条领域能力暂不支持，以及 Logical Stage、事件、聚合、窗口、rank 和跨资源计划尚未进入 Phase 5 首版规划器。它们是后续扩展清单，不应通过常量、假表或旧 SQL 片段绕过。

## 4. 近似比较边界

官方 DSL 的 `~=` 不是普通等号。架构设计要求数值近似采用绝对容差与相对容差组合，并由指标配置决定；字符串近似还需要专用相似度策略。当前物理目录没有这些参数，因此规划器返回 `PHYSICAL_APPROXIMATION_POLICY_MISSING`。旧后端将 `~=` 映射为 `=` 的行为不能复制到新后端，否则会改变筛选结果且难以在答辩中解释。

后续启用该能力时，应先在目录 Schema 中增加容差策略 ID，再由受控策略注册表生成 `ABS(a-b) <= abs_tol + rel_tol * GREATEST(ABS(a), ABS(b))` 类型的 AST，并用边界值、零值和量纲测试验证。

## 5. 使用方法

从仓库根目录安装开发依赖后，可执行：

```powershell
python -m findsl.cli official-slot-physical "indicator('', '', '成交量', '今日', '', '', '') > 100" --json
python -m findsl.cli official-slot-backend "indicator('', '', '成交量', '今日', '', '', '') > 100" --json
python -m findsl.cli official-backend-evidence --workbook "D:\path\to\选股提槽实例.xlsx" --json-output reports/official_backend_evidence.json --report-output reports/official_backend_evidence.md
```

未安装 editable package 时，先设置 `$env:PYTHONPATH='src'`。单问句物理命令输出资源、计划 ID 和决策轨迹；后端命令输出 Doris SQL、round-trip 状态和安全验证结果；全量命令输出机器可读 JSON 与中文 Markdown。

## 6. 证据边界与后续工作

本阶段证明的是物理映射、SQL AST 构造、静态安全性和确定性，不证明真实 Doris 行集等价或查询耗时。真实结果需要在官方数据已导入的 Doris 集群上执行旧、新 SQL，比较无序结果哈希；性能需要保存 EXPLAIN、Query Profile、P50/P95、扫描行数和资源消耗。

下一阶段应按收益与风险顺序扩展：先加入市场和日期约束下推，再处理同实体多表 join；随后实现 rank/window 的外层过滤、聚合与事件计划；最后接入统计信息和前缀资源候选。每增加一种节点，都必须先有 Physical IR 验证、SQLGlot AST 测试、旧新结构差异和可执行数据集上的结果哈希，不能只增加 SQL 模板。
