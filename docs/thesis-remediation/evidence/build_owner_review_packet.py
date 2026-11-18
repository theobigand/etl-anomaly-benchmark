# ruff: noqa: E501
"""Build the owner equivalence-review packet from the collected focused-mutation survivors.

    python docs/thesis-remediation/evidence/build_owner_review_packet.py

Inputs:  docs/thesis-remediation/evidence/mutation-survivors-2026-11-12.json  (collect_survivors.py)
Outputs: docs/thesis-remediation/OWNER_EQUIVALENCE_REVIEW_2026-11-12.md
         docs/thesis-remediation/equivalence/owner_review_candidates_2026-11-12.json

The technical assessments are not owner decisions. Every record is written with verdict "proposed" and
an empty approver and decision date; this script cannot create an approval. A survivor with no
assessment rule stops the build, so no candidate is silently left out.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent

STRONG = "strong_equivalence_evidence"
ADDITIONAL = "additional_verification_required"
DIFFERENCE = "meaningful_behavioral_difference"
INSUFFICIENT = "insufficient_evidence"
CATEGORIES = (STRONG, ADDITIONAL, DIFFERENCE, INSUFFICIENT)
LABEL = {
    STRONG: "Strong equivalence evidence",
    ADDITIONAL: "Additional verification required",
    DIFFERENCE: "Meaningful behavioral difference",
    INSUFFICIENT: "Insufficient evidence",
}
CLAIMS = "research/tests/test_equivalence_claims_focused.py"

FAMILIES: dict[str, dict] = {
    "choice_default": dict(
        category=STRONG,
        title="Generator.choice(..., replace=True) written without replace",
        why="replace=True is the documented default of numpy.random.Generator.choice, so omitting it requests the same sampling.",
        observable="The block indices drawn by the bootstrap, hence the resampled average precisions and the interval.",
        consumers="The temporal pilot interval stored in the pilot record and quoted in the manuscript.",
        inputs="Any size and seed; the draws were compared for equal seeds.",
        dependency="numpy 2.4.6 (default replace=True). A change of that default would break the claim.",
        evidence_for=f"Documented default; `{CLAIMS}::test_generator_choice_replaces_by_default` compares both forms over seeds.",
        evidence_against="None found.",
        uncertainty="Relies on numpy keeping the default; the pinned version is recorded.",
        more_testing="No: identical arguments after default resolution, so no input separates them.",
        action="Owner decision. If accepted it must be bound to the numpy version.",
    ),
    "argparse_default_none": dict(
        category=STRONG,
        title="argparse option declared without default=None",
        why="argparse gives an option with no explicit default the value None, which is what default=None states.",
        observable="The parsed value of --csv when the option is absent.",
        consumers="The temporal pilot command line; the value is None in both forms.",
        inputs="Any command line.",
        dependency="Python argparse (documented behavior).",
        evidence_for="Documented argparse behavior; the existing command-line tests pass an absent --csv.",
        evidence_against="None found.",
        uncertainty="None identified.",
        more_testing="No: the parsed namespace is identical.",
        action="Owner decision.",
    ),
    "aware_utc": dict(
        category=STRONG,
        title="pd.to_datetime(window_end, utc=...) on a column that is always timezone-aware",
        why="window_end is produced by WindowDriftMonitor.evaluate from timestamps that `_times` converted with utc=True, so the column is UTC-aware and utc=None, False or omitted leaves it unchanged; the comparison with an aware change time gives the same mask.",
        observable="Which windows count as before or after the change, and the counts of windows before and after.",
        consumers="Control-experiment fields written to the temporal pilot record.",
        inputs="Only monitor-produced windows reach this line; naive input never does.",
        dependency="pandas 3.0.6 and 3.1.1 (differential test run on both).",
        evidence_for=f"`src/etl_benchmark/quality/window_drift.py::_times` always passes utc=True; `{CLAIMS}::test_comparing_an_aware_column_with_an_aware_instant_ignores_the_utc_flag` over UTC, Europe/Paris and Asia/Tokyo.",
        evidence_against="If the monitor were changed to return naive times the original would still work and the mutants would raise; then the claim would no longer hold.",
        uncertainty="Depends on the monitor module keeping aware output.",
        more_testing="Not through the public path: monitor_control builds windows itself.",
        action="Owner decision. Binding to the window_drift source digest is advisable.",
    ),
    "to_numpy_dtype_none": dict(
        category=ADDITIONAL,
        title="to_numpy(dtype=None) after pd.to_numeric",
        why="After numeric coercion the series is numeric or nullable numeric; to_numpy(dtype=None) then returns float64 with NaN for the tested dtypes, the same as dtype=float, so the finite check refuses the same input with the same message.",
        observable="Whether non-finite elapsed times are refused with the stated message.",
        consumers="Every caller of to_timestamps (temporal pilot).",
        inputs="int64, float64, Int64 and Float64 with missing values, numeric strings.",
        dependency="pandas 3.0.1, 3.0.6, 3.1.1 (probe on all three; pytest on the last two).",
        evidence_for=f"`{CLAIMS}::test_to_numpy_without_a_dtype_equals_float_after_numeric_coercion`; a test that refuses a nullable column with a missing value passes with both.",
        evidence_against="Behavior of nullable dtypes under to_numpy is a pandas implementation detail.",
        uncertainty="Other extension dtypes (for example decimal or pyarrow-backed) were not checked.",
        more_testing="Possibly with pyarrow-backed numeric series; none is supported by the pipeline today.",
        action="Owner decision, or extend the differential test to pyarrow-backed dtypes first.",
    ),
    "groupby_sort_none": dict(
        category=ADDITIONAL,
        title="groupby(..., sort=None) in place of sort=False",
        why="pandas treats a falsy sort as not sorting, so None groups in order of appearance exactly as False does.",
        observable="Order and values of the per-method means (recall, precision, severity curves).",
        consumers="Typed-injection reference and severity result files, summary tables and figures.",
        inputs="Series concatenated over seeds; the order of appearance was checked with unsorted labels.",
        dependency="pandas 3.0.1, 3.0.6, 3.1.1. The parameter is documented as a bool; None is outside that contract.",
        evidence_for=f"`{CLAIMS}::test_groupby_sort_none_groups_exactly_like_sort_false` over unsorted labels on pandas 3.0.6 and 3.1.1; probe on 3.0.1.",
        evidence_against="Passing None where a bool is documented is the same shape as the LSTM `replace=None` candidate that the owner left inconclusive on 2026-11-11.",
        uncertainty="A future pandas could validate the argument as a strict bool.",
        more_testing="Not by behavior on current pandas; only by a dependency matrix.",
        action="Owner decision, consistent with the earlier inconclusive precedent for None passed to a boolean parameter.",
    ),
    "label_cast": dict(
        category=ADDITIONAL,
        title="np.asarray(labels).astype(None) in place of .astype(int) before comparing with 0",
        why="NumPy resolves astype(None) to float64; for the binary labels 0/1 (as integers, booleans, floats or digit strings) the comparison with 0 is identical.",
        observable="Which rows are selected as the normal class when loading a carrier.",
        consumers="Pool carrier construction in the typed severity experiment.",
        inputs="Binary labels only. Fractional labels differ: 0.5 is 0 under int and 0.5 under float.",
        dependency="numpy 2.4.6.",
        evidence_for=f"`{CLAIMS}::test_numpy_astype_none_agrees_with_int_for_binary_labels`.",
        evidence_against=f"`{CLAIMS}::test_numpy_astype_none_differs_from_int_for_fractional_labels` shows the forms differ outside the binary contract; no validation of the label range was found at this call.",
        uncertainty="Whether the loader guarantees binary labels for every registered file.",
        more_testing="Yes: a test with fractional or NaN labels would separate the two if the contract is to refuse them.",
        action="Technical first: decide whether non-binary labels must be refused here (then add the test and keep the mutant eligible); otherwise owner decision.",
    ),
    "labels_invisible": dict(
        category=STRONG,
        title="Column label of a cleaned feature piece (rename, dummy prefix)",
        why="The labels exist only on the local `table` inside clean(); the function returns table.to_numpy() and a report of counts and original names, and the row hash uses index=False values, so labels never reach an output.",
        observable="Nothing: the returned array, labels and report are unchanged.",
        consumers="Pool preparation and labelled benchmark through clean().",
        inputs="Numeric, boolean, categorical and constant columns.",
        dependency="pandas get_dummies and concat (labels do not affect values or column order).",
        evidence_for=f"Code reading (the table is local); `{CLAIMS}::test_cleaning_returns_values_not_column_labels`.",
        evidence_against="If clean() ever returned the DataFrame or recorded feature names, the labels would become observable.",
        uncertainty="Depends on clean() keeping returning an ndarray.",
        more_testing="Yes, if the function starts exposing feature names: that would turn these into killable mutants.",
        action="Owner decision, bound to the normalise source digest.",
    ),
    "astype_none": dict(
        category=ADDITIONAL,
        title="astype(None) in place of astype(float)",
        why="pandas and NumPy resolve astype(None) to float64, so the tested inputs give identical results.",
        observable="The dtype and values of the cast column or score.",
        consumers="Feature cleaning in normalise.clean and the base detector score method.",
        inputs="bool, int64, float64, Int64 and Float64 with missing values, numeric strings.",
        dependency="pandas 3.0.6 and 3.1.1 (differential test), numpy 2.4.6.",
        evidence_for=f"`{CLAIMS}::test_pandas_astype_none_is_astype_float`.",
        evidence_against="Equality rests on how pandas interprets None as a dtype, which is not a stated contract; the owner left the similar LSTM astype(None) candidates inconclusive on 2026-11-11.",
        uncertainty="Other dtypes (datetime, categorical, pyarrow) not exercised.",
        more_testing="Only by a wider dtype matrix or a dependency matrix.",
        action="Owner decision, with the earlier inconclusive precedent in view.",
    ),
    "index_none": dict(
        category=ADDITIONAL,
        title="index=None in place of index=False",
        why="pandas treats a falsy index flag as not writing or hashing the index.",
        observable="The CSV text written, or the row hash used to find duplicates and conflicts.",
        consumers="CSV exports (src/etl_benchmark/load.py) and duplicate detection in normalise.clean.",
        inputs="Frames with default and non-default indexes.",
        dependency="pandas 3.0.6 and 3.1.1. The parameter is documented as bool.",
        evidence_for=f"`{CLAIMS}::test_csv_and_row_hash_treat_a_missing_index_flag_as_false`.",
        evidence_against="Same shape as passing None to a boolean parameter, which the owner left inconclusive before.",
        uncertainty="Future validation of the argument type.",
        more_testing="Not by behavior on current pandas.",
        action="Owner decision.",
    ),
    "arg_type_path": dict(
        category=STRONG,
        title="argparse --output declared with type=None or without type",
        why="Both leave --output a str, while the original converts it to Path. The value is used only as the argument of atomic_path, which starts with Path(path).",
        observable="Nothing, unless another statement used a Path method on args.output; none does.",
        consumers="Command line of the pool builder and the pool checker.",
        inputs="Any path string.",
        dependency="None beyond the module source.",
        evidence_for="`src/etl_benchmark/atomic.py::atomic_path` converts its argument with Path(path); args.output has no other use in either main().",
        evidence_against="A later use of args.output as a Path (for example args.output.parent) would make the original and the mutants differ.",
        uncertainty="Depends on args.output staying confined to atomic_path.",
        more_testing="A spy on atomic_path asserting a Path argument would kill the mutants but would pin an internal type rather than behavior.",
        action="Owner decision, bound to the module digest.",
    ),
    "constant_labels": dict(
        category=STRONG,
        title="clean(features, [1] * n) in place of [0] * n",
        why="The label vector is constant, so within every group of identical rows the number of distinct labels is 1 whichever constant is used: no conflict is found and the report is identical; the returned labels are discarded.",
        observable="The carrier report (rows, duplicates, features), identical in both forms.",
        consumers="The carrier section of the pool inventory.",
        inputs="Any feature frame.",
        dependency="None.",
        evidence_for=f"Proof from the definition of conflicting rows; `{CLAIMS}::test_constant_label_vectors_give_the_same_cleaning` over four random frames.",
        evidence_against="None found.",
        uncertainty="None identified.",
        more_testing="No: the two inputs are indistinguishable by every output.",
        action="Owner decision.",
    ),
    "or_true_empty_holm": dict(
        category=STRONG,
        title="`if scored else []` replaced by `if (scored) or True else []`",
        why="With nothing scored the mutant calls holm([]), which returns []; the zip loop then has nothing to pair.",
        observable="The adjusted p-values written to each comparison entry.",
        consumers="Matched-alert analysis file.",
        inputs="An empty family of comparisons.",
        dependency="None.",
        evidence_for=f"holm([]) is [] by construction (empty argsort); `{CLAIMS}::test_holm_of_nothing_is_nothing`.",
        evidence_against="None found.",
        uncertainty="Holm would have to raise on empty input for the claim to fail.",
        more_testing="No.",
        action="Owner decision.",
    ),
    "problems_count_only": dict(
        category=STRONG,
        title="problems.append(None) in place of problems.append(run['problem'])",
        why="The list `problems` is read only for len(problems) and for its truthiness; its elements are never used, so None and the problem name are indistinguishable.",
        observable="The count of problems and whether any problem is present.",
        consumers="Matched-alert comparison entries.",
        inputs="Any runs.",
        dependency="None.",
        evidence_for="Code reading of compare(): `sources` carries the identities; `problems` is used as `len(problems)` and `if problems:`.",
        evidence_against="A later use of the elements would make the original differ.",
        uncertainty="Depends on the function staying this way.",
        more_testing="No, unless the elements start being used.",
        action="Owner decision. A cleaner alternative is to replace the list by a counter, which removes the mutant.",
    ),
    "zip_same_source": dict(
        category=STRONG,
        title="zip(moved, observed, strict=...) over two lists built from the same cells",
        why="`moved` and `observed` are comprehensions over the same `cells` list, so their lengths are equal by construction; strict only changes behavior if the lengths differ.",
        observable="Nothing under the construction; strict=True is a defensive assertion.",
        consumers="Prevalence-shift contrasts.",
        inputs="Any cells.",
        dependency="Python zip(strict=...) semantics.",
        evidence_for="Code reading: both lists iterate `cells` once.",
        evidence_against="None found.",
        uncertainty="None under the present code.",
        more_testing="Only by replacing the comprehensions with an injected list, which would change the code under test.",
        action="Owner decision.",
    ),
    "rpartition": dict(
        category=STRONG,
        title="problem.rpartition(':') in place of partition(':')",
        why="The branch that changes the result needs kind == 'adbench' and a name found in UCI_SOURCES, whose keys contain no colon; for such strings both splits agree, and for every other string both fall through to the problem itself.",
        observable="The source identity returned for a problem name.",
        consumers="All source-clustered analyses.",
        inputs="All problem names including several colons and no colon.",
        dependency="The UCI_SOURCES keys must stay colon-free.",
        evidence_for=f"`{CLAIMS}::test_source_ids_do_not_depend_on_which_colon_splits_the_problem_name` includes a key check.",
        evidence_against="A source key with a colon would separate them.",
        uncertainty="Depends on the registry content (asserted by the test).",
        more_testing="No.",
        action="Owner decision.",
    ),
    "f1_guard": dict(
        category=STRONG,
        title="`if tp else 0.0` replaced by `if (tp) or True else 0.0`",
        why="With tp == 0 the numerator is 0 and, since recall (evaluated earlier in the same literal) already raised when tp + fn == 0, the denominator fp + fn is positive: the value is 0.0 in both forms.",
        observable="The f1 field of a budget cell.",
        consumers="Alert-budget result files.",
        inputs="Any confusion counts for which the function does not already raise.",
        dependency="None.",
        evidence_for="Dictionary literals evaluate in order: the recall line raises ZeroDivisionError when tp + fn == 0 before f1 is reached.",
        evidence_against="Reordering of the literal's fields would change this.",
        uncertainty="Depends on the field order.",
        more_testing="No at present.",
        action="Owner decision.",
    ),
    "asarray_float_detector": dict(
        category=ADDITIONAL,
        title="np.asarray / to_numpy of detector output with dtype=None or without dtype",
        why="Detector scores are float Series, flags are boolean Series; converting a float or boolean array to its own dtype leaves it unchanged.",
        observable="The dtype of scores used for ROC and PR statistics and thresholds; differs only for non-float output.",
        consumers="Alert-budget and score-shift runs.",
        inputs="Float and boolean detector output.",
        dependency="Detector contract (scores are floats).",
        evidence_for="Detectors in the registry return float scores; the existing run tests use float stubs.",
        evidence_against="A detector returning integers, objects or missing values would reach the metric functions with a different dtype.",
        uncertainty="Whether every registered detector, including future ones, returns float.",
        more_testing="Yes: a stub detector returning integer or object scores would separate the forms if the contract is to coerce them.",
        action="Technical first: add a stub-based test for non-float scores; if the behavior is deliberately unspecified, owner decision.",
    ),
    "nonneg_compare": dict(
        category=STRONG,
        title="base precision > 0 replaced by >= 0 in the precision-collapse flag",
        why="When the base precision is 0 the second operand is `now < PRECISION_FLOOR * 0`, i.e. `now < 0`, which is false for a precision in [0, 1]; so the flag is false in both forms.",
        observable="The precision_collapse share per scenario.",
        consumers="Score-shift monitor table.",
        inputs="Precision values in [0, 1].",
        dependency="Precision is a rate (non-negative).",
        evidence_for="Arithmetic on the guarded comparison; `_counts` defines precision as a rate with 0.0 when undefined.",
        evidence_against="Negative precision input would separate them but is outside the data contract.",
        uncertainty="None under the contract.",
        more_testing="Only with out-of-contract negative precision.",
        action="Owner decision.",
    ),
    "continue_break_empty": dict(
        category=STRONG,
        title="`continue` replaced by `break` when a scenario has no rows",
        why="The rows of every scenario come from the same fits, so a scenario has no rows only when there are no fits, and then every scenario is empty.",
        observable="The scenarios present in the monitor table.",
        consumers="Score-shift monitor table.",
        inputs="Runs with and without fits.",
        dependency="None.",
        evidence_for="Code reading of monitor_table(): `rows` depends on `_fits(runs)` and the scenario key; a missing scenario key raises KeyError instead of producing an empty list.",
        evidence_against="A scenario that is absent from some fits is a KeyError in both forms, not an empty row list.",
        uncertainty="None identified.",
        more_testing="No.",
        action="Owner decision.",
    ),
}

# (module path, regex on the mutant name after the module prefix, family)
RULES = [
    ("research/temporal_pilot.py", r"x_block_bootstrap_ci__mutmut_38$", "choice_default"),
    ("research/temporal_pilot.py", r"x_main__mutmut_18$", "argparse_default_none"),
    (
        "research/temporal_pilot.py",
        r"x_monitor_control__mutmut_(56|58|61|99|101|104)$",
        "aware_utc",
    ),
    ("research/temporal_pilot.py", r"x_to_timestamps__mutmut_11$", "to_numpy_dtype_none"),
    ("research/typed_run.py", r"x_run_one__mutmut_(48|55)$", "groupby_sort_none"),
    ("research/pool_typed.py", r"x_load_carrier__mutmut_29$", "label_cast"),
    (
        "research/pool_typed.py",
        r"x_run_(reference__mutmut_(33|45)|severity__mutmut_28)$",
        "groupby_sort_none",
    ),
    ("research/normalise.py", r"x_clean__mutmut_(34|45|48|51)$", "labels_invisible"),
    ("research/normalise.py", r"x_clean__mutmut_35$", "astype_none"),
    ("research/normalise.py", r"x_clean__mutmut_64$", "index_none"),
    ("research/build_pool.py", r"x_main__mutmut_(27|30)$", "arg_type_path"),
    ("research/build_pool.py", r"x_pool_row__mutmut_38$", "constant_labels"),
    ("src/etl_benchmark/load.py", r"x_write_csv__mutmut_11$", "index_none"),
    ("src/etl_benchmark/quality/base.py", r"xǁDetectorǁscore__mutmut_1$", "astype_none"),
    ("research/pool_check.py", r"x_main__mutmut_(27|30)$", "arg_type_path"),
    ("research/matched_alert.py", r"x_analyse__mutmut_20$", "or_true_empty_holm"),
    ("research/matched_alert.py", r"x_compare__mutmut_43$", "problems_count_only"),
    ("research/prevalence_shift.py", r"x_contrasts__mutmut_(59|62|63)$", "zip_same_source"),
    ("research/source_clustered.py", r"x_source_id__mutmut_3$", "rpartition"),
    ("research/alert_budget.py", r"x__counts__mutmut_50$", "f1_guard"),
    ("research/alert_budget.py", r"x_run_method__mutmut_(23|54)$", "asarray_float_detector"),
    ("research/score_shift.py", r"x_monitor_table__mutmut_39$", "nonneg_compare"),
    ("research/score_shift.py", r"x_monitor_table__mutmut_48$", "continue_break_empty"),
    ("research/score_shift.py", r"x_run_method__mutmut_(23|25|39|41)$", "asarray_float_detector"),
]

ACCEPTED_EXCLUSIONS = {
    "research/lstm_detector.py": 4
}  # the owner's records of 2026-11-11, not changed here


def family_of(path: str, key: str) -> str | None:
    tail = key.rsplit(".", 1)[1]
    for rule_path, pattern, family in RULES:
        if rule_path == path and re.fullmatch(pattern, tail):
            return family
    return None


def changed_lines(diff: str) -> tuple[str, str]:
    removed = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("-") and not line.startswith("---")
    ]
    added = [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(removed).strip(), "\n".join(added).strip()


def function_of(key: str) -> str:
    tail = key.rsplit(".", 1)[1]
    match = re.match(r"x(?:ǁ\w+ǁ)?_?(.+?)__mutmut_\d+$", tail)
    return match.group(1) if match else tail


def tests_for(path: str) -> list[str]:
    module = Path(path).stem
    found = []
    for folder in (ROOT / "tests", ROOT / "research" / "tests"):
        for file in sorted(folder.glob("test_*.py")):
            text = file.read_text()
            if re.search(
                rf"(import {module}\b|from {module} import|etl_benchmark\.(?:quality\.)?{module}\b|import {module} as)",
                text,
            ):
                found.append(str(file.relative_to(ROOT)))
    return found


def pct(killed: int, total: int) -> str:
    scaled = (killed * 10000 * 2 + total) // (2 * total)  # round half up, integer arithmetic
    return f"{scaled // 100}.{scaled % 100:02d} %"


def passes(killed: int, adjusted: int, threshold: int = 98) -> bool:
    return killed * 100 >= threshold * adjusted


def minimum_exclusions(killed: int, total: int, available: int, threshold: int = 98) -> int | None:
    for excluded in range(available + 1):
        if passes(killed, total - excluded, threshold):
            return excluded
    return None


def main() -> None:
    data = json.loads((HERE / "mutation-survivors-2026-11-12.json").read_text())
    modules = data["modules"]
    git_head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    environment = {
        "pandas": data["environment"]["pandas"],
        "numpy": data["environment"]["numpy"],
        "mutmut": data["environment"]["mutmut"],
    }
    records, cases, unassigned, others = [], [], [], []
    by_module = {}
    for module in modules:
        path = module["path"]
        for survivor in module["survivors"]:
            if survivor["outcome"] != "survived":
                others.append((path, survivor))
                continue
            family = family_of(path, survivor["id"])
            if family is None:
                unassigned.append(survivor["id"])
                continue
            original, mutated = changed_lines(survivor["diff"])
            info = FAMILIES[family]
            case = {
                "module": module,
                "survivor": survivor,
                "family": family,
                "info": info,
                "original": original,
                "mutated": mutated,
                "function": function_of(survivor["id"]),
            }
            cases.append(case)
            by_module.setdefault(path, []).append(case)
            records.append(
                {
                    "id": survivor["id"],
                    "path": path,
                    "function": case["function"],
                    "diff": survivor["diff"],
                    "original_behavior": f"original expression: {original}",
                    "mutated_behavior": f"mutated expression: {mutated}",
                    "risk": "L4",
                    "reason": f"[{LABEL[info['category']]}; technical assessment only, not an owner decision] {info['title']}. {info['why']}",
                    "evidence": [
                        CLAIMS,
                        "docs/thesis-remediation/OWNER_EQUIVALENCE_REVIEW_2026-11-12.md",
                        "docs/thesis-remediation/evidence/mutation-survivors-2026-11-12.json",
                    ],
                    "source_sha256": module["source_sha256"],
                    "catalog_sha256": module["catalog_sha256"],
                    "author": "theobigand",
                    "verdict": "proposed",
                    "approver": "",
                    "decision_date": "",
                    "policy_version": 2,
                    "environment": environment,
                    "assessments": [],
                }
            )
    if unassigned:
        raise SystemExit("survivors without an assessment rule: " + ", ".join(unassigned))
    (
        ROOT / "docs/thesis-remediation/equivalence/owner_review_candidates_2026-11-12.json"
    ).write_text(
        json.dumps(
            {
                "version": 2,
                "review_mode": "sole_author_owner_review",
                "owner": "theobigand",
                "records": records,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )

    counts = {c: sum(1 for case in cases if case["info"]["category"] == c) for c in CATEGORIES}
    out = []
    w = out.append
    w("# Owner equivalence review packet, focused mutation survivors (2026-11-12)\n")
    w(
        "Status: **technical assessments only. No owner decision exists in this document or in the machine-readable index.** "
        "Every candidate is stored with `verdict: proposed`, an empty approver and an empty decision date. "
        "Nothing here changes `verification/mutation_equivalence.json`, the accepted denominator, or any score.\n"
    )
    w("## Executive overview\n")
    w(
        f"The focused mutation runs of 2026-11-12 (mutmut 3.8.0, `make mutation-focus`, repository revision `{git_head}` plus the test additions listed below) "
        f"left {len(cases)} surviving mutants in {len(by_module)} L4 modules that I assessed individually. "
        f"The technical assessment is: {counts[STRONG]} with strong equivalence evidence, {counts[ADDITIONAL]} requiring additional verification, "
        f"{counts[DIFFERENCE]} with a meaningful behavioral difference, {counts[INSUFFICIENT]} with insufficient evidence. "
        "These categories are my reading of the evidence; they are not verdicts, and a mutant that no current test can separate is not thereby equivalent.\n"
    )
    w(
        "Before building this packet I added behavioral tests for the survivors that I could separate on the supported contract. That work removed "
        "mutants from the list rather than moving them into it: boundary comparison of a window ending exactly at the change time, "
        "naive timestamps, integer typing of time blocks, the configured split ratios, a deprecated pandas unit alias, "
        "default method sets, flushed progress lines, wrong-length Holm adjustments, and missing-score refusals. "
        "What remains is the set I could not separate that way; two families (`label_cast`, `asarray_float_detector`) may still gain a test, see the outstanding-work table.\n"
    )
    below = [m["path"] for m in modules if m["counts"].get("killed", 0) * 100 < 98 * m["total"]]
    w(
        f"Raw focused scores, before any exclusion: {len(modules) - len(below)} of the {len(modules)} measured modules are at or above 98 "
        f"and {len(below)} are below ({', '.join('`' + b + '`' for b in below)}). "
        "A focused run is development feedback on one module; it is not a campaign result and certifies nothing.\n"
    )
    w(
        "Owner review is required because an exclusion changes the denominator of a release-gate score, and a decision binds the exact source digest, catalog digest, "
        "policy version and dependency versions of the record. Score arithmetic below is shown so the effect is visible; it is not a reason to approve.\n"
    )
    w(
        "Precedent already on record (owner decisions of 2026-11-11, `docs/thesis-remediation/EQUIVALENCE_REVIEW_PACKET_LSTM_2026-11-08.md`): four LSTM mutants accepted "
        "and five left **inconclusive**, among them `astype(None)` and `replace=None`. Several candidates below have the same shape as the inconclusive ones "
        "(None passed where a boolean or dtype is documented). I flag the resemblance; I do not infer a decision from it.\n"
    )

    w("## Candidate inventory\n")
    w("| Module | Mutant (suffix) | Function | Category | Family | Individual decision needed |")
    w("| --- | --- | --- | --- | --- | --- |")
    for path, items in by_module.items():
        for case in items:
            w(
                f"| `{path}` | `{case['survivor']['id'].rsplit('.', 1)[1]}` | `{case['function']}` | {LABEL[case['info']['category']]} | {case['family']} | yes |"
            )
    w("")
    w("Counts by category: " + "; ".join(f"{LABEL[c]} {counts[c]}" for c in CATEGORIES) + ".\n")

    w("## Score implications (exact integer arithmetic, hypothetical)\n")
    w(
        "Policy used: `verification/mutation_policy.py::_summary`: PASS when `killed * 100 >= threshold * adjusted_eligible`, with `adjusted_eligible = eligible - accepted_equivalents`. "
        "A timeout and a survivor are both outcomes other than `killed`; a timeout is not an exclusion candidate. "
        "Only a surviving mutant with an owner record bound to the current digests can be excluded. L4 threshold: 98.\n"
    )
    w(
        "Every figure in the *Hypothetical* columns is hypothetical: it assumes the owner accepts the named group and is not an achieved result.\n"
    )
    w(
        "| Module | Killed | Total | Survived | Timeouts | Incomplete | Accepted exclusions | Raw score | Hypothetical if strong group accepted | Hypothetical if all candidates accepted | Min. exclusions to reach 98 | Focused raw arithmetic at 98 (not a certification) |"
    )
    w("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for module in sorted(modules, key=lambda m: m["path"]):
        c = module["counts"]
        killed, total = c.get("killed", 0), module["total"]
        survived, timeouts = c.get("survived", 0), c.get("timeout", 0)
        incomplete = total - killed - survived - timeouts
        accepted = ACCEPTED_EXCLUSIONS.get(module["path"], 0)
        items = by_module.get(module["path"], [])
        strong = sum(1 for case in items if case["info"]["category"] == STRONG)
        allc = len(items)
        h_strong = (
            f"{killed}/{total - accepted - strong} = {pct(killed, total - accepted - strong)}"
            + (" (meets 98)" if passes(killed, total - accepted - strong) else " (below 98)")
        )
        h_all = f"{killed}/{total - accepted - allc} = {pct(killed, total - accepted - allc)}" + (
            " (meets 98)" if passes(killed, total - accepted - allc) else " (below 98)"
        )
        need = minimum_exclusions(killed, total - accepted, survived)
        need_text = "not reachable by excluding survivors" if need is None else str(need)
        result = (
            "meets 98"
            if passes(killed, total - accepted) and not incomplete
            else ("INCOMPLETE" if incomplete else "below 98")
        )
        w(
            f"| `{module['path']}` | {killed} | {total} | {survived} | {timeouts} | {incomplete} | {accepted} | {pct(killed, total)} | {h_strong} | {h_all} | {need_text} | {result} |"
        )
    w("")
    w(
        "A module that reaches 98 in a focused run is not thereby compliant: the release gate also needs a full native campaign on one revision with admissible provenance, "
        "owner records bound to that revision's digests, and the campaign-level policy evaluation. The release gate stays fail-closed.\n"
    )
    w("### Correction of the earlier threshold statement\n")
    t_total, t_killed = 589, 571
    w(
        f"The earlier measurement of `research/temporal_pilot.py` was {t_killed} killed of {t_total} (17 survived, 1 timeout), source digest prefix `03e63b296112`. "
        f"With six exclusions the score would have been {t_killed}/{t_total - 6} = {pct(t_killed, t_total - 6)} (below 98: {t_killed * 100} < {98 * (t_total - 6)}); "
        f"with seven, {t_killed}/{t_total - 7} = {pct(t_killed, t_total - 7)} (meets 98). "
        "My earlier note that six accepted equivalents would suffice was wrong and is superseded here. "
        f"For `research/typed_run.py` (343 of 351) one exclusion would give 343/350 = {pct(343, 350)}, exactly 98.00 % ({343 * 100} >= {98 * 350}), which the policy accepts. "
        "Both are hypothetical, and both measurements predate the tests added for this packet.\n"
    )
    w("### Timeout and incomplete outcomes\n")
    w(
        "The earlier temporal-pilot timeout was `x_block_bootstrap_ci__mutmut_40` (`index = None` in the bootstrap loop): the mutant makes sklearn compute average precision "
        "for a one-row multilabel input with one column per observation, which is slow but returns different numbers. A timeout was never treated as killed. "
        "The small test `test_a_small_bootstrap_equals_its_definition_and_runs_fast` alone did not remove the timeout, because mutmut runs the older test with 4,000 rows and 200 resamples first and the mutant makes it extremely slow; "
        "that older test now uses 1,500 rows and 60 resamples (same assertions: determinism and the interval brackets the estimate), and the mutant is killed. "
        "In the first alert-budget run one mutant (`x_run_job__mutmut_28`, a case-changed dictionary key) ended with exit code 255, an incomplete outcome; it was killed in the next run of the module, so the cause was the execution environment and not a property of the mutant. "
        "Outcomes other than killed and survived in the collected runs: "
        + ("; ".join(f"`{s['id']}` = {s['outcome']}" for _, s in others) or "none")
        + ". Such an outcome is neither a survivor nor killed and is never counted as either.\n"
    )

    w("## Individual case records\n")
    w(
        "Fields: identity; source and catalog binding; original and mutated code; outcome; existing tests; why it survived; intended observable behavior; consumers; supported inputs; dependency sensitivity; evidence for and against; uncertainty; whether further testing could separate it; next technical action; owner decision status.\n"
    )
    families_seen = {}
    for case in cases:
        families_seen.setdefault(case["family"], []).append(case)
    for path, items in by_module.items():
        module = items[0]["module"]
        w(f"### `{path}`\n")
        current = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        w(
            "Binding at build time: the working-tree source "
            + ("equals" if current == module["source_sha256"] else "DIFFERS from")
            + " the digest below.\n"
        )
        w(
            f"Source SHA-256 `{module['source_sha256']}`; catalog SHA-256 `{module['catalog_sha256']}` ({module['total']} mutants); existing tests importing the module: "
            + (", ".join(f"`{t}`" for t in tests_for(path)) or "none found")
            + ".\n"
        )
        for case in items:
            info = case["info"]
            w(f"#### `{case['survivor']['id']}`\n")
            w(
                f"- Function: `{case['function']}`; outcome: {case['survivor']['outcome']}; category: **{LABEL[info['category']]}** (family `{case['family']}`)."
            )
            w(f"- Original: `{case['original']}`")
            w(f"- Mutated: `{case['mutated']}`")
            w(f"- Change: {info['title']}.")
            w(f"- Why it survived: {info['why']}")
            w(f"- Observable behavior: {info['observable']}")
            w(f"- Downstream consumers: {info['consumers']}")
            w(f"- Supported inputs and boundaries: {info['inputs']}")
            w(f"- Dependency sensitivity: {info['dependency']}")
            w(f"- Evidence for equivalence: {info['evidence_for']}")
            w(f"- Evidence against or limits: {info['evidence_against']}")
            w(f"- Remaining uncertainty: {info['uncertainty']}")
            w(f"- Could further testing separate it: {info['more_testing']}")
            w(f"- Recommended next technical action: {info['action']}")
            w("- Owner decision status: **undecided** (no record exists).\n")

    w("## Decision instructions\n")
    w(
        "The owner decides each mutant individually by editing `verification/mutation_equivalence.json` (version 2) using the existing schema; the file under "
        "`docs/thesis-remediation/equivalence/owner_review_candidates_2026-11-12.json` is only the list of proposals and is never read as an approval source. "
        "For each decision set `verdict` to `accepted`, `rejected` or `inconclusive`, set `approver` to the owner login, set `decision_date`, and keep `source_sha256`, "
        "`catalog_sha256`, `policy_version` and `environment` exactly as in the proposal. A record stays valid only while the module source digest, catalog digest, risk level, "
        "policy version, the dependency versions in `environment` and the survival of the mutant all match; a changed source invalidates it. "
        "Leaving a candidate without a record keeps it in the denominator, the same as `inconclusive`. I have not prefilled any verdict, date or approver.\n"
    )

    w("## Outstanding work\n")
    w("| Class | Items |")
    w("| --- | --- |")
    ready = [c for c in cases if c["family"] in ("label_cast", "asarray_float_detector")]
    w(
        f"| Could still gain a behavioral test | {len(ready)} mutants in families `label_cast` (label range at the carrier loader) and `asarray_float_detector` (non-float detector output): {', '.join('`' + c['survivor']['id'].rsplit('.', 1)[1] + '`' for c in ready)} |"
    )
    w(
        f"| Need more evidence (dependency matrix or wider dtypes) | {sum(1 for c in cases if c['info']['category'] == ADDITIONAL)} mutants in the Additional-verification category |"
    )
    w(f"| Await owner judgment | all {len(cases)} candidates |")
    w(
        "| Timeouts / incomplete | "
        + (
            "; ".join(f"`{s['id']}` ({s['outcome']})" for _, s in others)
            or "none in the collected runs"
        )
        + " |"
    )
    w("| Modules still below 98 in focused runs | see the score table (raw result column) |")
    w(
        "| Missing or stale evidence | 9 L4 modules absent from the 2026-11-07 campaign; 56 campaign modules below 98 (`MUTATION_L4_INVENTORY.md`); the temporal pilot source differs from the revision that produced the archived record |"
    )
    w("")
    w("## Validation of this packet\n")
    w(
        "`tests/test_owner_review_packet.py` checks that every candidate id exists in the collected catalog, that the digests match the current source files and the catalog, "
        "that the arithmetic in this document matches the policy function, that no record carries an approver or a date, and that the proposals are never counted by `accepted_equivalents`.\n"
    )
    (ROOT / "docs/thesis-remediation/OWNER_EQUIVALENCE_REVIEW_2026-11-12.md").write_text(
        "\n".join(out) + "\n"
    )


if __name__ == "__main__":
    main()
