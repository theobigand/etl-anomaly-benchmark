"""The single-shard diagnostic and the command line state their exact contract.

Each refusal names its precise reason, git is run strictly, the proof is re-validated with the
runtime and scope it recorded, the case-sensitivity probe is a real probe, the report carries
exactly its documented fields, and the required command line arguments stay required.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.test_shard_execution_binding import MODULE, _build, _diagnostic_setup, _setup
from verification import mutation_cache, mutation_policy
from verification import mutation_shards as shards


@pytest.fixture(autouse=True)
def _tool_versions(monkeypatch):
    versions = {"mutmut": "3.8.0", "pytest": "9.1.1"}
    monkeypatch.setattr(shards, "version", lambda name: versions.get(name))


def _refusal(*args):
    with pytest.raises(ValueError) as caught:
        shards.diagnostic_equivalences(*args)
    return str(caught.value)


def test_every_diagnostic_refusal_states_its_exact_reason(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    foreign = copy.deepcopy(policy)
    foreign["units"][MODULE]["reason"] = "foreign"
    given = (document, foreign, tmp_path, 0, attempt, equivalence)
    assert _refusal(*given) == "diagnostic policy differs from the checked-out policy"
    given = (document, policy, tmp_path, 0, attempt, None)
    assert _refusal(*given) == "diagnostic requires an equivalence document"
    other = copy.deepcopy(equivalence)
    other["owner"] = "different"
    given = (document, policy, tmp_path, 0, attempt, other)
    assert _refusal(*given) == "diagnostic differs from the checked-out equivalence document"
    (tmp_path / "tests/untracked.py").write_text("untracked input")
    given = (document, policy, tmp_path, 0, attempt, equivalence)
    assert _refusal(*given) == "diagnostic has untracked test inputs"
    (tmp_path / "tests/untracked.py").unlink()
    (tmp_path / "tests/test_a.py").write_text("changed since execution")
    assert _refusal(*given) == "diagnostic tracked files changed from the tested commit"


def test_an_incomplete_shard_and_a_foreign_attempt_state_their_exact_reason(tmp_path):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    given = (document, policy, tmp_path, 0, attempt, equivalence)
    record = json.loads(attempt.read_text())
    record["proof"]["settled"] += 1
    record["proof"]["sha256"] = mutation_cache._digest(
        {key: value for key, value in record["proof"].items() if key != "sha256"}
    )
    attempt.write_text(json.dumps(record))
    assert _refusal(*given) == "diagnostic attempt differs from the current execution proof"
    (tmp_path / "mutants" / f"{MODULE}.meta").unlink()
    assert _refusal(*given) == "diagnostic shard has incomplete mutant outcomes"


def _spy_runs(monkeypatch):
    calls = []
    real = subprocess.run

    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(shards.subprocess, "run", run)
    return calls


def test_the_diagnostic_runs_git_strictly_on_the_checked_out_tree(tmp_path, monkeypatch):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    calls = _spy_runs(monkeypatch)
    shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)
    wanted = {
        "status": ["git", "status", "--porcelain", "--untracked-files=no"],
        "untracked": [
            "git", "ls-files", "--others", "--exclude-standard", "--",
            "conftest.py", "tests", "research/tests",
        ],
    }  # fmt: skip
    for argv in wanted.values():
        found = [kwargs for args, kwargs in calls if list(args[0]) == argv]
        assert len(found) == 1
        assert found[0]["cwd"] == tmp_path
        assert found[0]["check"] is True
        assert found[0]["capture_output"] is True
        assert found[0]["text"] is True


def test_the_recorded_proof_is_revalidated_with_its_own_runtime_and_scope(tmp_path, monkeypatch):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    context = json.loads(attempt.read_text())["proof"]["context"]
    seen = []
    real = mutation_cache.validate_execution

    def spy(*args, **kwargs):
        seen.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(shards.mutation_cache, "validate_execution", spy)
    shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)
    assert len(seen) == 1
    args, kwargs = seen[0]
    assert args == (tmp_path, sorted(context["sources"]))
    assert kwargs == {"runtime": context["runtime"], "mutated_sources": context["mutation_scope"]}


def test_the_case_probe_is_a_real_probe_in_a_scratch_directory_under_the_root(
    tmp_path, monkeypatch
):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    created, writes, lookups = [], [], []
    real_directory, real_write, real_exists = (
        tempfile.TemporaryDirectory,
        Path.write_text,
        Path.exists,
    )

    def directory(*args, **kwargs):
        created.append((args, kwargs))
        return real_directory(*args, **kwargs)

    def write(self, data, *args, **kwargs):
        writes.append((self.name, data))
        return real_write(self, data, *args, **kwargs)

    def exists(self, *args, **kwargs):
        lookups.append(self.name)
        return real_exists(self, *args, **kwargs)

    monkeypatch.setattr(shards.tempfile, "TemporaryDirectory", directory)
    monkeypatch.setattr(Path, "write_text", write)
    monkeypatch.setattr(Path, "exists", exists)
    shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)
    assert created == [((), {"prefix": ".mutation-case-", "dir": tmp_path})]
    assert [item for item in writes if item[0].lower() == "caseprobe"] == [("CaseProbe", "probe")]
    assert lookups.count("caseprobe") == 1
    assert "CASEPROBE" not in lookups


def test_a_case_insensitive_filesystem_is_reported_as_such(tmp_path, monkeypatch):
    policy, document, attempt, equivalence, _ = _diagnostic_setup(tmp_path)
    real_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: self.name == "caseprobe" or real_exists(self))
    result = shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)
    assert result["filesystem_case_sensitive"] is False


def test_the_diagnostic_report_carries_exactly_its_documented_fields(tmp_path):
    policy, document, attempt, equivalence, survivor = _diagnostic_setup(tmp_path)
    manifest = _build(tmp_path, policy, document, attempt)
    result = shards.diagnostic_equivalences(document, policy, tmp_path, 0, attempt, equivalence)
    assert set(result) == {
        "scope", "filesystem_case_sensitive", "limitations", "plan_sha256", "context",
        "sources", "execution", "catalog", "records", "catalog_sha256", "policy_file_sha256",
        "validator_sha256", "accepted", "modules",
    }  # fmt: skip
    assert result["limitations"] == [
        "Execution test bindings cover Python tests and specified configuration, not every "
        "non-Python or external input.",
        "The native proof has no revision field; commit attribution relies on a fresh "
        "single-job workflow and its before/after HEAD checks.",
    ]
    assert result["plan_sha256"] == document["sha256"]
    assert result["context"] == shards.current_context(tmp_path)
    assert result["sources"] == manifest["sources"]
    assert result["execution"] == manifest["execution"]
    assert result["catalog"] == manifest["catalog"]
    assert result["records"] == manifest["records"]
    assert result["catalog_sha256"] == {
        MODULE: mutation_policy.catalog_digest(manifest["catalog"][MODULE])
    }
    policy_file = tmp_path / "verification/mutation_risk_policy.json"
    assert result["policy_file_sha256"] == hashlib.sha256(policy_file.read_bytes()).hexdigest()
    validator = Path(mutation_policy.__file__).read_bytes()
    assert result["validator_sha256"] == hashlib.sha256(validator).hexdigest()
    assert result["accepted"] == {MODULE: [survivor]}
    assert set(result["modules"]) == {MODULE}


def test_the_aggregation_compares_the_execution_proof_of_every_shard(tmp_path, monkeypatch):
    policy, document, attempt = _setup(tmp_path)
    manifest = _build(tmp_path, policy, document, attempt)
    seen = []
    real = shards._check_common_suite
    monkeypatch.setattr(shards, "_check_common_suite", lambda ex: (seen.append(ex), real(ex))[1])
    shards.aggregate(document, [manifest], policy, tmp_path, shards.current_context(tmp_path))
    assert seen == [[manifest["execution"]]]


def test_the_diagnostic_command_defaults_to_the_current_directory(tmp_path, monkeypatch):
    _, _, attempt, _, survivor = _diagnostic_setup(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert shards.main([
        "diagnostic-equivalences", "--plan", "plan.json", "--index", "0",
        "--attempt", str(attempt), "--output", "diagnostic.json",
    ]) == 0  # fmt: skip
    assert json.loads((tmp_path / "diagnostic.json").read_text())["accepted"] == {
        MODULE: [survivor]
    }


def test_a_command_is_required(capsys):
    with pytest.raises(SystemExit) as caught:
        shards.main([])
    assert caught.value.code == 2
    assert "required: command" in capsys.readouterr().err


_DIAGNOSTIC_INDEX = {"--plan": "p.json", "--policy": "q.json", "--module": "m.py"}
_DIAGNOSTIC_VALIDATE = {
    "--plan": "p.json", "--index": "0", "--attempt": "a.json", "--output": "o.json",
}  # fmt: skip


def _without(command, options, name):
    return [command] + [
        part for key, value in options.items() if key != name for part in (key, value)
    ]


@pytest.mark.parametrize(
    ("command", "options", "name"),
    [("diagnostic-index", _DIAGNOSTIC_INDEX, name) for name in _DIAGNOSTIC_INDEX]
    + [("diagnostic-equivalences", _DIAGNOSTIC_VALIDATE, name) for name in _DIAGNOSTIC_VALIDATE],
)
def test_each_diagnostic_argument_stays_required(command, options, name, capsys):
    with pytest.raises(SystemExit) as caught:
        shards.main(_without(command, options, name))
    assert caught.value.code == 2
    assert name in capsys.readouterr().err


def test_the_build_help_describes_the_attempt_binding(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    with pytest.raises(SystemExit) as caught:
        shards.main(["build", "--help"])
    assert caught.value.code == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "--attempt ATTEMPT controller attempt record binding the execution" in text
