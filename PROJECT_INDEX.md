# FinDSL Forge 项目索引

本文档只描述当前仓库。历史阶段文件已由 Git 保存，不在当前目录重复归档。

## 根目录

| 文件 | 作用 |
| --- | --- |
| `README.md` | GitHub 首页、项目状态、快速开始和文档入口 |
| `PROJECT_INDEX.md` | 当前文件与目录职责索引 |
| `CHANGELOG.md` | 当前发布线的高层变更摘要 |
| `pyproject.toml` | Python 包、依赖、测试、Ruff 和 import-linter 配置 |
| `.gitignore` | 本地缓存、数据库、报告和最终展示产物忽略规则 |
| `.dockerignore` | API/Doris 镜像构建排除规则 |

## 核心目录

| 目录 | 应放内容 | 不应放内容 |
| --- | --- | --- |
| `.github/` | GitHub Actions 质量门禁 | 本地配置和密钥 |
| `src/findsl/official/` | 正式编译链、服务和证据核心 | 按单句硬编码的修补逻辑 |
| `src/findsl/compat/` | 旧前端兼容与迁移差分 | 新增官方业务语义 |
| `src/findsl/` | CLI、演示、readiness 及保留的通用组件 | 生成报告和本机缓存 |
| `grammar/` | ANTLR4 唯一文法源 | 复制出来的第二套文法 |
| `configs/official/` | 声明式指标、函数、表、策略、来源和证据合同 | 私有 token、临时抓取结果 |
| `data/official_correctness/` | 冻结用例、来源信息和独立 reference SQL | Doris 运行库或大体量原始行情 |
| `data/official_performance/` | 性能矩阵定义 | 手工挑选的最好结果 |
| `data/samples/` | 小型离线样例 | 官方大文件和敏感数据 |
| `data/real_samples/` | 带来源元数据的公开小样本 | 无法追溯来源的数据 |
| `deploy/` | API 容器与 Doris DDL/装载说明 | 真实密码和运行卷 |
| `scripts/` | 代码生成、数据同步、装载、评测、审计 | PPT、图片和长篇手册生成器 |
| `tests/` | 单元、集成、架构、正确率和门禁测试 | 依赖个人机器路径的测试 |
| `docs/` | 当前且必要的六份中文说明 | 历史阶段复盘和最终展示材料 |
| `submission_artifacts/` | 当前评分证据的机器可读快照 | 重复旧快照、PPT、视频、截图集 |
| `tools/` | 第三方工具校验信息 | 未核验二进制和安装包 |

## 正式运行入口

| 入口 | 用途 |
| --- | --- |
| `findsl.official.pipeline.compile_official` | 正式 Python 编译入口 |
| `python -m findsl.cli official-slot-parse` | 解析并查看源位置、诊断和 AST |
| `python -m findsl.cli official-slot-ir` | 查看 Logical/Physical IR |
| `python -m findsl.cli official-slot-backend` | 生成并校验 Doris SQL |
| `python -m findsl.cli serve-demo` | 启动 Web 演示 |
| `python -m findsl.official.api` | 启动服务接口 |

## 核心代码

| 文件或包 | 主要职责 |
| --- | --- |
| `official/frontend/` | ANTLR 解析、错误监听、源映射和 AST 适配 |
| `official/typed_ast.py`、`official/types.py` | 不可变强类型语法树与类型系统 |
| `official/domain/` | 指标、市场、范围和时间语义绑定 |
| `official/ir/` | 规范关系 IR 与结构验证 |
| `official/optimizer/` | 可追踪等价重写规则 |
| `official/physical/` | 物理策略、统计、候选计划、成本和风险选择 |
| `official/backend/doris.py` | SQLGlot Doris AST 构建和 SQL 渲染 |
| `official/backend/validation.py` | 表、列、函数及结构安全校验 |
| `official/correctness.py` | 完整结果集比较和正确率报告 |
| `official/performance.py` | 编译与查询性能测量 |
| `official/service.py`、`official/api.py` | 服务层请求、错误和健康状态 |
| `evidence_contract.py`、`evidence_metadata.py` | 证据合同、元数据和摘要 |

## 生成物规则

`reports/`、`output/`、`outputs/`、Doris 数据卷、数据库文件、PPT、DOCX、PDF、截图和视频都不属于源码。它们可以由脚本重新生成，默认不进入 Git。最终展示材料只在功能和证据封板后制作一次。

## 构建与验证

```powershell
python -m pip install -e ".[dev]"
python scripts/generate_antlr.py --check
python -m ruff check .
lint-imports
python -m pytest
```

Doris 与证据流程见 [运行测试与 Doris](docs/运行测试与Doris.md)。
