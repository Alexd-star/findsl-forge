from pathlib import Path

from scripts.admit_local_domain_snapshot import admit_local_snapshot


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_admit_local_snapshot_generates_versioned_manifest_and_contract_report(
    tmp_path: Path,
):
    data = tmp_path / "index_members.csv"
    data.write_text(
        "index_code,mktcode,tgtcode,effective_from,weight,publisher\n"
        "000300,1,600000,2026-08-13,1.2,CSI\n",
        encoding="utf-8",
    )

    manifest, report = admit_local_snapshot(
        source_registry_path=REPO_ROOT
        / "configs/official/external_source_registry.json",
        data_domains_path=REPO_ROOT / "configs/official/data_domains.json",
        contracts_path=REPO_ROOT
        / "configs/official/domain_table_contracts.json",
        provider_id="csindex",
        domain_id="index_reference",
        profile_id="competition-v1",
        as_of_date="2026-08-13",
        data_path=data,
        data_format="csv",
        license_note="Test fixture under reviewed publisher terms.",
        license_accepted=True,
    )

    assert manifest["snapshot_id"].startswith("csindex-2026-08-13-")
    assert manifest["row_count"] == 1
    assert report["passed"] is True
    assert report["status"] == "CANDIDATE"
    assert report["table_contract"]["matched_variant"] == "index_membership"
