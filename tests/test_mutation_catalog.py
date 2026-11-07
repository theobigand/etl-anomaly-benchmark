"""Native generation indexes constrain the mutation denominator independently."""

import importlib
import json

import pytest


def _api():
    return importlib.import_module("verification.mutation_catalog")


def _fixture(tmp_path, code=1, *, native="killed", bucket="killed"):
    source = tmp_path / "app/a.py"
    source.parent.mkdir()
    source.write_text("def compute(value):\n    return value + 1\n")
    policy = {
        "version": 2,
        "thresholds": {"L1": 80, "L2": 90, "L3": 95, "L4": 98},
        "roots": ["app"],
        "units": {"app/a.py": {"level": "L4", "reason": "Constructed critical scope"}},
    }
    cache = tmp_path / "cache"
    folder = cache / "app"
    folder.mkdir(parents=True)
    key = "app.a.x_compute__mutmut_1"
    meta = {
        "exit_code_by_key": {key: code},
        "hash_by_function_name": {"x_compute": "5d6e4cd023bc"},
        "type_check_error_by_key": {},
        "durations_by_key": {},
        "estimated_durations_by_key": {},
    }
    (folder / "a.py.meta").write_text(json.dumps(meta))
    (folder / "a.py.spans").write_text(
        json.dumps(
            {
                "version": 1,
                "spans": {
                    "x_compute__mutmut_orig": [1, 2],
                    "x_compute__mutmut_1": [3, 4],
                },
            }
        )
    )
    stats = {
        name: 0
        for name in [
            "killed",
            "survived",
            "no_tests",
            "skipped",
            "suspicious",
            "timeout",
            "check_was_interrupted_by_user",
            "segfault",
        ]
    }
    stats["total"] = 1
    if bucket:
        stats[bucket] = 1
    listing = f"    {key}: {native}\n"
    return policy, cache, stats, listing


@pytest.mark.parametrize(
    "code,native,bucket,outcome",
    [
        (1, "killed", "killed", "killed"),
        (3, "killed", "killed", "error"),
        (0, "survived", "survived", "survived"),
        (
            2,
            "check was interrupted by user",
            "check_was_interrupted_by_user",
            "check was interrupted by user",
        ),
        (5, "no tests", "no_tests", "no tests"),
        (33, "no tests", "no_tests", "no tests"),
        (34, "skipped", "skipped", "skipped"),
        (35, "suspicious", "suspicious", "suspicious"),
        (36, "timeout", "timeout", "timeout"),
        (-24, "timeout", "timeout", "timeout"),
        (24, "timeout", "timeout", "timeout"),
        (152, "timeout", "timeout", "timeout"),
        (255, "timeout", "timeout", "timeout"),
        (-11, "segfault", "segfault", "segfault"),
        (-9, "segfault", "segfault", "segfault"),
        (37, "caught by type check", None, "caught by type check"),
        (None, "not checked", None, "not checked"),
        (-10, "suspicious", "suspicious", "error"),
    ],
)
def test_native_outcomes_remain_distinct_and_errors_are_not_kills(
    tmp_path, code, native, bucket, outcome
):
    policy, cache, stats, listing = _fixture(tmp_path, code, native=native, bucket=bucket)
    report = _api().read_native(policy, tmp_path, cache, stats, listing)
    assert report["records"] == [
        {"id": "app.a.x_compute__mutmut_1", "path": "app/a.py", "outcome": outcome}
    ]
    assert report["catalog"] == {"app/a.py": ["app.a.x_compute__mutmut_1"]}
    assert report["native_stats"] == stats
    assert report["missing"] == []
    assert report["execution_provenance_verified"] is False


def test_deleting_a_verdict_and_adjusting_counts_cannot_shrink_the_catalog(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    path = cache / "app/a.py.meta"
    data = json.loads(path.read_text())
    data["exit_code_by_key"] = {}
    path.write_text(json.dumps(data))
    stats = {name: 0 for name in stats}
    with pytest.raises(ValueError, match="generation index"):
        _api().read_native(policy, tmp_path, cache, stats, "")


@pytest.mark.parametrize(
    "defect",
    [
        "count",
        "bool",
        "float",
        "negative",
        "missing_count",
        "extra_count",
        "wrong_listing",
        "missing_listing",
        "duplicate_listing",
        "header",
    ],
)
def test_native_stats_and_full_listing_must_reconcile_with_metadata(tmp_path, defect):
    policy, cache, stats, listing = _fixture(tmp_path)
    if defect == "count":
        stats["total"] = 2
    elif defect == "bool":
        stats["total"] = True
    elif defect == "float":
        stats["total"] = 1.0
    elif defect == "negative":
        stats["killed"] = -1
    elif defect == "missing_count":
        stats.pop("timeout")
    elif defect == "extra_count":
        stats["extra"] = 1
    elif defect == "wrong_listing":
        listing = listing.replace("killed", "survived")
    elif defect == "missing_listing":
        listing = ""
    elif defect == "duplicate_listing":
        listing *= 2
    else:
        listing = "campaign looks good\n" + listing
    with pytest.raises(ValueError):
        _api().read_native(policy, tmp_path, cache, stats, listing)


def test_missing_active_metadata_remains_explicitly_incomplete(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    (cache / "app/a.py.meta").unlink()
    report = _api().read_native(policy, tmp_path, cache, {name: 0 for name in stats}, "")
    assert report["missing"] == ["app/a.py"]
    assert report["catalog"] == {"app/a.py": []} and report["records"] == []


@pytest.mark.parametrize(
    "defect",
    [
        "missing_index",
        "wrong_version",
        "malformed_index",
        "duplicate_json",
        "invalid_exit",
        "non_mapping",
        "missing_function_hash",
    ],
)
def test_malformed_or_unbound_native_catalogs_fail_closed(tmp_path, defect):
    policy, cache, stats, listing = _fixture(tmp_path)
    meta, spans = cache / "app/a.py.meta", cache / "app/a.py.spans"
    if defect == "missing_index":
        spans.unlink()
    elif defect == "wrong_version":
        data = json.loads(spans.read_text())
        data["version"] = 2
        spans.write_text(json.dumps(data))
    elif defect == "malformed_index":
        spans.write_text("[]")
    elif defect == "duplicate_json":
        meta.write_text('{"exit_code_by_key":{},' + meta.read_text()[1:])
    elif defect == "invalid_exit":
        data = json.loads(meta.read_text())
        data["exit_code_by_key"]["app.a.x_compute__mutmut_1"] = True
        meta.write_text(json.dumps(data))
    elif defect == "non_mapping":
        meta.write_text("[]")
    else:
        data = json.loads(meta.read_text())
        data["hash_by_function_name"] = {}
        meta.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        _api().read_native(policy, tmp_path, cache, stats, listing)


def test_metadata_symlinks_cannot_read_outside_the_cache(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    meta = cache / "app/a.py.meta"
    outside = tmp_path / "outside.json"
    meta.rename(outside)
    meta.symlink_to(outside)
    with pytest.raises(ValueError):
        _api().read_native(policy, tmp_path, cache, stats, listing)


@pytest.mark.parametrize("span", [[], [0, 2], [True, 2], [3, 2], "lines"])
def test_generation_ranges_are_strict_positive_ordered_integer_pairs(tmp_path, span):
    policy, cache, stats, listing = _fixture(tmp_path)
    path = cache / "app/a.py.spans"
    data = json.loads(path.read_text())
    data["spans"]["x_compute__mutmut_1"] = span
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="span"):
        _api().read_native(policy, tmp_path, cache, stats, listing)


@pytest.mark.parametrize(
    "defect",
    [
        "missing_spans",
        "unknown_identity",
        "missing_field",
        "extra_field",
        "non_mapping_field",
        "invalid_hash",
        "non_mapping_stats",
        "non_text_listing",
    ],
)
def test_catalog_structure_does_not_have_implicit_fallbacks(tmp_path, defect):
    policy, cache, stats, listing = _fixture(tmp_path)
    meta, spans = cache / "app/a.py.meta", cache / "app/a.py.spans"
    if defect == "missing_spans":
        spans.write_text('{"version":1}')
    elif defect == "unknown_identity":
        spans.write_text('{"version":1,"spans":{"not_a_mutant":[1,2]}}')
    elif defect in {"missing_field", "extra_field", "non_mapping_field", "invalid_hash"}:
        data = json.loads(meta.read_text())
        if defect == "missing_field":
            data.pop("durations_by_key")
        elif defect == "extra_field":
            data["new_format"] = {}
        elif defect == "non_mapping_field":
            data["durations_by_key"] = []
        else:
            data["hash_by_function_name"]["x_compute"] = False
        meta.write_text(json.dumps(data))
    elif defect == "non_mapping_stats":
        stats = []
    else:
        listing = None
    with pytest.raises(ValueError):
        _api().read_native(policy, tmp_path, cache, stats, listing)


def test_empty_lines_do_not_change_native_result_identity(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    report = _api().read_native(policy, tmp_path, cache, stats, "\n\n" + listing + "\n")
    assert len(report["records"]) == 1


def test_technical_empty_modules_do_not_require_fake_metadata(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    (tmp_path / "app/a.py").write_text("VERSION = 1\n")
    policy["units"]["app/a.py"]["no_mutants"] = "Only a version constant"
    with pytest.raises(ValueError, match="received mutants"):
        _api().read_native(policy, tmp_path, cache, stats, listing)
    (cache / "app/a.py.meta").unlink()
    result = _api().read_native(policy, tmp_path, cache, {name: 0 for name in stats}, "")
    assert result["missing"] == [] and result["records"] == []


def test_changed_function_bodies_cannot_reuse_old_generation_hashes(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    (tmp_path / "app/a.py").write_text("def compute(value):\n    return value + 2\n")
    with pytest.raises(ValueError, match="source"):
        _api().read_native(policy, tmp_path, cache, stats, listing)


def test_forged_function_names_cannot_be_bound_by_a_plausible_hash(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    meta, spans = cache / "app/a.py.meta", cache / "app/a.py.spans"
    meta.write_text(meta.read_text().replace("x_compute", "x_forged"))
    spans.write_text(spans.read_text().replace("x_compute", "x_forged"))
    with pytest.raises(ValueError, match="source"):
        _api().read_native(policy, tmp_path, cache, stats, listing.replace("x_compute", "x_forged"))


@pytest.mark.parametrize(
    "source,local,fingerprint",
    [
        ("async def compute(value):\n    return value + 1\n", "x_compute", "8a7f61e373aa"),
        (
            "class Detector:\n    def compute(self, value):\n        return value + 1\n",
            "xǁDetectorǁcompute",
            "107992b53c91",
        ),
        (
            "class Outer:\n    class Inner:\n        def compute(self, value):\n"
            "            return value + 1\n",
            "xǁOuter.Innerǁcompute",
            "107992b53c91",
        ),
    ],
)
def test_function_fingerprints_match_captured_native_async_and_class_formats(
    tmp_path, source, local, fingerprint
):
    policy, cache, stats, listing = _fixture(tmp_path)
    (tmp_path / "app/a.py").write_text(source)
    path = cache / "app/a.py.meta"
    data = json.loads(path.read_text().replace("x_compute", local))
    data["hash_by_function_name"] = {local: fingerprint}
    path.write_text(json.dumps(data))
    spans = cache / "app/a.py.spans"
    spans.write_text(spans.read_text().replace("x_compute", local))
    result = _api().read_native(policy, tmp_path, cache, stats, listing.replace("x_compute", local))
    assert result["records"][0]["id"] == f"app.a.{local}__mutmut_1"
    assert result["execution_provenance_verified"] is False


def test_function_hashes_do_not_claim_that_module_globals_were_executed(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    source = tmp_path / "app/a.py"
    source.write_text("SCALE = 1\ndef compute(value):\n    return value + SCALE\n")
    path = cache / "app/a.py.meta"
    data = json.loads(path.read_text())
    data["hash_by_function_name"] = {"x_compute": "4b7c760a8d28"}
    path.write_text(json.dumps(data))
    assert (
        _api().read_native(policy, tmp_path, cache, stats, listing)["execution_provenance_verified"]
        is False
    )
    source.write_text(source.read_text().replace("SCALE = 1", "SCALE = 2"))
    assert (
        _api().read_native(policy, tmp_path, cache, stats, listing)["execution_provenance_verified"]
        is False
    )


def test_unparseable_current_source_is_a_catalog_validation_error(tmp_path):
    policy, cache, stats, listing = _fixture(tmp_path)
    (tmp_path / "app/a.py").write_text("def compute(\n")
    with pytest.raises(ValueError, match="source"):
        _api().read_native(policy, tmp_path, cache, stats, listing)
