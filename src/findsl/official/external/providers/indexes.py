from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO
from typing import Optional, Tuple

from .eastmoney import ExternalProviderError, security_market_code


@dataclass(frozen=True)
class IndexDefinition:
    source: str
    code: str
    name: str
    full_name: str


@dataclass(frozen=True)
class IndexConstituent:
    code: str
    name: str
    weight: Optional[float]
    effective_date: Optional[str]


class _BrowserHttp:
    def __init__(self, *, timeout_seconds: float = 60.0, session=None):
        if session is None:
            try:
                from curl_cffi import requests
            except ImportError as exc:
                raise ExternalProviderError(
                    "official index providers require the external-data dependencies"
                ) from exc
            session = requests.Session()
        self.session = session
        self.timeout_seconds = timeout_seconds

    def get(self, url, *, params=None):
        response = self.session.get(
            url,
            params=params,
            timeout=self.timeout_seconds,
            impersonate="chrome",
        )
        response.raise_for_status()
        return response

    def post(self, url, *, json, headers=None):
        response = self.session.post(
            url,
            json=json,
            headers=headers,
            timeout=self.timeout_seconds,
            impersonate="chrome",
        )
        response.raise_for_status()
        return response


class CsindexProvider:
    source = "csindex"
    source_url = "https://www.csindex.com.cn/"
    license_note = "CSI official public index list and constituent download"

    def __init__(self, *, http=None):
        self.http = http or _BrowserHttp()

    def list_indices(self) -> Tuple[IndexDefinition, ...]:
        import pandas as pd

        response = self.http.post(
            "https://www.csindex.com.cn/csindex-home/exportExcel/indexAll/CH",
            json={
                "sorter": {"sortField": "null", "sortOrder": None},
                "pager": {"pageNum": 1, "pageSize": 10},
                "indexFilter": {
                    "ifCustomized": None,
                    "ifTracked": None,
                    "ifWeightCapped": None,
                    "indexCompliance": None,
                    "hotSpot": None,
                    "indexClassify": None,
                    "currency": None,
                    "region": None,
                    "indexSeries": ["1"],
                    "undefined": None,
                },
            },
            headers={"Content-Type": "application/json;charset=UTF-8"},
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            frame = pd.read_excel(BytesIO(response.content))
        result = []
        for row in frame.to_dict("records"):
            code = str(row.get("指数代码") or "").strip().zfill(6)
            name = str(row.get("指数简称") or "").strip()
            full_name = str(row.get("指数全称") or name).strip()
            if len(code) == 6 and name:
                result.append(IndexDefinition(self.source, code, name, full_name))
        if not result:
            raise ExternalProviderError("CSI returned an empty index list")
        return tuple(result)

    def list_constituents(self, index: IndexDefinition) -> Tuple[IndexConstituent, ...]:
        import pandas as pd

        urls = (
            (
                f"https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/closeweight/{index.code}closeweight.xls",
                True,
            ),
            (
                f"https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/cons/{index.code}cons.xls",
                False,
            ),
        )
        last_error = None
        for url, has_weight in urls:
            try:
                response = self.http.get(url)
                frame = pd.read_excel(BytesIO(response.content))
                rows = []
                for row in frame.to_dict("records"):
                    code = _security_code(
                        _first_present(
                            row,
                            "成分券代码",
                            "成份券代码Constituent Code",
                        )
                    )
                    if security_market_code(code) is None:
                        continue
                    raw_date = _first_present(row, "日期", "日期Date")
                    parsed_date = _parse_date(pd, raw_date)
                    effective = None if pd.isna(parsed_date) else parsed_date.date().isoformat()
                    raw_weight = (
                        _first_present(row, "权重", "权重(%)weight")
                        if has_weight
                        else None
                    )
                    weight = None if raw_weight is None or pd.isna(raw_weight) else float(raw_weight)
                    rows.append(
                        IndexConstituent(
                            code,
                            str(
                                _first_present(
                                    row,
                                    "成分券名称",
                                    "成份券名称Constituent Name",
                                )
                                or ""
                            ).strip(),
                            weight,
                            effective,
                        )
                    )
                if rows:
                    return tuple(rows)
            except Exception as exc:
                last_error = exc
        raise ExternalProviderError(
            f"CSI returned no constituents for {index.code} {index.name}: {last_error}"
        )


def _first_present(row, *columns):
    for column in columns:
        value = row.get(column)
        if value is not None:
            return value
    return None


def _security_code(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)).zfill(6)
    return str(value).strip().split(".", 1)[0].zfill(6)


def _parse_date(pd, value):
    text = str(value).strip().split(".", 1)[0]
    if text.isdigit() and len(text) == 8:
        return pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    return pd.to_datetime(value, errors="coerce")


class AkshareCsindexProvider:
    """CSI definitions with current constituents from AKShare/Eastmoney.

    This provider is deliberately identified as third-party data.  It is used
    when the official CSI constituent files reject automated retrieval, so the
    resulting snapshot never claims official-constituent provenance.
    """

    source = "akshare-eastmoney-index"
    source_url = "https://github.com/akfamily/akshare"
    license_note = (
        "AKShare index_stock_cons interface backed by Eastmoney public data; "
        "use subject to upstream terms"
    )

    def __init__(self, *, definitions_provider=None, akshare_module=None):
        self.definitions_provider = definitions_provider or CsindexProvider()
        self._akshare_module = akshare_module

    def list_indices(self) -> Tuple[IndexDefinition, ...]:
        return tuple(
            IndexDefinition(self.source, item.code, item.name, item.full_name)
            for item in self.definitions_provider.list_indices()
        )

    def list_constituents(self, index: IndexDefinition) -> Tuple[IndexConstituent, ...]:
        import pandas as pd

        if self._akshare_module is None:
            import akshare as akshare_module
        else:
            akshare_module = self._akshare_module
        frame = akshare_module.index_stock_cons(symbol=index.code)
        required = {"品种代码", "品种名称", "纳入日期"}
        if not required.issubset(frame.columns):
            raise ExternalProviderError(
                f"AKShare returned invalid constituents for {index.code}: "
                f"{sorted(str(item) for item in frame.columns)}"
            )
        rows = []
        for row in frame.to_dict("records"):
            code = str(row.get("品种代码") or "").strip().zfill(6)
            if security_market_code(code) is None:
                continue
            raw_date = row.get("纳入日期")
            parsed_date = pd.to_datetime(raw_date, errors="coerce")
            effective = None if pd.isna(parsed_date) else parsed_date.date().isoformat()
            rows.append(
                IndexConstituent(
                    code,
                    str(row.get("品种名称") or "").strip(),
                    None,
                    effective,
                )
            )
        if not rows:
            raise ExternalProviderError(
                f"AKShare returned no constituents for {index.code} {index.name}"
            )
        return tuple(rows)


class AkshareIndexProvider:
    """Current SSE/SZSE index definitions and constituents exposed by AKShare."""

    source = "akshare-public-index"
    source_url = "https://github.com/akfamily/akshare"
    license_note = (
        "AKShare index_stock_info and index_stock_cons public interfaces; "
        "retain upstream attribution and snapshot date"
    )

    def __init__(self, *, akshare_module=None):
        self._akshare_module = akshare_module

    def _akshare(self):
        if self._akshare_module is not None:
            return self._akshare_module
        import akshare

        return akshare

    def list_indices(self) -> Tuple[IndexDefinition, ...]:
        frame = self._akshare().index_stock_info()
        required = {"index_code", "display_name"}
        if not required.issubset(frame.columns):
            raise ExternalProviderError(
                f"AKShare returned invalid index definitions: {sorted(frame.columns)}"
            )
        rows = []
        for item in frame.to_dict("records"):
            code = str(item.get("index_code") or "").strip().upper()
            name = str(item.get("display_name") or "").strip()
            if len(code) == 6 and code.isalnum() and name:
                rows.append(IndexDefinition(self.source, code, name, name))
        if not rows:
            raise ExternalProviderError("AKShare returned no public index definitions")
        return tuple(rows)

    def list_constituents(self, index: IndexDefinition) -> Tuple[IndexConstituent, ...]:
        import pandas as pd

        frame = self._akshare().index_stock_cons(symbol=index.code)
        required = {"品种代码", "品种名称", "纳入日期"}
        if not required.issubset(frame.columns):
            raise ExternalProviderError(
                f"AKShare returned invalid constituents for {index.code}: "
                f"{sorted(str(item) for item in frame.columns)}"
            )
        rows = []
        for item in frame.to_dict("records"):
            code = str(item.get("品种代码") or "").strip().zfill(6)
            if security_market_code(code) is None:
                continue
            parsed_date = pd.to_datetime(item.get("纳入日期"), errors="coerce")
            effective = None if pd.isna(parsed_date) else parsed_date.date().isoformat()
            rows.append(
                IndexConstituent(
                    code,
                    str(item.get("品种名称") or "").strip(),
                    None,
                    effective,
                )
            )
        if not rows:
            raise ExternalProviderError(
                f"AKShare returned no constituents for {index.code} {index.name}"
            )
        return tuple(rows)


class CniProvider:
    source = "cnindex"
    source_url = "https://www.cnindex.com.cn/"
    license_note = "CNI official public index and historical constituent download"

    def __init__(self, *, http=None):
        self.http = http or _BrowserHttp()

    def list_indices(self) -> Tuple[IndexDefinition, ...]:
        response = self.http.get(
            "https://www.cnindex.com.cn/index/indexList",
            params={"channelCode": "-1", "rows": "2000", "pageNum": "1"},
        )
        payload = response.json()
        rows = payload.get("data", {}).get("rows", [])
        result = []
        for row in rows:
            code = str(row.get("indexcode") or "").strip().zfill(6)
            name = str(row.get("indexname") or "").strip()
            full_name = str(row.get("indexfullcname") or name).strip()
            if len(code) == 6 and name:
                result.append(IndexDefinition(self.source, code, name, full_name))
        if not result:
            raise ExternalProviderError("CNI returned an empty index list")
        return tuple(result)

    def list_constituents(self, index: IndexDefinition) -> Tuple[IndexConstituent, ...]:
        import pandas as pd

        response = self.http.get(
            "https://www.cnindex.com.cn/sample-detail/download-history",
            params={"indexcode": index.code},
        )
        frame = pd.read_excel(BytesIO(response.content))
        if len(frame.columns) < 6:
            raise ExternalProviderError(
                f"CNI returned an invalid history workbook for {index.code}"
            )
        frame = frame.iloc[:, :6]
        frame.columns = ["日期", "样本代码", "样本简称", "所属行业", "总市值", "权重"]
        parsed_dates = pd.to_datetime(frame["日期"], errors="coerce")
        latest = parsed_dates.max()
        if pd.isna(latest):
            raise ExternalProviderError(f"CNI history has no valid date for {index.code}")
        current = frame.loc[parsed_dates == latest]
        rows = []
        for row in current.to_dict("records"):
            code = str(row.get("样本代码") or "").strip().zfill(6)
            if security_market_code(code) is None:
                continue
            raw_weight = row.get("权重")
            weight = None if raw_weight is None or pd.isna(raw_weight) else float(raw_weight)
            rows.append(
                IndexConstituent(
                    code,
                    str(row.get("样本简称") or "").strip(),
                    weight,
                    latest.date().isoformat(),
                )
            )
        if not rows:
            raise ExternalProviderError(f"CNI returned no constituents for {index.code}")
        return tuple(rows)
