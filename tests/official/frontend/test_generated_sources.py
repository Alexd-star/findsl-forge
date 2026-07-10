from pathlib import Path
from importlib.metadata import version


def test_antlr_runtime_and_generated_parser_are_pinned_to_4_13_2():
    from findsl.official.frontend.generated.OfficialSlotParser import OfficialSlotParser

    assert version("antlr4-python3-runtime") == "4.13.2"
    assert OfficialSlotParser.grammarFileName == "OfficialSlot.g4"


def test_production_grammar_is_owned_outside_documentation():
    root = Path(__file__).resolve().parents[3]

    assert (root / "grammar" / "OfficialSlot.g4").is_file()
