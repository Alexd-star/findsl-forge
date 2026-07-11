import pytest

from findsl.official.ir import Field, LiteralExpr, LogicalFilter, LogicalLimit, LogicalRank, LogicalScan, Schema
from findsl.official.ir.validate import OfficialIrError, validate_plan
from findsl.official.types import BOOLEAN, NUMERIC, STRING, UNKNOWN


SCHEMA = Schema((Field("stock_code", STRING, False),))
SCAN = LogicalScan("market_observation", SCHEMA)


def test_valid_nested_plan_passes_strict_validation():
    plan = LogicalLimit(LogicalFilter(SCAN, LiteralExpr(True, BOOLEAN), SCHEMA), 0, 10, SCHEMA)
    assert validate_plan(plan, strict=True) is plan


@pytest.mark.parametrize(
    "plan,code",
    [
        (LogicalFilter(SCAN, LiteralExpr(1, NUMERIC), SCHEMA), "IR_FILTER_TYPE"),
        (LogicalLimit(SCAN, -1, 10, SCHEMA), "IR_LIMIT_BOUNDS"),
        (LogicalLimit(SCAN, 0, 0, SCHEMA), "IR_LIMIT_BOUNDS"),
        (LogicalRank(SCAN, LiteralExpr(1, NUMERIC), "sideways", LiteralExpr(2, NUMERIC), SCHEMA), "IR_RANK_DIRECTION"),
        (LogicalFilter(SCAN, LiteralExpr(None, UNKNOWN), SCHEMA), "IR_UNKNOWN_TYPE"),
        (LogicalScan("newzl.hsj_stock_hq_basic", SCHEMA), "IR_PHYSICAL_ENTITY"),
    ],
)
def test_invalid_plan_reports_stable_code_and_path(plan, code):
    with pytest.raises(OfficialIrError) as excinfo:
        validate_plan(plan, strict=True)
    assert excinfo.value.code == code
    assert excinfo.value.path.startswith("$")
