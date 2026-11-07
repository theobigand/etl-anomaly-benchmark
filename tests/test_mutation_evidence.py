"""Current DEEP envelopes must bind risk-scoped reports and their raw evidence."""

import json

from tests.test_mutation_campaign import SOURCE, _fixture, _rewrite_proof
from verification import evidence_schema as evidence
from verification import mutation_cache

SOURCE_ID = {"revision": "a" * 40, "worktree_dirty": False, "scientific_fingerprint": "b" * 64}
EXECUTION = {"ci": False, "run_id": None, "runner_environment": None, "runner_name": None}


def _build(root, inputs):
    proof = json.loads((root / "mutants/execution-context.json").read_text())
    runtime = proof["context"]["runtime"]
    environment = {name: runtime[name] for name in ["python", "platform", "packages"]}
    return evidence.build_deep(
        inputs[0],
        inputs[1],
        run_report=inputs[2],
        root=root,
        source=SOURCE_ID,
        environment=environment,
        execution=EXECUTION,
    )


def test_current_deep_envelope_recomputes_the_risk_result_and_binds_all_raw_files(tmp_path):
    doc = _build(tmp_path, _fixture(tmp_path))
    assert doc["status"] == "PASS"
    assert doc["result"]["format_version"] == 2
    assert doc["result"]["analysis"]["modules"][SOURCE]["threshold"] == 98
    assert len(doc["artifacts"]) == 10
    assert evidence.validate(doc) == []
    assert evidence.validate(doc, root=tmp_path) == []


def test_a_native_internal_error_is_not_a_successful_kill_in_the_envelope(tmp_path):
    inputs = _fixture(tmp_path)
    path = tmp_path / ("mutants/" + SOURCE + ".meta")
    meta = json.loads(path.read_text())
    meta["exit_code_by_key"]["pkg.a.x_compute__mutmut_2"] = 3
    path.write_text(json.dumps(meta))
    _rewrite_proof(
        tmp_path,
        inputs,
        lambda proof: proof["metadata_sha256"].update(
            {SOURCE + ".meta": mutation_cache._metadata_digest(meta)}
        ),
    )
    doc = _build(tmp_path, inputs)
    assert doc["status"] == "INCOMPLETE"
    assert doc["result"]["analysis"]["total"]["killed"] == 1
    assert doc["result"]["analysis"]["total"]["error"] == 1
    doc["status"] = "PASS"
    assert evidence.validate(doc)


def test_missing_current_execution_never_falls_back_to_global_95_percent_counts(tmp_path):
    inputs = _fixture(tmp_path)
    inputs[2].unlink()
    doc = _build(tmp_path, inputs)
    assert doc["status"] == "INCOMPLETE"
    assert doc["result"]["format_version"] == 2 and doc["result"]["reason"]
    assert evidence.validate(doc, root=tmp_path) == []


def test_current_root_rejects_a_consistent_old_snapshot_after_source_changes(tmp_path):
    doc = _build(tmp_path, _fixture(tmp_path))
    (tmp_path / SOURCE).write_text("def compute(value):\n    return value+2\n")
    assert evidence.validate(doc) == [], "snapshot arithmetic is still internally consistent"
    assert evidence.validate(doc, root=tmp_path), "current certification must reject stale source"


def test_envelope_cannot_omit_required_artifact_hashes(tmp_path):
    doc = _build(tmp_path, _fixture(tmp_path))
    del doc["artifacts"]["mutants/" + SOURCE]
    assert evidence.validate(doc, root=tmp_path)


def test_envelope_environment_must_match_the_bound_execution(tmp_path):
    doc = _build(tmp_path, _fixture(tmp_path))
    doc["environment"]["python"] = "0.0.0"
    assert evidence.validate(doc, root=tmp_path)


def test_a_failed_threshold_cannot_be_relabelled_as_a_pass(tmp_path):
    doc = _build(tmp_path, _fixture(tmp_path, survived=True))
    assert doc["status"] == "FAIL"
    doc["status"] = "PASS"
    assert evidence.validate(doc)


def test_new_deep_status_must_distinguish_missing_evidence_from_failure(tmp_path):
    inputs = _fixture(tmp_path)
    inputs[2].unlink()
    doc = _build(tmp_path, inputs)
    doc["status"] = "FAIL"
    assert evidence.validate(doc), "missing evidence is not a confirmed mutation failure"
