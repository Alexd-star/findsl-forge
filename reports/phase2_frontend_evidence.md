# ANTLR 影子前端官方语料差分证据

- 官方语料：`5799` 条
- 输入 SHA-256：`b5603a9bf9db60a76abe46ec6360c4ab09e26e5c10fac3c9dbccd92615963623`
- Git HEAD：`a76ac80f28f5303a2e8a500ba246fd01e3b32f58`
- ANTLR runtime：`4.13.2`
- 迁移门禁：`PASS`
- 阻断差异：`0`
- 仅诊断阶段差异：`1`

## strict 模式

- 手写前端解析成功：`5792`
- ANTLR 前端解析成功：`5792`
- 手写前端 P95：`0.2454` ms
- ANTLR 前端 P95：`6.5797` ms

| 差分分类 | 数量 |
|---|---:|
| ERROR_MATCH | 6 |
| ERROR_MISMATCH | 1 |
| MATCH | 5792 |

## recovery 模式

- 手写前端解析成功：`5799`
- ANTLR 前端解析成功：`5799`
- 手写前端 P95：`0.2709` ms
- ANTLR 前端 P95：`7.0124` ms

| 差分分类 | 数量 |
|---|---:|
| MATCH | 5799 |

> 本报告只证明语法前端兼容性，不证明金融语义、SQL 行集正确率或 Doris 性能。
