from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


class ExternalProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoardDefinition:
    board_type: str
    code: str
    name: str


@dataclass(frozen=True)
class BoardConstituent:
    code: str
    name: str
    rank: int


@dataclass(frozen=True)
class SecurityProfile:
    code: str
    name: str
    industry: str
    region: str
    concepts: Tuple[str, ...]


class EastmoneyBoardProvider:
    source = "eastmoney"
    source_url = "https://quote.eastmoney.com/center/boardlist.html"
    license_note = "Public quotation endpoint; retain source attribution and snapshot date"

    _TOKEN = "bd1d9ddb04089700cf9c27f6f7426281"
    _BOARD_ENDPOINTS = {
        "concept": ("https://79.push2.eastmoney.com/api/qt/clist/get", "m:90 t:3 f:!50", "f12"),
        "industry": ("https://17.push2.eastmoney.com/api/qt/clist/get", "m:90 t:2 f:!50", "f3"),
    }

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        max_attempts: int = 5,
        backoff_seconds: float = 0.5,
        trust_environment_proxy: bool = False,
        session=None,
        browser_session=None,
        cache_dir: Path = None,
        request_interval_seconds: float = 0.0,
    ):
        if session is None:
            try:
                import requests
            except ImportError as exc:
                raise ExternalProviderError(
                    "Eastmoney provider requires the external-data optional dependencies"
                ) from exc
            session = requests.Session()
        session.trust_env = trust_environment_proxy
        self._session = session
        if browser_session is None:
            try:
                from curl_cffi import requests as browser_requests

                browser_session = browser_requests.Session()
            except ImportError:
                browser_session = None
        self._browser_session = browser_session
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.request_interval_seconds = max(0.0, float(request_interval_seconds))
        self._last_request_at = 0.0

    def list_boards(self, board_type: str) -> Tuple[BoardDefinition, ...]:
        try:
            url, scope, order_field = self._BOARD_ENDPOINTS[board_type]
        except KeyError as exc:
            raise ValueError(f"unsupported Eastmoney board type: {board_type}") from exc
        rows = self._fetch_pages(
            url,
            {
                "po": "1",
                "np": "1",
                "ut": self._TOKEN,
                "fltt": "2",
                "invt": "2",
                "fid": order_field,
                "fs": scope,
                "fields": "f12,f14",
            },
        )
        boards = []
        for row in rows:
            code = str(row.get("f12") or "").strip()
            name = str(row.get("f14") or "").strip()
            if code and name:
                boards.append(BoardDefinition(board_type, code, name))
        if not boards:
            raise ExternalProviderError(f"Eastmoney returned no {board_type} boards")
        return tuple(boards)

    def list_constituents(self, board: BoardDefinition) -> Tuple[BoardConstituent, ...]:
        rows = self._fetch_pages(
            "https://29.push2.eastmoney.com/api/qt/clist/get",
            {
                "po": "1",
                "np": "1",
                "ut": self._TOKEN,
                "fltt": "2",
                "invt": "2",
                "fid": "f12" if board.board_type == "concept" else "f3",
                "fs": f"b:{board.code} f:!50",
                "fields": "f12,f14",
            },
        )
        constituents = []
        for index, row in enumerate(rows, start=1):
            code = str(row.get("f12") or "").strip().zfill(6)
            name = str(row.get("f14") or "").strip()
            if len(code) == 6 and code.isdigit() and name:
                constituents.append(BoardConstituent(code, name, index))
        if not constituents:
            raise ExternalProviderError(
                f"Eastmoney returned no constituents for {board.code} {board.name}"
            )
        return tuple(constituents)

    def list_security_profiles(self) -> Tuple[SecurityProfile, ...]:
        rows = self._fetch_pages(
            "https://push2.eastmoney.com/api/qt/clist/get",
            {
                "po": "1",
                "np": "1",
                "ut": self._TOKEN,
                "fltt": "2",
                "invt": "2",
                "fid": "f12",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f12,f13,f14,f100,f102,f103",
            },
        )
        profiles = []
        for row in rows:
            code = str(row.get("f12") or "").strip().zfill(6)
            name = str(row.get("f14") or "").strip()
            if security_market_code(code) is None or not name:
                continue
            concepts = tuple(
                dict.fromkeys(
                    item.strip()
                    for item in str(row.get("f103") or "").split(",")
                    if item.strip() and item.strip() != "-"
                )
            )
            profiles.append(
                SecurityProfile(
                    code,
                    name,
                    str(row.get("f100") or "").strip(),
                    str(row.get("f102") or "").strip(),
                    concepts,
                )
            )
        if not profiles:
            raise ExternalProviderError("Eastmoney returned no security profiles")
        return tuple(profiles)

    def _fetch_pages(self, url: str, base_params: Dict[str, str]) -> Tuple[dict, ...]:
        page = 1
        page_size = 100
        total: Optional[int] = None
        rows = []
        while total is None or len(rows) < total:
            payload = self._request_json(
                url, {**base_params, "pn": str(page), "pz": str(page_size)}
            )
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ExternalProviderError("Eastmoney response does not contain a data object")
            if total is None:
                total = int(data.get("total") or 0)
            chunk = data.get("diff") or []
            if not isinstance(chunk, list):
                raise ExternalProviderError("Eastmoney response diff is not a list")
            rows.extend(item for item in chunk if isinstance(item, dict))
            if not chunk or len(rows) >= total:
                break
            page += 1
        return tuple(rows[:total] if total is not None else rows)

    def _request_json(self, url: str, params: Dict[str, str]) -> dict:
        cached = self._read_cache(url, params)
        if cached is not None:
            return cached
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._throttle()
                response = self._get(url, params)
                response.raise_for_status()
                payload = response.json()
                if payload.get("rc") not in {0, None}:
                    raise ExternalProviderError(
                        f"Eastmoney returned rc={payload.get('rc')}"
                    )
                self._write_cache(url, params, payload)
                return payload
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(self.backoff_seconds * attempt)
        raise ExternalProviderError(
            f"Eastmoney request failed after {self.max_attempts} attempts: {last_error}"
        ) from last_error

    def _throttle(self) -> None:
        if self.request_interval_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _cache_path(self, url: str, params: Dict[str, str]) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        canonical = json.dumps(
            {"url": url, "params": sorted((str(k), str(v)) for k, v in params.items())},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, url: str, params: Dict[str, str]) -> Optional[dict]:
        path = self._cache_path(url, params)
        if path is None or not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        expected_params = sorted((str(k), str(v)) for k, v in params.items())
        if record.get("url") != url or record.get("params") != [list(item) for item in expected_params]:
            return None
        payload = record.get("payload")
        return payload if isinstance(payload, dict) else None

    def _write_cache(self, url: str, params: Dict[str, str], payload: dict) -> None:
        path = self._cache_path(url, params)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "url": url,
            "params": sorted((str(k), str(v)) for k, v in params.items()),
            "payload": payload,
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _get(self, url: str, params: Dict[str, str]):
        headers = {
            "User-Agent": "Mozilla/5.0 FinDSL-Forge/0.1",
            "Connection": "close",
        }
        try:
            return self._session.get(
                url,
                params=params,
                timeout=self.timeout_seconds,
                headers=headers,
            )
        except Exception:
            if self._browser_session is None:
                raise
            return self._browser_session.get(
                url,
                params=params,
                timeout=self.timeout_seconds,
                headers=headers,
                impersonate="chrome",
            )


def security_market_code(code: str) -> Optional[int]:
    value = str(code).zfill(6)
    if value.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return 1
    if value.startswith(("000", "001", "002", "003", "200", "300", "301")):
        return 0
    if value.startswith(("4", "8", "92")):
        return 103
    return None
