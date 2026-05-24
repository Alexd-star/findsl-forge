# Real-Market Quote Sample Evidence

- Passed: True
- Data directory: `D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\data\real_samples\eastmoney_a_share_sample`
- Source: Eastmoney public historical K-line endpoint
- Raw payload count: 2
- Cases passed: 3/3
- SQL rows total: 21
- Missing files: <none>
- Errors: <none>

This evidence uses a small public Eastmoney quote sample for business realism. It is not used as the Doris-scale performance claim.

| Scenario | Name | Passed | SQL rows | Reference rows | Missing keys | Extra keys |
|---|---|---:|---:|---:|---:|---:|
| real_quote_turnover | 真实行情样本：A股换手率高于0.3 | True | 9 | 9 | 0 | 0 |
| real_quote_return_rate | 真实行情样本：近2日收盘收益率为正 | True | 5 | 5 | 0 | 0 |
| real_quote_volume_sum | 真实行情样本：近3日成交量累计超过2000000 | True | 7 | 7 | 0 | 0 |