from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from .models import CatalogSnapshot, InstrumentRule


_RULE_SOURCE = {
    0: "Shenzhen Stock Exchange trading rules: https://www.szse.cn/lawrules/rule/trade/current/",
    1: "Shanghai Stock Exchange trading rules: https://www.sse.com.cn/lawandrules/sselawsrules/trade/",
    103: "Beijing Stock Exchange trading rules: https://www.bse.cn/",
}


def build_official_stock_t0_snapshot(
    security_scope_path: Path, *, as_of_date: str = None
) -> CatalogSnapshot:
    raw = json.loads(Path(security_scope_path).read_text(encoding="utf-8"))
    entries = raw.get("entries", [])
    rules = []
    for entry in entries:
        market = int(entry["mktcode"])
        code = str(entry["tgtcode"])
        if market not in _RULE_SOURCE:
            continue
        instrument_type = (
            "b_share" if code.startswith(("200", "900")) else "a_share_stock"
        )
        rules.append(
            InstrumentRule(
                market,
                code,
                instrument_type,
                False,
                None,
                None,
                _RULE_SOURCE[market],
            )
        )
    if not rules:
        raise ValueError("official security scope contains no recognized A/B-share stocks")
    canonical = [dict(item.__dict__) for item in rules]
    digest = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    snapshot_date = as_of_date or date.today().isoformat()
    return CatalogSnapshot(
        f"exchange-stock-rules-{snapshot_date}-{digest[:12]}",
        "sse-szse-bse",
        "https://www.sse.com.cn/assortment/fund/etf/rules/",
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        "Public exchange trading rules; current supplied universe is classified as exchange-listed stocks",
        instrument_rules=tuple(rules),
    )
