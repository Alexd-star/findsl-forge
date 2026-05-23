from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from .errors import ConfigError


@dataclass(frozen=True)
class Registry:
    indicators: Dict[str, Dict[str, Any]]
    tables: Dict[str, Dict[str, Any]]
    functions: Dict[str, Dict[str, Any]]

    @classmethod
    def load(cls, config_dir: Path) -> "Registry":
        return cls(
            indicators=_read_json(config_dir / "indicators.json"),
            tables=_read_json(config_dir / "tables.json"),
            functions=_read_json(config_dir / "functions.json"),
        )

    def indicator(self, name: str) -> Dict[str, Any]:
        try:
            return self.indicators[name]
        except KeyError as exc:
            raise ConfigError(f"Unknown indicator: {name}") from exc

    def table(self, name: str) -> Dict[str, Any]:
        try:
            return self.tables[name]
        except KeyError as exc:
            raise ConfigError(f"Unknown table: {name}") from exc

    def function(self, name: str) -> Dict[str, Any]:
        for key in (name, name.lower(), name.upper()):
            if key in self.functions:
                return self.functions[key]
        raise ConfigError(f"Unknown function: {name}")


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def default_registry() -> Registry:
    root = Path(__file__).resolve().parents[2]
    return Registry.load(root / "configs")
