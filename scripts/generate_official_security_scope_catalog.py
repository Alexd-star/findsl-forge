from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the versioned official security-name scope catalog from Doris"
    )
    parser.add_argument("--client", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9030)
    parser.add_argument("--user", default="root")
    parser.add_argument("--database", default="newzl")
    parser.add_argument("--table", default="hsj_stock_code_info")
    parser.add_argument(
        "--output",
        default="configs/official/security_scopes.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the existing catalog differs from the live deterministic export",
    )
    args = parser.parse_args()

    source_table = f"{args.database}.{args.table}"
    sql = (
        "SELECT mktcode,tgtcode,name "
        f"FROM `{args.database}`.`{args.table}` "
        "WHERE name IS NOT NULL AND name<>'' "
        "ORDER BY mktcode,tgtcode"
    )
    rows = _query_rows(args, sql)
    entries = []
    canonical_lines = []
    for row in rows:
        if len(row) < 3:
            raise RuntimeError("security catalog query returned an incomplete row")
        entry = {"mktcode": int(row[0]), "tgtcode": row[1], "name": row[2]}
        entries.append(entry)
        canonical_lines.append(f"{entry['mktcode']}\t{entry['tgtcode']}\t{entry['name']}")
    if not entries:
        raise RuntimeError("security catalog query returned no rows")
    payload = {
        "schema_version": 1,
        "source_table": source_table,
        "source_sha256": hashlib.sha256("\n".join(canonical_lines).encode("utf-8")).hexdigest(),
        "entries": entries,
    }
    output = Path(args.output)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            print(f"Security scope catalog is stale: {output}")
            return 1
        print(f"Security scope catalog is current: {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    action = "Validated" if args.check else "Wrote"
    print(f"{action} {len(entries)} securities in {output}")
    print(f"Source SHA-256: {payload['source_sha256']}")
    return 0


def _query_rows(args, sql: str):
    command = [
        str(args.client),
        "--default-character-set=utf8mb4",
        "-h",
        args.host,
        "-P",
        str(args.port),
        "-u",
        args.user,
        "-N",
        "-B",
        "-e",
        sql,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return [line.split("\t") for line in result.stdout.splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
