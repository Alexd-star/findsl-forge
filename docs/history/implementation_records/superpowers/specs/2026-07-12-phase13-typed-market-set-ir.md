# Phase 13 Typed Market Set IR 与代码表质量审计

## 1. 官方合同与旧实现问题

赛题槽位说明允许在 `market` 中使用 `|`、`&`、`^` 连接多个市场，并把跨市场位运算列为编译器难点。旧后端按 `[|&]` 统一切分，正市场合并为一个代码列表，flag 条件全部相与。这会把 `科创板|创业板` 错误编译为两个 flag 同时为真，也无法表达 `沪|深&^创业板` 的结构。

新 IR 按常规集合代数定义：`^` 是一元补集，优先级最高；`&` 是交集；`|` 是并集。运算均为左结合。没有括号的官方字符串因此能得到唯一、可审计的语法树。

## 2. 原始数据质量

官方 `stock_schema_tables.md` 把 `kcbFlag` 和 `gemFlag` 标注为“无源 id，通过代码表计算”。实际 5,686 行代码表中，`kcbFlag`、`gemFlag`、`bShareFlag` 的真值数量均为 0，但证券代码分区清晰：

| 集合 | 受控条件 | 代码表数量 |
|---|---|---:|
| 科创板 | `mktcode=1` 且 `688000..688999` | 608 |
| 创业板 | `mktcode=0` 且 `300/301xxx` | 1,402 |
| 沪主板 | `mktcode=1` 且 `600/601/603/605xxx` | 1,726 |
| 深主板 | `mktcode=0` 且 `000/001/002/003xxx` | 1,503 |
| 北交所 | `mktcode=103` 且 `920xxx` | 307 |

项目不回写或修饰官方 CSV，而是在物理 catalog 层把上述规则作为受控集合定义。这样既保留原始数据可审计性，也避免全零 flag 造成系统性假阴性。

## 3. Domain 与 Logical IR

`MarketAtom` 只接受官方候选市场及项目已有组合别名。递归下降解析器实现以下文法：

```text
union        := intersection ('|' intersection)*
intersection := unary ('&' unary)*
unary        := '^' unary | market_atom
```

解析结果随 `BoundFunction` 和 `CallExpr` 进入 Logical IR。官方允许但当前 A 股数据不存在的港、美、日、韩等市场保留为合法 atom，到物理规划阶段返回 `PHYSICAL_MARKET_DATA_UNAVAILABLE`；它们不会被改写成 `1=0`。

## 4. Physical IR 与 SQLGlot

交易所级市场使用锚点资源的 `mktcode`。板块使用 `mktcode` 与六位 `tgtcode` 闭区间，所有列均为 catalog 稳定键，不需要连接质量有问题的 flag 列。`PhysicalNot` 只接受布尔操作数，后端通过 SQLGlot `Not` 节点渲染。

纯交易所并集在物理阶段合并为一个排序、去重的 `IN`，例如 `沪|深` 继续生成 `mktcode IN (0,1)`。含板块、补集或交集的表达式保留完整树形，避免过度化简改变补集全集。

## 5. 真实证据与边界

`scripts/collect_phase13_market_evidence.py` 同时采集 flag 真值、代码区间画像和五组完整行集哈希。科创板、创业板、沪深主板并集、`沪|深&^创业板`、`^沪&^深` 均与独立 reference SQL 一致。

迁移覆盖由 `183/1097` 提升到 `218/1097`。本阶段不处理 `filter_scope` 中的行业、概念和指数成员关系，因为官方数据没有对应成员表；也不把证券名称或 `hyBlkRefName` 当作概念成员关系的替代品。
