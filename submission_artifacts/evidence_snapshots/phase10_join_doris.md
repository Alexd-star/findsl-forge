# Phase 10 多资源稳定键连接真实 Doris 证据

- 状态：`PASS`
- Git HEAD：`94b84d1a0a7eec9d7f6c6d53962d08eb392b1dcc`
- Doris FE 版本：`doris-4.1.0-rc03-5960d4cea0e`
- MySQL 协议兼容版本：`5.7.99`
- 最新交易日：`2026-04-14`
- 行集哈希一致：`5/5`

| 场景 | 资源数 | 预期行数 | 实际行数 | 哈希一致 | P95 ms |
|---|---:|---:|---:|---|---:|
| basic_ext_latest | 2 | 2247 | 2247 | 是 | 944.1888 |
| basic_security_latest | 2 | 5573 | 5573 | 是 | 448.6873 |
| ext_security_latest | 3 | 2247 | 2247 | 是 | 652.9388 |
| basic_ext_security_latest | 3 | 2247 | 2247 | 是 | 662.1033 |
| basic_technical_latest | 2 | 5573 | 5573 | 是 | 1807.9418 |

> reference SQL 由人工定义的关系连接模板生成，只使用 catalog 声明的稳定键；编译器 SQL 独立经过 ANTLR/Typed AST/Logical IR/Physical IR/SQLGlot 路径生成。两侧均在同一 Doris 数据快照执行，并比较排序无关的完整结果行集 SHA-256。
