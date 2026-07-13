from __future__ import annotations

import os
from pathlib import Path


DEFAULT_OFFICIAL_WORKBOOK = (
    r"D:\Luo_docs\竞赛\研创赛\研究生金融科技创新大赛\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\19-多模态技术与数据治理赛道-华泰证券-行情选股 DSL 到高性能 Doris SQL 的自动化编译系统"
    r"\选股 DSL 规范文档\选股提槽实例.xlsx"
)
OFFICIAL_WORKBOOK = os.environ.get(
    "FINDSL_OFFICIAL_WORKBOOK",
    DEFAULT_OFFICIAL_WORKBOOK,
)


def external_file_available(path: str) -> bool:
    try:
        return Path(path).is_file()
    except (OSError, ValueError):
        return False
