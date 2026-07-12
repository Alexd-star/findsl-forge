# Phase 12 最近 N 个交易日集合设计

## 1. 两类“最近 N 日”不能混用

同一句“最近 5 日”在不同算子中有两种合同。普通指标筛选关心交易所最近五个交易日；`CONS/EXIST` 则需要按每只股票的交易记录序列判断连续或存在次数。停牌股票可能缺少某日记录，因此两者不能共享同一个窗口实现。

本阶段只处理 scalar indicator/rank 日期槽的全局交易日范围。Phase 9 的时序节点继续按股票分区使用记录序号，不受本阶段改写影响。

## 2. PhysicalRecentSessions

`PhysicalRecentSessions` 是布尔物理表达式，包含资源、分区日期列和正整数 N。它表示当前行日期是否属于基础行情表最近 N 个不同交易日。验证器要求列名等于资源 catalog 的 `partition_key`，并拒绝零或负数。

后端生成的关系形式为：

```sql
base.bizdate IN (
  SELECT calendar_sessions.bizdate
  FROM newzl.hsj_stock_hq_basic AS calendar_sessions
  GROUP BY calendar_sessions.bizdate
  ORDER BY calendar_sessions.bizdate DESC
  LIMIT N
)
```

查询按真实数据快照取交易日，不依赖操作系统当前时间，也不使用自然日减法。春节、国庆、周末和临时休市不会被误算成交易记录。

## 3. 与其他日期节点的关系

- `PhysicalLatestValue`：最新一个交易日。
- `PhysicalNthLatestValue`：倒数第 N 个单一交易日，例如昨天、前天。
- `PhysicalRecentSessions`：最近 N 个交易日的集合。
- `PhysicalTemporalWindow(recent_sessions)`：每只股票最近 N 条记录，用于 `CONS/EXIST`。

四个节点保留独立类型和验证规则，避免后续优化器在没有证明的情况下互换。

## 4. 真实 Doris 证据

`scripts/collect_phase12_session_evidence.py` 独立读取最近 30 个不同交易日，把前 5、10、30 个日期展开成 reference SQL 的显式 `IN` 集合，再与编译器生成的子查询结果比较完整行集 SHA-256。三个案例均为 `PASS`，对应行数分别为 467、993 和 3923。

官方迁移覆盖由 `163/1097` 提升到 `183/1097`。剩余日期缺口主要是动态本周/本月/本年、日历周/月范围、相对日期算术，以及日期合同与 rank、aggregate、temporal 的组合。
