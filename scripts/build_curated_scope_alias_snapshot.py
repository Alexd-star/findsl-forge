from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.models import CatalogSnapshot, ScopeMembership


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aliases", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--runtime", default="configs/official/external_scope_runtime.json"
    )
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    config = json.loads(Path(args.aliases).read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("unsupported curated alias schema")
    snapshot_date = args.as_of_date or date.today().isoformat()
    connection = sqlite3.connect(args.catalog)
    connection.row_factory = sqlite3.Row
    try:
        rows, audit = build_curated_rows(config, connection, snapshot_date)
    finally:
        connection.close()

    content = [dict(item.__dict__, aliases=list(item.aliases)) for item in rows]
    digest = hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    snapshot = CatalogSnapshot(
        f"curated-scope-alias-{snapshot_date}-{digest[:12]}",
        "curated-scope-alias",
        "urn:findsl:curated-scope-alias-manifest",
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        "Curated aliases over versioned source memberships; original snapshot retained per mapping",
        scope_memberships=tuple(rows),
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot, replace_source_date=True)
    runtime = catalog.export_runtime_manifest(Path(args.runtime))
    payload = {
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "content_sha256": digest,
        "mapping_count": len(audit),
        "scope_memberships": len(rows),
        "runtime_entries": len(runtime["entries"]),
        "mappings": audit,
    }
    Path(args.report).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_curated_rows(config, connection, snapshot_date: str):
    grouped = defaultdict(list)
    composites = []
    for item in config["mappings"]:
        if "components" in item:
            composites.append(item)
        else:
            grouped[(item["source_snapshot_id"], item["scope_code"])].append(item)

    rows = []
    audit = []
    for (snapshot_id, scope_code), mappings in grouped.items():
        source_rows = _source_rows(connection, snapshot_id, scope_code)
        minimum_member_count = max(
            int(item.get("minimum_member_count", 1)) for item in mappings
        )
        if len(source_rows) < minimum_member_count:
            raise ValueError(
                "curated alias source is below its minimum member count: "
                f"{snapshot_id}/{scope_code}: {len(source_rows)} < {minimum_member_count}"
            )
        aliases = tuple(item["alias"] for item in mappings)
        for source in source_rows:
            rows.append(
                ScopeMembership(
                    source["scope_type"],
                    source["scope_code"],
                    source["scope_name"],
                    aliases,
                    source["mktcode"],
                    source["tgtcode"],
                    source["effective_from"],
                    source["effective_to"],
                    source["weight"],
                    "curated_alias_exact_scope",
                )
            )
        audit.extend(
            {
                **item,
                "scope_name": source_rows[0]["scope_name"],
                "member_count": len(source_rows),
            }
            for item in mappings
        )

    for item in composites:
        operation = item.get("operation")
        components = item.get("components")
        if operation not in {"intersection", "union"}:
            raise ValueError(f"unsupported curated composite operation: {operation}")
        if not isinstance(components, list) or len(components) < 2:
            raise ValueError("curated composite requires at least two components")
        component_rows = [
            _source_rows(
                connection,
                component["source_snapshot_id"],
                component["scope_code"],
            )
            for component in components
        ]
        for component, values in zip(components, component_rows):
            minimum = int(component.get("minimum_member_count", 1))
            if len(values) < minimum:
                raise ValueError(
                    "curated composite component is below its minimum member count: "
                    f"{component['source_snapshot_id']}/{component['scope_code']}: "
                    f"{len(values)} < {minimum}"
                )
        component_keys = [
            {(row["mktcode"], row["tgtcode"]) for row in values}
            for values in component_rows
        ]
        selected = set(component_keys[0])
        for keys in component_keys[1:]:
            selected = selected & keys if operation == "intersection" else selected | keys
        minimum_member_count = int(item.get("minimum_member_count", 1))
        if len(selected) < minimum_member_count:
            raise ValueError(
                "curated composite result is below its minimum member count: "
                f"{item['alias']}: {len(selected)} < {minimum_member_count}"
            )
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "alias": item["alias"],
                    "operation": operation,
                    "components": components,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        scope_code = f"CURATED:{fingerprint[:16]}"
        scope_name = str(item.get("scope_name") or item["alias"])
        for mktcode, tgtcode in sorted(selected):
            rows.append(
                ScopeMembership(
                    "composite",
                    scope_code,
                    scope_name,
                    (item["alias"],),
                    mktcode,
                    tgtcode,
                    snapshot_date,
                    None,
                    None,
                    f"curated_{operation}",
                )
            )
        audit.append(
            {
                **item,
                "scope_code": scope_code,
                "scope_name": scope_name,
                "member_count": len(selected),
                "component_member_counts": [len(keys) for keys in component_keys],
            }
        )
    return rows, audit


def _source_rows(connection, snapshot_id: str, scope_code: str):
    rows = connection.execute(
        """SELECT scope_type,scope_code,scope_name,mktcode,tgtcode,
                  effective_from,effective_to,weight
             FROM scope_membership
            WHERE snapshot_id=? AND scope_code=?
         ORDER BY mktcode,tgtcode""",
        (snapshot_id, scope_code),
    ).fetchall()
    if not rows:
        raise ValueError(f"curated alias source is empty: {snapshot_id}/{scope_code}")
    return rows


if __name__ == "__main__":
    main()
