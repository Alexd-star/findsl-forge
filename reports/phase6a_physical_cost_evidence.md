# Phase 6A Doris 真实统计成本模型证据

- 状态：`PASS`
- 实现 Git HEAD：`1e80fb49eb085f3779befaf03ffc6f0d4299856a`
- 物理目录指纹：`c6fdb31e9e8f8dee4af42e802eaf477ec60449f47633feabc7760989a1f804d4`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- 自动测试：`522 passed`

## 真实资源统计

| 资源 | 行数 | 存储字节 | 行数可用 |
|---|---:|---:|---|
| official_basic | 13650347 | 411096318 | True |
| official_ext | 6170822 | 306901418 | True |
| official_security | 5686 | 303691 | True |
| official_technical | 13650347 | 1409823015 | True |

## 代表计划成本

| 场景 | 资源 | 成本（bytes） | 估算 | 组成 |
|---|---|---:|---|---|
| basic | official_basic | 411096318 | False | official_basic:411096318 |
| ext | official_ext | 717997736 | False | official_ext:306901418 + official_basic:411096318 |
| security | official_security | 411400009 | False | official_security:303691 + official_basic:411096318 |
| technical | official_technical | 1820919333 | False | official_technical:1409823015 + official_basic:411096318 |

> 成本只表示目录声明的主资源与锚资源存储字节之和；不使用未知选择率，也不等同于查询延迟。缺失统计时必须回退为 catalog_priority，并标记 estimated=true。
