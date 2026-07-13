from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

from .models import CatalogSnapshot, normalize_catalog_name


class ExternalCatalogError(ValueError):
    pass


_SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    license_note TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scope_membership (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    scope_type TEXT NOT NULL,
    scope_code TEXT NOT NULL,
    scope_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    mktcode INTEGER NOT NULL,
    tgtcode TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    weight REAL,
    match_method TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, scope_code, mktcode, tgtcode, effective_from)
);
CREATE TABLE IF NOT EXISTS scope_alias (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    scope_code TEXT NOT NULL,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, scope_code, normalized_alias)
);
CREATE TABLE IF NOT EXISTS industry_membership (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    classification_system TEXT NOT NULL,
    industry_level TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    industry_name TEXT NOT NULL,
    mktcode INTEGER NOT NULL,
    tgtcode TEXT NOT NULL,
    effective_from TEXT,
    effective_to TEXT,
    PRIMARY KEY (snapshot_id, classification_system, industry_level, industry_code, mktcode, tgtcode, effective_from)
);
CREATE TABLE IF NOT EXISTS instrument_rule (
    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
    mktcode INTEGER NOT NULL,
    tgtcode TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    t0_eligible INTEGER NOT NULL CHECK (t0_eligible IN (0, 1)),
    effective_from TEXT,
    effective_to TEXT,
    rule_source TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, mktcode, tgtcode, effective_from)
);
CREATE INDEX IF NOT EXISTS idx_scope_name ON scope_membership(normalized_name);
CREATE INDEX IF NOT EXISTS idx_scope_alias ON scope_alias(normalized_alias);
CREATE INDEX IF NOT EXISTS idx_scope_security ON scope_membership(mktcode, tgtcode);
CREATE INDEX IF NOT EXISTS idx_industry_security ON industry_membership(mktcode, tgtcode);
CREATE INDEX IF NOT EXISTS idx_instrument_security ON instrument_rule(mktcode, tgtcode);
"""


class ExternalCatalog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            current = connection.execute(
                "SELECT value FROM catalog_meta WHERE key='schema_version'"
            ).fetchone()
            if current is None:
                connection.execute(
                    "INSERT INTO catalog_meta(key,value) VALUES('schema_version',?)",
                    (str(_SCHEMA_VERSION),),
                )
            elif int(current[0]) != _SCHEMA_VERSION:
                raise ExternalCatalogError(
                    f"unsupported external catalog schema version: {current[0]}"
                )

    def import_snapshot(self, snapshot: CatalogSnapshot, *, replace: bool = False) -> None:
        self.initialize()
        with self._transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM snapshots WHERE snapshot_id=?", (snapshot.snapshot_id,)
            ).fetchone()
            if exists and not replace:
                raise ExternalCatalogError(f"snapshot already exists: {snapshot.snapshot_id}")
            if exists:
                self._delete_snapshot(connection, snapshot.snapshot_id)
            connection.execute(
                """INSERT INTO snapshots(
                       snapshot_id,source,source_url,retrieved_at,as_of_date,
                       content_sha256,license_note
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    snapshot.snapshot_id,
                    snapshot.source,
                    snapshot.source_url,
                    snapshot.retrieved_at,
                    snapshot.as_of_date,
                    snapshot.content_sha256,
                    snapshot.license_note,
                ),
            )
            self._insert_scope_memberships(connection, snapshot)
            self._insert_industry_memberships(connection, snapshot)
            self._insert_instrument_rules(connection, snapshot)

    def resolve_scope(
        self, name: str, *, as_of_date: Optional[str] = None
    ) -> Tuple[Dict[str, object], ...]:
        normalized = normalize_catalog_name(name)
        parameters = [normalized, normalized]
        date_clause = ""
        if as_of_date:
            date_clause = (
                " AND (sm.effective_from IS NULL OR sm.effective_from <= ?)"
                " AND (sm.effective_to IS NULL OR sm.effective_to >= ?)"
            )
            parameters.extend((as_of_date, as_of_date))
        query = f"""
            SELECT DISTINCT sm.scope_type,sm.scope_code,sm.scope_name,
                   sm.mktcode,sm.tgtcode,sm.effective_from,sm.effective_to,
                   sm.weight,sm.match_method,sm.snapshot_id
              FROM scope_membership sm
         LEFT JOIN scope_alias sa
                ON sa.snapshot_id=sm.snapshot_id AND sa.scope_code=sm.scope_code
             WHERE (sm.normalized_name=? OR sa.normalized_alias=?)
                   {date_clause}
          ORDER BY sm.scope_code,sm.weight DESC,sm.mktcode,sm.tgtcode
        """
        with self._connect(readonly=True) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(dict(row) for row in rows)

    def summary(self) -> Dict[str, object]:
        self.initialize()
        with self._connect(readonly=True) as connection:
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "snapshots",
                    "scope_membership",
                    "scope_alias",
                    "industry_membership",
                    "instrument_rule",
                )
            }
            sources = [
                dict(row)
                for row in connection.execute(
                    "SELECT snapshot_id,source,source_url,retrieved_at,as_of_date,content_sha256 FROM snapshots ORDER BY imported_at"
                )
            ]
        return {"schema_version": _SCHEMA_VERSION, "counts": counts, "snapshots": sources}

    def export_doris(self, output_dir: Path) -> Dict[str, object]:
        self.initialize()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        exports = {}
        tables = {
            "scope_membership": (
                "snapshot_id,scope_code,mktcode,tgtcode,scope_type,scope_name,effective_from,effective_to,weight",
                "snapshot_id,scope_code,mktcode,tgtcode,scope_type,scope_name,effective_from,effective_to,weight",
            ),
            "industry_membership": (
                "snapshot_id,classification_system,industry_code,mktcode,tgtcode,industry_level,industry_name,effective_from,effective_to",
                "snapshot_id,classification_system,industry_code,mktcode,tgtcode,industry_level,industry_name,effective_from,effective_to",
            ),
            "instrument_rule": (
                "snapshot_id,mktcode,tgtcode,instrument_type,t0_eligible,effective_from,effective_to,rule_source",
                "snapshot_id,mktcode,tgtcode,instrument_type,t0_eligible,effective_from,effective_to,rule_source",
            ),
        }
        with self._connect(readonly=True) as connection:
            for table, (columns, header) in tables.items():
                path = output_dir / f"{table}.csv"
                temporary = path.with_suffix(".csv.tmp")
                rows = connection.execute(
                    f"SELECT {columns} FROM {table} ORDER BY snapshot_id,1,2,3"
                )
                with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(header.split(","))
                    count = 0
                    for row in rows:
                        writer.writerow(
                            tuple("\\N" if value is None else value for value in row)
                        )
                        count += 1
                temporary.replace(path)
                exports[table] = {"path": str(path), "rows": count}
        manifest = {"schema_version": _SCHEMA_VERSION, "exports": exports}
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    def export_runtime_manifest(self, path: Path) -> Dict[str, object]:
        self.initialize()
        with self._connect(readonly=True) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT sm.scope_type,sm.scope_code,sm.scope_name,
                       sa.alias,sa.normalized_alias,s.source,s.as_of_date,
                       s.snapshot_id
                  FROM scope_membership sm
                  JOIN scope_alias sa
                    ON sa.snapshot_id=sm.snapshot_id AND sa.scope_code=sm.scope_code
                  JOIN snapshots s ON s.snapshot_id=sm.snapshot_id
              ORDER BY sa.normalized_alias,s.as_of_date DESC,s.source,sm.scope_code
                """
            ).fetchall()
        entries = []
        seen = set()
        for row in rows:
            item = dict(row)
            if not _runtime_scope_alias_allowed(
                str(item["scope_type"]),
                str(item["scope_name"]),
                str(item["alias"]),
            ):
                continue
            aliases = _runtime_alias_variants(
                str(item["scope_type"]),
                str(item["scope_name"]),
                str(item["alias"]),
            )
            for alias in aliases:
                candidate = dict(item)
                candidate["alias"] = alias
                candidate["normalized_alias"] = normalize_catalog_name(alias)
                key = (
                    candidate["snapshot_id"],
                    candidate["scope_code"],
                    candidate["normalized_alias"],
                )
                if key in seen:
                    continue
                seen.add(key)
                entries.append(candidate)
        entries.sort(
            key=lambda item: (
                item["normalized_alias"],
                item["source"],
                item["scope_code"],
            )
        )
        payload = {
            "schema_version": 1,
            "membership_resource_id": "external_scope_membership",
            "entries": entries,
        }
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
    @contextmanager
    def _connect(self, *, readonly: bool = False) -> Iterator[sqlite3.Connection]:
        if readonly:
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        else:
            connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            if not readonly:
                connection.commit()
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _delete_snapshot(connection: sqlite3.Connection, snapshot_id: str) -> None:
        for table in (
            "scope_alias",
            "scope_membership",
            "industry_membership",
            "instrument_rule",
        ):
            connection.execute(f"DELETE FROM {table} WHERE snapshot_id=?", (snapshot_id,))
        connection.execute("DELETE FROM snapshots WHERE snapshot_id=?", (snapshot_id,))

    @staticmethod
    def _insert_scope_memberships(connection, snapshot: CatalogSnapshot) -> None:
        for item in snapshot.scope_memberships:
            connection.execute(
                """INSERT OR IGNORE INTO scope_membership VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    snapshot.snapshot_id,
                    item.scope_type,
                    item.scope_code,
                    item.scope_name,
                    normalize_catalog_name(item.scope_name),
                    item.mktcode,
                    item.tgtcode,
                    item.effective_from,
                    item.effective_to,
                    item.weight,
                    item.match_method,
                ),
            )
            for alias in (item.scope_name, *item.aliases):
                connection.execute(
                    "INSERT OR IGNORE INTO scope_alias VALUES(?,?,?,?)",
                    (
                        snapshot.snapshot_id,
                        item.scope_code,
                        alias,
                        normalize_catalog_name(alias),
                    ),
                )

    @staticmethod
    def _insert_industry_memberships(connection, snapshot: CatalogSnapshot) -> None:
        for item in snapshot.industry_memberships:
            connection.execute(
                """INSERT OR IGNORE INTO industry_membership VALUES(?,?,?,?,?,?,?,?,?)""",
                (snapshot.snapshot_id, *asdict(item).values()),
            )

    @staticmethod
    def _insert_instrument_rules(connection, snapshot: CatalogSnapshot) -> None:
        for item in snapshot.instrument_rules:
            values = asdict(item)
            values["t0_eligible"] = int(values["t0_eligible"])
            connection.execute(
                """INSERT OR IGNORE INTO instrument_rule VALUES(?,?,?,?,?,?,?,?)""",
                (snapshot.snapshot_id, *values.values()),
            )


def _runtime_alias_variants(scope_type: str, scope_name: str, alias: str):
    variants = [alias]
    if alias == scope_name:
        if scope_type == "industry":
            variants.extend(
                f"{alias}{suffix}"
                for suffix in ("行业", "板块")
                if not alias.endswith(suffix)
            )
        elif scope_type == "concept":
            if alias.endswith("概念"):
                variants.append(f"{alias}板块")
            else:
                variants.extend((f"{alias}概念", f"{alias}概念板块"))
        elif scope_type == "index" and not alias.endswith("指数"):
            variants.append(f"{alias}指数")
    return tuple(dict.fromkeys(variants))


def _runtime_scope_alias_allowed(scope_type: str, scope_name: str, alias: str) -> bool:
    if scope_type != "index":
        return True
    source = alias.strip().casefold()
    canonical_name = scope_name.strip().casefold()
    if source == canonical_name or "指数" in source:
        return True
    if source.endswith(("公司", "企业", "行业", "板块", "类")):
        return False
    return not canonical_name.endswith(("指数", "行业"))
