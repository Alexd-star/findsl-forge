from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Tuple


class SecurityScopeCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class SecurityIdentity:
    mktcode: int
    tgtcode: str
    name: str

    def to_dict(self):
        return {"mktcode": self.mktcode, "tgtcode": self.tgtcode, "name": self.name}


@dataclass(frozen=True)
class ResolvedSecurityScope:
    source: str
    name: str
    identities: Tuple[SecurityIdentity, ...]
    explicit_code: bool


class SecurityScopeCatalog:
    def __init__(
        self,
        entries: Tuple[SecurityIdentity, ...],
        *,
        source_table: str,
        source_sha256: str,
    ):
        by_name: Dict[str, list[SecurityIdentity]] = {}
        by_code: Dict[str, list[SecurityIdentity]] = {}
        keys = set()
        for entry in entries:
            key = (entry.mktcode, entry.tgtcode)
            if key in keys:
                raise SecurityScopeCatalogError(f"duplicate security key: {key}")
            keys.add(key)
            by_name.setdefault(entry.name, []).append(entry)
            by_code.setdefault(entry.tgtcode, []).append(entry)
        self._entries = entries
        self._by_name = MappingProxyType({key: tuple(value) for key, value in by_name.items()})
        self._by_code = MappingProxyType({key: tuple(value) for key, value in by_code.items()})
        self.source_table = source_table
        self.source_sha256 = source_sha256
        payload = json.dumps(
            [entry.to_dict() for entry in entries],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self._fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @property
    def entries(self) -> Tuple[SecurityIdentity, ...]:
        return self._entries

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def resolve(self, atom: str) -> ResolvedSecurityScope:
        source = str(atom).strip()
        explicit = re.fullmatch(r"(?P<name>.+?)\((?P<code>\d{6})\)", source)
        if explicit:
            name = explicit.group("name").strip()
            code = explicit.group("code")
            identities = tuple(
                entry for entry in self._by_code.get(code, ()) if entry.name == name
            )
            if not identities:
                raise KeyError(source)
            return ResolvedSecurityScope(source, name, identities, True)
        identities = self._by_name.get(source, ())
        if not identities:
            raise KeyError(source)
        return ResolvedSecurityScope(source, source, identities, False)

    @classmethod
    def from_dict(cls, raw) -> "SecurityScopeCatalog":
        expected = {"schema_version", "source_table", "source_sha256", "entries"}
        if set(raw) != expected or raw.get("schema_version") != 1:
            raise SecurityScopeCatalogError("invalid security scope catalog root")
        source_sha256 = str(raw["source_sha256"])
        if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
            raise SecurityScopeCatalogError("invalid security scope source hash")
        entries = []
        for item in raw["entries"]:
            if set(item) != {"mktcode", "tgtcode", "name"}:
                raise SecurityScopeCatalogError("invalid security identity fields")
            mktcode = int(item["mktcode"])
            tgtcode = str(item["tgtcode"])
            name = str(item["name"]).strip()
            if not re.fullmatch(r"\d{6}", tgtcode) or not name:
                raise SecurityScopeCatalogError("invalid security identity value")
            entries.append(SecurityIdentity(mktcode, tgtcode, name))
        if not entries:
            raise SecurityScopeCatalogError("security scope catalog is empty")
        return cls(
            tuple(entries),
            source_table=str(raw["source_table"]),
            source_sha256=source_sha256,
        )

    @classmethod
    def load(cls, path: Path) -> "SecurityScopeCatalog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def default_security_scope_catalog() -> SecurityScopeCatalog:
    root = Path(__file__).resolve().parents[4]
    return SecurityScopeCatalog.load(root / "configs" / "official" / "security_scopes.json")
