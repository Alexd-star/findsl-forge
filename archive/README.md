# archive 目录说明

`archive/` 用于保存已经不作为当前主线使用、但仍有审计或回溯价值的历史文件。当前目录仅建立规则说明，暂未移动任何文件。

## 使用原则

1. 不直接删除历史文件。先在 `docs/16_历史文件说明.md` 记录文件来源、作用、归档原因和是否仍需保留。
2. 只归档不参与当前运行链路的文件，例如旧报告、旧截图、旧视频、临时 QA 输出、旧证据探测结果。
3. 不归档 `src/`、`configs/`、`data/samples/`、`tests/`、`deploy/doris/`、`submission_artifacts/evidence_snapshots/` 中的当前版本文件。
4. 如果归档文件体积较大，应优先确认是否已经被 `.gitignore` 忽略，以及是否需要保留在 Git 仓库中。

## 建议子目录

```text
archive/
├── reports/          # 旧报告和实验探测结果
├── screenshots/      # 旧 UI 截图
├── videos/           # 旧答辩视频
├── docs/             # 旧版文档草稿
└── notes/            # 临时分析记录
```

## 当前建议归档对象

- `reports/doris_cluster_evidence_*threshold_probe.md`：阈值探测报告，不是最终默认证据。
- `reports/manual_*`：文档渲染 QA 结果。
- `reports/ui_redesign_qa/*profile*`：浏览器自动化缓存。
- 根目录 `demo_876*.log`：当前为空日志，删除或归档前需确认 Demo 没有运行。

