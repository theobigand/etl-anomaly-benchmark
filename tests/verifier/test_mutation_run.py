"""Managed execution must finish and freeze inputs before binding native results."""

import copy
import importlib
import json
import os
import signal
import sys
from pathlib import Path

import pytest

SOURCE = "src/pkg/a.py"
RUNTIME = {"python": "3.11.17", "packages": {"mutmut": "3.8.0"}}


def _api():
    return importlib.import_module("verification.mutation_run")


def _repository(root):
    path = root / SOURCE
    path.parent.mkdir(parents=True)
    path.write_text("def compute(value):\n    return value + 1\n")
    (root / "tests").mkdir()
    (root / "tests/test_a.py").write_text("def test_a():\n    assert True\n")
    (root / "verification").mkdir()
    (root / "verification/mutation_risk_policy.json").write_text(
        json.dumps(
            {
                "version": 2,
                "thresholds": {"L1": 80, "L2": 90, "L3": 95, "L4": 98},
                "roots": ["src/pkg"],
                "units": {SOURCE: {"level": "L4", "reason": "Constructed scope"}},
            }
        )
    )
    (root / "pyproject.toml").write_text(
        '[tool.mutmut]\nsource_paths=["src/pkg"]\nonly_mutate=["src/pkg/a.py"]\n'
    )
    return root / "mutants"


def _engine(monkeypatch, root, *, exit_code=0, change_test=False, worker=False):
    api = _api()
    monkeypatch.setattr(api, "collect_runtime", lambda env: copy.deepcopy(RUNTIME))
    metadata = {
        "exit_code_by_key": {"pkg.a.x_compute__mutmut_1": 1},
        "hash_by_function_name": {"x_compute": "5d6e4cd023bc"},
        "type_check_error_by_key": {},
        "durations_by_key": {},
        "estimated_durations_by_key": {},
    }
    script = (
        "from pathlib import Path; import json,sys,subprocess; "
        f"p=Path('mutants/{SOURCE}.meta'); p.parent.mkdir(parents=True,exist_ok=True); "
        f"p.write_text({json.dumps(metadata)!r}); "
        f"p.with_suffix('').write_text(Path({SOURCE!r}).read_text()); "
        "Path(str(p.with_suffix(''))+'.spans').write_text('{}'); "
        "print('constructed native process',flush=True); "
    )
    if change_test:
        script += "Path('tests/test_a.py').write_text('changed during execution'); "
    if worker:
        script += (
            "worker=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']); "
            "Path('constructed-worker-pid').write_text(str(worker.pid)); "
        )
    script += f"sys.exit({exit_code})"
    monkeypatch.setattr(api, "_command", lambda max_children: [sys.executable, "-c", script])
    return api


def test_terminal_execution_binds_actual_native_exit_and_settled_results(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    result = api.run(tmp_path, max_children=2)
    proof = json.loads((cache / "execution-context.json").read_text())
    assert result["native_exit_code"] == proof["native_exit_code"] == 0
    assert proof["settled"] == 1
    assert not (cache / "execution-pending.json").exists()
    assert "constructed native process" in (tmp_path / result["native_log"]).read_text()


def test_nonzero_terminal_execution_remains_explicit(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path, exit_code=2)
    result = api.run(tmp_path, max_children=1)
    assert result["native_exit_code"] == 2
    assert json.loads((cache / "execution-context.json").read_text())["native_exit_code"] == 2


def test_input_changes_during_native_execution_cannot_receive_a_binding(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path, change_test=True)
    with pytest.raises(ValueError, match="inputs changed"):
        api.run(tmp_path)
    assert (cache / "execution-pending.json").exists()
    assert not (cache / "execution-context.json").exists()


def test_a_launch_error_leaves_no_successful_execution_binding(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    monkeypatch.setattr(api, "_command", lambda _: [str(tmp_path / "missing-executable")])
    with pytest.raises(OSError):
        api.run(tmp_path)
    assert (cache / "execution-pending.json").exists()
    assert not (cache / "execution-context.json").exists()


def test_a_terminal_parent_with_live_workers_cannot_bind_results(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path, worker=True)
    try:
        with pytest.raises(ValueError, match="process group"):
            api.run(tmp_path)
        pending = json.loads((cache / "execution-pending.json").read_text())
        os.killpg(pending["native_pid"], 0)
        assert not (cache / "execution-context.json").exists()
    finally:
        marker = tmp_path / "constructed-worker-pid"
        if marker.exists():
            try:
                os.kill(int(marker.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass


def test_observed_runtime_changes_during_execution_reject_binding(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    seen = []

    def collect(env):
        seen.append(env.copy())
        return {**RUNTIME, "observation": len(seen)}

    monkeypatch.setattr(api, "collect_runtime", collect)
    with pytest.raises(ValueError, match="inputs changed"):
        api.run(tmp_path)
    assert len(seen) == 2
    assert all(e["PYTHONPATH"] == "" for e in seen)
    assert all(
        e["OMP_NUM_THREADS"] == e["OPENBLAS_NUM_THREADS"] == e["MKL_NUM_THREADS"] == "1"
        for e in seen
    )
    assert not (cache / "execution-context.json").exists()


def test_scope_mismatch_fails_before_mutation_or_bootstrap_reset(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    (tmp_path / "pyproject.toml").write_text("[tool.mutmut]\nonly_mutate=[]\n")
    with pytest.raises(ValueError, match="scope"):
        api.run(tmp_path)
    assert not cache.exists()


@pytest.mark.parametrize("children", [0, -1, True, 1.5])
def test_invalid_parallelism_is_rejected_before_launch(tmp_path, children):
    _repository(tmp_path)
    with pytest.raises(ValueError, match="children"):
        _api().run(tmp_path, max_children=children)


def test_existing_pending_execution_cannot_be_overwritten(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    cache.mkdir()
    pending = cache / "execution-pending.json"
    pending.write_text('{"unresolved": true}\n')
    with pytest.raises(ValueError, match="pending"):
        api.run(tmp_path)
    assert pending.read_text() == '{"unresolved": true}\n'


def test_concurrent_controllers_cannot_reset_or_run_the_same_cache(tmp_path, monkeypatch):
    import fcntl

    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    cache.mkdir()
    with (cache / "execution.lock").open("a+") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="active controller"):
            api.run(tmp_path)
    assert not (cache / "execution-pending.json").exists()
    assert not list(cache.glob("attempts/*/native.log"))


def test_uninspectable_process_groups_cannot_authorize_binding(monkeypatch):
    def denied(pid, sig):
        raise PermissionError("constructed process inspection failure")

    monkeypatch.setattr(os, "killpg", denied)
    with pytest.raises(ValueError, match="cannot be inspected"):
        _api()._require_terminal_group(123)


def test_source_roots_must_cover_every_configured_file(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    path = tmp_path / "pyproject.toml"
    path.write_text(path.read_text().replace('source_paths=["src/pkg"]', 'source_paths=["tests"]'))
    with pytest.raises(ValueError, match="source roots"):
        api.run(tmp_path)
    assert not cache.exists()


def test_runtime_collects_installed_versions_and_hashes_effective_environment(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    api = _api()
    packages = [
        SimpleNamespace(metadata={"Name": "mutmut"}, version="3.8.0"),
        SimpleNamespace(metadata={"Name": "pytest_cov"}, version="7.1.0"),
        SimpleNamespace(metadata={"Name": "mutmut"}, version="3.8.0"),
    ]
    monkeypatch.setattr(api, "distributions", lambda: packages)
    result = api.collect_runtime({"OMP_NUM_THREADS": "1", "UNRELATED_SECRET": "never record this"})
    assert result["packages"] == {"mutmut": "3.8.0", "pytest-cov": "7.1.0"}
    assert result["environment_sha256"]["OMP_NUM_THREADS"] == hashlib.sha256(b"1").hexdigest()
    assert result["environment_sha256"]["PYTHONPATH"] is None
    assert "UNRELATED_SECRET" not in result["environment_sha256"]
    assert "never record this" not in json.dumps(result)
    assert (
        result["executable_sha256"] == hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
    )
    packages.append(SimpleNamespace(metadata={"Name": "mutmut"}, version="3.9.0"))
    with pytest.raises(ValueError, match="conflicting"):
        api.collect_runtime({})


def test_native_command_uses_the_observed_interpreter_and_bound_parallelism():
    assert _api()._command(3) == [
        sys.executable,
        "-P",
        "-m",
        "mutmut",
        "run",
        "--max-children",
        "3",
    ]


@pytest.mark.parametrize("exit_code,expected", [(0, 0), (2, 1)])
def test_cli_keeps_the_observed_native_status(tmp_path, monkeypatch, capsys, exit_code, expected):
    _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path, exit_code=exit_code)
    assert api.main(["--root", str(tmp_path), "--max-children", "3"]) == expected
    report = json.loads(capsys.readouterr().out)
    assert report["native_exit_code"] == exit_code


def test_command_entrypoint_documents_the_actual_execution_options(monkeypatch, capsys):
    import runpy

    monkeypatch.setattr(sys, "argv", ["mutation_run.py", "--help"])
    with pytest.raises(SystemExit) as outcome:
        runpy.run_path(_api().__file__, run_name="__main__")
    assert outcome.value.code == 0
    help_text = capsys.readouterr().out
    assert "--root" in help_text and "--max-children" in help_text


def test_attempt_logs_and_bindings_are_preserved_across_reuse(tmp_path, monkeypatch):
    _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    first = api.run(tmp_path)
    log = tmp_path / first["native_log"]
    record = tmp_path / first["attempt_record"]
    original = (log.read_bytes(), record.read_bytes())
    second = api.run(tmp_path)
    assert first["native_log"] != second["native_log"]
    assert first["attempt_record"] != second["attempt_record"]
    assert (log.read_bytes(), record.read_bytes()) == original
    assert json.loads(record.read_text())["proof"]["sha256"] == first["proof_sha256"]


def test_new_unclassified_sources_during_execution_cannot_be_bound(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    script = "from pathlib import Path;Path('src/pkg/new.py').write_text('def new(): return 1\\n')"
    monkeypatch.setattr(api, "_command", lambda _: [sys.executable, "-c", script])
    with pytest.raises(ValueError, match="unclassified"):
        api.run(tmp_path)
    assert not (cache / "execution-context.json").exists()


def test_a_valid_but_changed_inventory_during_execution_is_not_rebound(tmp_path, monkeypatch):
    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    path = tmp_path / "pyproject.toml"
    path.write_text(
        path.read_text().replace('only_mutate=["src/pkg/a.py"]', 'only_mutate=["src/pkg/*.py"]')
    )
    script = (
        "import json;from pathlib import Path;"
        "Path('src/pkg/new.py').write_text('def new(): return 1\\n');"
        "p=Path('verification/mutation_risk_policy.json');d=json.loads(p.read_text());"
        "d['units']['src/pkg/new.py']={'level':'L4','reason':'Constructed additional scope'};"
        "p.write_text(json.dumps(d))"
    )
    monkeypatch.setattr(api, "_command", lambda _: [sys.executable, "-c", script])
    with pytest.raises(ValueError, match="scope changed"):
        api.run(tmp_path)
    assert not (cache / "execution-context.json").exists()


def test_an_interrupted_wait_retains_ownership_information_without_claiming_termination(
    tmp_path, monkeypatch
):
    import subprocess

    cache = _repository(tmp_path)
    api = _engine(monkeypatch, tmp_path)
    original = subprocess.Popen
    process = None

    class Interrupted:
        def __init__(self, command, **kwargs):
            nonlocal process
            process = original([sys.executable, "-c", "import time;time.sleep(30)"], **kwargs)
            self.pid = process.pid

        def wait(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "Popen", Interrupted)
    try:
        with pytest.raises(KeyboardInterrupt):
            api.run(tmp_path)
        pending = json.loads((cache / "execution-pending.json").read_text())
        assert pending["native_pid"] == process.pid
        os.killpg(process.pid, 0)
        assert not (cache / "execution-context.json").exists()
    finally:
        if process is not None:
            process.terminate()
            process.wait()
