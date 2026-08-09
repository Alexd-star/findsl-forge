from pathlib import Path
from types import SimpleNamespace

from findsl.official.backend.diff import hash_result_rows
from findsl.official.backend.executor import (
    DorisExecutionConfig,
    DorisExecutionResult,
    DorisExplainResult,
)
from findsl.official.context import CompileContext
from findsl.official.correctness import CorrectnessCase, OFFICIAL_FUNCTION_FAMILIES
from findsl.official.performance import (
    PerformanceCase,
    load_performance_manifest,
    run_performance_matrix,
    select_performance_cases,
    write_performance_manifest,
)


ROOT = Path(__file__).resolve().parents[2]


def test_stratified_selection_covers_all_function_families_and_plan_families():
    cases = tuple(
        _correctness_case(index, family, f"plan-{index % 5}")
        for index, family in enumerate(sorted(OFFICIAL_FUNCTION_FAMILIES), start=1)
    )

    selected = select_performance_cases(cases, per_family=1, max_cases=20)

    assert {family for case in selected for family in case.function_families} == set(
        OFFICIAL_FUNCTION_FAMILIES
    )
    assert {case.plan_family for case in selected} == {f"plan-{index}" for index in range(5)}


def test_manifest_round_trip(tmp_path: Path):
    path = tmp_path / "matrix.jsonl"
    cases = (
        PerformanceCase("P1", "dsl", ("indicator",), "direct", "light", "ref.sql", True),
    )

    write_performance_manifest(cases, path)

    assert load_performance_manifest(path) == cases


def test_runner_requires_reference_match_before_performance_pass(tmp_path: Path):
    (tmp_path / "ref.sql").write_text("reference", encoding="utf-8")
    context = CompileContext.load(ROOT)
    case = PerformanceCase(
        "P1",
        "dsl",
        ("indicator",),
        "direct",
        "light",
        "ref.sql",
        True,
    )

    def compiler(dsl, *, context):
        return SimpleNamespace(
            backend={"sql": "generated"},
            physical={"selected_strategy": "direct_column"},
            elapsed_ms=1.0,
        )

    rows = (("1",),)

    def executor(config, sql):
        values = rows if sql in {"reference", "generated"} else (("2",),)
        return DorisExecutionResult(
            values,
            5.0,
            hash_result_rows(values, ordered=True),
            hash_result_rows(values, ordered=False),
        )

    report = run_performance_matrix(
        (case,),
        manifest_root=tmp_path,
        doris=DorisExecutionConfig("127.0.0.1", 9030, "root", "", "newzl"),
        warmups=0,
        repeats=3,
        context=context,
        compiler=compiler,
        executor=executor,
        explainer=lambda config, sql: DorisExplainResult("PLAN", 1.0),
    )

    assert report["all_matched_reference"] is True
    assert report["all_queries_under_10s"] is True
    assert report["results"][0]["execute_p95_ms"] == 5.0


def _correctness_case(index, family, plan):
    return CorrectnessCase(
        f"C{index}",
        f"dsl-{index}",
        (family,),
        plan,
        "eligible",
        "test",
        "official-semantic-policy-v1",
        "snapshot",
        True,
        f"ref-{index}.sql",
        "approved",
        "reviewer",
        False,
    )
