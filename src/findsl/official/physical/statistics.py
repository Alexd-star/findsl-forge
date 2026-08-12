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
from typing import Any, Dict, Optional, Tuple

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
    partition_min: Optional[str] = None
    partition_max: Optional[str] = None


@dataclass(frozen=True)
class AccelerationFreshness:
    source_resource_id: str
    acceleration_resource_id: str
    fresh: bool
    reason_code: str
    reason: str
    checks: Tuple[Tuple[str, Any, Any, bool], ...]


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
        if schema_version not in {1, 2, 3}:
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
                catalog_resource = catalog.resource(item.resource_id)
            except KeyError as exc:
                raise PhysicalStatisticsError(f"unknown statistics resource: {item.resource_id}") from exc
            if item.row_count < 0 or item.data_size_bytes < 0:
                raise PhysicalStatisticsError(f"negative statistics value for {item.resource_id}")
            if item.partition_value_count is not None and item.partition_value_count < 0:
                raise PhysicalStatisticsError(
                    f"invalid partition value count for {item.resource_id}"
                )
            if (item.partition_min is None) != (item.partition_max is None):
                raise PhysicalStatisticsError(
                    f"incomplete partition bounds for {item.resource_id}"
                )
            if item.partition_min is not None and (
                not item.partition_min.strip()
                or not item.partition_max.strip()
                or item.partition_min > item.partition_max
            ):
                raise PhysicalStatisticsError(
                    f"invalid partition bounds for {item.resource_id}"
                )
            if schema_version >= 3:
                _validate_partition_statistics(item, catalog_resource)
            index[item.resource_id] = item

        self.schema_version = schema_version
        self.catalog_sha256 = catalog_sha256
        self.collected_at = collected_at
        self.doris_version = str(doris_version)
        self._resources = MappingProxyType(index)

    def resource(self, resource_id: str) -> PhysicalResourceStatistics:
        return self._resources[resource_id]

    def acceleration_freshness(
        self,
        source_resource_id: str,
        acceleration_resource_id: str,
    ) -> AccelerationFreshness:
        try:
            source = self.resource(source_resource_id)
            acceleration = self.resource(acceleration_resource_id)
        except KeyError as exc:
            missing = str(exc.args[0])
            return AccelerationFreshness(
                source_resource_id,
                acceleration_resource_id,
                False,
                "ACCELERATION_WATERMARK_MISSING",
                f"statistics are missing for {missing}",
                (),
            )
        if not source.row_count_available or not acceleration.row_count_available:
            return AccelerationFreshness(
                source_resource_id,
                acceleration_resource_id,
                False,
                "ACCELERATION_WATERMARK_INCOMPLETE",
                "exact row-count statistics are unavailable",
                (),
            )
        required_partition_values = (
            source.partition_value_count,
            source.partition_min,
            source.partition_max,
            acceleration.partition_value_count,
            acceleration.partition_min,
            acceleration.partition_max,
        )
        if any(value is None for value in required_partition_values):
            return AccelerationFreshness(
                source_resource_id,
                acceleration_resource_id,
                False,
                "ACCELERATION_WATERMARK_INCOMPLETE",
                "partition count or date bounds are unavailable",
                (),
            )
        checks = tuple(
            (name, source_value, acceleration_value, source_value == acceleration_value)
            for name, source_value, acceleration_value in (
                ("row_count", source.row_count, acceleration.row_count),
                (
                    "partition_value_count",
                    source.partition_value_count,
                    acceleration.partition_value_count,
                ),
                ("partition_min", source.partition_min, acceleration.partition_min),
                ("partition_max", source.partition_max, acceleration.partition_max),
            )
        )
        mismatches = tuple(name for name, _, _, matched in checks if not matched)
        if mismatches:
            return AccelerationFreshness(
                source_resource_id,
                acceleration_resource_id,
                False,
                "ACCELERATION_WATERMARK_STALE",
                "watermark mismatch: " + ", ".join(mismatches),
                checks,
            )
        return AccelerationFreshness(
            source_resource_id,
            acceleration_resource_id,
            True,
            "ACCELERATION_WATERMARK_FRESH",
            "row count and partition date watermarks match the source resource",
            checks,
        )

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


def _validate_partition_statistics(item, resource) -> None:
    count = item.partition_value_count
    has_bounds = item.partition_min is not None
    if resource.partition_key is None:
        if count is not None or has_bounds:
            raise PhysicalStatisticsError(
                f"non-partitioned resource declares partition statistics: {item.resource_id}"
            )
        return
    if count is None:
        raise PhysicalStatisticsError(
            f"partitioned resource is missing partition statistics: {item.resource_id}"
        )
    if item.row_count == 0:
        if count != 0 or has_bounds:
            raise PhysicalStatisticsError(
                f"empty resource has inconsistent partition statistics: {item.resource_id}"
            )
        return
    if count == 0 or not has_bounds:
        raise PhysicalStatisticsError(
            f"non-empty resource has incomplete partition statistics: {item.resource_id}"
        )


def _resource(raw) -> PhysicalResourceStatistics:
    required = {"resource_id", "row_count", "data_size_bytes", "row_count_available"}
    allowed = required | {"partition_value_count", "partition_min", "partition_max"}
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
    partition_min = raw.get("partition_min")
    partition_max = raw.get("partition_max")
    if partition_min is not None and not isinstance(partition_min, str):
        raise PhysicalStatisticsError("partition_min must be a string or null")
    if partition_max is not None and not isinstance(partition_max, str):
        raise PhysicalStatisticsError("partition_max must be a string or null")
    return PhysicalResourceStatistics(
        resource_id=str(raw["resource_id"]),
        row_count=raw["row_count"],
        data_size_bytes=raw["data_size_bytes"],
        row_count_available=raw["row_count_available"],
        partition_value_count=partition_value_count,
        partition_min=partition_min,
        partition_max=partition_max,
    )


def parse_doris_size(value: str) -> int:
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)?\s*",
        str(value),
        re.IGNORECASE,
    )
    if not match:
        raise PhysicalStatisticsError(f"invalid Doris data size: {value}")
    factors = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
        "TB": 1024 ** 4,
    }
    unit = match.group(2)
    if unit is None and Decimal(match.group(1)) != 0:
        raise PhysicalStatisticsError(f"non-zero Doris data size has no unit: {value}")
    try:
        size = Decimal(match.group(1)) * factors[(unit or "B").upper()]
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
        if row_count == 0:
            exact_rows = _metadata_rows(
                config,
                (
                    "SELECT COUNT(*) AS exact_row_count "
                    f"FROM `{resource.database}`.`{resource.table}`"
                ),
                runner,
                database=resource.database,
            )
            if len(exact_rows) != 1:
                raise PhysicalStatisticsError(
                    f"exact row count is unavailable for {resource.table}"
                )
            row_count = int(exact_rows[0]["exact_row_count"])
        partition_value_count = None
        partition_min = None
        partition_max = None
        if resource.partition_key is not None:
            partition_rows = _metadata_rows(
                config,
                (
                    f"SELECT COUNT(DISTINCT `{resource.partition_key}`) AS partition_value_count, "
                    f"MIN(`{resource.partition_key}`) AS partition_min, "
                    f"MAX(`{resource.partition_key}`) AS partition_max "
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
            raw_partition_min = partition_rows[0]["partition_min"]
            raw_partition_max = partition_rows[0]["partition_max"]
            partition_min = (
                None if raw_partition_min in {None, "NULL"} else str(raw_partition_min)
            )
            partition_max = (
                None if raw_partition_max in {None, "NULL"} else str(raw_partition_max)
            )
        resources.append(
            PhysicalResourceStatistics(
                resource_id=resource.resource_id,
                row_count=row_count,
                data_size_bytes=sizes[(resource.database, resource.table)],
                row_count_available=True,
                partition_value_count=partition_value_count,
                partition_min=partition_min,
                partition_max=partition_max,
            )
        )

    timestamp = collected_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return PhysicalStatisticsSnapshot(
        schema_version=3,
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
