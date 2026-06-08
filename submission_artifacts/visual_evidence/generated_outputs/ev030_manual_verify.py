from __future__ import annotations

import json
from pathlib import Path

from findsl.equivalence import verify_sql_equivalence


dsl = 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)'
result = verify_sql_equivalence(dsl, Path("data/real_samples/eastmoney_a_share_sample"))
payload = {
    "dsl": result.dsl,
    "passed": result.passed,
    "sql": result.sql,
    "sql_row_count": result.sql_row_count,
    "reference_row_count": result.reference_row_count,
    "sql_keys": result.sql_keys,
    "reference_keys": result.reference_keys,
    "missing_keys": result.missing_keys,
    "extra_keys": result.extra_keys,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(0 if result.passed else 1)
