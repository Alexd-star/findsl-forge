from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Tuple


class DataProfileError(ValueError):
    pass


@dataclass(frozen=True)
class DataProfile:
    profile_id: str
    manifest_path: str
    uses_external_data: bool
    offline_reproducible: bool
    description: str


class DataProfileCatalog:
    def __init__(self, profiles: Tuple[DataProfile, ...], *, default_profile: str):
        by_id: Dict[str, DataProfile] = {}
        for profile in profiles:
            if profile.profile_id in by_id:
                raise DataProfileError(f"duplicate data profile: {profile.profile_id}")
            by_id[profile.profile_id] = profile
        if default_profile not in by_id:
            raise DataProfileError("default data profile is absent from the catalog")
        self.default_profile = default_profile
        self._profiles = MappingProxyType(by_id)

    def resolve(self, profile_id: str | None = None) -> DataProfile:
        selected = str(profile_id or self.default_profile).strip()
        try:
            return self._profiles[selected]
        except KeyError as exc:
            raise DataProfileError(f"unknown data profile: {selected}") from exc

    def profiles(self) -> Tuple[DataProfile, ...]:
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    @classmethod
    def from_dict(cls, raw) -> "DataProfileCatalog":
        if set(raw) != {"schema_version", "default_profile", "profiles"}:
            raise DataProfileError("invalid data profile catalog root")
        if raw["schema_version"] != 1:
            raise DataProfileError("unsupported data profile catalog version")
        required = {
            "profile_id",
            "manifest_path",
            "uses_external_data",
            "offline_reproducible",
            "description",
        }
        profiles = []
        for index, item in enumerate(raw["profiles"]):
            if not isinstance(item, dict) or set(item) != required:
                raise DataProfileError(f"invalid data profile entry {index}")
            text_fields = (
                str(item["profile_id"]).strip(),
                str(item["manifest_path"]).strip().replace("\\", "/"),
                str(item["description"]).strip(),
            )
            if not all(text_fields):
                raise DataProfileError(f"empty data profile field at entry {index}")
            profiles.append(
                DataProfile(
                    text_fields[0],
                    text_fields[1],
                    bool(item["uses_external_data"]),
                    bool(item["offline_reproducible"]),
                    text_fields[2],
                )
            )
        return cls(tuple(profiles), default_profile=str(raw["default_profile"]).strip())

    @classmethod
    def load(cls, path: Path) -> "DataProfileCatalog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
