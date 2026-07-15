from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple
from urllib.parse import parse_qs

from .eastmoney import ExternalProviderError


@dataclass(frozen=True)
class BaiduScopeDefinition:
    scope_type: str
    code: str
    name: str
    description: str = ""


@dataclass(frozen=True)
class BaiduSecurityClassification:
    security_code: str
    security_name: str
    scopes: Tuple[BaiduScopeDefinition, ...]


class BaiduRelatedBlockProvider:
    source = "baidu-related-block"
    source_url = "https://finance.pae.baidu.com/api/getrelatedblock"
    license_note = (
        "Baidu Stock public related-block endpoint; retain source attribution "
        "and snapshot date"
    )
    max_batch_size = 20
    _CATEGORY_TYPES = {"行业": "industry", "概念": "concept", "地域": "region"}

    def __init__(
        self,
        *,
        session=None,
        cache_dir: Path = None,
        timeout_seconds: float = 20.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        request_interval_seconds: float = 0.1,
        trust_environment_proxy: bool = False,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must not be negative")
        if session is None:
            import requests

            session = requests.Session()
        session.trust_env = trust_environment_proxy
        self.session = session
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.request_interval_seconds = max(0.0, float(request_interval_seconds))
        self._last_request_at = 0.0

    def list_classifications(
        self, identities: Iterable[tuple]
    ) -> Tuple[BaiduSecurityClassification, ...]:
        normalized = tuple(
            (str(code).strip().zfill(6), str(name).strip())
            for code, name in identities
            if str(code).strip() and str(name).strip()
        )
        if not normalized:
            raise ValueError("at least one security identity is required")
        rows = []
        for offset in range(0, len(normalized), self.max_batch_size):
            batch = normalized[offset : offset + self.max_batch_size]
            rows.extend(self._fetch_batch(batch))
        return tuple(rows)

    def _fetch_batch(self, batch):
        codes = tuple(code for code, _name in batch)
        payload = self._read_cache(codes)
        if payload is None:
            payload = self._request(codes)
            self._write_cache(codes, payload)
        result = payload.get("Result")
        if str(payload.get("ResultCode")) != "0" or not isinstance(result, dict):
            raise ExternalProviderError("Baidu related-block response is not successful")
        missing = sorted(set(codes) - set(result))
        if missing:
            raise ExternalProviderError(
                "Baidu related-block response omitted requested securities: "
                + ",".join(missing)
            )
        names = dict(batch)
        return tuple(
            BaiduSecurityClassification(
                code,
                names[code],
                self._parse_scopes(result[code]),
            )
            for code in codes
        )

    def _request(self, codes):
        stocks = [
            {"code": code, "market": "ab", "type": "stock"} for code in codes
        ]
        params = {
            "stock": json.dumps(stocks, ensure_ascii=False, separators=(",", ":")),
            "finClientType": "pc",
        }
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                self._throttle()
                response = self.session.get(
                    self.source_url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                        "Referer": "https://gushitong.baidu.com/",
                    },
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ExternalProviderError("Baidu returned a non-object response")
                return payload
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(self.backoff_seconds * attempt)
        raise ExternalProviderError(
            f"Baidu related-block request failed after {self.max_attempts} attempts: "
            f"{last_error}"
        ) from last_error

    @classmethod
    def _parse_scopes(cls, categories):
        if not isinstance(categories, list):
            raise ExternalProviderError("Baidu related-block categories are invalid")
        scopes = {}
        for category in categories:
            if not isinstance(category, dict):
                continue
            scope_type = cls._CATEGORY_TYPES.get(str(category.get("name") or ""))
            if scope_type is None:
                continue
            for item in category.get("list") or ():
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                query = parse_qs(str(item.get("xcx_query") or ""))
                code = str((query.get("code") or ("",))[0]).strip()
                if not name or not code:
                    continue
                scope = BaiduScopeDefinition(
                    scope_type,
                    code,
                    name,
                    str(item.get("describe") or "").strip(),
                )
                scopes[(scope_type, code)] = scope
        return tuple(scopes[key] for key in sorted(scopes))

    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _cache_path(self, codes):
        if self.cache_dir is None:
            return None
        digest = hashlib.sha256("\n".join(codes).encode("ascii")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _read_cache(self, codes):
        path = self._cache_path(codes)
        if path is None or not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_cache(self, codes, payload):
        path = self._cache_path(codes)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
