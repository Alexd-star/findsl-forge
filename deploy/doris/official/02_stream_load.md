# 官方真实 CSV 数据 Stream Load 导入说明

本目录面向赛题 19 官方真实数据包，目标是把三张 CSV 导入 Apache Doris 的 `newzl` 数据库。Doris 官方推荐 Stream Load 通过 HTTP 将本地文件直接导入表，本项目采用该方式保留可复现命令。官方 `hsj_stock_hq_basic.csv` 中 `lastPx` 和 `preClosePx` 存在真实空值，因此 schema 将这两个字段设为可空；Stream Load 使用 `strict_mode:true` 与 `max_filter_ratio:0`，合法空值按 NULL 落库，同时任何类型转换失败或过滤行都会阻断装载。

推荐优先使用自动脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare_official_doris_evidence.ps1 `
  -OfficialRoot "<官方数据解压目录>"
```

脚本会启动/等待 Doris、重建官方表、Stream Load 三张 CSV、校验行数、构建 `04_feature_tables.sql`，并生成 `reports/official_doris_evidence.md` 与 JSON sidecar。下面的手工命令保留用于故障排查。

在本地 Docker Desktop 环境中，建议 Stream Load 直连 BE 映射出来的 `8040` 端口，而不是依赖 FE `8030` 端口重定向到容器内网地址。Doris 对 Stream Load 请求还要求 `Expect: 100-continue` 头；如果缺少该头，可能直接返回 `There is no 100-continue header`。本项目脚本已经按该约束设置默认参数。

官方资料根目录示例：

```powershell
$OfficialRoot = "<官方数据解压目录>"
```

连接参数：

```powershell
$FeHost = "127.0.0.1"
$HttpPort = 8030
$BeHttpPort = 8040
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
  -H "Expect: 100-continue" `
  -H "label: findsl_code_info_20260609_01" `
  -H "format: csv" `
  -H "column_separator:," `
  -H "skip_lines:1" `
  -H "strict_mode:true" `
  -H "timeout:7200" `
  -T $CodeInfo `
  "http://$FeHost`:$BeHttpPort/api/$Db/hsj_stock_code_info/_stream_load"

$HqBasic = Join-Path $OfficialRoot "Doris A股行情数据集\行情基本数据宽表\hsj_stock_hq_basic.csv"
curl.exe --location-trusted -u "$User`:$Password" `
  -H "Expect: 100-continue" `
  -H "label: findsl_hq_basic_20260609_01" `
  -H "format: csv" `
  -H "column_separator:," `
  -H "skip_lines:1" `
  -H "strict_mode:true" `
  -H "timeout:7200" `
  -T $HqBasic `
  "http://$FeHost`:$BeHttpPort/api/$Db/hsj_stock_hq_basic/_stream_load"

$HqExt = Join-Path $OfficialRoot "Doris A股行情数据集\行情衍生数据\hsj_stock_hq_ext.csv"
curl.exe --location-trusted -u "$User`:$Password" `
  -H "Expect: 100-continue" `
  -H "label: findsl_hq_ext_20260609_01" `
  -H "format: csv" `
  -H "column_separator:," `
  -H "skip_lines:1" `
  -H "strict_mode:true" `
  -H "timeout:7200" `
  -T $HqExt `
  "http://$FeHost`:$BeHttpPort/api/$Db/hsj_stock_hq_ext/_stream_load"
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
