from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Dict, Optional, Tuple

from .catalog import PhysicalCatalog


class PhysicalStatisticsError(ValueError):
    pass


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class PhysicalResourceStatistics:
    resource_id: str
    row_count: int
    data_size_bytes: int
    row_count_available: bool
    partition_value_count: Optional[int] = None


class PhysicalStatisticsSnapshot:
    def __init__(
        self,
        *,
        schema_version: int,
        catalog_sha256: str,
        collected_at: str,
        doris_version: str,
        resources: Tuple[PhysicalResourceStatistics, ...],
        catalog: PhysicalCatalog,
    ):
        if schema_version not in {1, 2}:
            raise PhysicalStatisticsError(f"unsupported statistics schema version: {schema_version}")
        if not _SHA256.fullmatch(catalog_sha256):
            raise PhysicalStatisticsError("invalid catalog fingerprint")
        if catalog_sha256 != catalog.fingerprint:
            raise PhysicalStatisticsError("statistics catalog fingerprint does not match physical catalog")
        try:
            timestamp = datetime.fromisoformat(collected_at)
        except ValueError as exc:
            raise PhysicalStatisticsError("invalid statistics collection timestamp") from exc
        if timestamp.tzinfo is None:
            raise PhysicalStatisticsError("statistics collection timestamp must include a timezone")
        if not str(doris_version).strip():
            raise PhysicalStatisticsError("Doris version must not be empty")

        index: Dict[str, PhysicalResourceStatistics] = {}
        for item in resources:
            if item.resource_id in index:
                raise PhysicalStatisticsError(f"duplicate statistics resource: {item.resource_id}")
            try:
                catalog.resource(item.resource_id)
            except KeyError as exc:
                raise PhysicalStatisticsError(f"unknown statistics resource: {item.resource_id}") from exc
            if item.row_count < 0 or item.data_size_bytes < 0:
                raise PhysicalStatisticsError(f"negative statistics value for {item.resource_id}")
            if item.partition_value_count is not None and item.partition_value_count <= 0:
                raise PhysicalStatisticsError(
                    f"invalid partition value count for {item.resource_id}"
                )
            index[item.resource_id] = item

        self.schema_version = schema_version
        self.catalog_sha256 = catalog_sha256
        self.collected_at = collected_at
        self.doris_version = str(doris_version)
        self._resources = MappingProxyType(index)

    def resource(self, resource_id: str) -> PhysicalResourceStatistics:
        return self._resources[resource_id]

    @property
    def resources(self) -> Tuple[PhysicalResourceStatistics, ...]:
        return tuple(self._resources[key] for key in sorted(self._resources))

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "catalog_sha256": self.catalog_sha256,
            "collected_at": self.collected_at,
            "doris_version": self.doris_version,
            "resources": [asdict(item) for item in self.resources],
        }

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def write(self, path: Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, raw, catalog: PhysicalCatalog) -> "PhysicalStatisticsSnapshot":
        expected = {"schema_version", "catalog_sha256", "collected_at", "doris_version", "resources"}
        if not isinstance(raw, dict) or set(raw) != expected:
            raise PhysicalStatisticsError("invalid statistics snapshot fields")
        resources = tuple(_resource(item) for item in raw["resources"])
        return cls(
            schema_version=raw["schema_version"],
            catalog_sha256=raw["catalog_sha256"],
            collected_at=raw["collected_at"],
            doris_version=raw["doris_version"],
            resources=resources,
            catalog=catalog,
        )

    @classmethod
    def load(cls, path: Path, catalog: PhysicalCatalog) -> "PhysicalStatisticsSnapshot":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PhysicalStatisticsError(f"cannot load physical statistics: {exc}") from exc
        return cls.from_dict(raw, catalog)


def _resource(raw) -> PhysicalResourceStatistics:
    required = {"resource_id", "row_count", "data_size_bytes", "row_count_available"}
    allowed = required | {"partition_value_count"}
    if (
        not isinstance(raw, dict)
        or not required.issubset(raw)
        or not set(raw).issubset(allowed)
    ):
        raise PhysicalStatisticsError("invalid resource statistics fields")
    if isinstance(raw["row_count"], bool) or not isinstance(raw["row_count"], int):
        raise PhysicalStatisticsError("resource row_count must be an integer")
    if isinstance(raw["data_size_bytes"], bool) or not isinstance(raw["data_size_bytes"], int):
        raise PhysicalStatisticsError("resource data_size_bytes must be an integer")
    if not isinstance(raw["row_count_available"], bool):
        raise PhysicalStatisticsError("resource row_count_available must be a boolean")
    partition_value_count = raw.get("partition_value_count")
    if (
        partition_value_count is not None
        and (isinstance(partition_value_count, bool) or not isinstance(partition_value_count, int))
    ):
        raise PhysicalStatisticsError("partition_value_count must be an integer or null")
    return PhysicalResourceStatistics(
        resource_id=str(raw["resource_id"]),
        row_count=raw["row_count"],
        data_size_bytes=raw["data_size_bytes"],
        row_count_available=raw["row_count_available"],
        partition_value_count=partition_value_count,
    )


def parse_doris_size(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)\s*", str(value), re.IGNORECASE)
    if not match:
        raise PhysicalStatisticsError(f"invalid Doris data size: {value}")
    factors = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
        "TB": 1024 ** 4,
    }
    try:
        size = Decimal(match.group(1)) * factors[match.group(2).upper()]
    except InvalidOperation as exc:
        raise PhysicalStatisticsError(f"invalid Doris data size: {value}") from exc
    return int(size.to_integral_value(rounding=ROUND_HALF_UP))


def collect_physical_statistics(catalog, config, *, runner=None, collected_at=None):
    runner = runner or subprocess.run
    frontend_rows = _metadata_rows(config, "SHOW FRONTENDS", runner)
    if not frontend_rows:
        raise PhysicalStatisticsError("SHOW FRONTENDS returned no Doris version")
    frontend = next(
        (row for row in frontend_rows if str(row.get("IsMaster", "")).lower() == "true"),
        frontend_rows[0],
    )
    doris_version = str(frontend.get("Version", "")).strip()
    if not doris_version:
        raise PhysicalStatisticsError("SHOW FRONTENDS returned no Doris version")

    sizes = {}
    for database in sorted({resource.database for resource in catalog.resources}):
        data_rows = _metadata_rows(config, "SHOW DATA", runner, database=database)
        sizes.update(
            {
                (database, row["TableName"]): parse_doris_size(row["Size"])
                for row in data_rows
            }
        )
    missing_tables = sorted(
        f"{resource.database}.{resource.table}"
        for resource in catalog.resources
        if (resource.database, resource.table) not in sizes
    )
    if missing_tables:
        raise PhysicalStatisticsError(f"SHOW DATA missing catalog table(s): {', '.join(missing_tables)}")

    resources = []
    for resource in sorted(catalog.resources, key=lambda item: item.resource_id):
        rows = _metadata_rows(
            config,
            f"SHOW TABLE STATS `{resource.table}`",
            runner,
            database=resource.database,
        )
        if len(rows) != 1 or not str(rows[0].get("row_count", "")).strip():
            raise PhysicalStatisticsError(f"SHOW TABLE STATS missing row_count for {resource.table}")
        try:
            row_count = int(rows[0]["row_count"])
        except ValueError as exc:
            raise PhysicalStatisticsError(f"invalid row_count for {resource.table}") from exc
        partition_value_count = None
        if resource.partition_key is not None:
            partition_rows = _metadata_rows(
                config,
                (
                    f"SELECT COUNT(DISTINCT `{resource.partition_key}`) AS partition_value_count "
                    f"FROM `{resource.database}`.`{resource.table}`"
                ),
                runner,
                database=resource.database,
            )
            if len(partition_rows) != 1:
                raise PhysicalStatisticsError(
                    f"partition value count is unavailable for {resource.table}"
                )
            partition_value_count = int(partition_rows[0]["partition_value_count"])
        resources.append(
            PhysicalResourceStatistics(
                resource_id=resource.resource_id,
                row_count=row_count,
                data_size_bytes=sizes[(resource.database, resource.table)],
                row_count_available=True,
                partition_value_count=partition_value_count,
            )
        )

    timestamp = collected_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return PhysicalStatisticsSnapshot(
        schema_version=2,
        catalog_sha256=catalog.fingerprint,
        collected_at=timestamp,
        doris_version=doris_version,
        resources=tuple(resources),
        catalog=catalog,
    )


def _metadata_rows(config, sql: str, runner, *, database=None):
    command = [
        config.mysql_executable,
        "--batch",
        "--raw",
        "--host", config.host,
        "--port", str(config.port),
        "--user", config.user,
        "--database", database or config.database,
        "--execute", sql,
    ]
    environment = os.environ.copy()
    if config.password:
        environment["MYSQL_PWD"] = config.password
    completed = runner(
        command,
        env=environment,
        text=True,
        capture_output=True,
        timeout=config.timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or "Doris metadata command failed").strip()
        if config.password:
            detail = detail.replace(config.password, "<redacted>")
        raise PhysicalStatisticsError(f"Doris metadata command failed: {detail}")
    lines = [line.split("\t") for line in completed.stdout.splitlines() if line]
    if not lines:
        return []
    headers = lines[0]
    return [dict(zip(headers, row)) for row in lines[1:]]


@lru_cache(maxsize=1)
def default_physical_statistics(catalog=None) -> PhysicalStatisticsSnapshot:
    if catalog is None:
        from .catalog import default_physical_catalog

        catalog = default_physical_catalog()
    root = Path(__file__).resolve().parents[4]
    return PhysicalStatisticsSnapshot.load(
        root / "configs" / "official" / "physical_statistics.json",
        catalog,
    )
