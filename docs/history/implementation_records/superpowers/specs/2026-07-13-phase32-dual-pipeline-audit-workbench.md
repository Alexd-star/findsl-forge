# Phase 32：双管线编译与证据工作台

## 1. 问题与目标

Phase 31 已经把当前官方数据能够证明的 ANTLR/IR 迁移覆盖推进到 `742/1097`，但原 Web Demo 仍只展示内部 FinDSL 编译器。官方七槽 DSL 虽然已有 `/api/official/analyze`、ANTLR 前端、Typed AST、Logical IR、Physical IR 和 SQLGlot 后端，评委却无法在页面中操作这条链路。若只演示旧管线，新架构的主要竞争力只能靠口头说明，且内部 DSL 与官方 DSL 的身份容易混淆。

本阶段目标是建立“审计型投研工作台”：一套页面保留内部验证能力，同时提供独立的官方赛题管线。两种 DSL 不共用样例语义，不把浏览器编译冒充 Doris 执行，也不把受控拒绝包装成成功。

## 2. 产品边界

### 2.1 内部验证管线

内部模式服务于中文需求到受限 FinDSL 的交互演示。它保留 NL2DSL 候选、编译器验证、独立参考执行器、前缀优化开关、样本结果和诊断预设。Eastmoney 小样本仅用于展示真实证券代码与日期，不参与官方 1,097 条迁移口径或 Doris 规模性能口径。

### 2.2 官方赛题管线

官方模式直接调用 `compile_official()`，执行以下真实阶段：

```text
官方七槽 DSL
  -> ANTLR4 frontend
  -> Typed AST
  -> Logical IR
  -> Rule optimizer
  -> Physical IR
  -> SQLGlot Doris AST
  -> SQL validation
```

成功载荷展示 Doris SQL、前端 AST、Typed AST、Logical IR、Physical IR、阶段轨迹、资源选择和物理策略。页面只做编译与审计，不直接连接生产 Doris。真实行集、完整 SHA-256、EXPLAIN 和延迟结果来自版本化 evidence snapshots。

### 2.3 失败也是正式输出

财务数据域缺失、T+0 日频数据不足等输入必须返回稳定诊断。页面展示失败阶段、错误码、修复建议和失败前已经完成的中间阶段，不生成 `1=0`、`1=1`、空表或猜测字段。程序接口 `/api/official/analyze` 保持 HTTP 400；页面专用 `/api/official/preview` 返回 HTTP 200 和 `{ok:false,error:...}`，使预期负例不会在浏览器控制台产生误导性的网络错误。

## 3. 信息架构与交互

页面按“管线身份、输入、执行、阶段结果、交付证据”的顺序组织。顶部证据只读取后端返回的版本化元数据，当前展示 `742/1097` 官方严格迁移、`908 passed`、`36.24x` Doris 加速和结果集一致。若文件缺失，界面显示证据缺失，不回退到写死数字。

官方样例覆盖基础行情、证券主数据、扩展行情、排名、市场与日期、技术特征、固定日期以来事件、事件候选后阶段排名、精确证券时序事件，以及两类关键缺失数据诊断。切换模式会清空上一模式结果，重置 Tab 和指标，避免旧 SQL 被误认为当前输入的输出。

结果区使用稳定高度的内部滚动审计窗。复杂 Physical IR 的内容高度可超过八千像素，但页面本身不会随之无限增长；用户可在输入和输出之间保持稳定位置。没有成功 SQL 时复制按钮处于禁用状态。

## 4. 可访问性和响应式要求

- 正文、说明、成功、警告和失败状态均使用文字表达，颜色不是唯一信号。
- 管线分段控件与结果 Tab 使用 `aria-selected` 和 roving tabindex；左右方向键循环切换，Home/End 跳到首尾项。
- 结果状态使用 `role=status` 与礼貌播报，错误摘要使用 `role=alert`。
- 结果视窗可获得键盘焦点，长 IR 可在区域内部滚动。
- 360、390、768、1440 像素宽度均不得出现页面级横向滚动、按钮文字裁切或 DSL 输入溢出。
- 960 像素以下切换为单栏，桌面保持输入与结果双栏；移动端证据和结果指标保持两列，阶段 Tab 允许区域内横向滚动。
- `prefers-reduced-motion` 下关闭状态过渡。

## 5. 接口合同

| 接口 | 用途 | 成功 | 受控失败 |
|---|---|---|---|
| `GET /api/examples` | 内部样例 | HTTP 200 | 空列表仍为 200 |
| `GET /api/official/examples` | 官方编译与诊断样例 | HTTP 200 | 空列表仍为 200 |
| `POST /api/analyze` | 内部编译与参考验证 | HTTP 200 | HTTP 400 + 诊断 |
| `POST /api/official/analyze` | 程序化官方编译 | HTTP 200 | HTTP 400 + OfficialPipelineError |
| `POST /api/official/preview` | 浏览器官方编译预览 | HTTP 200 + `ok:true` | HTTP 200 + `ok:false` |
| `GET /api/evidence` | Doris 与交付证据摘要 | HTTP 200 | 显式 `available:false` |

## 6. 验证矩阵

| 验证项 | 实际结果 |
|---|---|
| Demo 单元/API 测试 | `12/12 PASS` |
| JavaScript 语法 | Node `--check` PASS |
| 官方基础过滤 | 成功，策略 `direct_column` |
| 官方事件后阶段排名 | 成功，策略 `stage_rank`，可查看完整 Physical IR |
| 官方 T+0 负例 | 预期和实际均为 `PHYSICAL_PLAN_UNAVAILABLE` |
| 负例控制台 | 0 error，0 warning |
| 360px 页面横向溢出 | 0px |
| 390px 页面横向溢出 | 0px |
| 768px 页面横向溢出 | 0px |
| 1440px 页面横向溢出 | 0px |
| 长 Physical IR | 结果窗内部滚动，页面高度不随 8,711px 内容增长 |
| 结果 Tab 键盘操作 | ArrowLeft/ArrowRight/Home/End PASS |
| 管线分段键盘操作 | ArrowLeft/ArrowRight/Home/End PASS |

## 7. 诚实口径

页面中的 `742/1097` 是旧严格成功集迁移到新 Physical IR/SQLGlot 后端的覆盖，不是 5,799 条语料的总体准确率。`908 passed` 是版本化证据生成时的 pytest 数量，不代表每条官方问句都有人工真值。`36.24x` 来自指定 5,000,000 行 Doris 前缀优化证据，不代表所有 SQL 都有相同加速。浏览器显示“编译通过”证明编译与静态验证完成，不证明该次输入已经由浏览器实时查询生产 Doris。

剩余 355 条严格迁移缺口继续保留结构化边界：缺失概念、指数、行业与板块成员关系，缺失其他数据域，空排名指标语义未定义，以及日频数据无法证明 T+0。Phase 32 不改变这些事实，也不以 UI 文案扩大能力口径。
