"""Prospective risk scopes must fail independently and retain every mutant."""

from __future__ import annotations

import copy
import importlib

import pytest


def _policy(tmp_path, levels=("L1", "L2", "L3", "L4")):
    units = {}
    for index, level in enumerate(levels):
        name = f"app/unit{index}.py"
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("def compute(value):\n    return value + 1\n")
        units[name] = {"level": level, "reason": f"Constructed {level} acceptance scope"}
    return {
        "version": 2,
        "thresholds": {"L1": 80, "L2": 90, "L3": 95, "L4": 98},
        "roots": ["app"],
        "units": units,
    }


def _api():
    return importlib.import_module("verification.mutation_policy")


def _campaign(policy, counts):
    catalog, records = {}, []
    for path, (killed, total) in zip(policy["units"], counts, strict=True):
        module = path[:-3].replace("/", ".")
        keys = [f"{module}.x_compute__mutmut_{i + 1}" for i in range(total)]
        catalog[path] = keys
        records.extend(
            {"id": key, "path": path, "outcome": "killed" if i < killed else "survived"}
            for i, key in enumerate(keys)
        )
    return catalog, records


@pytest.mark.parametrize("level,threshold", [("L1", 80), ("L2", 90), ("L3", 95), ("L4", 98)])
def test_each_tier_enforces_its_exact_boundary(tmp_path, level, threshold):
    policy = _policy(tmp_path, (level,))
    for killed, expected in [(threshold, "PASS"), (threshold - 1, "FAIL")]:
        catalog, records = _campaign(policy, [(killed, 100)])
        result = _api().evaluate(policy, tmp_path, catalog, records)
        assert result["status"] == expected
        scope = result["modules"]["app/unit0.py"]
        assert scope["status"] == expected
        assert result["levels"][level]["status"] == expected
        assert scope["threshold"] == threshold and scope["eligible"] == 100
        assert scope["killed"] == killed and scope["survived"] == 100 - killed


def test_lower_risk_passes_cannot_compensate_for_a_critical_failure(tmp_path):
    policy = _policy(tmp_path)
    catalog, records = _campaign(policy, [(1000, 1000)] * 3 + [(97, 100)])
    result = _api().evaluate(policy, tmp_path, catalog, records)
    assert result["status"] == "FAIL"
    assert result["levels"]["L4"]["status"] == "FAIL"
    assert result["total"]["score"] > 99


def test_a_stronger_module_cannot_hide_a_weaker_module_of_the_same_tier(tmp_path):
    policy = _policy(tmp_path, ("L4", "L4"))
    catalog, records = _campaign(policy, [(1000, 1000), (1, 2)])
    result = _api().evaluate(policy, tmp_path, catalog, records)
    assert result["status"] == "FAIL"
    assert result["levels"]["L4"]["status"] == "FAIL"
    assert result["modules"]["app/unit1.py"]["status"] == "FAIL"


@pytest.mark.parametrize("bad", ["L0", "L5", None, 4])
def test_invalid_classification_is_refused(tmp_path, bad):
    policy = _policy(tmp_path, ("L4",))
    policy["units"]["app/unit0.py"]["level"] = bad
    with pytest.raises(ValueError, match="level"):
        _api().validate_policy(policy, tmp_path)


@pytest.mark.parametrize("change", ["lower", "float", "missing", "version", "reason"])
def test_policy_downgrades_and_malformed_contracts_are_refused(tmp_path, change):
    policy = _policy(tmp_path, ("L4",))
    if change == "lower":
        policy["thresholds"]["L4"] = 97
    elif change == "float":
        policy["thresholds"]["L1"] = 80.0
    elif change == "missing":
        del policy["thresholds"]["L2"]
    elif change == "version":
        policy["version"] = 1
    else:
        policy["units"]["app/unit0.py"]["reason"] = " "
    with pytest.raises(ValueError):
        _api().validate_policy(policy, tmp_path)


def test_new_executable_files_fail_closed_until_classified(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    (tmp_path / "app/new.py").write_text("def score():\n    return 1\n")
    with pytest.raises(ValueError, match="unclassified.*app/new.py"):
        _api().validate_policy(policy, tmp_path)


def test_stale_classification_cannot_silently_shrink_the_population(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    (tmp_path / "app/unit0.py").unlink()
    with pytest.raises(ValueError, match="stale"):
        _api().validate_policy(policy, tmp_path)


def test_test_sources_are_not_production_units(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    folder = tmp_path / "app/tests"
    folder.mkdir()
    (folder / "test_unit.py").write_text("def test_example():\n    assert True\n")
    _api().validate_policy(policy, tmp_path)


@pytest.mark.parametrize("defect", ["duplicate", "extra", "wrong_path", "unknown_status"])
def test_ambiguous_or_forged_mutant_records_are_refused(tmp_path, defect):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(1, 1)])
    if defect == "duplicate":
        records.append(copy.deepcopy(records[0]))
    elif defect == "extra":
        records[0]["id"] = "app.unit0.x_compute__mutmut_2"
    elif defect == "wrong_path":
        records[0]["path"] = "app/other.py"
    else:
        records[0]["outcome"] = "looks good"
    with pytest.raises(ValueError):
        _api().evaluate(policy, tmp_path, catalog, records)


@pytest.mark.parametrize("outcome", ["timeout", "suspicious", "survived", "caught by type check"])
def test_non_killed_outcomes_stay_in_the_denominator(tmp_path, outcome):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(98, 100)])
    records[-1]["outcome"] = outcome
    result = _api().evaluate(policy, tmp_path, catalog, records)
    assert result["status"] == "PASS"
    assert result["modules"]["app/unit0.py"]["eligible"] == 100
    assert result["modules"]["app/unit0.py"]["killed"] == 98


@pytest.mark.parametrize(
    "outcome",
    ["not checked", "no tests", "skipped", "segfault", "check was interrupted by user", "error"],
)
def test_invalid_or_unexecuted_outcomes_never_pass(tmp_path, outcome):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(99, 100)])
    records[-1]["outcome"] = outcome
    assert _api().evaluate(policy, tmp_path, catalog, records)["status"] == "INCOMPLETE"


def test_missing_catalog_or_missing_record_is_not_a_success(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(1, 1)])
    assert _api().evaluate(policy, tmp_path, {}, [])["status"] == "INCOMPLETE"
    assert _api().evaluate(policy, tmp_path, catalog, [])["status"] == "INCOMPLETE"


def test_policy_and_source_changes_invalidate_evidence_without_mutating_input(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(1, 1)])
    saved = copy.deepcopy((policy, catalog, records))
    before = _api().evaluate(policy, tmp_path, catalog, records)
    assert (policy, catalog, records) == saved
    policy["units"]["app/unit0.py"]["reason"] += "; reviewed"
    changed = _api().evaluate(policy, tmp_path, catalog, records)
    assert changed["policy_sha256"] != before["policy_sha256"]
    (tmp_path / "app/unit0.py").write_text("def compute(value):\n    return value + 2\n")
    changed = _api().evaluate(policy, tmp_path, catalog, records)
    assert changed["sources"] != before["sources"]


def test_an_empty_scope_cannot_claim_a_passing_campaign(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(0, 0)])
    result = _api().evaluate(policy, tmp_path, catalog, records)
    assert result["status"] == "INCOMPLETE"
    assert result["levels"]["L1"]["status"] == "NOT_APPLICABLE"


@pytest.mark.parametrize("bad", [2.0, True, None])
def test_policy_version_is_a_strict_integer(tmp_path, bad):
    policy = _policy(tmp_path, ("L4",))
    policy["version"] = bad
    with pytest.raises(ValueError):
        _api().validate_policy(policy, tmp_path)


def test_malformed_classification_level_fails_with_a_policy_error(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    policy["units"]["app/unit0.py"]["level"] = []
    with pytest.raises(ValueError):
        _api().validate_policy(policy, tmp_path)


@pytest.mark.parametrize("path", ["/tmp", "../app", "app/../app", "app//sub", "app\\sub", ""])
def test_policy_roots_cannot_escape_or_alias_paths(tmp_path, path):
    policy = _policy(tmp_path, ("L4",))
    policy["roots"] = [path]
    with pytest.raises(ValueError):
        _api().validate_policy(policy, tmp_path)


def test_symlink_sources_cannot_substitute_an_external_file(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    (tmp_path / "outside.py").write_text("def changed():\n    return False\n")
    path = tmp_path / "app/unit0.py"
    path.unlink()
    path.symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError, match="aliases"):
        _api().validate_policy(policy, tmp_path)


@pytest.mark.parametrize(
    "defect",
    [
        "missing_root",
        "duplicate_root",
        "empty_units",
        "missing_units",
        "non_mapping",
        "bad_roots",
        "bad_unit",
        "bad_reason",
    ],
)
def test_policy_structure_is_validated_before_execution(tmp_path, defect):
    policy = _policy(tmp_path, ("L4",))
    if defect == "missing_root":
        policy["roots"] = ["missing"]
    elif defect == "duplicate_root":
        policy["roots"] *= 2
    elif defect == "empty_units":
        policy["units"] = {}
    elif defect == "missing_units":
        policy.pop("units")
    elif defect == "non_mapping":
        policy = []
    elif defect == "bad_roots":
        policy["roots"] = [1]
    elif defect == "bad_unit":
        policy["units"]["app/unit0.py"] = []
    else:
        policy["units"]["app/unit0.py"]["reason"] = False
    with pytest.raises(ValueError):
        _api().validate_policy(policy, tmp_path)


def test_technical_no_mutant_declarations_are_explicit_and_cannot_hide_functions(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    unit = policy["units"]["app/unit0.py"]
    unit["no_mutants"] = " "
    with pytest.raises(ValueError, match="reason"):
        _api().validate_policy(policy, tmp_path)
    unit["no_mutants"] = "No functions for the tool to mutate"
    with pytest.raises(ValueError, match="contains functions"):
        _api().validate_policy(policy, tmp_path)
    (tmp_path / "app/unit0.py").write_text("VERSION = 1\n")
    result = _api().evaluate(policy, tmp_path, {}, [])
    assert result["status"] == "INCOMPLETE"
    assert result["modules"]["app/unit0.py"]["status"] == "NO_MUTANTS_TECHNICAL"
    assert result["modules"]["app/unit0.py"]["exclusions"] == [unit["no_mutants"]]
    with pytest.raises(ValueError, match="excluded"):
        _api().evaluate(policy, tmp_path, {"app/unit0.py": ["app.unit0.x_f__mutmut_1"]}, [])


@pytest.mark.parametrize(
    "key",
    [
        "other.unit.x_f__mutmut_1",
        "app.unit0.x_f",
        "app.unit0.x_f__mutmut_0",
        "app.unit0.x_f__mutmut_x",
        "app.unit0.x-foo__mutmut_1",
        "app.unit0.extra.x_f__mutmut_1",
    ],
)
def test_catalog_identities_must_belong_to_the_declared_module(tmp_path, key):
    policy = _policy(tmp_path, ("L4",))
    with pytest.raises(ValueError):
        _api().evaluate(policy, tmp_path, {"app/unit0.py": [key]}, [])


@pytest.mark.parametrize(
    "defect",
    [
        "catalog_type",
        "records_type",
        "unclassified",
        "keys_type",
        "duplicate_key",
        "record_type",
        "record_fields",
    ],
)
def test_catalog_and_record_shapes_fail_closed(tmp_path, defect):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(1, 1)])
    if defect == "catalog_type":
        catalog = []
    elif defect == "records_type":
        records = {}
    elif defect == "unclassified":
        catalog["app/unknown.py"] = []
    elif defect == "keys_type":
        catalog["app/unit0.py"] = "wrong"
    elif defect == "duplicate_key":
        catalog["app/unit0.py"] *= 2
    elif defect == "record_type":
        records = [None]
    else:
        records[0]["count"] = 1
    with pytest.raises(ValueError):
        _api().evaluate(policy, tmp_path, catalog, records)


def test_src_layout_and_package_marker_identities_are_supported(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    path = tmp_path / "src/app/__init__.py"
    path.parent.mkdir(parents=True)
    path.write_text("def compute(value):\n    return value\n")
    (tmp_path / "app/unit0.py").unlink()
    policy["roots"] = ["src/app"]
    policy["units"] = {"src/app/__init__.py": {"level": "L4", "reason": "Package function"}}
    key = "app.x_compute__mutmut_1"
    result = _api().evaluate(
        policy,
        tmp_path,
        {"src/app/__init__.py": [key]},
        [{"id": key, "path": "src/app/__init__.py", "outcome": "killed"}],
    )
    assert result["status"] == "PASS"


def test_known_failure_is_preserved_when_another_module_is_incomplete(tmp_path):
    policy = _policy(tmp_path, ("L4", "L4"))
    catalog, records = _campaign(policy, [(1, 2), (0, 0)])
    result = _api().evaluate(policy, tmp_path, catalog, records)
    assert result["status"] == "FAIL"
    assert result["modules"]["app/unit1.py"]["status"] == "INCOMPLETE"


def test_fractional_score_is_not_rounded_across_a_critical_boundary(tmp_path):
    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(97, 99)])
    result = _api().evaluate(policy, tmp_path, catalog, records)
    assert result["status"] == "FAIL"
    assert result["modules"]["app/unit0.py"]["score"] == pytest.approx(97.97979797979798)


def test_report_metadata_and_all_outcome_counts_remain_auditable(tmp_path):
    import hashlib

    policy = _policy(tmp_path, ("L4",))
    catalog, records = _campaign(policy, [(2, 3)])
    result = _api().evaluate(policy, tmp_path, catalog, records)
    assert result["policy_version"] == 2
    assert result["policy_sha256"] == _api().policy_digest(policy)
    assert result["sources"] == {
        "app/unit0.py": hashlib.sha256(b"def compute(value):\n    return value + 1\n").hexdigest()
    }
    module = result["modules"]["app/unit0.py"]
    assert module == {
        "level": "L4",
        "reason": "Constructed L4 acceptance scope",
        "eligible": 3,
        "killed": 2,
        "survived": 1,
        "timeout": 0,
        "suspicious": 0,
        "error": 0,
        "caught by type check": 0,
        "not checked": 0,
        "no tests": 0,
        "skipped": 0,
        "segfault": 0,
        "check was interrupted by user": 0,
        "threshold": 98,
        "score": pytest.approx(66.66666666666667),
        "status": "FAIL",
        "exclusions": [],
    }
    assert result["levels"]["L4"] == {
        key: value for key, value in module.items() if key not in {"level", "reason"}
    }
    assert result["total"] == {
        key: value for key, value in module.items() if key not in {"level", "reason", "threshold"}
    }


def test_policy_digest_is_canonical_and_rejects_nonfinite_values():
    import hashlib

    expected = hashlib.sha256(b'{"a":2,"b":1}').hexdigest()
    assert _api().policy_digest({"b": 1, "a": 2}) == expected
    assert _api().policy_digest({"a": 2, "b": 1}) == expected
    with pytest.raises(ValueError):
        _api().policy_digest({"value": float("nan")})


@pytest.mark.parametrize("path", ["app/", "app/./", "app/../app"])
def test_noncanonical_roots_are_diagnosed_before_discovery(tmp_path, path):
    policy = _policy(tmp_path, ("L4",))
    policy["roots"] = [path]
    with pytest.raises(ValueError, match="canonical relative"):
        _api().validate_policy(policy, tmp_path)
