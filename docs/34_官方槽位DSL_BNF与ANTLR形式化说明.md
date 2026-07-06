# 官方槽位 DSL BNF 与 ANTLR 形式化说明

生成时间：2026-07-06

## 1. 编写目的

本文档用于把当前项目中的官方槽位 DSL 解析规则写成可审计、可答辩、可迁移的形式化材料。项目运行时仍使用 `src/findsl/official_slot.py` 中经过测试的递归下降解析器；新增的 `docs/grammar/OfficialSlot.g4` 是该解析器的 ANTLR 风格镜像，用来说明语法边界、优先级和后续迁移方向，并不表示项目已经把生产解析器切换为 ANTLR。

这种做法比较稳妥。比赛现场如果评委问“你的 DSL 语法是不是随手写的”，我们可以指出三层证据：第一，官方 `选股提槽说明.txt` 明确要求 DSL 使用候选函数、`and/or/then`、括号、`between`、`limit` 和四则运算；第二，项目在 `OfficialSlotParser` 中按优先级实现了完整解析链；第三，本文把同一套规则整理成 BNF/ANTLR 形式，方便审计人员不读 Python 也能看懂语法结构。

## 2. 官方 DSL 语法边界

官方槽位 DSL 是“函数调用 + 比较表达式 + 逻辑连接”的类 SQL 表达式，不是自由 SQL。它允许的核心函数包括 `indicator`、`rank`、`belong_industry`、`queryData`、`cross_above`、`cross_down`、`close_together`、`reset`、`golden_cross`、`record_high`、`record_low`、`position`。函数参数本身多数是字符串槽位，例如市场、范围、指标名、日期、标的类型、聚合函数和 `count_exp`。

语法层只负责判断“表达式能否形成语法树”。它不会在词法阶段判断“归母净利润是否存在于官方三表”，也不会在语法阶段判断“成分股是否有指数成分表”。这些属于语义层和数据域审计层。项目刻意把语法、语义、数据可落地性分开，是为了避免把缺数据的问题伪装成解析成功，更避免把缺字段意图硬编译为假 SQL。

## 3. BNF 描述

下面是当前实现对应的简化 BNF。尖括号表示非终结符，单引号表示字面量，`*` 表示可重复，`?` 表示可选。

```bnf
<program> ::= <limit-expression> EOF

<limit-expression> ::= <then-expression> [ "limit" <signed-int> "," <signed-int> ]

<then-expression> ::= <or-expression> { "then" <or-expression> }

<or-expression> ::= <and-expression> { "or" <and-expression> }

<and-expression> ::= <comparison-expression> { "and" <comparison-expression> }

<comparison-expression> ::=
      <additive-expression> "between" <range-literal>
    | <additive-expression> <comparison-operator> <additive-expression>
    | <additive-expression>

<comparison-operator> ::= ">=" | "<=" | "!=" | "~=" | "=" | ">" | "<"

<additive-expression> ::= <multiplicative-expression>
                          { ("+" | "-") <multiplicative-expression> }

<multiplicative-expression> ::= <primary-expression>
                                { ("*" | "/") <primary-expression> }

<primary-expression> ::=
      "(" <then-expression> ")"
    | <function-call>
    | <literal>
    | <identifier>

<function-call> ::= <identifier> "(" [ <argument-list> ] ")"

<argument-list> ::= <then-expression> { "," <then-expression> }

<range-literal> ::=
      ("[" | "(") <additive-expression> "," <additive-expression> ("]" | ")")
    | <string-range>

<literal> ::= <string> | <percent> | <signed-number> | "True" | "False"
```

这套优先级与代码一致：`limit` 最外层，`then` 低于 `or`，`or` 低于 `and`，`and` 低于比较，比较低于加减，加减低于乘除，括号可以提升优先级。这样可以正确表达“先筛选再排名”“分支条件后再排名”“指标之间四则运算后比较”等官方样例中常见的结构。

## 4. ANTLR 文件说明

ANTLR 风格语法文件位于：

```text
docs/grammar/OfficialSlot.g4
```

该文件只描述语法结构，不加载官方指标表，不连接 Doris，也不决定某个指标是否能落地。它与 `OfficialSlotParser` 的关系如下：

| 项目 | 当前实现 | 形式化文件 |
|---|---|---|
| 运行时解析器 | `src/findsl/official_slot.py::OfficialSlotParser` | 不参与运行 |
| 词法输入 | 单引号/双引号字符串、数字、百分号、布尔值、关键字、操作符 | `STRING`、`NUMBER`、`PERCENT`、`TRUE/FALSE`、关键字 token |
| 语法优先级 | `_parse_limit -> _parse_then -> _parse_or -> _parse_and -> _parse_comparison -> _parse_additive -> _parse_multiplicative -> _parse_primary` | `limitExpression -> thenExpression -> orExpression -> andExpression -> comparisonExpression -> additiveExpression -> multiplicativeExpression -> primaryExpression` |
| 语义校验 | Python 编译器负责 | 不负责 |
| 后续价值 | 已测试、稳定、便于快速修补官方脏数据 | 便于答辩说明、审计阅读、未来迁移 |

如果后续要真正迁移到 ANTLR，建议按“只迁移语法层，不改语义层”的方式做。也就是说，ANTLR 负责输出等价 AST，后续仍复用现有 `OfficialSlotCompiler` 的指标映射、日期归一化、`count_exp` 编译和缺失数据域诊断。这样迁移风险最小，也不会让语法工具替代金融语义判断。

## 5. `count_exp` 的形式化边界

官方规范把 `count_exp` 定义为候选函数的一个字符串槽位，形式为：

```text
CONS/EXIST + 逻辑符号 + 次数 + 单位
```

其中 `CONS` 表示连续出现，`EXIST` 表示出现次数；逻辑符号包括 `>`、`>=`、`=`、`<=`、`<`、`!=`；次数可以是数字或“每”；单位主要是年、季度、月、周、日。项目在语法层不把 `CONS=3日` 作为独立语法节点解析，因为它本来就是函数参数中的字符串。真正解释 `count_exp` 的位置是 `src/findsl/official_slot.py::_parse_count_exp_rule()`。

本轮补强后，项目已经支持普通整数次数、区间次数、连续区间、`CONS=每日`、`EXIST>=3日`、半年度归一到月桶等可由日频官方三表解释的场景。对于 `CONS=10分钟` 这类分钟级表达，当前官方数据没有逐分钟序列；对于没有排名指标的 `rank(..., count_exp)`，系统无法定义排序依据；对于营业收入、预测营业收入等财务/预测指标，官方三表没有字段来源。此类情况不应通过语法层“放宽”来伪造成功。

## 6. 与测试证据的对应关系

当前语法层的核心证据包括：

| 语法能力 | 测试或报告证据 |
|---|---|
| 单引号、双引号、百分数、布尔值 | `tests/test_official_slot.py` |
| `and/or/then` 与括号优先级 | `tests/test_official_slot.py`、官方 workbook 覆盖率 |
| `between '[1,5)'` 与未加引号范围 | `tests/test_official_slot.py` |
| `limit x,y` | `tests/test_official_slot.py` |
| 官方 Excel 7 条标点噪声归档修复 | `test_parse_official_slot_tolerates_documented_workbook_punctuation_noise` |
| 全量官方 workbook 解析 | `reports/official_slot_coverage.md`，当前 `5799/5799` 可解析 |

这说明当前项目的解析层已经不再是“能跑几个样例”的状态，而是对官方 5799 条真实槽位语料完成了全量语法读取。后续如果继续提升覆盖率，重点不应是继续放宽语法，而是补充真实数据域、物化特征表和高价值语义编译路径。

## 7. 答辩解释口径

答辩时可以这样解释：

“我们没有让大模型直接生成 SQL，而是先让输入进入受控 DSL。官方 DSL 的语法被实现为递归下降解析器，并用 BNF/ANTLR 形式化材料复核了优先级和表达边界。解析成功只说明语法可读，后面还会经过语义校验和数据域校验。只要官方三表没有对应字段，系统不会为了覆盖率生成伪 SQL，而是输出结构化错误码和缺失数据域分类。这一点是金融场景里比表面覆盖率更重要的可审计性。”

