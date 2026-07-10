from findsl.official import CompileMode, SourceRepair


def test_compile_mode_parses_cli_values():
    assert CompileMode.parse("strict") is CompileMode.STRICT
    assert CompileMode.parse("recovery") is CompileMode.RECOVERY


def test_source_repair_serializes_for_evidence():
    repair = SourceRepair(code="TRAILING_QUOTE", message="remove trailing quote", position=12)

    assert repair.to_dict() == {
        "code": "TRAILING_QUOTE",
        "message": "remove trailing quote",
        "position": 12,
    }
