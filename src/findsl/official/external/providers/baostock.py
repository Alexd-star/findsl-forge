from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


class BaoStockProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class BaoStockIndustryRow:
    update_date: str
    code: str
    name: str
    industry: str
    classification_system: str


class BaoStockIndustryProvider:
    source = "baostock"
    source_url = "http://baostock.com/baostock/index.php/Python_API文档"
    license_note = (
        "Public BaoStock industry endpoint; classification label is retained verbatim"
    )

    def fetch(self) -> Tuple[BaoStockIndustryRow, ...]:
        try:
            import baostock as bs
        except ImportError as exc:
            raise BaoStockProviderError(
                "BaoStock provider requires the external-data optional dependencies"
            ) from exc
        login = bs.login()
        if login.error_code != "0":
            raise BaoStockProviderError(
                f"BaoStock login failed: {login.error_code} {login.error_msg}"
            )
        try:
            result = bs.query_stock_industry()
            if result.error_code != "0":
                raise BaoStockProviderError(
                    "BaoStock industry query failed: "
                    f"{result.error_code} {result.error_msg}"
                )
            rows = []
            while result.next():
                values = result.get_row_data()
                if len(values) != 5:
                    raise BaoStockProviderError(
                        "BaoStock industry response has an unexpected schema"
                    )
                rows.append(BaoStockIndustryRow(*values))
            if not rows:
                raise BaoStockProviderError("BaoStock returned no industry rows")
            return tuple(rows)
        finally:
            bs.logout()
