from __future__ import annotations

import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Tuple

from .eastmoney import ExternalProviderError, security_market_code


@dataclass(frozen=True)
class ThsConceptDefinition:
    code: str
    name: str
    aliases: Tuple[str, ...]


@dataclass(frozen=True)
class ThsConceptConstituent:
    code: str
    name: str


class _ThsConstituentTableParser(HTMLParser):
    """Extract cells from the constituent table without optional HTML engines."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._table_depth = 0
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        if tag == "table":
            if self._table_depth:
                self._table_depth += 1
            elif "m-pager-table" in attributes.get("class", "").split():
                self._table_depth = 1
            return
        if not self._table_depth:
            return
        if tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag) -> None:
        if not self._table_depth:
            return
        if tag in {"th", "td"} and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(tuple(self._row))
            self._row = None
            self._cell = None
        elif tag == "table":
            self._table_depth -= 1


class ThsConceptProvider:
    source = "ths-concept"
    source_url = "https://q.10jqka.com.cn/gn/"
    license_note = "THS public concept constituent pages; retain attribution and snapshot date"

    def __init__(
        self,
        *,
        cache_dir: Path = None,
        session=None,
        max_attempts: int = 8,
        request_interval_seconds: float = 0.3,
        trust_environment_proxy: bool = False,
        header_factory=None,
    ):
        if session is None:
            import requests

            session = requests.Session()
        session.trust_env = trust_environment_proxy
        self.session = session
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_attempts = max_attempts
        self.request_interval_seconds = max(0.0, float(request_interval_seconds))
        self._last_request_at = 0.0
        self._header_factory = header_factory or self._headers

    def list_constituents(
        self, concept: ThsConceptDefinition
    ) -> Tuple[ThsConceptConstituent, ...]:
        first = self._page(concept.code, 1)
        match = re.search(r'class="page_info">\s*1/(\d+)\s*<', first, re.I)
        pages = int(match.group(1)) if match else 1
        rows = {}
        for page in range(1, pages + 1):
            text = first if page == 1 else self._page(concept.code, page)
            for item in self._parse_table(text):
                rows[item.code] = item
        if not rows:
            raise ExternalProviderError(
                f"THS returned no constituents for {concept.code} {concept.name}"
            )
        return tuple(rows[key] for key in sorted(rows))

    def _page(self, code: str, page: int) -> str:
        cached = self._cache_path(code, page)
        if cached is not None and cached.exists():
            return cached.read_text(encoding="utf-8")
        url = (
            f"https://q.10jqka.com.cn/gn/detail/code/{code}/"
            f"field/264648/order/desc/page/{page}/ajax/1/"
        )
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._throttle()
                response = self.session.get(
                    url,
                    headers=self._header_factory(),
                    timeout=30,
                )
                if response.status_code in {401, 403}:
                    raise ExternalProviderError(
                        f"THS anti-bot response {response.status_code}"
                    )
                response.raise_for_status()
                if "m-pager-table" not in response.text:
                    raise ExternalProviderError("THS page has no constituent table")
                if cached is not None:
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    cached.write_text(response.text, encoding="utf-8")
                return response.text
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(min(attempt * 0.3, 2.0))
        raise ExternalProviderError(
            f"THS page failed after {self.max_attempts} attempts: {code}/{page}: {last_error}"
        ) from last_error

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    @staticmethod
    def _headers():
        import py_mini_racer
        from akshare.datasets import get_ths_js

        runtime = py_mini_racer.MiniRacer()
        runtime.eval(Path(get_ths_js("ths.js")).read_text(encoding="utf-8"))
        token = runtime.call("v")
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
            "Cookie": f"v={token}",
            "Referer": "https://q.10jqka.com.cn/gn/",
            "Connection": "close",
        }

    @staticmethod
    def _parse_table(text: str):
        parser = _ThsConstituentTableParser()
        parser.feed(text)
        header_index = next(
            (
                index
                for index, row in enumerate(parser.rows)
                if "代码" in row and "名称" in row
            ),
            None,
        )
        if header_index is None:
            raise ExternalProviderError("THS constituent table schema changed")
        header = parser.rows[header_index]
        code_index = header.index("代码")
        name_index = header.index("名称")
        rows = []
        for item in parser.rows[header_index + 1 :]:
            if len(item) <= max(code_index, name_index):
                continue
            code = item[code_index].split(".")[0].zfill(6)
            name = item[name_index].strip()
            if security_market_code(code) is not None and name:
                rows.append(ThsConceptConstituent(code, name))
        return tuple(rows)

    def _cache_path(self, code: str, page: int):
        return None if self.cache_dir is None else self.cache_dir / code / f"{page}.html"
