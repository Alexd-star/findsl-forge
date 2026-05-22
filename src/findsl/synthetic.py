from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class SyntheticDataset:
    output_dir: Path
    stock_count: int
    day_count: int
    seed: int
    start_date: str

    @property
    def row_count(self) -> int:
        return self.stock_count * self.day_count

    def files(self) -> Dict[str, Path]:
        return {
            "daily_quote": self.output_dir / "daily_quote.csv",
            "money_flow": self.output_dir / "money_flow.csv",
            "stock_universe": self.output_dir / "stock_universe.csv",
        }

    def to_markdown(self) -> str:
        return "\n".join(
            [
                "# Synthetic Dataset",
                "",
                f"- Output directory: `{self.output_dir}`",
                f"- Stock count: {self.stock_count}",
                f"- Day count: {self.day_count}",
                f"- Rows per base table: {self.row_count}",
                f"- Seed: {self.seed}",
                f"- Start date: {self.start_date}",
                "",
                "| Logical table | File |",
                "|---|---|",
                *[f"| {name} | `{path}` |" for name, path in self.files().items()],
            ]
        )


def write_synthetic_dataset(
    output_dir: Path,
    stock_count: int = 300,
    day_count: int = 260,
    start_date: str = "2025-01-01",
    seed: int = 2026,
) -> SyntheticDataset:
    if stock_count <= 0:
        raise ValueError("stock_count must be positive")
    if day_count <= 0:
        raise ValueError("day_count must be positive")
    start = date.fromisoformat(start_date)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    codes = [_stock_code(idx) for idx in range(stock_count)]
    dates = [(start + timedelta(days=offset)).isoformat() for offset in range(day_count)]
    rng = random.Random(seed)

    _write_csv(
        output_dir / "daily_quote.csv",
        ["ts_code", "trade_date", "close", "turnover_rate", "volume"],
        _daily_quote_rows(codes, dates, rng),
    )
    _write_csv(
        output_dir / "money_flow.csv",
        ["ts_code", "trade_date", "main_net_inflow"],
        _money_flow_rows(codes, dates, rng),
    )
    _write_csv(
        output_dir / "stock_universe.csv",
        ["ts_code", "trade_date", "market"],
        _stock_universe_rows(codes, dates),
    )
    return SyntheticDataset(
        output_dir=output_dir,
        stock_count=stock_count,
        day_count=day_count,
        seed=seed,
        start_date=start_date,
    )


def _daily_quote_rows(codes: List[str], dates: List[str], rng: random.Random) -> Iterable[Dict[str, object]]:
    base_prices = {code: 8.0 + (idx % 80) * 0.7 for idx, code in enumerate(codes)}
    for stock_idx, code in enumerate(codes):
        price = base_prices[code]
        for day_idx, trade_date in enumerate(dates):
            drift = ((stock_idx * 17 + day_idx * 11) % 23 - 10) * 0.015
            price = max(1.0, price * (1 + drift / 100) + rng.uniform(-0.08, 0.08))
            turnover = 0.2 + ((stock_idx * 19 + day_idx * 7) % 500) / 100
            volume = 900 + ((stock_idx * 53 + day_idx * 31) % 9000) + rng.randint(0, 800)
            yield {
                "ts_code": code,
                "trade_date": trade_date,
                "close": f"{price:.2f}",
                "turnover_rate": f"{turnover:.2f}",
                "volume": volume,
            }


def _money_flow_rows(codes: List[str], dates: List[str], rng: random.Random) -> Iterable[Dict[str, object]]:
    for stock_idx, code in enumerate(codes):
        for day_idx, trade_date in enumerate(dates):
            wave = ((stock_idx * 29 + day_idx * 13) % 2000) - 1000
            noise = rng.randint(-300, 300)
            yield {
                "ts_code": code,
                "trade_date": trade_date,
                "main_net_inflow": wave + noise,
            }


def _stock_universe_rows(codes: List[str], dates: List[str]) -> Iterable[Dict[str, object]]:
    for stock_idx, code in enumerate(codes):
        market = "A" if stock_idx % 5 else "B"
        for trade_date in dates:
            yield {
                "ts_code": code,
                "trade_date": trade_date,
                "market": market,
            }


def _write_csv(path: Path, columns: List[str], rows: Iterable[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _stock_code(idx: int) -> str:
    suffix = "SH" if idx % 2 == 0 else "SZ"
    return f"{idx + 1:06d}.{suffix}"
