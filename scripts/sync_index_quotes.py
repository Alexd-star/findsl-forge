from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path


INDEX_SYMBOLS = {
    "000001": "sh000001",
    "000300": "sh000300",
    "399001": "sz399001",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    import akshare as ak
    import pandas as pd

    rows = []
    counts = {}
    for index_code, symbol in INDEX_SYMBOLS.items():
        frame = ak.stock_zh_index_daily(symbol=symbol).copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date", "close"]).sort_values("date")
        frame["pct_change"] = frame["close"].pct_change() * 100.0
        counts[index_code] = len(frame)
        for item in frame.to_dict("records"):
            rows.append(
                {
                    "index_code": index_code,
                    "bizdate": item["date"].date().isoformat(),
                    "open": _number(item.get("open")),
                    "high": _number(item.get("high")),
                    "low": _number(item.get("low")),
                    "close": _number(item.get("close")),
                    "volume": _integer(item.get("volume")),
                    "pct_change": _number(item.get("pct_change")),
                    "source": "akshare-sina-index-daily",
                }
            )
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    snapshot_date = args.as_of_date or date.today().isoformat()
    snapshot_id = f"akshare-sina-index-{snapshot_date}-{digest[:12]}"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "snapshot_id",
                "index_code",
                "bizdate",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "pct_change",
                "source",
            ),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "snapshot_id": snapshot_id,
                    **{key: ("\\N" if value is None else value) for key, value in row.items()},
                }
            )
    runtime = {
        "schema_version": 1,
        "resource_id": "external_index_quote",
        "entries": [
            {
                "scope_code": code,
                "snapshot_id": snapshot_id,
                "source": "akshare-sina-index-daily",
                "as_of_date": snapshot_date,
            }
            for code in sorted(INDEX_SYMBOLS)
        ],
    }
    Path(args.runtime).write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "source": "akshare-sina-index-daily",
        "source_url": "https://github.com/akfamily/akshare",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": snapshot_date,
        "content_sha256": digest,
        "rows": len(rows),
        "index_counts": counts,
        "output": str(output),
    }
    Path(args.report).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else round(number, 10)


def _integer(value):
    number = _number(value)
    return None if number is None else int(number)


if __name__ == "__main__":
    main()
