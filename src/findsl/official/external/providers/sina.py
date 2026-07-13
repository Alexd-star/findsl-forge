from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from .eastmoney import ExternalProviderError, security_market_code


@dataclass(frozen=True)
class SinaSectorDefinition:
    sector_type: str
    code: str
    name: str


@dataclass(frozen=True)
class SinaSectorConstituent:
    code: str
    name: str


class SinaSectorProvider:
    source = "sina-finance"
    source_url = "https://finance.sina.com.cn/stock/sl/"
    license_note = "Sina public sector endpoints; retain attribution and snapshot date"

    _LIST_ENDPOINT = "http://money.finance.sina.com.cn/q/view/newFLJK.php"
    _COUNT_ENDPOINT = (
        "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "Market_Center.getHQNodeStockCount"
    )
    _DETAIL_ENDPOINT = (
        "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
        "Market_Center.getHQNodeData"
    )
    _PARAMETERS = {"concept": "class", "region": "area", "industry": "industry"}

    def __init__(
        self,
        *,
        session=None,
        cache_dir: Path = None,
        timeout_seconds: float = 20.0,
        max_attempts: int = 5,
        request_interval_seconds: float = 0.05,
    ):
        if session is None:
            import requests

            session = requests.Session()
        session.trust_env = False
        self.session = session
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.request_interval_seconds = max(0.0, float(request_interval_seconds))
        self._last_request_at = 0.0

    def list_sectors(self, sector_type: str) -> Tuple[SinaSectorDefinition, ...]:
        try:
            parameter = self._PARAMETERS[sector_type]
        except KeyError as exc:
            raise ValueError(f"unsupported Sina sector type: {sector_type}") from exc
        text = self._get_text(self._LIST_ENDPOINT, {"param": parameter})
        start = text.find("{")
        if start < 0:
            raise ExternalProviderError("Sina sector response has no JSON object")
        try:
            payload = json.loads(text[start:])
        except json.JSONDecodeError as exc:
            raise ExternalProviderError("Sina sector response is not valid JSON") from exc
        sectors = []
        for value in payload.values():
            fields = str(value).split(",")
            if len(fields) < 2:
                continue
            code, name = fields[0].strip(), fields[1].strip()
            if code and name:
                sectors.append(SinaSectorDefinition(sector_type, code, name))
        if not sectors:
            raise ExternalProviderError(f"Sina returned no {sector_type} sectors")
        return tuple(sectors)

    def list_constituents(
        self, sector: SinaSectorDefinition
    ) -> Tuple[SinaSectorConstituent, ...]:
        count_text = self._get_text(self._COUNT_ENDPOINT, {"node": sector.code})
        try:
            count = int(json.loads(count_text))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExternalProviderError("Sina sector count is invalid") from exc
        rows = {}
        for page in range(1, math.ceil(count / 80) + 1):
            text = self._get_text(
                self._DETAIL_ENDPOINT,
                {
                    "page": str(page),
                    "num": "80",
                    "sort": "symbol",
                    "asc": "1",
                    "node": sector.code,
                    "symbol": "",
                    "_s_r_a": "page",
                },
            )
            try:
                from akshare.utils import demjson

                payload = demjson.decode(text)
            except Exception as exc:
                raise ExternalProviderError("Sina constituent response is invalid") from exc
            for item in payload if isinstance(payload, list) else ():
                code = str(item.get("code") or "").strip().zfill(6)
                name = str(item.get("name") or "").strip()
                if security_market_code(code) is not None and name:
                    rows[code] = SinaSectorConstituent(code, name)
        if not rows:
            raise ExternalProviderError(
                f"Sina returned no constituents for {sector.code} {sector.name}"
            )
        return tuple(rows[key] for key in sorted(rows))

    def _get_text(self, url: str, params: Dict[str, str]) -> str:
        cached = self._read_cache(url, params)
        if cached is not None:
            return cached
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._throttle()
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                    headers={"User-Agent": "Mozilla/5.0 FinDSL-Forge/0.1"},
                )
                response.raise_for_status()
                if not response.text.strip():
                    raise ExternalProviderError("Sina returned an empty response")
                self._write_cache(url, params, response.text)
                return response.text
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(min(0.25 * attempt, 1.5))
        raise ExternalProviderError(
            f"Sina request failed after {self.max_attempts} attempts: {last_error}"
        ) from last_error

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _cache_path(self, url: str, params: Dict[str, str]) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        canonical = json.dumps(
            {"url": url, "params": sorted((str(k), str(v)) for k, v in params.items())},
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, url: str, params: Dict[str, str]) -> Optional[str]:
        path = self._cache_path(url, params)
        if path is None or not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        expected = [list(item) for item in sorted((str(k), str(v)) for k, v in params.items())]
        if record.get("url") != url or record.get("params") != expected:
            return None
        text = record.get("text")
        return text if isinstance(text, str) and text.strip() else None

    def _write_cache(self, url: str, params: Dict[str, str], text: str) -> None:
        path = self._cache_path(url, params)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "url": url,
            "params": sorted((str(k), str(v)) for k, v in params.items()),
            "text": text,
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
