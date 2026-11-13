"""Each refusal, mapping and reconciliation rule of the native mutation catalog, stated exactly."""

import hashlib
import json

import pytest

from verification import mutation_catalog as mcat
from verification.mutation_policy import THRESHOLDS

SOURCE = "def f(x):\n    return x + 1\n\n\nclass C:\n    def m(self):\n        return 1\n"
HASHES = mcat._function_hashes(SOURCE)


def _refused(call, message):
    with pytest.raises(ValueError) as refused:
        call()
    assert str(refused.value) == message


def test_a_duplicated_field_in_native_json_is_refused_by_name():
    assert mcat._pairs([("a", 1), ("b", 2)]) == {"a": 1, "b": 2}
    _refused(lambda: mcat._pairs([("a", 1), ("a", 2)]), "duplicate native JSON field: a")
    with pytest.raises(ValueError):
        json.loads('{"a": 1, "a": 2}', object_pairs_hook=mcat._pairs)


def test_a_native_file_is_read_inside_the_cache_and_its_hash_is_recorded(tmp_path):
    cache = tmp_path / "c"
    cache.mkdir()
    (cache / "x.json").write_text('{"k": 1}')
    artifacts = {}
    assert mcat._read(cache, "x.json", artifacts) == {"k": 1}
    assert artifacts == {"x.json": hashlib.sha256(b'{"k": 1}').hexdigest()}
    _refused(
        lambda: mcat._read(cache, "gone.json", {}), "native catalog file unavailable: gone.json"
    )
    (cache / "list.json").write_text("[1]")
    _refused(
        lambda: mcat._read(cache, "list.json", {}), "native catalog files must be JSON objects"
    )
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (cache / "link.json").symlink_to(outside)
    _refused(
        lambda: mcat._read(cache, "link.json", {}),
        "native catalog paths must stay inside the cache",
    )
    _refused(
        lambda: mcat._read(cache, "../outside.json", {}),
        "native catalog paths must stay inside the cache",
    )


def _index(spans, version=1):
    return mcat._index({"version": version, "spans": spans}, "pkg/a.py")


def test_the_generation_index_yields_the_mutant_keys_and_skips_the_original():
    spans = {"x_f__mutmut_orig": [1, 3], "x_f__mutmut_1": [1, 3], "x_f__mutmut_12": [4, 4]}
    assert _index(spans) == {"pkg.a.x_f__mutmut_1", "pkg.a.x_f__mutmut_12"}
    assert _index({}) == set()


@pytest.mark.parametrize("version", [2, True, "1", None])
def test_only_version_one_of_the_index_is_supported(version):
    _refused(lambda: _index({}, version=version), "unsupported native generation index version")


def test_the_index_must_record_spans_of_two_positive_ordered_integers():
    _refused(
        lambda: mcat._index({"version": 1}, "pkg/a.py"), "native generation index must record spans"
    )
    _refused(
        lambda: mcat._index({"version": 1, "spans": []}, "pkg/a.py"),
        "native generation index must record spans",
    )
    for span in ("x", [1], [1, 2, 3], [0, 1], [1, 0], [True, 2], [1.0, 2], [5, 4]):
        _refused(lambda s=span: _index({"x_f__mutmut_1": s}), "invalid native source span")
    assert _index({"x_f__mutmut_1": [3, 3]}) == {"pkg.a.x_f__mutmut_1"}


@pytest.mark.parametrize(
    "name", ["x_f", "x_f__mutmut_0", "x_f__mutmut_01", "x_f__mutmut_", "__mutmut_1x"]
)
def test_an_index_identity_must_be_a_function_with_the_original_or_a_positive_number(name):
    _refused(lambda: _index({name: [1, 2]}), "unknown native generation index identity")


def test_an_index_identity_must_also_follow_the_native_function_naming():
    with pytest.raises(ValueError):
        _index({"y_f__mutmut_1": [1, 2]})


def test_the_result_listing_maps_each_key_to_its_outcome_and_refuses_odd_lines():
    assert mcat._listing("a: killed\n\n  b.c: no tests  \n") == {"a": "killed", "b.c": "no tests"}
    assert mcat._listing("") == {}
    for text in ("a killed", "a: killed\na: survived"):
        _refused(lambda t=text: mcat._listing(t), "invalid or duplicated native result listing")
    _refused(lambda: mcat._listing(5), "native result listing must be text")


def test_function_hashes_name_functions_methods_and_nested_classes_and_skip_inner_functions():
    source = (
        "def top():\n    def inner():\n        pass\n\n\nasync def aio():\n    pass\n\n\n"
        "class A:\n    def m(self):\n        pass\n\n"
        "    class B:\n        def n(self):\n            pass\n"
    )
    hashes = mcat._function_hashes(source)
    assert set(hashes) == {"x_top", "x_aio", "xǁAǁm", "xǁA.Bǁn"}
    assert all(len(v) == 12 and set(v) <= set("0123456789abcdef") for v in hashes.values())
    changed = mcat._function_hashes(source.replace("def top", "def top2"))
    assert hashes["x_aio"] == changed["x_aio"] and "x_top2" in changed
    assert mcat._function_hashes("X = 1\n") == {}
    _refused(lambda: mcat._function_hashes("def ("), "current source is not parseable")
    assert (
        mcat._function_hashes(SOURCE)["x_f"]
        != mcat._function_hashes(SOURCE.replace("+ 1", "+ 2"))["x_f"]
    )


def test_the_metadata_digest_binds_verdicts_and_function_hashes_but_not_timings():
    base = {
        "exit_code_by_key": {"k": 1}, "hash_by_function_name": {"f": "a" * 12},
        "durations_by_key": {"k": 1.0}, "estimated_durations_by_key": {},
        "type_check_error_by_key": {},
    }  # fmt: skip
    payload = {"exit_code_by_key": {"k": 1}, "hash_by_function_name": {"f": "a" * 12}}
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert mcat.metadata_digest(base) == expected
    assert mcat.metadata_digest({**base, "durations_by_key": {"k": 9.0}}) == expected
    assert mcat.metadata_digest({**base, "exit_code_by_key": {"k": 0}}) != expected
    with pytest.raises(ValueError):
        mcat.metadata_digest({**base, "exit_code_by_key": {"k": float("nan")}})


def test_each_native_exit_code_maps_to_its_documented_status():
    expected = {
        1: "killed", 3: "killed", 0: "survived", 5: "no tests", 33: "no tests",
        2: "check was interrupted by user", None: "not checked", 34: "skipped", 35: "suspicious",
        36: "timeout", 37: "caught by type check", -24: "timeout", 24: "timeout", 152: "timeout",
        255: "timeout", -11: "segfault", -9: "segfault",
    }  # fmt: skip
    assert dict(mcat.NATIVE_STATUS) == expected
    assert mcat.NATIVE_OUTCOMES == (
        "killed", "survived", "no_tests", "skipped", "suspicious", "timeout",
        "check_was_interrupted_by_user", "segfault",
    )  # fmt: skip
    fields = {
        "exit_code_by_key", "hash_by_function_name", "type_check_error_by_key",
        "durations_by_key", "estimated_durations_by_key",
    }  # fmt: skip
    assert fields == mcat.META_FIELDS


def _project(
    tmp_path, verdicts=None, hashes=None, spans=None, extra=None, source=SOURCE, no_mutants=False
):
    root = tmp_path / "root"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text(source)
    cache = root / "mutants"
    (cache / "pkg").mkdir(parents=True)
    verdicts = (
        {"pkg.a.x_f__mutmut_1": 1, "pkg.a.xǁCǁm__mutmut_1": 0} if verdicts is None else verdicts
    )
    meta = {
        "exit_code_by_key": verdicts,
        "hash_by_function_name": {"x_f": HASHES["x_f"], "xǁCǁm": HASHES["xǁCǁm"]}
        if hashes is None
        else hashes,
        "type_check_error_by_key": {},
        "durations_by_key": {},
        "estimated_durations_by_key": {},
    }
    meta.update(extra or {})
    (cache / "pkg" / "a.py.meta").write_text(json.dumps(meta))
    keys = spans if spans is not None else {k.split(".", 2)[2]: [1, 2] for k in verdicts}
    (cache / "pkg" / "a.py.spans").write_text(json.dumps({"version": 1, "spans": keys}))
    unit = {"level": "L4", "reason": "r", **({"no_mutants": "why"} if no_mutants else {})}
    policy = {
        "version": 2, "thresholds": dict(THRESHOLDS), "roots": ["pkg"], "units": {"pkg/a.py": unit},
    }  # fmt: skip
    return policy, root, cache


def test_a_consistent_cache_gives_the_catalog_records_native_statuses_and_hashes(tmp_path):
    policy, root, cache = _project(tmp_path)
    catalog, records, native, missing, artifacts, metadata = mcat.read_modules(policy, root, cache)
    assert catalog == {"pkg/a.py": ["pkg.a.x_f__mutmut_1", "pkg.a.xǁCǁm__mutmut_1"]}
    assert records == [
        {"id": "pkg.a.x_f__mutmut_1", "path": "pkg/a.py", "outcome": "killed"},
        {"id": "pkg.a.xǁCǁm__mutmut_1", "path": "pkg/a.py", "outcome": "survived"},
    ]
    assert native == {"pkg.a.x_f__mutmut_1": "killed", "pkg.a.xǁCǁm__mutmut_1": "survived"}
    assert missing == [] and set(artifacts) == {"pkg/a.py.meta", "pkg/a.py.spans"}
    assert list(metadata) == ["pkg/a.py.meta"] and len(metadata["pkg/a.py.meta"]) == 64


def test_pytest_internal_errors_and_unknown_codes_are_errors_never_kills_and_null_is_unchecked(
    tmp_path,
):
    verdicts = {
        f"pkg.a.x_f__mutmut_{i}": code for i, code in enumerate([3, 99, None, 37, 36], start=1)
    }
    policy, root, cache = _project(tmp_path, verdicts=verdicts, hashes={"x_f": HASHES["x_f"]})
    _, records, native, _, _, _ = mcat.read_modules(policy, root, cache)
    assert [r["outcome"] for r in records] == [
        "error",
        "error",
        "not checked",
        "caught by type check",
        "timeout",
    ]
    assert list(native.values()) == [
        "killed",
        "suspicious",
        "not checked",
        "caught by type check",
        "timeout",
    ]


def test_a_non_integer_exit_code_is_refused_and_an_absent_module_is_reported_missing(tmp_path):
    policy, root, cache = _project(
        tmp_path, verdicts={"pkg.a.x_f__mutmut_1": "1"}, hashes={"x_f": HASHES["x_f"]}
    )
    _refused(
        lambda: mcat.read_modules(policy, root, cache), "native exit codes must be integers or null"
    )
    policy, root, cache = _project(tmp_path / "again")
    (cache / "pkg" / "a.py.meta").unlink()
    assert mcat.read_modules(policy, root, cache)[3] == ["pkg/a.py"]
    policy["units"]["pkg/a.py"]["no_mutants"] = "why"
    assert mcat.read_modules(policy, root, cache)[3] == []
    only = mcat.read_modules(policy, root, cache, only=set())
    assert only[0] == {}


def test_every_inconsistency_between_index_verdicts_hashes_and_source_is_refused_alone(tmp_path):
    cases = {
        "invalid native metadata structure": dict(extra={"surplus": {}}),
        "verdict population differs from native generation index": dict(
            spans={"x_f__mutmut_1": [1, 2]}
        ),
        "native function hashes do not bind the generated catalog": dict(
            hashes={"x_f": HASHES["x_f"]}
        ),
        "native function hashes differ from current source": dict(
            hashes={"x_f": "0" * 12, "xǁCǁm": HASHES["xǁCǁm"]}
        ),
    }
    for index, (message, arguments) in enumerate(cases.items()):
        policy, root, cache = _project(tmp_path / str(index), **arguments)
        _refused(lambda p=policy, r=root, c=cache: mcat.read_modules(p, r, c), message)
    policy, root, cache = _project(
        tmp_path / "bad-hash", hashes={"x_f": "XYZ", "xǁCǁm": HASHES["xǁCǁm"]}
    )
    _refused(
        lambda: mcat.read_modules(policy, root, cache),
        "native function hashes do not bind the generated catalog",
    )
    policy, root, cache = _project(tmp_path / "nm", no_mutants=True)
    _refused(
        lambda: mcat.read_modules(policy, root, cache), "technical no-mutant scope received mutants"
    )


def _native(policy, root, cache, stats=None, listing=None):
    _, _, native, *_ = mcat.read_modules(policy, root, cache)
    listing = listing if listing is not None else "".join(f"{k}: {v}\n" for k, v in native.items())
    counts = {name: 0 for name in mcat.NATIVE_OUTCOMES}
    counts.update({"killed": 1, "survived": 1})
    stats = stats if stats is not None else {"total": 2, **counts}
    return mcat.read_native(policy, root, cache, stats, listing)


def test_native_statistics_and_listing_must_equal_the_catalog_outcomes(tmp_path):
    policy, root, cache = _project(tmp_path)
    result = _native(policy, root, cache)
    assert set(result) == {
        "catalog", "records", "missing", "native_stats", "artifacts", "metadata_sha256",
        "execution_provenance_verified",
    }  # fmt: skip
    assert result["execution_provenance_verified"] is False and result["missing"] == []
    assert result["native_stats"]["total"] == 2 and result["native_stats"]["killed"] == 1
    base = {"total": 2, **{name: 0 for name in mcat.NATIVE_OUTCOMES}}
    _refused(
        lambda: _native(policy, root, cache, stats={**base, "killed": 2}),
        "native statistics differ from catalog outcomes",
    )
    _refused(
        lambda: _native(policy, root, cache, listing="pkg.a.x_f__mutmut_1: killed\n"),
        "full native listing differs from verdict metadata",
    )
    for bad in (
        "x",
        {**base, "extra": 1},
        {"total": 2},
        {**base, "killed": -1},
        {**base, "killed": True},
    ):
        _refused(
            lambda b=bad: _native(policy, root, cache, stats=b),
            "invalid native mutation statistics",
        )


def test_a_listing_line_is_split_at_its_first_separator_so_an_outcome_may_contain_one():
    assert mcat._listing("a.b: not checked: no tests") == {"a.b": "not checked: no tests"}


def test_the_metadata_digest_does_not_depend_on_the_order_of_the_native_keys():
    one = {
        "exit_code_by_key": {"b": 1, "a": 0},
        "hash_by_function_name": {"y": "b" * 12, "x": "a" * 12},
    }
    other = {
        "exit_code_by_key": {"a": 0, "b": 1},
        "hash_by_function_name": {"x": "a" * 12, "y": "b" * 12},
    }
    assert mcat.metadata_digest(one) == mcat.metadata_digest(other)


def test_an_unselected_or_absent_module_does_not_stop_the_reading_of_the_next_ones(tmp_path):
    policy, root, cache = _project(tmp_path)
    policy["units"]["pkg/0.py"] = {"level": "L4", "reason": "r"}
    only = mcat.read_modules(policy, root, cache, only={"pkg/a.py"})
    assert sorted(only[0]) == ["pkg/a.py"] and len(only[1]) == 2 and only[3] == []
    everything = mcat.read_modules(policy, root, cache)
    assert everything[3] == ["pkg/0.py"]
    assert sorted(everything[0]) == ["pkg/0.py", "pkg/a.py"] and len(everything[1]) == 2
    policy["units"]["pkg/0.py"]["no_mutants"] = "why"
    assert mcat.read_modules(policy, root, cache)[3] == []
    assert len(mcat.read_modules(policy, root, cache)[1]) == 2
