import json

import pytest

from findsl.official.physical.approximation import (
    ApproximationPolicyError,
    NumericApproximationPolicy,
    default_numeric_approximation_policy,
)


def test_default_numeric_approximation_policy_is_bounded_and_versioned():
    policy = default_numeric_approximation_policy()

    assert policy.relative_tolerance == 0.01
    assert policy.absolute_tolerance == 0.01
    assert policy.version


def test_numeric_approximation_policy_rejects_invalid_tolerance(tmp_path):
    path = tmp_path / "approximation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "version": "test",
                "numeric": {
                    "relative_tolerance": 1.0,
                    "absolute_tolerance": 0.01,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ApproximationPolicyError, match="out of range"):
        NumericApproximationPolicy.load(path)
