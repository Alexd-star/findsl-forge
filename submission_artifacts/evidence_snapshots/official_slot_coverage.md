# 官方槽位 DSL 编译覆盖率报告

本报告逐条读取官方 `选股提槽实例.xlsx`，先做语法解析，再尝试把可落地槽位编译为 `newzl` 三表上的 Doris SQL。它用于区分三类情况：语法可解析、可在本批官方三表落地、以及规范存在但当前官方数据没有对应字段。

## 覆盖率总览

- 编译模式：recovery

| 指标 | 数值 |
|---|---:|
| 官方样例总数 | 5799 |
| 主展示模式解析成功 | 5799 |
| 主展示模式编译成功 | 1830 |
| 严格解析成功 | 5792 |
| 严格解析失败 | 7 |
| 恢复解析成功 | 5799 |
| 恢复解析失败 | 0 |
| 发生源码修复 | 7 |
| 严格编译成功 | 1097 |
| 严格编译失败 | 4702 |
| 恢复编译成功 | 1830 |
| 恢复编译失败 | 3969 |
| 含 warning 的恢复结果 | 731 |
| 降级恢复结果 | 733 |
| 含 1=0 降级谓词 | 472 |
| 含 1=1 降级谓词 | 328 |
| 严格全量编译率 | 18.92% |
| 恢复全量编译率 | 31.56% |

兼容字段 `parse_ok/compile_ok` 暂时保留，均指 recovery 口径，不代表严格正确率。

## recovery 模式编译失败错误码

| 错误码 | 次数 |
|---|---:|
| UNSUPPORTED_OFFICIAL_INDICATOR | 3868 |
| OFFICIAL_TYPE_ERROR | 97 |
| UNSUPPORTED_OFFICIAL_COUNT_EXP | 3 |
| UNSUPPORTED_OFFICIAL_PERIOD_FUNCTION | 1 |

## 编译失败细分原因 TopN

| 原因 | 次数 |
|---|---:|
| UNSUPPORTED_OFFICIAL_INDICATOR: 成分股 | 165 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 跟踪指数 | 113 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 热门 | 104 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 主营业务 | 99 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 归母净利润 | 76 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 基金类型 | 76 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 上市日期 | 69 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 龙头股 | 63 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 归母净利润同比增长率 | 55 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 基金十大重仓股 | 52 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 股息率 | 48 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 已发布财报期 | 47 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 净利润同比增长率 | 44 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 分红金额 | 42 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 投资市场 | 42 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 净资产收益率 | 39 |
| OFFICIAL_TYPE_ERROR: Comparison = requires compatible operands, got string and numeric | 38 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 我的持仓股 | 36 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 营业收入同比增长率 | 35 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 潜力 | 29 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 优质 | 27 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 强势 | 27 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 波动率 | 26 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 龙虎榜上榜日期 | 25 |
| UNSUPPORTED_OFFICIAL_INDICATOR: MACD金叉 | 23 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 估值 | 23 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 基金公司 | 21 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 上市天数 | 20 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 规模 | 19 |
| UNSUPPORTED_OFFICIAL_INDICATOR: 我的自选股 | 18 |

## 缺失数据域分层

这一节把不能落地的官方样例按根因归类。它不是为失败找借口，而是区分“本批三张官方 A 股行情表没有该数据域”和“编译器函数语义仍需增强”两类问题，避免生成看似可执行但实际无字段来源的伪 SQL。

| 缺失或待增强类别 | 次数 |
|---|---:|
| 官方三表未覆盖的其他指标 | 1669 |
| 财务报表数据缺失 | 772 |
| 公司画像与题材热度数据缺失 | 383 |
| 指数成分与权重数据缺失 | 279 |
| 基金产品与持仓数据缺失 | 256 |
| 高级形态/相似度模型数据缺失 | 169 |
| 公司事件与交易日历扩展数据缺失 | 148 |
| 其他解析或编译问题 | 97 |
| 用户账户与自选股数据缺失 | 85 |
| 龙虎榜与交易异动数据缺失 | 54 |
| 交易规则与跨市场标的属性缺失 | 53 |
| 出现次数/连续次数时间语义待特征表增强 | 3 |
| 创新高低/位置函数复杂周期待增强 | 1 |

## 编译失败样本

| Excel 行 | 错误码 | 原因 | DSL |
|---:|---|---|---|
| 2 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 个人持有比例 | `indicator('深', '', '个人持有比例', '5日内', '', '', '') > 5% and indicator('深', '', '均线多头排列', '5日内', '', '', '') = True` |
| 3 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 基本每股收益 | `indicator('沪主板\|深主板\|新三板', '', '基本每股收益', '1周内', '', '', '') <= 22 * indicator('沪主板\|深主板\|新三板', '', '每手股数', '1周内', '', '', '') and indicator('沪主板\|深主板\|新三板', '', '周均线空头排列', '1周内', '', '', '') = True` |
| 4 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 资产回报率 | `rank('沪', '白酒行业', '资产回报率', 'desc', '最近一周', '', '', '') = 1 and indicator('沪', '白酒行业', '归母净利润', '', '', '', '') >= 0` |
| 5 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 上市日期 | `indicator('京\|深', '', '上市日期', '', '', '', '') > '21年' and indicator('京\|深', '', '上市日期', '', '', '', '') < queryData('京\|深', '300691', '上市日期', '', '') and indicator('京\|深', '', '跌幅', '上市次日', '', '', '') = 5% and indicator('京\|深', '', '历史最高价', '', '', '', '') > 15` |
| 6 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 预测市盈率 | `indicator('沪\|深\|京', '', '预测市盈率', '07年', '', '', '') > 100 and rank('沪\|深\|京', '', 'KDJ', 'desc', '07年', '', '', '') <= 5` |
| 7 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 基本每股收益同比增长率 | `indicator('沪\|深', '', '基本每股收益同比增长率', '11月18日', '期货', '', '') > 10% and indicator('沪\|深', '', '港股通标识', '11月18日', '期货', '', '') = True` |
| 8 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 净利润率 | `indicator('其他\|美', '', '净利润率', '今天', '', '', '') > 10 and rank('其他\|美', '', '主力净流入', 'desc', '本周的后3日', '', '', '') = 1` |
| 9 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: KDJ底背离 | `indicator('深主板', '', 'KDJ底背离', '00年', '债券', '', '') = True` |
| 10 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 除权除息日 | `indicator('港', '', '除权除息日', '', '私募基金', '', '') = '上周'` |
| 11 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 90%筹码集中度 | `indicator('', '', '90%筹码集中度', '2021年', '', '', '') > 50 and indicator('', '', '陆股通标识', '2021年', '', '', '') = True and indicator('', '', '主力净流入', '2021年', '', '', '') > 100000` |
| 12 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 资产总计 | `indicator('', '', '资产总计', '最近一周', '场内基金', '', '') > 15 and indicator('', '', '升水率', '最近一周', '场内基金', '', '') ~= 5%` |
| 14 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 股息率TTM | `indicator('沪', '', '股息率TTM', '07年', '场内基金', '', '') > 0.4% and indicator('沪', '', 'RSI', '07年', '场内基金', '', '') < 30` |
| 15 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 除权除息日 | `indicator('沪', '', '港股通标识', '', '', '', '') = True and indicator('沪', '', '除权除息日', '', '', '', '') >= '19年' and indicator('沪', '', '上穿压力位', '今天', '', '', '') = True` |
| 16 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 归母净利润同比增长率 | `rank('沪主板', '', '归母净利润同比增长率', 'desc', '五年之内', '', 'MIN', '') <= 10` |
| 17 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 销售净利率 | `indicator('沪\|深\|京', '', '销售净利率', '', '', '', '') < 10% and indicator('沪\|深\|京', '', '相似K线', '', '', '', '') = '沪上阿姨'` |
| 19 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 复牌日期 | `indicator('', '', '复牌日期', '', '期货', '', '') < '2007年' and indicator('', '', '内盘', '零六年', '期货', '', '') / indicator('', '', '每手股数', '零六年', '期货', '', '') < 6000000` |
| 21 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 净资产收益率 | `belong_industry('沪\|深', '', '净资产收益率', '半年之内', '') ~= 5%` |
| 22 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 主营业务 | `indicator('深', '', '主营业务', '上个月', '', '', '') ~= queryData('', '英伟达', '主营业务', '上个月', '') then rank('深', '', '个人持有比例', 'desc', '上个月', '', '', '') <= 10` |
| 23 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 复牌日期 | `indicator('深', '', '复牌日期', '', '可转债', '', '') > '本周' and (indicator('深', '', '投资市场', '', '可转债', '', '') = '港股' or indicator('深', '', '投资市场', '', '可转债', '', '') = '美股')` |
| 24 | UNSUPPORTED_OFFICIAL_INDICATOR | Official indicator is not mapped to the provided three-table dataset: 我的持仓股 | `indicator('', '', '我的持仓股', '', '', '', '') = True and indicator('', '', '利润总额', '上月', '', '', '') > 3000 and indicator('', '', '上穿压力位', '上月', '', '', 'EXIST=3日') = True and indicator('', '', '主力抢筹', '上月', '', '', '') = True` |

## recovery 编译返回样本（含降级状态）

| Excel 行 | 严格成功 | repair | warning 数 | 依赖表 | SQL 预览 |
|---:|---|---|---:|---|---|
| 13 | true | 无 | 0 | hsj_stock_hq_basic, hsj_stock_hq_ext | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode LEFT JOIN newzl.hsj_stock_hq_ext AS ext ON ext.mktcode = base.mktcode AND ext.tgtcode = base.tgtcode AND ext.bizdate = base.bizdate WHERE ((ext.riseSpd3m / 10000.0) > 5 AND EXISTS (   SELECT 1 FROM (     SELECT rb.mktcode, rb.tgtcode, rb.bizdate,            ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY (rb.lastPx / 10000.0) DESC, rb.tgtcode ASC) AS rank_no,            COUNT(*) OVER (PART` |
| 18 | false | 无 | 2 | hsj_stock_hq_basic, hsj_stock_code_info | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (code.hkConnFlag = TRUE AND (base.highPx / 10000.0) < 200.7) AND 1=0 AND base.bizdate BETWEEN '2000-01-01' AND '2000-12-31'` |
| 20 | false | 无 | 1 | hsj_stock_hq_basic, hsj_stock_hq_ext | `SELECT * FROM (   SELECT base.mktcode, base.tgtcode, base.bizdate, code.name,          ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY (ext.riseSpd3m / 10000.0) ASC, base.tgtcode ASC) AS rank_no,          COUNT(*) OVER (PARTITION BY base.bizdate) AS partition_count   FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode LEFT JOIN newzl.hsj_stock_hq_ext AS ext ON ext.mktcode = base.mktcode AND ext.tgtcode = base.tgtcode AND ext.bizdate = base.bizdate   WHERE (ext.riseSpd3m / 10000.0) < (ext.riseSpd3` |
| 29 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (EXISTS (   SELECT 1   FROM newzl.hsj_stock_hq_basic AS lb     LEFT JOIN newzl.hsj_stock_code_info AS lc ON lc.mktcode = lb.mktcode AND lc.tgtcode = lb.tgtcode   WHERE lb.mktcode = base.mktcode AND lb.tgtcode = base.tgtcode AND (lb.amplitude / 10000.0) > 5 AND lb.mktcode IN (1, 103) AND (lc.hyBlkRefName = '鸡肉概念\|家电类' OR lc.name = '鸡肉概念\|家电类') AND lb.bizdate BETWEEN '2005-01-01' AND '2005-1` |
| 37 | true | 无 | 0 | hsj_stock_hq_basic, hsj_stock_hq_ext, hsj_stock_hq_basic_technical | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode LEFT JOIN newzl.hsj_stock_hq_ext AS ext ON ext.mktcode = base.mktcode AND ext.tgtcode = base.tgtcode AND ext.bizdate = base.bizdate LEFT JOIN newzl.hsj_stock_hq_basic_technical AS tech ON tech.mktcode = base.mktcode AND tech.tgtcode = base.tgtcode AND tech.bizdate = base.bizdate WHERE ((ext.bigSellTur > 10000000000 AND (base.upperShadow / 10000.0) > 0) AND tech.volume_avg_60 > 5000000) AND cod` |
| 39 | false | 无 | 1 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (base.closePx / 10000.0) = 5 AND base.mktcode IN (0, 1) AND code.gemFlag = TRUE AND 1=0 AND base.bizdate BETWEEN '2026-01-15' AND '2026-04-14'` |
| 53 | false | 无 | 3 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE ((SELECT MAX(run_length) > 3  FROM (    SELECT run_group, COUNT(*) AS run_length    FROM (      SELECT matched.bizdate,             DATEDIFF(matched.bizdate, '1970-01-01') - ROW_NUMBER() OVER (ORDER BY matched.bizdate) AS run_group      FROM (        SELECT DISTINCT wb.bizdate        FROM newzl.hsj_stock_hq_basic AS wb     LEFT JOIN newzl.hsj_stock_code_info AS wc ON wc.mktcode = wb.mktc` |
| 56 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (EXISTS (   SELECT 1   FROM newzl.hsj_stock_hq_basic AS lb     LEFT JOIN newzl.hsj_stock_code_info AS lc ON lc.mktcode = lb.mktcode AND lc.tgtcode = lb.tgtcode   WHERE lb.mktcode = base.mktcode AND lb.tgtcode = base.tgtcode AND (lb.dynPE / 10000.0) > 0.05 AND lb.mktcode IN (1) AND lb.bizdate BETWEEN '2026-04-11' AND '2026-04-14' ) AND EXISTS (   SELECT 1   FROM newzl.hsj_stock_hq_basic A` |
| 58 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE ((EXISTS (   SELECT 1   FROM newzl.hsj_stock_hq_basic AS lb     LEFT JOIN newzl.hsj_stock_code_info AS lc ON lc.mktcode = lb.mktcode AND lc.tgtcode = lb.tgtcode   WHERE lb.mktcode = base.mktcode AND lb.tgtcode = base.tgtcode AND (lc.shConnFlag = TRUE AND (lb.staticPE / 10000.0) > 15) AND lb.bizdate BETWEEN '2017-01-01' AND '2017-12-31' ) AND EXISTS (   SELECT 1   FROM newzl.hsj_stock_hq_` |
| 65 | false | 无 | 1 | hsj_stock_hq_basic | `SELECT * FROM (   SELECT base.mktcode, base.tgtcode, base.bizdate, code.name,          ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY base.listedShare DESC, base.tgtcode ASC) AS rank_no,          COUNT(*) OVER (PARTITION BY base.bizdate) AS partition_count   FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode   WHERE base.mktcode IN (0) AND (code.hyBlkRefName = '金属管件制品' OR code.name = '金属管件制品') AND 1=0 AND base.bizdate BETWEEN '2006-01-01' AND '2012-12-31' ) AS ranked WHERE ranked.rank_no <= 10` |
| 71 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT * FROM (   SELECT base.mktcode, base.tgtcode, base.bizdate, code.name,          ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY base.totalShare ASC, base.tgtcode ASC) AS rank_no,          COUNT(*) OVER (PARTITION BY base.bizdate) AS partition_count   FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode   WHERE base.mktcode IN (0, 1, 103) AND (code.hyBlkRefName = '算力' OR code.name = '算力') ) AS ranked WHERE ranked.rank_no <= 10` |
| 79 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT * FROM (   SELECT base.mktcode, base.tgtcode, base.bizdate, code.name,          ROW_NUMBER() OVER (PARTITION BY base.bizdate ORDER BY (SELECT MIN(((wb.lastPx / 10000.0) * wb.totalShare))  FROM newzl.hsj_stock_hq_basic AS wb  WHERE wb.mktcode = base.mktcode AND wb.tgtcode = base.tgtcode) DESC, base.tgtcode ASC) AS rank_no,          COUNT(*) OVER (PARTITION BY base.bizdate) AS partition_count   FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode   WHERE (code.hyBlkRefName = '家居日用品' OR code.name = ` |
| 81 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE base.totalShare > 50000000000 AND base.mktcode IN (0) AND base.bizdate BETWEEN '2018-01-01' AND '2018-12-31'` |
| 83 | false | 无 | 1 | hsj_stock_hq_basic, hsj_stock_hq_ext | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode LEFT JOIN newzl.hsj_stock_hq_ext AS ext ON ext.mktcode = base.mktcode AND ext.tgtcode = base.tgtcode AND ext.bizdate = base.bizdate WHERE ext.ZJLXMainNetTur > 50000000 AND base.mktcode IN (0, 1, 103) AND (code.hyBlkRefName = '上证180动量指数' OR code.name = '上证180动量指数') AND 1=0` |
| 84 | true | 无 | 0 | hsj_stock_hq_basic, hsj_stock_code_info | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (EXISTS (   SELECT 1 FROM (     SELECT rb.mktcode, rb.tgtcode, rb.bizdate,            ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY (rb.pBR / 10000.0) ASC, rb.tgtcode ASC) AS rank_no,            COUNT(*) OVER (PARTITION BY rb.bizdate) AS partition_count     FROM newzl.hsj_stock_hq_basic AS rb     LEFT JOIN newzl.hsj_stock_code_info AS rcode ON rcode.mktcode = rb.mktcode AND rcode.t` |
| 97 | false | 无 | 2 | hsj_stock_hq_basic, hsj_stock_hq_basic_technical | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode LEFT JOIN newzl.hsj_stock_hq_basic_technical AS tech ON tech.mktcode = base.mktcode AND tech.tgtcode = base.tgtcode AND tech.bizdate = base.bizdate WHERE (base.lastPx / 10000.0) > tech.ma250 AND base.mktcode IN (0, 1) AND (code.hyBlkRefName = '^aigc' OR code.name = '^aigc') AND 1=1` |
| 99 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE ((base.dynPE / 10000.0) > 20 AND EXISTS (   SELECT 1 FROM (     SELECT rb.mktcode, rb.tgtcode, rb.bizdate,            ROW_NUMBER() OVER (PARTITION BY rb.bizdate ORDER BY (rb.dynPE / 10000.0) DESC, rb.tgtcode ASC) AS rank_no,            COUNT(*) OVER (PARTITION BY rb.bizdate) AS partition_count     FROM newzl.hsj_stock_hq_basic AS rb     LEFT JOIN newzl.hsj_stock_code_info AS rcode ON rco` |
| 101 | true | 无 | 0 | hsj_stock_hq_basic, hsj_stock_code_info | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (code.name LIKE '%科技%' AND ((base.commissionBuy - base.commissionSale) * 100.0 / NULLIF(base.commissionBuy + base.commissionSale, 0)) > 10) AND base.mktcode IN (0) AND base.bizdate BETWEEN '2016-01-01' AND '2016-12-31'` |
| 108 | true | 无 | 0 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (EXISTS (   SELECT 1   FROM newzl.hsj_stock_hq_basic AS lb     LEFT JOIN newzl.hsj_stock_code_info AS lc ON lc.mktcode = lb.mktcode AND lc.tgtcode = lb.tgtcode   WHERE lb.mktcode = base.mktcode AND lb.tgtcode = base.tgtcode AND (SELECT COUNT(*) > 50  FROM newzl.hsj_stock_hq_basic AS wb     LEFT JOIN newzl.hsj_stock_code_info AS wc ON wc.mktcode = wb.mktcode AND wc.tgtcode = wb.tgtcode  W` |
| 112 | false | 无 | 2 | hsj_stock_hq_basic | `SELECT base.mktcode, base.tgtcode, base.bizdate, code.name FROM newzl.hsj_stock_hq_basic AS base LEFT JOIN newzl.hsj_stock_code_info AS code ON code.mktcode = base.mktcode AND code.tgtcode = base.tgtcode WHERE (EXISTS (   SELECT 1   FROM newzl.hsj_stock_hq_basic AS lb     LEFT JOIN newzl.hsj_stock_code_info AS lc ON lc.mktcode = lb.mktcode AND lc.tgtcode = lb.tgtcode   WHERE lb.mktcode = base.mktcode AND lb.tgtcode = base.tgtcode AND (((lb.lastPx - lb.preClosePx) * 100.0 / NULLIF(lb.preClosePx, 0)) >= 8 AND (SELECT MAX(run_length) >= 3  FROM (    SELECT run_group, COUNT(*) AS run_length    FRO` |