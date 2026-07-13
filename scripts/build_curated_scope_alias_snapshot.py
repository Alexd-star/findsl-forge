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
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    config = json.loads(Path(args.aliases).read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("unsupported curated alias schema")
    grouped = defaultdict(list)
    for item in config["mappings"]:
        grouped[(item["source_snapshot_id"], item["scope_code"])].append(item)

    rows = []
    audit = []
    connection = sqlite3.connect(args.catalog)
    connection.row_factory = sqlite3.Row
    try:
        for (snapshot_id, scope_code), mappings in grouped.items():
            source_rows = connection.execute(
                """SELECT scope_type,scope_code,scope_name,mktcode,tgtcode,
                          effective_from,effective_to,weight
                     FROM scope_membership
                    WHERE snapshot_id=? AND scope_code=?
                 ORDER BY mktcode,tgtcode""",
                (snapshot_id, scope_code),
            ).fetchall()
            if not source_rows:
                raise ValueError(f"curated alias source is empty: {snapshot_id}/{scope_code}")
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
    finally:
        connection.close()

    content = [dict(item.__dict__, aliases=list(item.aliases)) for item in rows]
    digest = hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    snapshot_date = args.as_of_date or date.today().isoformat()
    snapshot = CatalogSnapshot(
        f"curated-scope-alias-{snapshot_date}-{digest[:12]}",
        "curated-scope-alias",
        "https://quote.eastmoney.com/center/boardlist.html",
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        "Curated aliases over versioned Eastmoney memberships; source snapshot retained in audit report",
        scope_memberships=tuple(rows),
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot, replace=True)
    payload = {
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "content_sha256": digest,
        "mapping_count": len(audit),
        "scope_memberships": len(rows),
        "mappings": audit,
    }
    Path(args.report).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
