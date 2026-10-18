"""Timing methodology has its own fingerprint, apart from the scientific one."""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
import provenance  # noqa: E402

from verification import lineage  # noqa: E402

PIPELINE = (
    "import time\n\n"
    "class DetectionResult:\n    fit_s = 1\n\n"
    "def _features():\n    return 1\n\n"
    "def detect():\n    return time.perf_counter()\n"
)


def _files(changes=None):
    files = {
        "src/etl_benchmark/pipeline.py": PIPELINE.encode(),
        "src/etl_benchmark/metrics.py": b"m = 1\n",
        "verification/scaling.py": b"s = 1\n",
        "verification/release.py": b"gate = 1\n",
        "experiments/run_benchmark.py": b"b = 1\n",
        "environment.yml": b"name: e\n",
        "pyproject.toml": b'[project]\nname = "p"\n',
    }
    files.update(changes or {})
    return files


def _m(changes=None):
    return provenance.measurement_fingerprint_of(_files(changes))


def _s(changes=None):
    return provenance.scientific_fingerprint_of(_files(changes))


def test_a_scaling_methodology_change_moves_only_the_measurement_fingerprint():
    changes = {"verification/scaling.py": b"s = 2\n"}
    assert _m(changes) != _m()
    assert _s(changes) == _s()


def test_the_timing_code_of_the_pipeline_is_part_of_the_measurement_method():
    changes = {
        "src/etl_benchmark/pipeline.py": PIPELINE.replace("perf_counter", "process_time").encode()
    }
    assert _m(changes) != _m()


def test_other_pipeline_code_and_unrelated_files_do_not_move_the_measurement_fingerprint():
    other = PIPELINE.replace("return 1\n\ndef detect", "return 2\n\ndef detect").encode()
    assert _m({"src/etl_benchmark/pipeline.py": other}) == _m()
    assert _m({"src/etl_benchmark/metrics.py": b"m = 2\n"}) == _m()
    assert _m({"experiments/run_benchmark.py": b"b = 2\n"}) == _m()
    assert _m({"verification/release.py": b"gate = 2\n"}) == _m()


def test_a_verification_gate_change_moves_neither_fingerprint():
    changes = {"verification/release.py": b"gate = 2\n"}
    assert (_m(changes), _s(changes)) == (_m(), _s())


def test_a_registered_new_measurement_script_is_part_of_the_fingerprint(monkeypatch):
    new = {"verification/new_timing.py": b"t = 1\n"}
    assert _m(new) == _m()
    monkeypatch.setattr(
        provenance,
        "MEASUREMENT_FILES",
        (*provenance.MEASUREMENT_FILES, "verification/new_timing.py"),
    )
    assert _m(new) != _m()
    assert _m({"verification/new_timing.py": b"t = 2\n"}) != _m(new)


def test_the_recipe_number_is_part_of_the_hash(monkeypatch):
    before = _m()
    monkeypatch.setattr(provenance, "MEASUREMENT_RECIPE", 99)
    assert _m() != before


def test_every_timing_primitive_in_the_repository_is_registered():
    """A new script that measures time must be added to the fingerprint on purpose."""
    registered = set(provenance.MEASUREMENT_FILES) | set(provenance.MEASUREMENT_FUNCTIONS)
    pattern = re.compile(r"perf_counter|process_time|tracemalloc|timeit")
    found = set()
    for base in ("src", "experiments", "verification"):
        for path in (ROOT / base).rglob("*.py"):
            if "__pycache__" not in path.parts and pattern.search(path.read_text()):
                found.add(str(path.relative_to(ROOT)))
    unregistered = sorted(found - registered - set(provenance.TIMING_NOT_MEASUREMENT))
    assert not unregistered, f"register these measurement scripts: {unregistered}"
    assert all(reason.strip() for reason in provenance.TIMING_NOT_MEASUREMENT.values())


def test_the_working_tree_fingerprint_matches_the_file_based_one():
    assert provenance.measurement_fingerprint() == provenance.measurement_fingerprint_of(
        lineage.worktree_files()
    )


def test_new_run_records_carry_the_measurement_fingerprint(tmp_path, monkeypatch):
    path = provenance.write_record(
        tmp_path / "r.json",
        experiment="e",
        seeds=[1],
        dataset="d",
        data_path=None,
        settings={},
        outputs=[],
    )
    record = json.loads(path.read_text())
    assert record["measurement_recipe"] == provenance.MEASUREMENT_RECIPE
    assert record["measurement_fingerprint"] == provenance.measurement_fingerprint()


# --- lineage of performance evidence ---


def test_a_record_bound_to_the_current_method_is_bound():
    current = _files()
    record = {
        "measurement_recipe": provenance.MEASUREMENT_RECIPE,
        "measurement_fingerprint": provenance.measurement_fingerprint_of(current),
    }
    assert lineage.check_measurement(record, current) == ("BOUND", [])


def test_a_record_bound_to_another_method_is_stale_with_a_reason():
    record = {
        "measurement_recipe": provenance.MEASUREMENT_RECIPE,
        "measurement_fingerprint": _m(),
    }
    state, reasons = lineage.check_measurement(record, _files({"verification/scaling.py": b"x\n"}))
    assert state == "STALE" and "measurement method changed" in reasons[0]


def test_a_record_without_a_measurement_fingerprint_is_legacy_and_untouched():
    assert lineage.check_measurement({"source_revision": "a" * 40}, _files()) == ("LEGACY", [])


def test_an_unknown_measurement_recipe_is_stale():
    record = {"measurement_recipe": 99, "measurement_fingerprint": _m()}
    state, reasons = lineage.check_measurement(record, _files())
    assert state == "STALE" and "recipe" in reasons[0]


@pytest.mark.parametrize("value", [None, "", 3])
def test_a_malformed_measurement_fingerprint_is_stale(value):
    record = {"measurement_recipe": provenance.MEASUREMENT_RECIPE, "measurement_fingerprint": value}
    assert lineage.check_measurement(record, _files())[0] == "STALE"


def test_the_archived_scaling_record_is_legacy_and_was_not_restamped():
    record = json.loads((ROOT / "verification/evidence/scaling.json").read_text())
    assert "measurement_fingerprint" not in record
    assert lineage.check_measurement(record, lineage.worktree_files())[0] == "LEGACY"


def test_the_segments_are_joined_by_one_newline_in_source_order():
    source = b"def a():\n    return 1\n\nx = 3\n\nclass B:\n    pass\n"
    assert provenance._segments(source, ("B", "a")) == b"def a():\n    return 1\nclass B:\n    pass"


def test_a_missing_measurement_file_does_not_stop_the_hash_of_the_others():
    without_pipeline = {
        "verification/scaling.py": b"s = 1\n",
        "pyproject.toml": b'[project]\nname = "p"\n',
    }
    changed = {**without_pipeline, "verification/scaling.py": b"s = 2\n"}
    assert provenance.measurement_fingerprint_of(changed) != provenance.measurement_fingerprint_of(
        without_pipeline
    )
