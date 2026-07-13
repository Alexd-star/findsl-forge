from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.models import CatalogSnapshot, ScopeMembership
from findsl.official.external.providers import ThsConceptDefinition, ThsConceptProvider
from findsl.official.external.providers.eastmoney import security_market_code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    definitions = tuple(
        ThsConceptDefinition(item["code"], item["name"], tuple(item["aliases"]))
        for item in raw["concepts"]
    )
    provider = ThsConceptProvider(cache_dir=Path(args.cache))
    snapshot_date = args.as_of_date or date.today().isoformat()
    rows = []
    counts = {}
    for concept in definitions:
        members = provider.list_constituents(concept)
        counts[concept.name] = len(members)
        for member in members:
            rows.append(
                ScopeMembership(
                    "concept",
                    f"THS:{concept.code}",
                    concept.name,
                    concept.aliases,
                    security_market_code(member.code),
                    member.code,
                    snapshot_date,
                    None,
                    None,
                    "ths_concept_exact",
                )
            )
    content = [dict(item.__dict__, aliases=list(item.aliases)) for item in rows]
    digest = hashlib.sha256(
        json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    snapshot = CatalogSnapshot(
        f"ths-concept-{snapshot_date}-{digest[:12]}",
        provider.source,
        provider.source_url,
        datetime.now(timezone.utc).isoformat(),
        snapshot_date,
        digest,
        provider.license_note,
        scope_memberships=tuple(rows),
    )
    catalog = ExternalCatalog(Path(args.catalog))
    catalog.import_snapshot(snapshot, replace=True)
    report = {
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "content_sha256": digest,
        "concepts": counts,
        "scope_memberships": len(rows),
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
