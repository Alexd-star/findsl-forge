# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "real_samples" / "eastmoney_a_share_sample"
DEFAULT_BEGIN = "20240102"
DEFAULT_END = "20240112"


@dataclass(frozen=True)
class StockSource:
    ts_code: str
    secid: str
    name: str
    market: str


DEFAULT_STOCKS = [
    StockSource(ts_code="600519.SH", secid="1.600519", name="贵州茅台", market="A"),
    StockSource(ts_code="000001.SZ", secid="0.000001", name="平安银行", market="A"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a small public A-share quote sample from Eastmoney.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--begin", default=DEFAULT_BEGIN, help="Begin date in YYYYMMDD.")
    parser.add_argument("--end", default=DEFAULT_END, help="End date in YYYYMMDD.")
    parser.add_argument("--proxy", help="Optional HTTP(S) proxy, for example http://127.0.0.1:7897.")
    parser.add_argument("--refresh", action="store_true", help="Fetch raw JSON again even if cached raw files exist.")
    args = parser.parse_args()

    raw_dir = args.output_dir / "raw"
    rows = []
    sources = []
    for stock in DEFAULT_STOCKS:
        url = eastmoney_kline_url(stock.secid, args.begin, args.end)
        payload = load_or_fetch_payload(raw_dir, stock, args.begin, args.end, url, refresh=args.refresh, proxy=args.proxy)
        parsed_rows = parse_eastmoney_klines(payload, stock)
        rows.extend(parsed_rows)
        sources.append(
            {
                "ts_code": stock.ts_code,
                "secid": stock.secid,
                "name": stock.name,
                "url": url,
                "rows": len(parsed_rows),
            }
        )

    write_sample(args.output_dir, rows, sources, args.begin, args.end, refresh=args.refresh)
    print(f"Wrote {len(rows)} quote rows to {args.output_dir}")


def eastmoney_kline_url(secid: str, begin: str, end: str) -> str:
    return (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}"
        "&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        "&klt=101&fqt=1"
        f"&beg={begin}&end={end}"
    )


def fetch_json(url: str, proxy: str | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy})) if proxy else urllib.request.build_opener()
            with opener.open(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - network fetch gets a short retry window.
            last_error = exc
            time.sleep(0.8 * (attempt + 1))
    curl_payload = fetch_with_curl(url, proxy=proxy)
    if curl_payload is not None:
        return curl_payload
    raise RuntimeError(f"Failed to fetch Eastmoney payload after retries: {url}") from last_error


def load_or_fetch_payload(
    raw_dir: Path,
    stock: StockSource,
    begin: str,
    end: str,
    url: str,
    refresh: bool = False,
    proxy: str | None = None,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{stock.secid.replace('.', '_')}_{begin}_{end}.json"
    if raw_path.exists() and not refresh:
        return json.loads(raw_path.read_text(encoding="utf-8"))
    payload = fetch_json(url, proxy=proxy)
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def fetch_with_curl(url: str, proxy: str | None = None) -> dict[str, Any] | None:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        return None
    command = [
        curl,
        "-L",
        "--ssl-no-revoke",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "20",
    ]
    if proxy:
        command.extend(["--proxy", proxy])
    command.append(url)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return json.loads(completed.stdout)


def parse_eastmoney_klines(payload: dict[str, Any], stock: StockSource) -> list[dict[str, str]]:
    if payload.get("rc") != 0:
        raise RuntimeError(f"Eastmoney returned rc={payload.get('rc')} for {stock.ts_code}")
    data = payload.get("data") or {}
    klines = data.get("klines") or []
    if not klines:
        raise RuntimeError(f"Eastmoney returned no kline rows for {stock.ts_code}")

    rows = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 11:
            raise RuntimeError(f"Unexpected Eastmoney kline row for {stock.ts_code}: {line!r}")
        trade_date, _open, close, _high, _low, volume, _amount, _amp, _pct, _change, turnover = parts[:11]
        rows.append(
            {
                "ts_code": stock.ts_code,
                "trade_date": trade_date,
                "close": normalize_decimal(close),
                "turnover_rate": normalize_decimal(turnover),
                "volume": str(int(float(volume))),
                "market": stock.market,
            }
        )
    return rows


def normalize_decimal(value: str) -> str:
    number = float(value)
    text = f"{number:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def write_sample(
    output_dir: Path,
    rows: list[dict[str, str]],
    sources: list[dict[str, Any]],
    begin: str,
    end: str,
    refresh: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda row: (row["ts_code"], row["trade_date"]))

    daily_rows = [
        {
            "ts_code": row["ts_code"],
            "trade_date": row["trade_date"],
            "close": row["close"],
            "turnover_rate": row["turnover_rate"],
            "volume": row["volume"],
        }
        for row in rows
    ]
    universe_rows = [
        {
            "ts_code": row["ts_code"],
            "trade_date": row["trade_date"],
            "market": row["market"],
        }
        for row in rows
    ]
    money_rows = [
        {
            "ts_code": row["ts_code"],
            "trade_date": row["trade_date"],
            "main_net_inflow": "0",
        }
        for row in rows
    ]

    write_csv(output_dir / "daily_quote.csv", daily_rows, ["ts_code", "trade_date", "close", "turnover_rate", "volume"])
    write_csv(output_dir / "stock_universe.csv", universe_rows, ["ts_code", "trade_date", "market"])
    write_csv(output_dir / "money_flow.csv", money_rows, ["ts_code", "trade_date", "main_net_inflow"])
    write_queries(output_dir / "queries.jsonl")
    write_metadata(output_dir / "source_metadata.json", sources, begin, end, refresh=refresh)
    write_readme(output_dir / "README.md")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_queries(path: Path) -> None:
    cases = [
        {
            "name": "真实行情样本：A股换手率高于0.3",
            "dsl": 'filter(date_between("2024-01-02", "2024-01-12") & market("A") & indicator("turnover_rate") > 0.3)',
            "scenario": "real_quote_turnover",
        },
        {
            "name": "真实行情样本：近2日收盘收益率为正",
            "dsl": 'filter(date_between("2024-01-02", "2024-01-12") & RET(indicator("close"), 2) > 0)',
            "scenario": "real_quote_return_rate",
        },
        {
            "name": "真实行情样本：近3日成交量累计超过2000000",
            "dsl": 'filter(date_between("2024-01-02", "2024-01-12") & SUM(indicator("volume"), 3) > 2000000)',
            "scenario": "real_quote_volume_sum",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        for case in cases:
            fh.write(json.dumps(case, ensure_ascii=False) + "\n")


def write_metadata(path: Path, sources: list[dict[str, Any]], begin: str, end: str, refresh: bool = False) -> None:
    created_at = None
    if path.exists() and not refresh:
        try:
            created_at = json.loads(path.read_text(encoding="utf-8")).get("created_at_utc")
        except json.JSONDecodeError:
            created_at = None
    if not created_at:
        created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata = {
        "dataset": "eastmoney_a_share_sample",
        "created_at_utc": created_at,
        "source": "Eastmoney public historical K-line endpoint",
        "source_scope": "daily_quote and stock_universe are derived from Eastmoney K-line rows.",
        "money_flow_scope": (
            "money_flow.csv is a neutral zero-valued placeholder so the existing three-table "
            "sample loader can run quote-only DSLs. It is not used as real money-flow evidence."
        ),
        "date_range": {"begin": begin, "end": end},
        "stocks": sources,
        "field_mapping": {
            "f51": "trade_date",
            "f53": "close",
            "f56": "volume",
            "f61": "turnover_rate",
        },
    }
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_readme(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Eastmoney A 股真实行情小样本",
                "",
                "本目录用于补足答辩中的真实业务样本。`daily_quote.csv` 和 `stock_universe.csv` 来自东方财富公开历史 K 线接口，覆盖贵州茅台 `600519.SH` 与平安银行 `000001.SZ` 在 2024-01-02 至 2024-01-12 的日线数据。",
                "",
                "`money_flow.csv` 是中性占位文件，所有 `main_net_inflow` 为 0，仅用于保持项目既有三表加载器可运行 quote-only DSL。它不能作为真实资金流证据使用，资金流性能与正确性仍以项目已有 Doris evidence 和样例数据为准。",
                "",
                "推荐演示命令：",
                "",
                "```powershell",
                "$env:PYTHONPATH=\"src\"",
                "python -m findsl.cli verify-sql 'filter(date_between(\"2024-01-02\", \"2024-01-12\") & RET(indicator(\"close\"), 2) > 0)' --data-dir data/real_samples/eastmoney_a_share_sample",
                "```",
                "",
                "重新生成：",
                "",
                "```powershell",
                "python scripts\\fetch_real_market_sample.py",
                "# 如果要重新联网刷新 raw JSON，再追加 --refresh；需要代理时加 --proxy \"http://127.0.0.1:7897\"",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
