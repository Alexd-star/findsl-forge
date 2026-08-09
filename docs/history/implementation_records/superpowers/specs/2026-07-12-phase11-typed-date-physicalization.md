# Phase 11 Typed Date IR 与交易日偏移设计

## 1. 设计目标

日期不是普通字符串。选股问句中的“2024年”“2024年8月”“昨天”和“近5日”分别对应日历范围、单个交易日和交易记录窗口，如果物理层临时用正则猜测，很容易把节假日、月份边界或中文数字解释错。

本阶段把确定性最强的日期合同完整贯通到物理层：明确年份、明确年月、明确日期、最新交易日和向前 N 个交易日。最近 N 个交易日范围、动态本周/本月/本年以及相对日期算术仍单独保留，不在本阶段用日历天近似。

## 2. Typed Date 合同

领域绑定器统一输出 `DateConstraint`：

| 输入类别 | IR kind | 示例 |
|---|---|---|
| 最新交易日 | `relative(today)` | 今天、今日、当天、现在 |
| 交易日偏移 | `relative_session` | 昨天、昨日、前天、前一个交易日 |
| 明确日期 | `exact` | 2011年3月25日、2024-08-01 |
| 明确年月 | `calendar_range(month)` | 2024年8月 |
| 明确年份 | `calendar_range(year)` | 2024年、二四年 |
| 最近交易记录 | `recent_sessions` | 近5日、10个交易日内 |
| 最近日历范围 | `recent_calendar` | 两年内、近三月 |

`CallExpr` 保存已绑定 `DateConstraint`，因此 Logical IR、Physical IR 和审计 JSON 能看到同一份日期语义。旧版本手工构造且没有 typed contract 的 CallExpr 才会调用同一公共解析函数作为兼容兜底。

## 3. 日历边界

明确年份生成闭区间 `YYYY-01-01` 至 `YYYY-12-31`。明确月份使用标准公历计算月末，包含闰年二月。明确日期在绑定时校验真实月日；例如 `2024年13月` 和 `2024年2月30日` 以 `DOMAIN_DATE_INVALID` 终止，不能进入 SQL 后端。

两位年份沿用官方语料口径：`00` 至 `26` 映射到 2000 至 2026，其他两位数映射到 1900 年代。四位年份只接受当前合同允许的 1990 至 2100 范围；超出范围的表达保留为未物理化日期，而不是静默截断。

## 4. 交易日偏移

自然日减一天不能代表上一交易日。周一的上一交易日通常是周五，春节前后的间隔更长。`PhysicalNthLatestValue` 因此查询基础行情表中的不同 `bizdate`：

```sql
SELECT q_session.bizdate
FROM newzl.hsj_stock_hq_basic AS q_session
GROUP BY q_session.bizdate
ORDER BY q_session.bizdate DESC
LIMIT 1 OFFSET n
```

昨天使用 `n=1`，前天使用 `n=2`。节点只能引用资源的 catalog `partition_key`，offset 必须大于零。该子查询完全由 SQLGlot AST 构造，不存在 Raw SQL 逃生口。

## 5. 证据与边界

`scripts/collect_phase11_date_evidence.py` 先从真实 Doris 独立读取最近三个交易日，再将显式日期 reference SQL 与编译器 SQL 的完整结果行集进行 SHA-256 对比。年份、月份、日期、昨天和前天五组均为 `PASS`。

官方迁移漏斗由 `135/1097` 提升到 `163/1097`。剩余日期缺口主要是最近 N 个交易日范围、动态本周/本月/本年、相对日期表达式和它们与 rank/aggregate/temporal 的组合。这些合同需要关系窗口节点，不能继续堆等值日期谓词。
