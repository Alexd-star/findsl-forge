# SQL Equivalence Verification

- Passed: True
- SQL rows: 2
- Reference rows: 2
- Missing keys: 0
- Extra keys: 0

## DSL

```text
then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))
```

## SQL

```sql
WITH stage1 AS (SELECT * FROM (SELECT base_features.*, SUM(CASE WHEN main_net_inflow > 0 THEN 1 ELSE 0 END) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS __roll_1 FROM (SELECT base.*, mf.main_net_inflow AS main_net_inflow, su.market AS market FROM dwd_stock_daily_quote AS base LEFT JOIN dwd_stock_money_flow AS mf USING (ts_code, trade_date) LEFT JOIN dim_stock_universe AS su USING (ts_code, trade_date)) base_features) rolling_features_1 WHERE (market = 'A' AND __roll_1 = 3)), stage2 AS (SELECT * FROM (SELECT base.*, ROW_NUMBER() OVER (PARTITION BY trade_date ORDER BY turnover_rate DESC, ts_code ASC) AS rank_no FROM (SELECT base.ts_code AS ts_code, base.trade_date AS trade_date, base.close AS close, base.turnover_rate AS turnover_rate, base.volume AS volume, base.main_net_inflow AS main_net_inflow, base.market AS market FROM stage1 AS base) AS base WHERE turnover_rate IS NOT NULL) ranked WHERE rank_no <= 100) SELECT * FROM stage2
```

## Differences

| Type | ts_code | trade_date |
|---|---|---|
| none |  |  |