import json
from collections import Counter
from pathlib import Path

from findsl.official.correctness import OFFICIAL_FUNCTION_FAMILIES, load_correctness_manifest


def test_formal_corpus_has_balanced_function_families_and_compositions():
    cases = load_correctness_manifest(Path("data/official_correctness/manifest.jsonl"))
    eligible = [case for case in cases if case.score_eligible]
    counts = Counter(family for case in eligible for family in case.function_families)
    compositions = [case for case in eligible if case.plan_family == "balanced_cross_function_composition"]

    assert len(eligible) >= 240
    assert len(compositions) >= 30
    assert all(len(case.function_families) >= 2 for case in compositions)
    assert OFFICIAL_FUNCTION_FAMILIES == set(counts)
    assert min(counts.values()) >= 12


def test_formal_corpus_has_adversarial_shapes_and_complete_provenance():
    cases = load_correctness_manifest(Path("data/official_correctness/manifest.jsonl"))
    adversarial = [case for case in cases if case.plan_family.startswith("adversarial_")]
    shapes = Counter(case.plan_family for case in adversarial)
    provenance = json.loads(Path("data/official_correctness/provenance.json").read_text(encoding="utf-8"))

    assert len(adversarial) == 82
    assert shapes == {
        "adversarial_intersection": 32,
        "adversarial_union": 24,
        "adversarial_and_or": 15,
        "adversarial_or_and": 11,
    }
    assert provenance["case_count"] == len(cases)
    assert provenance["approved"] == len(cases)
    assert set(provenance["cases"]) == {case.case_id for case in cases}
    assert all(case.expected_non_empty is False for case in adversarial)
    configured = [
        case for case in cases if case.plan_family == "configured_expression_template"
    ]
    assert len(configured) == 1
    assert configured[0].expected_non_empty is True
