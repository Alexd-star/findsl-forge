from collections import Counter

from scripts.extract_external_scope_targets import _unresolved_counts


class _Catalog:
    def __init__(self, values):
        self.values = set(values)

    def resolve(self, atom):
        if atom not in self.values:
            raise KeyError(atom)
        return atom


def test_scope_target_extraction_omits_atoms_already_available_at_runtime():
    counts = Counter({"官方证券": 2, "公开概念": 3, "缺失板块": 4})

    unresolved = _unresolved_counts(
        counts,
        _Catalog({"官方证券"}),
        _Catalog({"公开概念"}),
    )

    assert unresolved == Counter({"缺失板块": 4})
