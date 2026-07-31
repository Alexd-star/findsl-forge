from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from findsl.official.external import ExternalCatalog
from findsl.official.external.models import CatalogSnapshot, ScopeMembership
from findsl.official.external.policy import ScopeSemanticPolicyCatalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aliases", required=True)
    parser.add_argument(
        "--policies",
        default="configs/official/scope_semantic_policies.json",
    )
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
    policy_catalog = ScopeSemanticPolicyCatalog.load(Path(args.policies))
    _assert_no_alias_conflicts(config, policy_catalog)
    snapshot_date = args.as_of_date or date.today().isoformat()
    connection = sqlite3.connect(args.catalog)
    connection.row_factory = sqlite3.Row
    try:
        rows, alias_audit = build_curated_rows(config, connection, snapshot_date)
        policy_rows, policy_audit = build_semantic_policy_rows(
            policy_catalog,
            connection,
            snapshot_date,
        )
    finally:
        connection.close()

    rows = [*rows, *policy_rows]
    audit = [*alias_audit, *policy_audit]

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
        "legacy_alias_count": len(alias_audit),
        "semantic_policy_count": len(policy_audit),
        "semantic_policy_set_id": policy_catalog.policy_set_id,
        "semantic_policy_profile": policy_catalog.profile,
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


def build_semantic_policy_rows(
    catalog: ScopeSemanticPolicyCatalog,
    connection,
    snapshot_date: str,
):
    rows = []
    audit = []
    for policy in catalog.policies:
        component_member_counts = []
        matched_security_names = []
        if policy.resolution_kind == "exact_scope":
            source_rows = _source_rows(
                connection,
                policy.source_snapshot_id,
                policy.target_scope_code,
            )
            selected_rows = {
                (row["mktcode"], row["tgtcode"]): row for row in source_rows
            }
        elif policy.resolution_kind == "security_name_regex":
            try:
                matcher = re.compile(policy.selector_pattern)
            except re.error as exc:
                raise ValueError(
                    f"invalid security name policy regex: {policy.policy_id}"
                ) from exc
            source_rows = _security_source_rows(
                connection,
                policy.source_snapshot_id,
            )
            matches = [row for row in source_rows if matcher.search(row["scope_name"])]
            selected_rows = {
                (row["mktcode"], row["tgtcode"]): row for row in matches
            }
            matched_security_names = sorted(
                {str(row["scope_name"]) for row in matches}
            )
        else:
            component_rows = [
                _source_rows(
                    connection,
                    component.source_snapshot_id,
                    component.scope_code,
                )
                for component in policy.components
            ]
            for component, values in zip(policy.components, component_rows):
                if len(values) < component.minimum_member_count:
                    raise ValueError(
                        "semantic policy component is below its minimum member count: "
                        f"{policy.policy_id}/{component.scope_code}: "
                        f"{len(values)} < {component.minimum_member_count}"
                    )
            keyed_components = [
                {(row["mktcode"], row["tgtcode"]): row for row in values}
                for values in component_rows
            ]
            selected_keys = set(keyed_components[0])
            for keyed in keyed_components[1:]:
                if policy.operation == "intersection":
                    selected_keys &= set(keyed)
                else:
                    selected_keys |= set(keyed)
            selected_rows = {}
            for key in sorted(selected_keys):
                selected_rows[key] = next(
                    keyed[key] for keyed in keyed_components if key in keyed
                )
            component_member_counts = [len(values) for values in component_rows]

        _validate_policy_member_count(policy, len(selected_rows))
        for (mktcode, tgtcode), source in sorted(selected_rows.items()):
            rows.append(
                ScopeMembership(
                    (
                        source["scope_type"]
                        if policy.resolution_kind == "exact_scope"
                        else "semantic_policy"
                    ),
                    policy.scope_code,
                    policy.scope_name,
                    policy.aliases,
                    mktcode,
                    tgtcode,
                    source["effective_from"],
                    source["effective_to"],
                    source["weight"],
                    f"semantic_policy_{policy.resolution_kind}",
                )
            )
        item = policy.to_audit_dict()
        item["member_count"] = len(selected_rows)
        if component_member_counts:
            item["component_member_counts"] = component_member_counts
        if matched_security_names:
            item["matched_security_names"] = matched_security_names
        audit.append(item)
    return rows, audit


def _validate_policy_member_count(policy, member_count: int) -> None:
    if member_count < policy.minimum_member_count:
        raise ValueError(
            "semantic policy result is below its minimum member count: "
            f"{policy.policy_id}: {member_count} < {policy.minimum_member_count}"
        )
    if (
        policy.maximum_member_count is not None
        and member_count > policy.maximum_member_count
    ):
        raise ValueError(
            "semantic policy result exceeds its maximum member count: "
            f"{policy.policy_id}: {member_count} > {policy.maximum_member_count}"
        )


def _assert_no_alias_conflicts(config, catalog: ScopeSemanticPolicyCatalog) -> None:
    from findsl.official.external.models import normalize_catalog_name

    legacy_aliases = {
        normalize_catalog_name(item["alias"]): item["alias"]
        for item in config["mappings"]
    }
    for policy in catalog.policies:
        for alias in policy.aliases:
            normalized = normalize_catalog_name(alias)
            if normalized in legacy_aliases:
                raise ValueError(
                    "semantic policy alias conflicts with legacy curated alias: "
                    f"{alias}"
                )


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


def _security_source_rows(connection, snapshot_id: str):
    rows = connection.execute(
        """SELECT scope_type,scope_code,scope_name,mktcode,tgtcode,
                  effective_from,effective_to,weight
             FROM scope_membership
            WHERE snapshot_id=? AND scope_type='security'
         ORDER BY mktcode,tgtcode""",
        (snapshot_id,),
    ).fetchall()
    if not rows:
        raise ValueError(f"semantic security source is empty: {snapshot_id}")
    return rows


if __name__ == "__main__":
    main()
