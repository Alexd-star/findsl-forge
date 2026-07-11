from findsl.official.backend.executor import DorisDigestResult
from findsl.official_prefix_evidence import build_official_prefix_evidence


def test_prefix_evidence_requires_default_direct_and_shadow_hash_equivalence():
    calls = []

    def executor(config, sql):
        calls.append(sql)
        return DorisDigestResult(row_count=3, elapsed_ms=10.0 + len(calls), sha256="same")

    report = build_official_prefix_evidence(
        ["indicator('', '', '5日均线', '', '', '', '') > 10"],
        config=object(),
        executor=executor,
    )

    assert report["status"] == "PASS"
    assert report["matched"] == 1
    assert report["results"][0]["default_strategy"] == "direct_column"
    assert report["results"][0]["shadow_strategy"] == "ma5_prefix_average"
    assert report["results"][0]["row_count"] == 3
    assert len(calls) == 2
