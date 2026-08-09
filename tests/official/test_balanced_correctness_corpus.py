from collections import Counter
from pathlib import Path

from findsl.official.correctness import OFFICIAL_FUNCTION_FAMILIES, load_correctness_manifest


def test_formal_corpus_has_balanced_function_families_and_compositions():
    cases = load_correctness_manifest(Path("data/official_correctness/manifest.jsonl"))
    eligible = [case for case in cases if case.score_eligible]
    counts = Counter(family for case in eligible for family in case.function_families)
    compositions = [case for case in eligible if case.plan_family == "balanced_cross_function_composition"]

    assert len(compositions) >= 30
    assert all(len(case.function_families) >= 2 for case in compositions)
    assert OFFICIAL_FUNCTION_FAMILIES == set(counts)
    assert min(counts.values()) >= 10
