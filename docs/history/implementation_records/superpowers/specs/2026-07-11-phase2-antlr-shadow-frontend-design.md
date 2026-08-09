# Phase 2：ANTLR4 影子前端与 Typed AST 适配设计

## 1. 阶段目标

Phase 2 将官方槽位 DSL 的语法识别从单文件手写递归下降解析器扩展为可复现生成的 ANTLR4 前端，但不立即删除或替换现有解析器。新前端首先以影子模式运行，使用同一输入分别调用手写解析器和 ANTLR 解析器，再比较两者输出的稳定 AST、错误分类和源码位置。只有全部兼容门禁通过后，ANTLR 才能成为可选主入口。

本阶段解决的是“语法前端是否标准、可维护、可审计”的问题，不改变金融函数语义、SQL 生成策略或 Doris 物理规划。Logical IR、规则优化器、代价模型和 SQLGlot 后端属于后续独立阶段。

## 2. 成功条件

本阶段完成必须同时满足以下条件：

1. ANTLR4 Python runtime 和生成器版本固定，能够用仓库内命令从 `.g4` 文件重建 Python 解析器。
2. 语法源文件由 `docs/grammar` 提升到源码所有的 grammar 目录；生成代码与手写代码隔离，禁止人工修改生成文件。
3. ANTLR Parse Tree 可转换成现有不可变 `OfficialNode` AST，不让下游编译器依赖 ANTLR 类型。
4. AST 节点能够携带半开区间源码位置，错误诊断至少包含错误码、行、列、起止偏移和原始片段。
5. strict 模式不执行输入修复；recovery 模式继续复用结构化修复记录，并在修复后文本上运行所选前端。
6. 现有解析入口和 CLI 默认行为不变；ANTLR 通过显式前端参数或影子模式启用。
7. 5,799 条官方数据在 recovery 模式下保持 5,799 条可解析；strict 的 5,792/5,799 基线不得下降。
8. 对两种前端都能成功解析的官方输入，规范化 AST 必须逐行相等。任何差异必须形成可定位记录，不能静默忽略。
9. 现有 355 项测试不得回归，并增加语法、适配、诊断、影子比较和生成物一致性测试。
10. 解析性能应记录 P50/P95；本阶段不以微基准单独宣称赛题编译性能达标，但不得出现数量级退化。

## 3. 方案选择

采用“ANTLR 影子前端 + AST 适配器 + 差分门禁”。不采用直接替换，因为现有手写解析器已经承载官方语料兼容行为和结构化修复，直接切换会把语法差异、恢复差异和语义回归混在一次变更中。也不先进行大范围 AST 重构，因为这会扩大 Phase 2 的验证面，并延迟可展示的 ANTLR 成果。

影子迁移保留两个事实：手写解析器是当前行为基线，ANTLR 文法是目标语法规范。差分不意味着旧行为永远正确；遇到差异时必须依据赛题原文、正式文法和最小测试判断哪一方需要修正，并在报告中记录裁决理由。

## 4. 目录与模块边界

目标目录如下：

```text
grammar/
  OfficialSlot.g4                 官方槽位 DSL 的唯一文法源
scripts/
  generate_antlr.py               下载/校验生成器并可复现生成 Python 文件
src/findsl/official/frontend/
  __init__.py                     稳定前端接口
  protocol.py                     Frontend、ParseOutcome 等公共协议
  handwritten.py                  现有解析器适配层
  antlr_frontend.py               ANTLR 调用、错误监听和适配入口
  ast_adapter.py                  Parse Tree -> OfficialNode
  shadow.py                       双前端比较和差异分类
  generated/                      ANTLR 生成文件，禁止手工编辑
tests/official/frontend/
  test_antlr_grammar.py
  test_ast_adapter.py
  test_diagnostics.py
  test_shadow_parity.py
  test_generated_sources.py
```

`official_slot.py` 暂时保留 AST 定义和兼容门面。新模块不得反向把 ANTLR 对象传入语义分析器或 SQL 生成器。后续 AST 独立拆包时，两个前端只需修改适配层。

## 5. 稳定前端契约

公共前端接口接收原始文本、编译模式和可选文件标识，返回 `ParseOutcome`：

- `ast`：成功时为 `OfficialNode`，失败时为空；
- `diagnostics`：有序结构化诊断；
- `original_source`：用户原始输入；
- `normalized_source`：实际参与解析的输入；
- `repairs`：recovery 模式下执行的结构化修复；
- `frontend`：`handwritten` 或 `antlr`；
- `elapsed_ns`：仅用于前端性能证据。

调用方不得通过异常消息文本推断错误类型。兼容门面可以继续抛出 `OfficialSlotError`，但应由 `ParseOutcome` 的首个阻断诊断构造。

## 6. 文法设计约束

`OfficialSlot.g4` 必须覆盖当前正式语法：布尔优先级、`then` 阶段、比较、`between` 范围、算术、函数调用、字符串、百分比、正负数和尾部 `limit offset,count`。关键词大小写不敏感，标识符保留原始拼写。

文法只表达结构，不编码 12 类官方函数的参数数量、参数类型和金融含义。这些规则继续由 signatures/semantics 层负责，避免把业务语义散落进 parser action。文法不使用嵌入式 Python action，从而保持可移植和可测试。

生成器与 runtime 使用同一 ANTLR 小版本。生成命令必须固定语言、visitor 选项和输出目录，并在 CI 中校验重新生成后工作区无差异。

## 7. AST 适配与源码位置

适配器使用 visitor 将 Parse Tree 映射到现有节点类型。运算符结合性和优先级由 Parse Tree 决定，不通过拼接源码重新解析。数字保持当前 AST 所需的数值表示，字符串只在词法层执行一次反转义，百分比保持可区分语义。

每个节点的位置采用 `[start_offset, end_offset)` 半开区间。ANTLR token 的 stop index 是闭区间，适配时必须加一。行列使用面向用户的 1 基行号和 1 基列号；内部保存偏移用于精确截取。对于修复后的文本，同时保留 normalized span，并在已有 repair 映射可确定时映射回 original span；无法可靠映射时必须显式标记，而不是提供虚假坐标。

为避免一次性破坏 `OfficialNode` 的相等性和序列化，本阶段优先使用旁路 `SourceMap` 按节点身份保存 span；只有测试证明不会影响现有输出后，才考虑把 span 直接加入 AST 基类。

## 8. 诊断模型

ANTLR 默认控制台错误监听器必须移除，改用项目错误监听器生成稳定诊断。语法错误码至少区分：

- `OFFICIAL_ANTLR_LEX_ERROR`：无法形成合法 token；
- `OFFICIAL_ANTLR_PARSE_ERROR`：token 合法但结构不符合文法；
- `OFFICIAL_ANTLR_ADAPTER_ERROR`：Parse Tree 无法映射到稳定 AST；
- `OFFICIAL_FRONTEND_DIVERGENCE`：影子比较发现行为差异。

诊断包括严重级别、阶段、消息、行列、起止偏移、源码片段、前端名称和可选修复建议。strict 下任一语法错误均阻断；recovery 仅允许进入既有白名单的源码修复，ANTLR 自身的 token insertion/deletion 不得被当作成功 AST。解析结束后如有语法错误，即使 ANTLR 构造了恢复树也必须返回失败。

## 9. 影子模式与差异分类

影子模式以现有手写前端作为用户可见结果，同时后台运行 ANTLR。比较过程先将 AST 转换为不含对象地址和 span 的规范结构，再比较：

1. 双方成功且 AST 相等：`MATCH`；
2. 双方成功但 AST 不等：`AST_MISMATCH`；
3. 仅手写成功：`ANTLR_REJECTED`；
4. 仅 ANTLR 成功：`HANDWRITTEN_REJECTED`；
5. 双方失败且错误位置/分类相容：`ERROR_MATCH`；
6. 双方失败但诊断不相容：`ERROR_MISMATCH`。

报告必须包含官方行号、输入哈希、差异分类、两侧诊断和最小 AST 差异路径。原始金融文本可能具有提交限制，默认报告只保存截断片段和哈希，显式调试模式才保存完整输入。

## 10. 前端选择与回滚

新增 `official_frontend` 配置，允许 `handwritten`、`antlr` 和 `shadow`。在 Phase 2 内默认值保持 `handwritten`，测试和证据命令显式使用 `shadow`。当全量门禁稳定通过后，可在后续提交中把默认值切换到 `antlr`，但仍保留一版可配置回滚路径。

切换不使用环境中隐含的随机比例。若未来在线灰度，应按输入哈希稳定采样，并保证同一输入始终进入相同路径。

## 11. 测试策略

所有实现遵循先失败测试、再最小实现、再重构的顺序：

1. 文法金样测试覆盖每种运算符、优先级、转义、嵌套和 limit。
2. AST 适配测试逐节点核对类型、字段、结合性和 span。
3. 非法输入测试确认 ANTLR 恢复树不会被误判为成功。
4. strict/recovery 测试确认修复策略与前端选择正交。
5. 现有 parser 测试参数化到两个前端；尚未对齐的用明确差异清单管理，不使用无理由 skip。
6. 官方 5,799 行执行影子差分，输出 JSON 和 Markdown 汇总。
7. 生成物测试运行生成脚本后检查 `git diff --exit-code`。
8. 微基准对官方语料预热后多轮测量 P50/P95，并分别报告手写、ANTLR 和 shadow 成本。

## 12. 验收与证据

Phase 2 证据包至少包含：固定工具版本、生成命令、生成物校验、单元测试结果、全量测试结果、官方数据 strict/recovery 解析计数、影子差分分类、解析性能分位数和 Git HEAD。报告中的数字必须由同一提交实际生成，并记录输入文件 SHA-256。

ANTLR 语法全量解析通过只能证明结构兼容，不能证明 12 类函数金融语义正确，也不能证明 SQL 行集正确或 Doris 性能达标。相关结论继续使用 Phase 1 的严格口径，直到后续独立解释器与真实 Doris 差分证据完成。

## 13. 实施顺序

1. 固定依赖、生成器和生成命令。
2. 校正文法并建立生成物一致性测试。
3. 定义稳定前端契约和结构化诊断。
4. 实现 ANTLR 错误监听器和 Parse Tree 适配器。
5. 将现有手写解析器包装为同一前端协议。
6. 实现前端选择和影子差分。
7. 迁移现有解析测试并补充性质与边界测试。
8. 跑官方全量差分，逐项修正文法或适配器。
9. 记录性能，刷新证据和中文说明。

## 14. 非目标

- 本阶段不重写现有 12 类函数语义和 SQL 生成器。
- 不引入完整 Apache Calcite，也不复制 Doris Nereids CBO。
- 不因 ANTLR 的自动错误恢复而提高“解析成功率”口径。
- 不删除手写解析器，不提前切换默认前端。
- 不把编译覆盖率、语法覆盖率或无异常率表述为结果正确率。
