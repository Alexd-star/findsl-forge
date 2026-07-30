# CHANGELOG

本文档记录 FinDSL Forge 的重要变更。详细提交历史以 Git 为准，提交包证据以 `submission_artifacts/evidence_snapshots/` 为准。

## 2026-07-30

### 公开范围补齐与别名语义治理

- 接入两批完整东方财富板块快照和一批可追溯人工审核别名，Doris 外部目录达到 203,181 条范围成员、40,907 条行业成员和 5,686 条交易规则，Stream Load 过滤行均为 0。
- 修复来源精确名称与规范化别名冲突：`白酒` 保持公开概念板块，`白酒行业` 单独指向白酒二级行业，不再因去除“行业”后缀而误选同一范围。
- 缺口提取改为反查官方证券目录和外部运行时目录，只统计真正未解析原子；当前 104 条范围迁移缺口对应 97 个未解析原子，不再把同一问句中已解析的范围重复列为缺失。
- 同花顺同步改为默认拒绝部分快照，只有显式指定 `--allow-partial` 才可导入，拒绝时返回非零退出码；缓存继续使用原子替换，失败页不会留下半写文件。
- 官方严格迁移由 `971/1097` 提升至 `990/1097（90.25%）`，新后端成功数由 1,000 提升至 1,021；21 条新增后端成功在真实 Doris 上三轮执行全部通过，完整结果哈希稳定，最高 P95 为 2.389 秒。

### 组合范围与中证官方成员修复

- 人工审核目录支持基于多个版本化来源的集合交集和并集；组合范围生成确定性 `CURATED` 代码，报告保存各分量快照、分量成员数、集合运算和最终成员数。
- `宁夏算力概念` 由 16 只宁夏证券与 205 只算力概念证券求交得到 1 只，`银行保险` 由 42 只银行证券与 5 只保险证券求并得到 47 只，不维护比赛答案名单。
- 六位数字范围只在官方 5,686 只证券主表中唯一命中时按证券代码解析；未知数字板块继续拒绝。
- 修复中证指数成分文件改用中英双语列名后的解析错误，并补充深交所 `302xxx` 创业板代码范围；沪深300官方快照从异常 1 行重建为严格 `300/300` 行，映射配置增加最小成员数门禁。
- 官方严格迁移进一步达到 `998/1097（90.98%）`，新后端成功数达到 1,029；新增 8 条真实 Doris 三轮执行 `8/8 PASS`，最高 P95 低于 0.79 秒。

## 2026-07-13

### 双管线编译与证据 Web 工作台

- 将原有内部 FinDSL Demo 与官方七槽 DSL 编译器分成两个明确模式；官方模式直接调用 ANTLR、Typed AST、Logical IR、Physical IR 和 SQLGlot Doris 后端，不再让评委只能从命令行或报告观察新架构。
- 增加官方成功、阶段排名、固定日期事件、精确证券时序事件、财务数据缺失和 T+0 数据缺失样例；成功结果展示 SQL 与完整中间表示，失败结果展示阶段、稳定诊断码和失败前部分管线。
- 新增 `/api/official/preview` 供预期负例的浏览器演示使用，保持 HTTP 200 加结构化失败载荷，避免控制台把受控拒绝误记为网络错误；原 `/api/official/analyze` 继续保留 HTTP 400 的程序接口语义。
- `/api/evidence` 同时提供 Doris 集群证据和版本化交付元数据，界面从真实 `evidence_metadata.json` 读取 `742/1097`、pytest、门禁、警告和 Git 版本，不在 JavaScript 中写死交付结论。
- 复杂 SQL、Logical IR 和 Physical IR 改为固定审计视窗内部滚动，避免结果把整页拉长；无 SQL 时禁用复制按钮。
- 补齐分段控件和结果 Tab 的标准键盘漫游、可见焦点、状态文字与 `aria-selected`；360、390、768、1440 像素实测均无页面横向溢出，预期负例浏览器控制台 0 错误。

### ANTLR/IR 最终可落地迁移缺口

- 固定日期以来的创新高/低先在事件源关系上应用起始日期，再执行分证券无界窗口；最新数据日约束保留在事件投影外层，避免误算为全历史极值。
- 将顶层 `then rank` 的关系规划置于通用事件分派之前，使事件与普通指标组成的完整候选集能够作为确定性阶段排名输入。
- 官方严格迁移由 `740/1097` 提升至 `742/1097（67.64%）`，新后端总成功数由 764 提升至 766；两条新增成功审计 `2/2 PASS`。
- 两条官方原问句在真实 Doris 上分别返回 34 行与 2 行，独立参考 SQL 完整结果哈希一致 `2/2`、非空 `2/2`、结构合同 `2/2`，最高三轮 P95 低于 0.09 秒。
- 当前数据条件下可由代码独立证明的迁移缺口已清零；剩余 355 条依赖缺失数据域、未定义空排名指标或日频表无法提供的 T+0 能力。

### ANTLR/IR 受数据支撑的事件范围与自然周期

- 允许事件关系使用经版本化证券目录验证的精确证券名称范围，并通过 `official_security` 稳定键连接物理化；概念、行业、指数和自定义板块仍保持缺失数据诊断。
- 将事件槽中的“半个月”与“上个月/上月”分别规范化为每只证券 10、20 条有效交易观测；“半年内”进入以 Doris 最新数据日为锚点的六个自然月日期代数。
- 补齐压力位受控表达式，以及基于 `upSealPx/highPx/limitFlag` 的“涨停未封板”表达式；增加 `upSealPx > 0` 哨兵保护，把错误的 5,445 个候选修正为与独立参考一致的 35 个。
- 官方严格迁移由 `734/1097` 提升至 `740/1097（67.46%）`，新后端总成功数由 758 提升至 764；六条新增后端成功审计 `6/6 PASS`。
- 六类非空真实 Doris 场景完整结果哈希一致 `6/6`、结构合同 `6/6`、性能目标 `6/6`，最高三轮 P95 约 1.03 秒。

### ANTLR/IR 泛化时序事件投影

- 将 `PhysicalEventProjection` 从仅支持 Crossing 扩展为可承载 Crossing、Extreme、Position、Pattern 及普通标量投影的通用事件特征关系。
- SQLGlot 后端复用同一事件列生成函数，直接事件筛选与时序量化不再各自维护一套窗口、位置和形态表达式。
- 时序 Position、创新高低、均线粘合和回踩形态均先物化事件列，再执行 `CONS/EXIST`；停牌证券的近 N 日继续按每只证券有效观测序列解释。
- 官方严格迁移由 `729/1097` 提升至 `734/1097（66.91%）`，新后端总成功数由 752 提升至 758；六条新增后端成功审计 `6/6 PASS`。
- 四类有界真实 Doris 场景完整结果哈希一致 `4/4`、非空 `4/4`、结构合同 `4/4`，最高三轮 P95 约 1.37 秒。

### ANTLR/IR 官方事件默认价格语义

- 将官方问句中“突破均线、回踩均线、均线粘合、创新高低、历史位置”等省略价格主语的槽位，在领域绑定入口统一规范化为 `最新价`，并把规范化后的槽位写入 Logical IR。
- 空右操作数和空 rank 度量继续返回确定性诊断；本轮没有把任意空槽位普遍解释为价格，也没有恢复旧后端的隐式降级路径。
- 官方迁移覆盖由 `690/1097（62.90%）` 提升到 `729/1097（66.45%）`，新后端总成功数由 713 提升到 752，新增 39 条全部来自旧严格成功集。
- 39 条新增成功完成槽位、事件算子、占位谓词和后端安全审计，结果 `39/39 PASS`。
- 六类非空真实 Doris 场景与独立参考 SQL 完整行集哈希一致 `6/6`，结构合同 `6/6`，最高三轮 P95 约 3.60 秒。

### 全仓静态质量门禁

- 将 Ruff 0.15.13 固定加入开发依赖，并在 GitHub Actions 中作为 pytest 前置必过门禁。
- 精确排除 ANTLR 自动生成目录，仅对承担公共 API 重导出的 `__init__.py` 忽略对应 F401/F403/F405，不采用全局规则关闭。
- 清理文档生成、科研绘图、答辩材料、官方槽位、参考执行器和测试中的真实未使用导入/变量与歧义命名。
- 修复 Linux CI 对硬编码 Windows 外部工作簿路径执行 `Path.is_file()` 时触发 `ENAMETOOLONG` 的收集失败；支持 `FINDSL_OFFICIAL_WORKBOOK` 覆盖并安全跳过不可用外部资产。
- 全仓 Ruff 从 214 条降为 0；ANTLR 生成源检查通过；全量 pytest `876 passed`；官方迁移覆盖保持 `690/1097`。

### Phase 6C 集合式前缀 CTE/Join 性能计划

- 新增 `PhysicalPrefixRef` 与 `PhysicalPrefixJoin`，把均线/均量前缀差分从逐行相关标量子查询提升为稳定键命名关系。
- SQLGlot 后端生成 `prefix_anchor_rows`、`prefix_values` CTE，使用当前前缀 Inner Join 和历史累计 Left Join；筛选 SQL 不再包含相关 `SELECT`。
- 14 个固定均线/均量筛选在真实 Doris 上完整哈希一致 `14/14`、结构合同 `14/14`、性能提升 `14/14`，中位加速约 `1.55x`，范围约 `1.23x–2.00x`。
- 14 个筛选策略由 shadow 校准为 active；排名计划因热缓存性能基本持平而继续默认使用技术列，前缀排名保留显式 shadow 回退路径。
- 证据新增 EXPLAIN 扫描节点、投影列、分区/基数和逻辑宽度成本模型，并明确区分模型成本与实测 I/O。
- 官方迁移覆盖保持 `690/1097（62.90%）`，策略切换没有引入编译回退或伪覆盖。

### ANTLR/IR 新后端事件时序投影与跨日期组合

- 新增 `PhysicalEventProjection`，在日期裁剪前使用 `LAG` 投影穿越事件，再由 `PhysicalTemporal` 完成存在次数、自然月桶和连续交易日段计算。
- 按类型化日期签名分解不同时点的事件条件，通过证券稳定键 `INTERSECT/UNION/EXCEPT` 组合，避免把今日和昨日错误压到同一行情行。
- 非时序无日期标量统一下推最新交易日快照；`80内` 规范化为 80 会话滚动窗口。
- 真实 Doris 发现并修复 `ROWS BETWEEN 0 PRECEDING` 方言错误，一日极值窗口现使用 `CURRENT ROW` 边界。
- 官方迁移覆盖由 `686/1097` 提升到 `690/1097（62.90%）`，新后端总成功数 713，新增四条且历史成功零回退。
- 四条新增成功物化审计 `4/4 PASS`；四类非空 Doris 场景与独立参考 SQL 完整行集哈希一致 `4/4`，结构合同 `4/4 PASS`，最高两轮 P95 约 2.1 秒。

### ANTLR/IR 新后端受控指标映射与窗口事件关系

- 新增 29 个经官方 Doris 字段与单位核验的受控表达式，覆盖流通市值、振幅、成交均价、委比/委差、涨跌停价、盘口涨速、集合竞价涨幅、资金占比、最大回撤、K 线形态、放量和均线排列等指标。
- 新增 `PhysicalEventFilter`、`PhysicalCrossing`、`PhysicalExtreme`、`PhysicalPosition`、`PhysicalPattern` 及投影引用。上穿/下穿/金叉使用稳定证券键上的 `LAG`；新高/新低和位置使用交易会话行框上的滚动 `MIN/MAX`；窗口函数只出现在派生关系投影中，不进入 Doris `WHERE`。
- `position` 保留“最低、最高、低、高、中”五档及明确优先级；周/月/季度/年按 5/20/60/250 个交易会话换算。`reset` 和 `close_together` 从版本化阈值配置加载，并以受控 `ABS/GREATEST/NULLIF` AST 实现。
- 支持窗口事件与同日期普通指标的集合式投影组合；不同非空日期作用域、聚合槽、时序槽和选择类型不会被静默忽略，而是返回专用诊断。
- 真实 Doris 哈希审计发现并修复复合布尔表达式比较时的括号优先级缺陷。修复前 `涨停炸板=True AND 今日` 错误放出 11,104 行，修复后与独立参考结果 70 行完整哈希一致。
- 新增 `scripts/collect_phase20_mapping_event_evidence.py`。13 类新增能力全部为非空结果，生成 SQL 与独立参考 SQL 完整结果集哈希一致 `13/13`，并保存五轮 P95 和 EXPLAIN 摘要。
- 官方迁移覆盖由 `406/1097（37.01%）` 提升至 `534/1097（48.68%）`，新后端总成功数由 413 提升至 548。原 95 条 `PHYSICAL_PLAN_UNAVAILABLE` 降至 3 条，原 81 条 `PHYSICAL_EXPRESSION_UNSUPPORTED` 降至 0；15 条行业相对比较被准确归类为 `PHYSICAL_INDUSTRY_DATA_UNAVAILABLE`。

## 2026-07-12

### ANTLR/IR 新后端证券名称范围与 queryData 命名关系

- 新增 Typed Scope Set IR，正式定义范围表达式的补集、交集、并集优先级；范围原子不再作为无法审计的裸字符串进入物理层。
- 从真实 Doris `hsj_stock_code_info` 生成 5,686 行版本化证券目录 `configs/official/security_scopes.json`，记录源数据 SHA-256。生成器提供 `--check`，可验证目录与实时官方主数据是否一致。
- 精确证券名称和“名称(六位代码)”通过 `official_security` 稳定键 Join 物理化；名称、市场、日期和指标谓词均保留在各自关系中。概念、行业、指数和自定义板块没有成员表时返回 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`。
- 新增 `PhysicalNamedScalar`，把直接 `queryData` 值建成单行命名关系；无日期时取最新数据日，非单值日期拒绝。候选全集通过 Cross Join 使用该值，不会被 benchmark 证券名称错误过滤。
- `PhysicalAggregateGroup` 新增按证券分组/全局标量两种合同。`queryData(...,AVG/SUM/MAX/MIN)` 使用全局聚合关系，不再按候选证券键错误连接。
- 修复组合聚合中范围名称被映射到行情表别名的假阳性；聚合组现在显式连接证券主数据，SQL 不会引用不存在的 `basic.name` 列。
- 新增 `scripts/collect_phase19_security_scope_evidence.py`。证券全集、市场叠加、名称代码、直接标量、全局聚合、范围排名和名称并集七类非空结果与独立 reference SQL 完整行集哈希一致 `7/7`，目录源哈希与实时 Doris 一致，最高 P95 约 0.62 秒。
- 原 `PHYSICAL_CONSTRAINT_UNSUPPORTED` 259 条归零：13 条问句获得真实执行能力，244 条缺失成员关系被准确归入 `PHYSICAL_SCOPE_DATA_UNAVAILABLE`。迁移覆盖由 `393/1097` 提升至 `406/1097（37.01%）`，新后端总成功数达到 413。

### ANTLR/IR 新后端动态日期与交易日边界集合

- `DateConstraint` 新增动态周期、锚定年月日、交易日切片和边界交易日集合合同。`本周/本月/本季度/今年`、`上周/上个月/去年/前年` 均以 Doris 最新数据日为锚点，不读取开发机当前日期。
- 滚动周、月、年保留各自的自然周期语义；滚动月采用旧规范的 `anchor-N MONTH+1 DAY` 左闭边界，滚动年从覆盖年度的 1 月 1 日开始。`日/天/交易日` 继续表示交易所会话，不与自然日混用。
- 新增 `PhysicalDynamicDateRange`、带 offset 的 `PhysicalRecentSessions` 和 `PhysicalSessionBoundaryRange`。`最近三天的前3日` 使用去重交易日倒序集合的 `LIMIT/OFFSET`；`本周的前3天` 与 `固定日期的后5日` 通过边界比较、排序和限额选择真实交易日。
- 锚定年份的 `7月`、`3月2号`、`8号` 由最新数据年份或月份解析；运行期月份一致性检查防止 2 月 30 日一类日期被数据库自动滚入下一月。
- 时序窗口同步支持动态自然周期、相对交易日切片与边界交易日集合，标量筛选和 `CONS/EXIST` 不再维护两套不一致的日期规则。
- 新增 `scripts/collect_phase18_dynamic_date_evidence.py`。九类日期场景先从 4,631 个 Doris 交易日独立解析显式日期集合，再与生成 SQL 比较完整行集 SHA-256，结果 `9/9 PASS`，最高五次 P95 约 0.59 秒。
- 官方迁移日期缺口从 `82` 降为 `0`；迁移覆盖从 `317/1097（28.90%）` 提升到 `393/1097（35.83%）`，新后端总成功数由 `319` 提升到 `400`。

### ANTLR/IR 新后端类型化排名与百分位边界

- 将布尔表达式中的 rank 条件降低为独立证券集合：`and` 使用稳定键交集，`or` 使用去重并集；`then rank` 继续表示前一阶段结果上的排名，不混淆两类语义。
- `PhysicalRank` 新增百分比边界合同。SQLGlot 后端在同一候选分区中生成 `ROW_NUMBER()` 与 `COUNT(*)`，以 `CEIL(count * percent / 100)` 得到包含至少一只证券的确定性比例边界。
- 新增 `PhysicalAggregateRank`。聚合 rank 先按 `(mktcode,tgtcode)` 计算 `SUM/AVG/MAX/MIN`，再对命名度量执行窗口排名，最后连接基础行情最新快照；不使用相关标量聚合。
- 普通排名与聚合排名均以指标方向、`mktcode`、`tgtcode` 形成稳定排序，解决跨市场同代码或指标并列时结果不确定的问题。
- rank 比较新增 `=`/`!=`，并允许数学上有效的 `rank > 0`/`rank >= 0`；零边界在等值或上界比较中仍被拒绝。
- 修复 `limit` 或 `LogicalStage` 包裹集合计划时物理入口无法识别的问题；修复 Doris SQL 安全扫描器跨越 `INTERSECT/EXCEPT` 误报 `WINDOW_IN_WHERE` 的边界缺陷。
- 新增 `scripts/collect_phase17_rank_evidence.py`。绝对 Top 10、Top 10%、五日 AVG Top 10、五日 AVG Top 10% 和 rank/标量交集五组场景在 13,650,347 行 Doris 表上完整行集哈希一致 `5/5`，最高 P95 约 0.54 秒。
- 新后端迁移覆盖从 `250/1097（22.79%）` 提升到 `317/1097（28.90%）`，新后端总成功数从 `252` 提升到 `319`，没有恢复 Phase 16 已撤销的语义假阳性。

### ANTLR/IR 新后端命名组合聚合

- 新增 `PhysicalAggregateGroup`、`PhysicalNamedAggregate`、`PhysicalAggregateRef` 和 `PhysicalCompositeAggregate`，以关系代数方式表达“每只证券的多个分组度量，再执行外层算术或布尔比较”。
- 每个聚合调用保留自己的市场和日期合同，先独立按 `(mktcode,tgtcode)` 分组，再与最新或明确日期的标量快照连接；不同窗口不会被错误合并到一个源表 WHERE 中。
- 相同聚合调用按规范节点 ID 去重并复用命名度量。跨资源聚合通过 catalog 声明的证券稳定键连接，不使用每只证券相关标量子查询。
- 组合除法统一降低为 `NULLIF(denominator,0)`；同时修复 Typed AST 中数值百分比在物理层被渲染为 SQL 字符串的问题。百分比 rank 仍等待分区基数合同，不会被误当成绝对名次。
- 标量与聚合混用时，标量调用必须共享一个单值快照日期。冲突日期返回 `PHYSICAL_SCALAR_SCOPE_MISMATCH`，范围型标量返回 `PHYSICAL_SCALAR_SCOPE_UNBOUNDED`。
- 新增 `scripts/collect_phase16_composite_evidence.py`。最新成交量对 100 日最小值、跨 basic/ext 双 AVG 比值、双窗口加最新标量、非空双窗口比较四组场景在 13,650,347 行 Doris 表上完整行集哈希一致 `4/4`，集合式与安全除零检查均为 `4/4`，最高 P95 约 1.23 秒。
- 官方漏斗新增 3 条精确组合聚合成功，同时撤销 11 条历史假阳性：这些问句此前静默忽略 `GROWTH_RISE/FALL`、时序聚合或 rank 聚合槽。审计后迁移覆盖为 `250/1097（22.79%）`，新后端总成功数为 `252`；该下降是语义正确性修复，不是已实现能力回退。

### ANTLR/IR 新后端类型化证券全集

- 新增 `UniverseSpec`，把官方 `indicator(market, filter_scope, '', date, ...) = 'all'` 解释为受市场、日期和可用范围约束的证券全集选择，而不是缺失指标或布尔占位。
- Binder 只允许 `indicator` 的单一空指标槽进入全集合同；空 `rank`、空 `queryData`、空事件操作数继续返回 `DOMAIN_CAPABILITY_UNSUPPORTED`。
- 物理规划器选择 `official_basic` 作为全集锚点，不构造虚假指标列；只接受左侧全集调用与字符串字面量 `all` 的直接等值比较，其他运算符或字面量返回 `PHYSICAL_UNIVERSE_COMPARISON_UNSUPPORTED`。
- 市场集合和日期合同继续落到 Typed Physical IR；概念、行业、指数成员等未提供的数据范围继续返回明确约束错误，不以全市场替代。
- 新增 `scripts/collect_phase15_universe_evidence.py`。全市场、沪主板、创业板补集和最近五个交易日四组生成 SQL 与独立 reference SQL 完整行集哈希一致 `4/4`，且 `4/4` 不含 `1=0/1=1` 占位。
- 修复领域证据隔离子进程在源码检出、未执行 editable install 时无法导入 `findsl` 的问题；子进程现在显式继承规范化 `src` 路径和 UTF-8 环境。
- 新后端迁移覆盖从 `231/1097（21.06%）` 提升到 `258/1097（23.52%）`，新后端总成功数从 `233` 提升到 `260`。27 条全集问句精确迁移，带缺失成员关系范围的剩余问句转入可审计的物理约束缺口。

### ANTLR/IR 新后端集合式分组聚合

- 新增 `PhysicalGroupedAggregate`，支持单指标 `SUM/AVG/MAX/MIN` 与数值比较，并把输出证券集合连接到基础行情最新快照。
- 聚合输入继续复用 Typed Market 和 Typed Date 约束；最近 N 个交易日先裁剪交易日集合，再按 `mktcode,tgtcode` 分组，不把全历史误聚合。
- SQLGlot 后端生成源表 `GROUP BY`、派生 `aggregate_rows`、资格集合和 `anchor_out` 最新快照连接，不使用旧后端的每只股票相关标量子查询。
- `GROWTH/GROWTH_RISE/GROWTH_FALL` 返回 `PHYSICAL_AGGREGATE_FUNCTION_UNSUPPORTED`；多聚合、聚合算术和 rank 聚合返回独立 composition/rank 缺口，不能近似成普通聚合。
- 新增 `scripts/collect_phase14_aggregate_evidence.py`。四类聚合与独立 `GROUP BY/HAVING` reference SQL 完整行集哈希一致 `4/4`，集合式计划检查 `4/4`，当前最高 P95 约 0.30 秒。
- 新后端迁移覆盖从 `218/1097（19.87%）` 提升到 `231/1097（21.06%）`，新后端总成功数为 `233`。原聚合约束被拆分为 13 条已迁移、59 条组合聚合和 22 条增长类函数。

### ANTLR/IR 新后端市场集合代数

- 新增 SQL 无关的 `MarketAtom/MarketNot/MarketAnd/MarketOr`，正式定义 `^ > & > |` 优先级；非法连续运算符、尾随运算符和未知市场返回稳定诊断。
- `BoundFunction` 与 `CallExpr` 现在携带 Typed Market Set 合同，物理层不再把 `|`、`&` 都用字符串 split 后混为同一种约束。
- 新增布尔 `PhysicalNot` 及 SQLGlot `NOT` 渲染。纯交易所并集会规范化为单个 `IN`，板块交并补保留显式布尔树。
- 官方代码表 5,686 行中的 `kcbFlag/gemFlag/bShareFlag` 真值均为 0。项目不修改原始数据，改以受控代码区间物理化：科创板 688、创业板 300/301、沪主板 600/601/603/605、深主板 000/001/002/003、北交所 920。
- 新增 `scripts/collect_phase13_market_evidence.py`。科创板、创业板、主板并集、混合优先级和双重排除五组 reference SQL 与生成 SQL 的完整 Doris 行集哈希一致 `5/5`，当前五次重复快照最高 P95 约 0.36 秒。
- 新后端迁移覆盖从 `183/1097（16.68%）` 提升到 `218/1097（19.87%）`，新后端总成功数为 `220`；原市场约束不支持项已清零，境外市场改为 `PHYSICAL_MARKET_DATA_UNAVAILABLE`。

### ANTLR/IR 新后端最近交易日集合

- 新增布尔物理表达式 `PhysicalRecentSessions`，把 scalar date slot 的 `recent_sessions` 合同物理化为最近 N 个不同交易日的集合成员判断。
- SQLGlot 后端生成 `bizdate IN (SELECT bizdate ... GROUP BY bizdate ORDER BY bizdate DESC LIMIT N)`；该路径使用交易所全局交易日集合，不以 `CURRENT_DATE - N` 近似，也不与每只股票最近 N 条记录的时序合同混用。
- 验证器限制该节点只能读取 catalog 分区日期列，且 N 必须为正数。`近5日`、`最近十个交易日`、`30个交易日内` 均有边界测试。
- 新增 `scripts/collect_phase12_session_evidence.py`。5/10/30 个交易日三组生成 SQL 与独立显式日期集合 reference SQL 的完整 Doris 行集哈希一致 `3/3`，当前五次重复快照最高 P95 约 0.45 秒。
- 新后端迁移覆盖从 `163/1097（14.86%）` 提升到 `183/1097（16.68%）`，新后端总成功数为 `184`；物理日期终止项从 68 条下降到 44 条。

### ANTLR/IR 新后端 Typed Date 物理化

- `DateConstraint` 现在随 `CallExpr` 进入 Logical IR，物理规划器直接消费已绑定日期合同；原始字符串解析仅保留为旧 IR 兼容路径。
- 日期绑定新增中文/数字年份、明确年月、明确年月日、`当天/现在`、`昨天/昨日/前一个交易日` 和 `前天`，非法月份或日期返回 `DOMAIN_DATE_INVALID`。
- 新增 `PhysicalNthLatestValue`。昨天和前天通过基础行情表的去重交易日倒序序列解析为 offset 1/2，不用 `DATE_SUB` 近似交易日。
- SQLGlot 后端为交易日偏移生成受控 `GROUP BY bizdate ORDER BY bizdate DESC LIMIT 1 OFFSET n` 子查询，验证器限制它只能访问 catalog 声明的分区日期列且 offset 必须为正数。
- 新增 `scripts/collect_phase11_date_evidence.py`。年份、月份、日期、昨天和前天五组场景与独立显式日期 reference SQL 的完整 Doris 行集哈希一致 `5/5`，当前五次重复快照最高 P95 约 0.23 秒。
- 新后端迁移覆盖从 `135/1097（12.31%）` 提升到 `163/1097（14.86%）`，新后端总成功数为 `164`；物理日期终止项从 95 条下降到 68 条。

### ANTLR/IR 新后端多资源稳定键连接

- 新增 `PhysicalTableScan` 和可执行的左深 `PhysicalJoin`。规划器以 `official_basic` 为证券行情锚点，只连接相同 `logical_entity` 的资源，连接键从双方 `stable_keys` 交集推导。
- 静态证券维表使用 `(mktcode,tgtcode)`，行情、资金流与技术指标表使用 `(mktcode,tgtcode,bizdate)`；缺少证券稳定键、逻辑实体不一致或无法确定唯一锚点时返回稳定错误，不生成猜测性 Join。
- SQLGlot 后端新增多资源星型 Join 渲染和资源别名校验，表达式列只能引用当前关系树中实际存在的资源。多资源时序继续显式返回 `PHYSICAL_TEMPORAL_MULTI_RESOURCE_UNSUPPORTED`，没有用普通 Join 近似时序合同。
- 物理谓词归一器会展开 `AND` 并按规范节点 ID 去重，多个函数共享“今日”约束时只生成一个 `MAX(bizdate)` 子查询。
- 新增 `scripts/collect_phase10_join_evidence.py`。在官方 Doris 数据快照上，basic/ext/security/technical 的五个两表或三表案例与独立 reference SQL 完整行集哈希一致 `5/5`；基础行情表为 13,650,347 行，本轮最高 P95 约 1.81 秒。
- 新后端迁移覆盖从 `107/1097（9.75%）` 提升到 `135/1097（12.31%）`，新后端总成功数为 `136`。原多资源终止项中 28 条完成迁移，其余问句暴露出的日期、rank、近似比较和表达式缺口继续单独统计。

### ANTLR/IR 新后端时序语义

- 新增 SQL 无关的 `TemporalQuantifier`，严格解析 `CONS/EXIST`、比较符、范围、中文数字、`每年/每月/每日`、单位归一和默认阈值，非法合同返回稳定错误码。
- `BoundFunction` 不再把 `count_exp` 作为裸字符串保存；原子时序比较会降低为 `LogicalConsecutive` 或 `LogicalExist`，行谓词保留在时序节点内部，避免先过滤后错误拼接连续段。
- 新增 `PhysicalTemporal` 与交易窗口合同。日粒度 `EXIST` 使用集合聚合，`CONS` 使用完整交易序号与匹配序号之差的岛屿法，不使用自然日 `DATEDIFF`，也不把连续次数近似为窗口总次数。
- SQLGlot Doris 后端新增集合式 CTE 计划：`source_rows/eligible_rows/sequenced_rows/matched_rows/runs/temporal_metrics/qualified`，最终按稳定股票键连接最新行情快照。
- 新增 Logical/Physical Set Operation。顶层时序 `AND` 降低为稳定股票键集合交集，`OR` 降低为去重并集；每个分支保留独立时间窗、指标资源和 CTE 命名空间，支持 `official_basic` 与 `official_ext` 跨资源组合。
- 年、季度、月、周粒度新增基于 `DATE_TRUNC` 的日历桶物理计划；桶内按 `MAX(matched)` 合并，连续段使用无间隙序号，`每年/每周` 同时校验非空和桶跨度，缺失日历桶不会被错误拼接。
- 新增独立 Python 时序 oracle 和 `scripts/collect_phase9_temporal_evidence.py`。官方 13,650,347 行基础表上，六个日粒度/集合案例覆盖最新交易日全体股票，四个日历桶案例覆盖稳定排序的 200 只固定样本股票，Doris 与独立 oracle 行集哈希一致 `10/10`，本轮最高 P95 约 1.30 秒（以提交快照实际值为准）。
- 日期槽新增 Typed DateConstraint，区分最近 N 个交易记录、最近 N 个日历月/年和显式年份范围；覆盖“这五天”“过去6天”“近3个交易日”“两年内”“近两月”和中文数字年份，不再在物理层猜测原始字符串。
- 新后端迁移覆盖从 `72/1097（6.56%）` 提升至 `107/1097（9.75%）`，新后端总成功数为 `108`。日历桶不支持错误已清零；多时序迁移缺口剩余 7 条，后续重点转向同一算术比较内多个时序合同、声明式约束、多资源连接和聚合物理化。
- 官方领域证据生成改为隔离 Phase 3 基线并按 750 条分块执行 Phase 4，全量 5,799 条门禁保持不变，同时限制 Windows 开发机和 CI 的峰值内存。
- Doris 版本证据改从 `SHOW FRONTENDS` 获取真实 FE build；`SELECT VERSION()` 的 `5.7.99` 仅标注为 MySQL 协议兼容版本。

## 2026-07-11

### 严格官方编译基线

- 新增 strict/recovery 双模式。strict 不静默修复源码，recovery 返回结构化 repair、warning、fallback 和 degraded 状态。
- 为官方 12 类函数建立精确签名，禁止额外参数被切片忽略，禁止数字、布尔值或表达式冒充字符串槽位。
- 新增官方 AST 类型分析，覆盖数值/布尔/字符串/时间、百分比、四则运算、比较、`between`、`~=` 和裸标识符检查。
- strict compiler 对 repair、warning 和结构化 fallback 统一使用 `OFFICIAL_DEGRADED_SEMANTICS`，CLI JSON 错误路径返回稳定错误码和退出码 2。
- 重建官方 5,799 条工作簿覆盖率：strict parse `5,792`、recovery parse `5,799`、strict compile `1,097`、recovery compile `1,830`、degraded `733`。
- `1=0/1=1` 改为编译器结构化记录，当前分别为 `472/328` 条，不再扫描 SQL 文本，避免误判合法 `WHERE 1=1` 和字符串 `'1=0'`。
- 修正官方 CSV 日期画像，`first_date/last_date` 使用全文件真实最小值和最大值，不再假设 CSV 已按日期排序。
- 新增 `docs/36_严格官方编译基线与口径说明.md`，明确历史 `compile_ok=1,882` 是 recovery 返回口径，不能作为 SQL 正确率。

## 2026-07-06

### 官方真实数据证据与审计口径刷新

- 刷新官方 workbook 覆盖率：语法解析从 `5,792/5,799` 提升到 `5,799/5,799`，可落地 Doris SQL 编译数从 `1,873` 提升到 `1,882`，`UNSUPPORTED_OFFICIAL_COUNT_EXP` 从 `14` 降到 `3`。
- 修复并归档官方 Excel 中 7 条文档噪声样例，覆盖边缘引号、前导 `and`、多余右括号和孤立日期字面量等可判定标点问题；原始输入仍保留在覆盖率报告中用于审计。
- 增强 `count_exp` 解析和 SQL 生成，支持可由日频官方三表解释的区间次数、连续区间、半年度归一到月份桶和 bounded count/run-length 谓词。
- 新增 `python -m findsl.cli official-performance-matrix`，从真实 `reports/official_doris_evidence.json` 生成逐问句性能矩阵；当前 6 条官方 Doris 查询全部满足 P95 <= 10s，最大 P95 为 `61.269 ms`。
- `evidence_metadata.json` 和 `evidence_summary.md` 新增官方逐问句性能矩阵摘要，确保代码、报告、截图和 metadata 引用同一份 evidence。
- 新增 `docs/grammar/OfficialSlot.g4` 与 `docs/34_官方槽位DSL_BNF与ANTLR形式化说明.md`，将官方槽位 DSL 的语法优先级、函数调用、比较、`between`、`limit` 和四则运算形式化。
- 新增 `docs/35_官方三表缺失数据域不可伪造SQL审计报告.md`，逐条说明剩余 3 条 `count_exp` 和 1 条周期函数为什么不能在缺失数据域下伪造 SQL。

## 2026-06-10

### 官方 DSL 语义补强

- 支持 `rank(..., agg_func, count_exp)`，将聚合排名编译为时间桶聚合、桶内 `ROW_NUMBER()` 排名和 `CONS/EXIST` 命中桶统计。
- 支持 `cross_above/cross_down/golden_cross(..., count_exp)`，将上穿、下穿和金叉编译为基于 `LAG()` 的每日事件行，再交给统一 `count_exp` 逻辑统计。
- 修正穿越事件窗口语义：`LAG()` 源数据保留目标窗口开始日前的历史行，事件次数只在 `event_rows.bizdate` 目标窗口内统计，避免漏判窗口首日上穿/下穿/金叉。
- 支持官方三表可解释的表达式级聚合 `count_exp`，例如 `indicator(..., AVG, CONS=每日) / indicator(... 每手股数 ...) < 阈值` 会编译为每日 bucket 行后再统计每日表达式是否满足。
- 补充 `涨停价`、`跌停价` 官方指标别名，分别映射到 `upSealPx`、`downSealPx` 并沿用价格单位换算。
- 补强官方口语日期归一化，覆盖 `过去20天`、`30个交易日`、`三个月之内`、`近半年`、`近5个月至今`、`2024年8月`、`9号`、`九月十五号`、`本季度` 等表达。
- `count_exp` 表达式比较支持同义日期 scope：当两个日期槽能无 warning 归一到同一日期窗口时，可以在同一个计数比较中使用。
- 官方 workbook 覆盖刷新为 `5,792/5,799` 可解析、`1,873` 条可落地编译，`UNSUPPORTED_OFFICIAL_COUNT_EXP` 降至 `14`。

### 官方真实数据与 Doris 证据

- 完成官方三张 CSV 在本地 Apache Doris 中的真实落库核验：`hsj_stock_code_info=5686`、`hsj_stock_hq_basic=13650347`、`hsj_stock_hq_ext=6170822`。
- 修正官方 schema 中 `lastPx/preClosePx` 真实空值处理，避免 Stream Load 过滤或失败。
- 将官方 Stream Load 默认路径调整为宿主机直连 BE `8040`，并显式使用 `Expect: 100-continue`、`strict_mode:false`、`max_filter_ratio:0` 和长超时。
- 将 `hsj_stock_hq_basic_technical` 构建从单次大 INSERT 改为 `mktcode + tgtcode hash bucket` 分片构建，解决单 BE Docker 环境下的内存 OOM。
- 新增 `scripts/prepare_official_doris_evidence.ps1`，统一完成官方文件检查、Doris 就绪检查、落库、特征表构建、行数验收、SQL/EXPLAIN 证据和 Markdown/JSON 报告生成。
- 新增 `deploy/doris/official/05_technical_features_by_market.sql`，用于按市场和 hash bucket 构建长周期技术特征。
- 生成官方 Doris 证据报告，确认三张派生特征表均为 `13650347` 行，并在报告生成前强制校验 baseline/prefix 行数一致。
- 新增 `docs/22_官方真实数据落库复盘与满分冲刺计划.md`，记录真实数据分析、根因修复、证据结果、剩余短板和后续冲刺计划。

## 2026-06-07

### 文档整理

- 新增 `PROJECT_INDEX.md`，统一说明项目目录、核心文件、运行入口、历史文件和维护建议。
- 新增 `docs/01_项目简介.md` 至 `docs/17_项目交付说明.md`，建立中文编号文档体系。
- 新增 `archive/README.md`，说明历史归档目录使用规则。
- 在 `README.md` 增加中文文档体系和文件索引入口。

### 语义与验证修复

- 将 `rank(percent=...)` 的百分比阈值 SQL 从近似 `CAST` 写法改为 Doris 官方 `CEIL()` 函数。
- 在 SQLite 本地执行器中注册 `CEIL`，保证本地等价验证可执行 Doris 方言 SQL。
- 修复 reference oracle 中 `OR` 对 `NULL/UNKNOWN` 的三值逻辑处理，补充稀疏辅助表回归测试。
- 保持 `CONS/EXIST`、比较运算、percent rank 与 SQL/Doris 语义一致。
- 补强 Doris SQL validator 的表引用解析，支持反引号表名和库名限定表名，避免未知表通过 `` `table` `` 或 `db.table` 写法绕过检查。
- 新增 SQL validator 和 evidence metadata 回归测试，本轮审计后全量测试数为 197。

### 提交证据

- readiness 证据显示 required gates 全部通过，warning count 为 0。
- 官方风格正例、负例、SQL/reference 等价、Doris 资产完整性和提交包检查均纳入门禁。
- 新增 `src/findsl/evidence_metadata.py` 与 `python -m findsl.cli evidence-metadata`，自动从提交证据快照中抽取门禁、pytest、官方套件和 Doris 加速指标，生成 `submission_artifacts/evidence_metadata.json` 与 `submission_artifacts/evidence_summary.md`，降低技术报告、答辩材料和 Demo 指标之间的人工口径漂移风险。

## 2026-05 至 2026-06

### 核心能力建设

- 实现 DSL 词法、语法、AST、语义校验和 Doris SQL 生成链路。
- 支持 `filter`、`then`、`rank`、`date_between`、`CONS`、`EXIST`、`MA`、`SUM`、`MAX`、`MIN`、`RET` 等主要算子。
- 实现 prefix-sum 长窗口优化、Doris DDL 生成、Doris evidence 采集、Web Demo、NL2DSL 模板和 LLM 候选安全适配。
- 建立 Pandas reference oracle、SQLite 执行器、官方风格测试、readiness 报告和 submission artifacts。

## 版本说明

当前 `pyproject.toml` 中项目版本为 `0.1.0`。该版本是比赛原型/提交版本，不代表商业生产版本。若后续进入长期维护，建议按 `0.2.0`、`0.3.0` 或 `1.0.0` 方式维护语义版本，并在本文档中记录每次变更范围、测试结果和证据快照。
