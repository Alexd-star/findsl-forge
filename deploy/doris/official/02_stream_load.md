# 官方真实 CSV 数据 Stream Load 导入说明

本目录面向赛题 19 官方真实数据包，目标是把三张 CSV 导入 Apache Doris 的 `newzl` 数据库。Doris 官方推荐 Stream Load 通过 HTTP 将本地文件直接导入表，本项目采用该方式保留可复现命令。

官方资料根目录示例：

```powershell
$OfficialRoot = "D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
```

连接参数：

```powershell
$FeHost = "127.0.0.1"
$HttpPort = 8030
$User = "root"
$Password = ""
$Db = "newzl"
```

导入前先执行：

```powershell
mysql --host=$FeHost --port=9030 --user=$User --password=$Password < .\deploy\doris\official\01_schema.sql
```

三张表导入命令如下。`label` 必须唯一，重复导入时请改时间戳或先检查导入状态。

```powershell
$CodeInfo = Join-Path $OfficialRoot "Doris A股行情数据集\股票代码表\hsj_stock_code_info.csv"
curl.exe --location-trusted -u "$User`:$Password" `
  -H "label: findsl_code_info_20260609_01" `
  -H "format: csv" `
  -H "column_separator: ," `
  -H "skip_lines: 1" `
  -T $CodeInfo `
  "http://$FeHost`:$HttpPort/api/$Db/hsj_stock_code_info/_stream_load"

$HqBasic = Join-Path $OfficialRoot "Doris A股行情数据集\行情基本数据宽表\hsj_stock_hq_basic.csv"
curl.exe --location-trusted -u "$User`:$Password" `
  -H "label: findsl_hq_basic_20260609_01" `
  -H "format: csv" `
  -H "column_separator: ," `
  -H "skip_lines: 1" `
  -T $HqBasic `
  "http://$FeHost`:$HttpPort/api/$Db/hsj_stock_hq_basic/_stream_load"

$HqExt = Join-Path $OfficialRoot "Doris A股行情数据集\行情衍生数据\hsj_stock_hq_ext.csv"
curl.exe --location-trusted -u "$User`:$Password" `
  -H "label: findsl_hq_ext_20260609_01" `
  -H "format: csv" `
  -H "column_separator: ," `
  -H "skip_lines: 1" `
  -T $HqExt `
  "http://$FeHost`:$HttpPort/api/$Db/hsj_stock_hq_ext/_stream_load"
```

导入后执行：

```powershell
mysql --host=$FeHost --port=9030 --user=$User --password=$Password < .\deploy\doris\official\03_smoke_queries.sql
mysql --host=$FeHost --port=9030 --user=$User --password=$Password < .\deploy\doris\official\04_feature_tables.sql
```

通过标准：

- `hsj_stock_code_info` 行数应为 5686；
- `hsj_stock_hq_basic` 行数应为 13650347；
- `hsj_stock_hq_ext` 行数应为 6170822；
- `hsj_stock_hq_basic` 日期范围应覆盖 2015-01-05 至 2026-04-14；
- `hsj_stock_hq_ext` 日期范围应覆盖 2019-06-06 至 2026-04-14；
- smoke SQL 可以返回结果且 `EXPLAIN` 能看到对 `newzl` 三表的访问计划。

参考资料：

- Apache Doris Stream Load: https://doris.apache.org/docs/dev/data-operate/import/import-way/stream-load-manual/
- Apache Doris Unique Key: https://doris.apache.org/docs/dev/table-design/data-model/unique/
