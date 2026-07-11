# ANTLR4 影子前端与迁移证据

## 1. 引入第二套语法前端的原因

项目早期使用手写递归下降解析器。它体积小、速度快，也经过官方问句反复验证，但文法规则、容错处理和 AST 构造集中在同一个大文件中。随着运算符、阶段表达式和函数槽位增加，仅靠代码阅读很难准确回答语法边界、优先级和修改影响范围。

Phase 2 增加 ANTLR4 生成前端，目的是把语法变成独立、可生成、可逐行比较的正式资产。ANTLR 只处理词法和语法结构；金融函数签名、类型检查、数据域约束和 Doris SQL 生成仍由原有语义层负责。这样可以防止业务规则被塞进 grammar，也使以后替换前端时不必改动 SQL 后端。

## 2. 代码结构

正式文法位于 `grammar/OfficialSlot.g4`。`scripts/generate_antlr.py` 固定使用 ANTLR 4.13.2，并校验生成器 jar 的 SHA-256。生成的 lexer、parser 和 visitor 位于 `src/findsl/official/frontend/generated/`，不得人工修改。

`antlr_frontend.py` 负责调用 lexer/parser、关闭 ANTLR 默认控制台输出并收集结构化诊断。`ast_adapter.py` 将 Parse Tree 转换为稳定的 `OfficialNode`，下游代码不会接触 ANTLR 对象。`handwritten.py` 把原解析器包装成相同协议。`shadow.py` 同时运行两套前端，比较规范化 AST，并输出输入哈希、耗时和第一处 JSON Path 差异。

## 3. 安装和生成

```powershell
python -m pip install -e ".[dev]"
python scripts/generate_antlr.py --check
```

`--check` 会在临时目录重新生成代码，再逐文件比较已提交生成物。grammar 修改后若忘记重新生成，命令返回非零退出码。更新生成物时执行 `python scripts/generate_antlr.py`，随后重新运行测试和 `--check`。

## 4. 前端使用方式

默认入口仍选择 `handwritten`，避免在证据完成前静默切换生产行为。显式调用 ANTLR 的命令如下：

```powershell
python -m findsl.cli official-slot-parse "indicator('', '', '涨幅', '今日', '', '', '') > 5%" --mode strict --frontend antlr --json
```

strict 模式使用原始输入，不执行修复。recovery 模式先运行已有的白名单修复，再把同一份 normalized source 分别交给两套前端。ANTLR 自带的 token insertion/deletion 只用于形成错误上下文；只要 lexer 或 parser 报错，恢复树就不会被当作成功 AST。

## 5. 源码位置和诊断

ANTLR 诊断包含错误码、严重级别、消息、前端名称、1 基行列和 `[start_offset,end_offset)` 半开偏移。项目区分词法错误、语法错误和 AST 适配错误。正常解析时，旁路 `SourceMap` 保存 AST 节点对应的源码范围，不改变 AST 的相等性和既有 JSON 格式。

恢复后的文本可能与原始文本不同。结果明确保存 `original_source`、`normalized_source` 和结构化 `repairs`，不会把修复后坐标冒充原始坐标。后续若界面需要逐字符高亮，可基于已有 `_MappedSource` 补充完整坐标映射。

## 6. 官方 5,799 条差分结果

```powershell
python -m findsl.cli official-frontend-evidence --workbook "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\选股 DSL 规范文档\选股提槽实例.xlsx" --json-output reports/phase2_frontend_evidence.json --report-output reports/phase2_frontend_evidence.md
```

当前 recovery 结果为 `5,799/5,799 MATCH`。strict 模式中，两套前端都成功解析 5,792 条且 AST 全部一致；剩余 7 条均被双方拒绝，其中 6 条首个错误阶段一致，1 条因未加引号中文片段的检测顺序不同而表现为 lexer/parse 阶段差异。该差异不改变接受集合，也不产生 AST，因此作为非阻断诊断差异留档。

迁移门禁把 `AST_MISMATCH`、`ANTLR_REJECTED` 和 `HANDWRITTEN_REJECTED` 视为阻断项。只有双方都拒绝、但首错阶段不同的情况可以作为非阻断项，同时必须保留行号、输入 SHA-256 和两侧诊断供审计。

## 7. 性能解释

官方语料全量测量显示 ANTLR 前端 P95 低于项目 50 ms 编译预算，但明显慢于手写解析器。这符合生成型通用解析器的预期。影子模式用于迁移、回归和抽样审计，不应在生产请求中永久双跑。性能数字由本机单进程 Python 测得，只反映前端开销，不代表完整编译延迟，更不代表 Doris 查询耗时。

## 8. 差分开发发现的旧前端问题

差分期间发现 recovery 清洗器会把行尾半开区间 `[1,4)` 的右圆括号误判为多余括号。修复后，清洗器能够识别方括号开始、圆括号结束的合法范围，且官方 recovery 基线不下降。该修复有独立回归测试。

## 9. 回滚和切换原则

Phase 2 不切换默认前端。出现兼容问题时，调用方继续使用默认 `handwritten` 即可。未来切换到 ANTLR 前，应重新生成同一代码版本的证据，确认官方工作簿 SHA-256、迁移门禁、完整 pytest 和性能预算全部通过，并至少保留一个发布周期的手写前端回滚能力。

## 10. 证据边界

`5,799/5,799 MATCH` 证明 recovery 模式下两套语法前端得到相同 AST，不证明这些 AST 的金融含义全部正确。strict 编译覆盖率、SQL 行集正确率、缺失数据域、Doris 执行耗时和长周期加速比需要各自独立证据。项目禁止把语法兼容率改写成赛题正确率，也禁止把双方一致的错误解释成正确实现。
