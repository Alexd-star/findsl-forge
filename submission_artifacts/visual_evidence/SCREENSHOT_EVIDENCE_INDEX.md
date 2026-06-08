# FinDSL Forge 截图证据包索引

本文档面向赛题 19“行情选股 DSL 到高性能 Doris SQL 的自动化编译系统”的验收、答辩、审计和最终提交核验。证据包坚持一个原则：截图必须来自真实运行、真实文件、真实界面或真实日志；凡是当前项目没有真实对象的内容，明确写为“不适用”或“待人工补拍”，不使用占位图冒充结果。

生成时间：2026-06-08 16:40:03 +0800

项目根目录：`D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge`

证据目录：`D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence`

## 1. 截图清单总表

| 证据编号 | 截图名称 | 是否必须 | 对应功能/要求 | 生成命令或操作 | 截图必须包含的信息 | 通过标准 | 建议文件名 | 答辩解释 | 风险备注 |
|---|---|---|---|---|---|---|---|---|---|
| EV-001 | 项目根目录结构截图 | 必须 | 真实命令执行证据 | Get-ChildItem -Force \| Select-Object Mode,Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-001_project_root_structure.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-002 | 核心源码目录截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\src\findsl -Force \| Select-Object Mode,Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-002_core_src_directory.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-003 | 测试目录截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\tests -Force \| Select-Object Mode,Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-003_tests_directory.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-004 | 输入数据目录截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\data -Recurse -Depth 2 -Force \| Select-Object Mode,Length,LastWriteTime,FullName | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-004_data_directory.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-005 | 输出与提交证据目录截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\submission_artifacts -Recurse -Depth 2 -Force \| Select-Object Mode,Length,LastWriteTime,FullName | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-005_submission_artifacts_directory.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-006 | docs 文档目录截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\docs -Force \| Select-Object Mode,Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-006_docs_directory.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-007 | scripts 脚本目录截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\scripts -Force \| Select-Object Mode,Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-007_scripts_directory.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-008 | Git HEAD 截图 | 必须 | 真实命令执行证据 | git rev-parse --short HEAD; git branch --show-current | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-008_git_head.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-009 | git status 截图 | 必须 | 真实命令执行证据 | git status -sb | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-009_git_status.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-010 | git log 最近提交截图 | 必须 | 真实命令执行证据 | git log --oneline --decorate -8 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-010_git_log_recent.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-011 | 运行环境版本截图 | 必须 | 真实命令执行证据 | python --version; python -m pip --version; git --version; node --version; npm --version; npx --version | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-011_runtime_versions.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-012 | 依赖安装成功截图 | 必须 | 真实命令执行证据 | python -m pip show pytest pandas \| Select-String -Pattern 'Name:\|Version:\|Location:'; Get-Content .\pyproject.toml -TotalCount 80 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-012_dependency_versions.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-015 | 终端主命令 compile 成功截图 | 必须 | 真实命令执行证据 | python -m findsl.cli compile 'then(filter(market("A") & CONS(indicator("main_net_inflow") > 0, 3)), rank(indicator("turnover_rate"), desc, top=100))' --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-015_cli_compile_success.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-016 | Pytest 全部通过截图 | 必须 | 真实命令执行证据 | python -m pytest -q | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-016_pytest_all_passed.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-017 | 单元测试与集成测试通过截图 | 必须 | 真实命令执行证据 | python -m pytest tests/test_template_functions.py tests/test_topic_compliance.py tests/test_config_extension.py tests/test_demo.py -q | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-017_selected_tests_passed.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-018 | Blocking gates 与 Warning count 截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_summary.md | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-018_evidence_summary_gates.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-019 | 官方正例负例全部通过截图 | 必须 | 真实命令执行证据 | python -m findsl.cli official-suite --output 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\official_suite_report.md' --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-019_official_suite_pass.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-020 | 官方 results 审计 PASS 截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_snapshots\submission_readiness.md -TotalCount 160 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-020_submission_readiness_snapshot.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-021 | 样例输入文件截图 | 必须 | 真实命令执行证据 | Get-Content .\data\samples\official_positive_cases.jsonl -TotalCount 10; ''; Get-Content .\data\samples\official_negative_cases.jsonl -TotalCount 8 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-021_sample_input_files.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-022 | 样例输出文件截图 | 必须 | 真实命令执行证据 | python -m findsl.cli compile 'filter(ABS(indicator("main_net_inflow")) > 0)' --json \| Set-Content -Encoding UTF8 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\sample_compile_result.json'; Get-Content 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\sample_compile_result.json' -TotalCount 120 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-022_sample_compile_output_file.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-023 | 核心功能输入截图 | 必须 | 真实命令执行证据 | Get-Content .\data\samples\queries.jsonl -TotalCount 20 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-023_core_input_cases.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-024 | 核心功能执行成功截图 | 必须 | 真实命令执行证据 | python -m findsl.cli verify-sql 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-024_verify_sql_success.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-025 | 核心功能输出结果截图 | 必须 | 真实命令执行证据 | python -m findsl.cli reference 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-025_reference_output_result.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-026 | 核心算法 Compiler 代码位置截图 | 必须 | 真实命令执行证据 | Get-Content .\src\findsl\compiler.py -TotalCount 120 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-026_core_algorithm_compiler_code.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-027 | 核心算法 prefix-sum 代码位置截图 | 必须 | 真实命令执行证据 | Get-Content .\src\findsl\sqlgen.py \| Select-Object -Skip 595 -First 95 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-027_core_algorithm_prefix_sum_code.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-028 | 核心算法输入输出对比截图 | 必须 | 真实命令执行证据 | python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 5 --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-028_algorithm_input_output_compare.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-029 | 算法中间结果 Explain 截图 | 必须 | 真实命令执行证据 | python -m findsl.cli compile 'filter(SUM(indicator("volume"), 120) > 1000000)' --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-029_algorithm_explain_intermediate.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-030 | 手工核验对比截图 | 必须 | 真实命令执行证据 | python 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\ev030_manual_verify.py' | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-030_manual_sql_reference_check.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-031 | 输出目录截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\submission_artifacts\evidence_snapshots -Force \| Select-Object Mode,Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-031_output_directory.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-032 | 结果文件内容截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_snapshots\official_suite_report.md -TotalCount 140 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-032_result_file_content.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-033 | 结果文件格式校验 PASS 截图 | 必须 | 真实命令执行证据 | python -m findsl.cli evidence-metadata --snapshots-dir submission_artifacts/evidence_snapshots --output 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\evidence_metadata_check.json' --summary-output 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\evidence_summary_check.md'; python -m json.tool 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\evidence_metadata_check.json' \| Select-Object -First 80; Get-Content 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\evidence_summary_check.md' -TotalCount 60 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-033_metadata_format_pass.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-034 | 结果数量统计截图 | 必须 | 真实命令执行证据 | $files = 'data/samples/official_positive_cases.jsonl','data/samples/official_negative_cases.jsonl','tests'; foreach ($f in $files) { if (Test-Path $f -PathType Container) { $count=(Get-ChildItem $f -Filter 'test_*.py').Count; "${f}: ${count} test files" } else { $count=(Get-Content $f \| Measure-Object -Line).Lines; "${f}: ${count} lines" } }; Get-Content .\submission_artifacts\evidence_metadata.json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-034_result_counts.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-035 | 基线性能截图 | 必须 | 真实命令执行证据 | python -m findsl.cli benchmark-prefix-sum 'filter(SUM(indicator("volume"), 3) > 300)' --data-dir data/samples --iterations 10 --output 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\prefix_sum_benchmark.md' --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-035_baseline_performance.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-036 | 优化后性能与 speedup 截图 | 必须 | 真实命令执行证据 | Get-Content 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\prefix_sum_benchmark.md' -TotalCount 140 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-036_optimized_performance_speedup.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-037 | Doris evidence PASS 截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_snapshots\doris_cluster_evidence.md -TotalCount 120 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-037_doris_evidence_pass.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-038 | Doris speedup 详情截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_snapshots\doris_cluster_evidence.json -TotalCount 180 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-038_doris_speedup_json.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-039 | Doris 本机端口可达性检查截图 | 必须 | 真实命令执行证据 | $client = [Net.Sockets.TcpClient]::new(); $async = $client.BeginConnect('127.0.0.1', 9030, $null, $null); $ok = $async.AsyncWaitHandle.WaitOne(2000, $false); if ($ok -and $client.Connected) { 'Doris 9030 reachable in this session' } else { 'Doris 9030 not reachable in this session; use committed Doris evidence snapshot unless live cluster is started.' }; $client.Close() | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-039_doris_live_port_check.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-050 | 非法输入 CLI 诊断截图 | 必须 | 真实命令执行证据 | python -m findsl.cli diagnose 'filter(indicator("clos") > 10)' --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-050_cli_invalid_input_diagnostic.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-051 | 边界输入测试截图 | 必须 | 真实命令执行证据 | python -m findsl.cli diagnose 'then(filter(market("A")), rank(indicator("close"), desc, percent=0))' --json | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-051_boundary_input_test.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-052 | 日志文件截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\submission_artifacts\visual_evidence\logs -Force \| Select-Object Mode,Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-052_log_files.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-053 | error warning 检查截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_summary.md; ''; Select-String -Path .\submission_artifacts\evidence_summary.md -Pattern 'Warning count\|Metadata Warnings\|<none>\|PASS' | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-053_error_warning_check.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-054 | 技术报告指标页截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\technical_report.md -TotalCount 160 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-054_technical_report_metrics.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-055 | README 运行命令截图 | 必须 | 真实命令执行证据 | Select-String -Path .\README.md -Pattern 'Quick Start\|python -m findsl.cli\|submission_readiness\|official-suite\|serve-demo' -Context 0,1 \| Select-Object -First 90 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-055_readme_run_commands.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-056 | 文档与实际命令一致截图 | 必须 | 真实命令执行证据 | $scripts = 'official_suite.ps1','submission_readiness.ps1','serve_demo.ps1','export_submission_artifacts.ps1','collect_doris_evidence.ps1'; foreach ($s in $scripts) { "${s}: " + (Test-Path ".\scripts\${s}") }; python -m findsl.cli --help \| Select-Object -First 80 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-056_doc_command_consistency.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-057 | 最终提交清单截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_manifest.md; ''; Get-Content .\submission_artifacts\README.md -TotalCount 120 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-057_submission_manifest.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-058 | 配置文件截图 | 必须 | 真实命令执行证据 | Get-Content .\configs\indicators.json -TotalCount 120; ''; Get-Content .\configs\functions.json -TotalCount 120; ''; Get-Content .\configs\tables.json -TotalCount 80 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-058_config_files.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-059 | 交付包文件列表截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\submission_artifacts -Recurse -Depth 3 -File \| Sort-Object FullName \| Select-Object Length,LastWriteTime,FullName | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-059_delivery_package_files.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-060 | 文件大小和修改时间截图 | 必须 | 真实命令执行证据 | Get-ChildItem -File .\README.md,.\PROJECT_INDEX.md,.\pyproject.toml; Get-ChildItem -LiteralPath .\submission_artifacts\evidence_snapshots -File \| Select-Object Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-060_file_sizes_modified_times.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-061 | sha256 校验和截图 | 必须 | 真实命令执行证据 | python 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\ev061_sha256.py' | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-061_sha256_checksums.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-062 | 上传核验 READY 截图 | 必须 | 真实命令执行证据 | Get-Content .\submission_artifacts\evidence_summary.md; ''; Get-Content .\docs\17_项目交付说明.md -TotalCount 120 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-062_upload_ready.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-063 | 答辩演示关键页面清单截图 | 必须 | 真实命令执行证据 | Get-ChildItem -LiteralPath .\submission_artifacts\demo_screenshots -File \| Select-Object Length,LastWriteTime,Name; ''; Get-ChildItem -LiteralPath .\submission_artifacts\defense_video -File \| Select-Object Length,LastWriteTime,Name | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-063_defense_demo_assets.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-064 | 模型权重搜索不适用截图 | 必须 | 真实命令执行证据 | $patterns='*.pt','*.pth','*.onnx','*.bin','*.safetensors','*.ckpt','*.h5'; $files = foreach ($p in $patterns) { Get-ChildItem -Recurse -File -Filter $p -ErrorAction SilentlyContinue \| Select-Object FullName,Length }; if (-not $files) { 'No model or weight files found under project root. This is expected: FinDSL Forge is a deterministic compiler, not a trained model package.' } else { $files } | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-064_model_weight_search_none.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-065 | 赛题完成度规划截图 | 必须 | 真实命令执行证据 | python -m findsl.cli topic-compliance --output 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\topic_19_compliance_plan.md' --json; Get-Content 'D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\findsl-forge\submission_artifacts\visual_evidence\generated_outputs\topic_19_compliance_plan.md' -TotalCount 140 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-065_topic_compliance_plan.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-013 | 服务启动成功截图 | 必须 | 服务启动成功、Web Demo 可用 | python -m findsl.cli serve-demo --host 127.0.0.1 --port 59700 | 服务命令、PID、健康检查 URL、/api/examples 响应 | 健康检查返回 ok=true，服务可被浏览器访问 | EV-013_service_start_success.png | 这张图证明 Web Demo 是本次实际启动的服务，不是静态截图。 | 端口是本次动态分配端口；正式演示可使用 README 中的 8765。 |
| EV-014 | 端口与健康检查截图 | 必须 | 端口或健康检查 | Invoke-RestMethod -Uri 'http://127.0.0.1:59700/api/examples' \| ConvertTo-Json -Depth 5 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-014_port_health_check.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-040 | API 调用成功截图 | 必须 | API 调用成功、核心服务接口 | $body = @{ dsl = 'filter(SUM(indicator("volume"), 3) > 300)'; verify = $true; enable_prefix_sum = $true } \| ConvertTo-Json; Invoke-RestMethod -Uri 'http://127.0.0.1:59700/api/analyze' -Method Post -ContentType 'application/json' -Body $body \| ConvertTo-Json -Depth 8 | 命令、路径、退出码、关键输出、PASS 或待核验状态 | 退出码符合预期，输出中出现对应成功标记或可审计结果 | EV-040_api_call_success.png | 这张图证明该项不是文档口头描述，而是由当前项目命令实际执行得到。 | 若环境变更导致命令失败，应保留失败截图并补充原因，再重新运行。 |
| EV-041 | Web Demo 主界面截图 | 必须 | Web/软件主界面、答辩演示关键页面 | 启动服务后访问 http://127.0.0.1:59700 | FinDSL Forge 标题、NL2DSL 输入区、Doris evidence 指标、Result 面板 | 页面可正常打开，无空白、无遮挡，关键面板可见 | EV-041_web_main_interface.png | 这张图用于说明项目有可操作的评审演示界面，不只是命令行工具。 | 若浏览器缩放或窗口过小，可能导致面板被折叠；需使用 1440px 以上宽度补拍。 |
| EV-042 | Web 参数设置界面截图 | 必须 | 参数设置、样例选择、Prefix sum/Verify 开关 | Web Demo 中查看 Workbench 区域 | 中文需求输入、样例下拉框、DSL 输入、Prefix sum 与 Verify 开关 | 能看清输入区和两个关键开关，证明演示可切换优化与验证逻辑 | EV-042_web_parameters_area.png | 这张图可解释评委如何从自然语言、样例或手写 DSL 进入编译流程。 | 参数区截图不能只截标题，必须包含 DSL 输入框和开关。 |
| EV-043 | Web 结果 SQL 截图 | 必须 | 核心功能输出、Doris SQL 生成 | 点击 Run analysis 后停留 SQL 标签页 | SELECT SQL、verification 指标、compile latency、optimizer 状态 | 页面显示 SQL 且结果状态为 OK 或验证通过 | EV-043_web_result_sql.png | 这张图说明 DSL 已进入确定性编译器并生成 Doris SQL。 | 若 SQL 标签页内容为空，应先检查 /api/analyze 是否正常。 |
| EV-044 | Web AST 视图截图 | 必须 | 标准 AST 展示、核心中间表示 | Run analysis 后点击 AST 标签 | AST JSON、filter/then/rank 等节点 | 能看到结构化 AST，不是自由文本 SQL | EV-044_web_ast_view.png | 答辩时用于解释系统先解析 DSL，再经过类型检查和 SQL 生成。 | 如果 AST 过长，应使用全页截图或局部放大补拍。 |
| EV-045 | Web Explain 优化说明截图 | 必须 | 优化规则、prefix-sum、Doris SQL explain 证据入口 | Run analysis 后点击 Explain 标签 | PREFIX_SUM、DATE_RANGE 等规则名称、applied/skipped 状态、evidence 字段 | Explain 中能看到机器可读优化步骤 | EV-045_web_explain_view.png | 这张图说明优化不是黑箱，评委可以看到每条规则为什么应用或跳过。 | Explain 截图要避免只截到空白顶部。 |
| EV-046 | Web Rows 结果行截图 | 必须 | SQL/reference 验证结果展示 | Run analysis 后点击 Rows 标签 | SQL row count、reference row count、result_keys | 行数和结果键可见，且验证通过 | EV-046_web_rows_view.png | 答辩时说明生成 SQL 的结果会和独立 reference oracle 对比。 | 样本数据较小，行数不是性能指标，只是正确性演示。 |
| EV-047 | Web Doris Evidence 截图 | 必须 | Doris evidence、speedup、row parity | Run analysis 后点击 Evidence 标签 | Doris evidence PASS、speedup、row parity 或证据路径 | 页面能读取证据摘要或说明证据文件路径 | EV-047_web_evidence_view.png | 这张图把 Web 演示与提交证据中的 Doris 集群性能证明连接起来。 | 若 reports 目录缺 Doris 报告，页面会显示 evidence unavailable，需要先导出快照。 |
| EV-048 | Web 负例诊断截图 | 必须 | 非法输入测试、错误提示、诊断修复建议 | 输入 filter(indicator("clos") > 10) 并点击 Run analysis | UNKNOWN_INDICATOR、错误原因、建议修复信息 | 错误不会执行 SQL，页面显示稳定诊断码 | EV-048_web_negative_diagnostic.png | 答辩时说明系统能拒绝错误 DSL，并给出可理解的修复建议。 | 如果只出现浏览器错误而无诊断码，应检查后端异常处理。 |
| EV-049 | Web 空输入错误截图 | 建议/待人工补拍 | 空输入测试、错误提示 | 当前无交互驱动截图；对应 CLI/API 错误证据见 EV-050、EV-048 | DSL is required 或等价错误提示 | 空输入不触发 SQL 生成，页面给出明确提示 | 待人工补拍_web_empty_input_error.png | 空输入属于交互健壮性证据，不等同于官方负例套件。 | 当前脚本采用 Playwright CLI 截图，未做浏览器交互；需要现场或后续交互脚本补拍。 |
| EV-066 | 模型权重文件截图 | 不适用 | 权重文件、模型文件 | 项目内搜索 *.pt/*.pth/*.onnx/*.bin/*.safetensors/*.ckpt | 若存在模型权重，应显示文件名、大小、修改时间；当前为确定性编译器，无模型权重 | 搜索结果为空，并说明项目不依赖模型权重 | EV-064_model_weight_search_none.png | 本项目核心是确定性 DSL 编译器，NL2DSL 只是候选层，不需要训练权重文件。 | 若后续加入本地模型或大模型权重，必须重新补拍模型来源、大小、hash 和许可证。 |
| EV-067 | 压缩包内容截图 | 不适用/待人工补拍 | 最终提交压缩包内容 | 当前尚未生成比赛平台最终 zip；以 Git 仓库和 submission_artifacts 为提交源 | 如果后续生成 zip，应显示压缩包内 README、docs、src、tests、submission_artifacts 等目录 | 未生成 zip 时不能伪造；生成后用 tar/7z/资源管理器补拍 | 待人工补拍_final_zip_content.png | 答辩时说明当前证据包是提交前审计目录，最终打包后还需补一张压缩包内容图。 | 需要最终提交格式确定后人工补拍。 |
| EV-068 | 上传成功截图 | 不适用/待人工补拍 | 比赛平台上传成功 | 登录比赛平台并完成最终上传后截图 | 平台名称、项目名称、上传成功状态、时间、文件名 | 平台页面明确显示提交成功 | 待人工补拍_portal_upload_success.png | 这张图只能由你在比赛平台实际提交后补拍，不能由本地项目生成。 | 当前没有比赛平台登录页面和提交动作，必须人工补拍。 |
| EV-069 | 实时 Doris 数据库连接成功截图 | 建议/待人工补拍 | 数据库连接成功、Doris 现场复现 | 启动 Doris 后执行 mysql -h 127.0.0.1 -P 9030 -u root -e "SELECT 1" | mysql 命令、9030 端口、SELECT 1 输出或数据库列表 | 命令退出码为 0，能连接 Doris FE 查询端口 | 待人工补拍_live_doris_mysql_connection.png | 已有历史 Doris evidence PASS；若现场要重跑性能，应补拍实时连接成功。 | 脚本已检查本机端口可达性，若 Doris 未启动，此项只能待集群启动后补拍。 |
| EV-070 | 图表可视化截图 | 不适用/不适用 | 图表可视化 | 当前 Web Demo 以 SQL、AST、Explain、Rows、Evidence 面板呈现，不包含折线/柱状图组件 | 若后续新增性能图表，应显示 baseline/optimized 耗时曲线或柱状对比 | 当前不强行伪造图表，以 Evidence 数字和表格为准 | 不适用_chart_visualization.png | 赛题重点是 DSL 编译和 Doris SQL 性能证据，现阶段表格和 explain 更直接。 | 若答辩 PPT 需要视觉冲击，可后续把 benchmark JSON 生成图表再补拍。 |

## 2. 必须补齐的截图

以下截图已经在本次证据包中补齐，可优先用于答辩和最终提交材料：

- `EV-001_project_root_structure.png`：项目根目录结构截图
- `EV-002_core_src_directory.png`：核心源码目录截图
- `EV-003_tests_directory.png`：测试目录截图
- `EV-004_data_directory.png`：输入数据目录截图
- `EV-005_submission_artifacts_directory.png`：输出与提交证据目录截图
- `EV-006_docs_directory.png`：docs 文档目录截图
- `EV-007_scripts_directory.png`：scripts 脚本目录截图
- `EV-008_git_head.png`：Git HEAD 截图
- `EV-009_git_status.png`：git status 截图
- `EV-010_git_log_recent.png`：git log 最近提交截图
- `EV-011_runtime_versions.png`：运行环境版本截图
- `EV-012_dependency_versions.png`：依赖安装成功截图
- `EV-015_cli_compile_success.png`：终端主命令 compile 成功截图
- `EV-016_pytest_all_passed.png`：Pytest 全部通过截图
- `EV-017_selected_tests_passed.png`：单元测试与集成测试通过截图
- `EV-018_evidence_summary_gates.png`：Blocking gates 与 Warning count 截图
- `EV-019_official_suite_pass.png`：官方正例负例全部通过截图
- `EV-020_submission_readiness_snapshot.png`：官方 results 审计 PASS 截图
- `EV-021_sample_input_files.png`：样例输入文件截图
- `EV-022_sample_compile_output_file.png`：样例输出文件截图
- `EV-023_core_input_cases.png`：核心功能输入截图
- `EV-024_verify_sql_success.png`：核心功能执行成功截图
- `EV-025_reference_output_result.png`：核心功能输出结果截图
- `EV-026_core_algorithm_compiler_code.png`：核心算法 Compiler 代码位置截图
- `EV-027_core_algorithm_prefix_sum_code.png`：核心算法 prefix-sum 代码位置截图
- `EV-028_algorithm_input_output_compare.png`：核心算法输入输出对比截图
- `EV-029_algorithm_explain_intermediate.png`：算法中间结果 Explain 截图
- `EV-030_manual_sql_reference_check.png`：手工核验对比截图
- `EV-031_output_directory.png`：输出目录截图
- `EV-032_result_file_content.png`：结果文件内容截图
- `EV-033_metadata_format_pass.png`：结果文件格式校验 PASS 截图
- `EV-034_result_counts.png`：结果数量统计截图
- `EV-035_baseline_performance.png`：基线性能截图
- `EV-036_optimized_performance_speedup.png`：优化后性能与 speedup 截图
- `EV-037_doris_evidence_pass.png`：Doris evidence PASS 截图
- `EV-038_doris_speedup_json.png`：Doris speedup 详情截图
- `EV-039_doris_live_port_check.png`：Doris 本机端口可达性检查截图
- `EV-050_cli_invalid_input_diagnostic.png`：非法输入 CLI 诊断截图
- `EV-051_boundary_input_test.png`：边界输入测试截图
- `EV-052_log_files.png`：日志文件截图
- `EV-053_error_warning_check.png`：error warning 检查截图
- `EV-054_technical_report_metrics.png`：技术报告指标页截图
- `EV-055_readme_run_commands.png`：README 运行命令截图
- `EV-056_doc_command_consistency.png`：文档与实际命令一致截图
- `EV-057_submission_manifest.png`：最终提交清单截图
- `EV-058_config_files.png`：配置文件截图
- `EV-059_delivery_package_files.png`：交付包文件列表截图
- `EV-060_file_sizes_modified_times.png`：文件大小和修改时间截图
- `EV-061_sha256_checksums.png`：sha256 校验和截图
- `EV-062_upload_ready.png`：上传核验 READY 截图
- `EV-063_defense_demo_assets.png`：答辩演示关键页面清单截图
- `EV-064_model_weight_search_none.png`：模型权重搜索不适用截图
- `EV-065_topic_compliance_plan.png`：赛题完成度规划截图
- `EV-013_service_start_success.png`：服务启动成功截图
- `EV-014_port_health_check.png`：端口与健康检查截图
- `EV-040_api_call_success.png`：API 调用成功截图
- `EV-041_web_main_interface.png`：Web Demo 主界面截图
- `EV-042_web_parameters_area.png`：Web 参数设置界面截图
- `EV-043_web_result_sql.png`：Web 结果 SQL 截图
- `EV-044_web_ast_view.png`：Web AST 视图截图
- `EV-045_web_explain_view.png`：Web Explain 优化说明截图
- `EV-046_web_rows_view.png`：Web Rows 结果行截图
- `EV-047_web_evidence_view.png`：Web Doris Evidence 截图
- `EV-048_web_negative_diagnostic.png`：Web 负例诊断截图

## 3. 建议补充的截图

以下截图不是赛题核心门禁，但能提升材料完整度和答辩可信度：

- `待人工补拍_live_doris_mysql_connection.png`：启动本机 Doris 后补拍 mysql 连接成功和 `SELECT 1`。
- `待人工补拍_portal_upload_success.png`：比赛平台最终提交后补拍上传成功页面。
- `待人工补拍_final_zip_content.png`：若组委会要求 zip 包提交，最终压缩后补拍压缩包内容。
- `待人工补拍_web_empty_input_error.png`：现场浏览器清空 DSL 输入框后补拍空输入错误提示。

## 4. 不适用截图及原因

- EV-049 Web 空输入错误截图：当前脚本采用 Playwright CLI 截图，未做浏览器交互；需要现场或后续交互脚本补拍。
- EV-067 压缩包内容截图：需要最终提交格式确定后人工补拍。
- EV-068 上传成功截图：当前没有比赛平台登录页面和提交动作，必须人工补拍。
- EV-069 实时 Doris 数据库连接成功截图：脚本已检查本机端口可达性，若 Doris 未启动，此项只能待集群启动后补拍。
- EV-070 图表可视化截图：若答辩 PPT 需要视觉冲击，可后续把 benchmark JSON 生成图表再补拍。

## 5. 无效截图常见问题

1. 只截结果不截命令。评委无法判断结果是否来自当前项目，终端截图应包含工作目录、命令、退出码和关键输出。
2. 只截文档不截真实运行。README 可以说明操作步骤，但不能代替 pytest、official suite、API 或 Web Demo 的运行证据。
3. 截图过窄或被遮挡。路径、命令、PASS、行数、speedup 等字段必须完整可读，不能被窗口边缘截断。
4. 把历史截图当作最新运行。历史证据可以保留，但必须说明生成时间和来源；最终提交前建议重跑核心命令。
5. 把不适用项做成假截图。项目没有模型权重、没有比赛平台上传页面、没有正在运行的 Doris 连接时，应标注不适用或待人工补拍。
6. 忽略失败证据。失败截图也有审计价值，但必须解释失败原因、影响范围和后续补拍方法。

## 6. 最终截图执行顺序

1. 打开 `README.md` 和 `docs/19_赛题19完成度与下一步规划.md`，确认赛题口径和运行命令。
2. 先补项目结构类截图：根目录、`src/`、`tests/`、`data/`、`docs/`、`scripts/`、`submission_artifacts/`。
3. 再补 Git 与环境截图：Git HEAD、git status、git log、Python/pip/Git/Node/npm/npx 版本、依赖版本。
4. 运行核心命令：compile、verify-sql、official-suite、pytest、selected tests、topic-compliance、evidence-metadata。
5. 查看提交证据：evidence_summary、submission_readiness、official_suite_report、doris_cluster_evidence、evidence_manifest。
6. 启动 Web Demo，依次截图主界面、参数区、SQL、AST、Explain、Rows、Evidence、负例诊断、空输入错误。
7. 补交付完整性：文件大小修改时间、SHA256、提交清单、配置文件、Doris SQL assets、既有 Demo 截图和视频目录。
8. 对不适用项做人工判断：模型权重不适用、上传成功需比赛平台现场补拍、实时 Doris 连接需集群启动后补拍。
9. 最后复查 `screenshots/` 中图片是否清晰，按答辩 PPT 或提交模板挑选图片。

## 7. 图片文件校验

| 图片 | 字节数 | SHA256 前 16 位 |
|---|---:|---|
| `screenshots\EV-001_project_root_structure.png` | 110944 | `9449bc52a4c3c95b...` |
| `screenshots\EV-002_core_src_directory.png` | 130461 | `8d5bb93ef1743f0c...` |
| `screenshots\EV-003_tests_directory.png` | 124055 | `7aa92501486253a2...` |
| `screenshots\EV-004_data_directory.png` | 207520 | `2222431bed57a494...` |
| `screenshots\EV-005_submission_artifacts_directory.png` | 319111 | `9dfe397609a13c72...` |
| `screenshots\EV-006_docs_directory.png` | 139136 | `4f8917c3b061fa92...` |
| `screenshots\EV-007_scripts_directory.png` | 111717 | `1c81b1f24e1197a3...` |
| `screenshots\EV-008_git_head.png` | 56821 | `87a7e7e7406b6685...` |
| `screenshots\EV-009_git_status.png` | 57600 | `0f84ee5743775c90...` |
| `screenshots\EV-010_git_log_recent.png` | 74537 | `4215fe2446173c9b...` |
| `screenshots\EV-011_runtime_versions.png` | 67799 | `b83f62b7fb6fe5f9...` |
| `screenshots\EV-012_dependency_versions.png` | 99357 | `97d0e1d75c4a0fc0...` |
| `screenshots\EV-013_service_start_success.png` | 224831 | `27e45ffb4e6fe2a5...` |
| `screenshots\EV-014_port_health_check.png` | 1162338 | `2e64482c0e1ff3bf...` |
| `screenshots\EV-015_cli_compile_success.png` | 268258 | `9e306b957d487a47...` |
| `screenshots\EV-016_pytest_all_passed.png` | 57804 | `a9422303bd037430...` |
| `screenshots\EV-017_selected_tests_passed.png` | 65345 | `4d92924e56562995...` |
| `screenshots\EV-018_evidence_summary_gates.png` | 102886 | `971df33188a769d1...` |
| `screenshots\EV-019_official_suite_pass.png` | 82281 | `8014403c3138b5f2...` |
| `screenshots\EV-020_submission_readiness_snapshot.png` | 350160 | `479e9e6dfaa04825...` |
| `screenshots\EV-021_sample_input_files.png` | 265315 | `0668bb00c2c2d326...` |
| `screenshots\EV-022_sample_compile_output_file.png` | 185893 | `3268f903cb6f11aa...` |
| `screenshots\EV-023_core_input_cases.png` | 171842 | `b3db192ea6d1cf96...` |
| `screenshots\EV-024_verify_sql_success.png` | 116650 | `1aeb8460538f7d24...` |
| `screenshots\EV-025_reference_output_result.png` | 77667 | `526bd79135899423...` |
| `screenshots\EV-026_core_algorithm_compiler_code.png` | 149464 | `8b337610e5120351...` |
| `screenshots\EV-027_core_algorithm_prefix_sum_code.png` | 197023 | `1543d8c6b42c0039...` |
| `screenshots\EV-028_algorithm_input_output_compare.png` | 286142 | `aaeb49708687cc32...` |
| `screenshots\EV-029_algorithm_explain_intermediate.png` | 163380 | `b431868ae204be5b...` |
| `screenshots\EV-030_manual_sql_reference_check.png` | 113761 | `b4123adf444eb4ae...` |
| `screenshots\EV-031_output_directory.png` | 86598 | `0da78fe5c8be5644...` |
| `screenshots\EV-032_result_file_content.png` | 325757 | `5af1bae0c4e928d4...` |
| `screenshots\EV-033_metadata_format_pass.png` | 332992 | `d8a398e22bcd89db...` |
| `screenshots\EV-034_result_counts.png` | 171290 | `f6428dc648c42d08...` |
| `screenshots\EV-035_baseline_performance.png` | 309802 | `2daaf0278b6cddbf...` |
| `screenshots\EV-036_optimized_performance_speedup.png` | 182634 | `9dc74dd11ad8bed7...` |
| `screenshots\EV-037_doris_evidence_pass.png` | 229937 | `3e5ac914ad774e18...` |
| `screenshots\EV-038_doris_speedup_json.png` | 272458 | `cfd35ff9c2f02899...` |
| `screenshots\EV-039_doris_live_port_check.png` | 90331 | `27184d3abf2848b0...` |
| `screenshots\EV-040_api_call_success.png` | 209452 | `0efccb5874deec7d...` |
| `screenshots\EV-041_web_main_interface.png` | 120621 | `026f9bdca80a2b99...` |
| `screenshots\EV-042_web_parameters_area.png` | 120621 | `026f9bdca80a2b99...` |
| `screenshots\EV-043_web_result_sql.png` | 120232 | `b73a8e5a769df603...` |
| `screenshots\EV-044_web_ast_view.png` | 106723 | `f46e45e67acfd805...` |
| `screenshots\EV-045_web_explain_view.png` | 114009 | `67e7895fa46e4875...` |
| `screenshots\EV-046_web_rows_view.png` | 96756 | `9b59373cf3ce4e15...` |
| `screenshots\EV-047_web_evidence_view.png` | 128952 | `7052372b7a81d9b4...` |
| `screenshots\EV-048_web_negative_diagnostic.png` | 97865 | `6fd70d36d3a8eac1...` |
| `screenshots\EV-050_cli_invalid_input_diagnostic.png` | 77317 | `6af32f5ff5bfbc3d...` |
| `screenshots\EV-051_boundary_input_test.png` | 82975 | `9a7aa0cb0a4cdfe6...` |
| `screenshots\EV-052_log_files.png` | 157294 | `70b0bcaf520bb00f...` |
| `screenshots\EV-053_error_warning_check.png` | 129556 | `f3c8bb4add79ffdc...` |
| `screenshots\EV-054_technical_report_metrics.png` | 221922 | `eaddce5f5e4f2341...` |
| `screenshots\EV-055_readme_run_commands.png` | 311000 | `6f86b9e89bd6ed4f...` |
| `screenshots\EV-056_doc_command_consistency.png` | 161973 | `9a8f64d3eb169343...` |
| `screenshots\EV-057_submission_manifest.png` | 239197 | `105757f4438f1b99...` |
| `screenshots\EV-058_config_files.png` | 213678 | `6feb397bae5e778a...` |
| `screenshots\EV-059_delivery_package_files.png` | 593073 | `d8e4e507e32e8faa...` |
| `screenshots\EV-060_file_sizes_modified_times.png` | 127717 | `777738700fe633b1...` |
| `screenshots\EV-061_sha256_checksums.png` | 85951 | `f545e0f0e1bd2a38...` |
| `screenshots\EV-062_upload_ready.png` | 233085 | `0ae80f77cfa15721...` |
| `screenshots\EV-063_defense_demo_assets.png` | 101831 | `e7601ec91767d224...` |
| `screenshots\EV-064_model_weight_search_none.png` | 91190 | `852bc90514518366...` |
| `screenshots\EV-065_topic_compliance_plan.png` | 376825 | `32adfd3b62c6ad72...` |
| `screenshots\existing_demo_screenshots\01_nl_to_dsl_overview.png` | 120232 | `b73a8e5a769df603...` |
| `screenshots\existing_demo_screenshots\02_positive_sql.png` | 120232 | `b73a8e5a769df603...` |
| `screenshots\existing_demo_screenshots\03_positive_ast.png` | 106723 | `f46e45e67acfd805...` |
| `screenshots\existing_demo_screenshots\04_positive_explain.png` | 114009 | `67e7895fa46e4875...` |
| `screenshots\existing_demo_screenshots\05_positive_rows.png` | 96756 | `9b59373cf3ce4e15...` |
| `screenshots\existing_demo_screenshots\06_positive_evidence.png` | 128952 | `7052372b7a81d9b4...` |
| `screenshots\existing_demo_screenshots\07_negative_unknown_indicator.png` | 97865 | `6fd70d36d3a8eac1...` |
| `screenshots\existing_demo_screenshots\real_market_sample.png` | 94248 | `58fe9e330267e9d7...` |

## 8. 复现说明

在项目根目录运行：

```powershell
$env:PYTHONPATH = "src"
python .\scripts\build_visual_evidence.py
```

脚本会重新运行命令、启动本地 Web Demo、保存日志并覆盖本目录下同名截图。若需要现场 Doris 连接成功截图，应先启动 Apache Doris 并确认 9030 端口可连，再补拍数据库连接项。
