from findsl.official.external.profile_sync import (
    build_security_identity_snapshot,
    build_security_profile_snapshot,
)
from findsl.official.external.providers.eastmoney import SecurityProfile


def test_security_profile_snapshot_separates_scope_semantics():
    snapshot = build_security_profile_snapshot(
        (
            SecurityProfile(
                "000001",
                "平安银行",
                "银行",
                "广东板块",
                ("人工智能", "跨境支付"),
            ),
        ),
        as_of_date="2026-07-13",
    )

    rows = snapshot.scope_memberships
    assert snapshot.source == "eastmoney-security-profile"
    assert {item.scope_type for item in rows} == {
        "security",
        "region",
        "industry",
        "concept",
    }
    region = next(item for item in rows if item.scope_type == "region")
    assert region.scope_name == "广东"
    assert region.aliases == ("广东板块",)
    security = next(item for item in rows if item.scope_type == "security")
    assert security.aliases == ("000001",)
    assert all(item.effective_from == "2026-07-13" for item in rows)


def test_security_identity_snapshot_is_exact_and_singleton():
    snapshot = build_security_identity_snapshot(
        (("000001", "平安银行"), ("600000", "浦发银行")),
        as_of_date="2026-07-13",
    )

    assert snapshot.source == "akshare-security-identity"
    assert len(snapshot.scope_memberships) == 2
    assert {item.scope_name for item in snapshot.scope_memberships} == {
        "平安银行",
        "浦发银行",
    }
    assert all(item.scope_type == "security" for item in snapshot.scope_memberships)
