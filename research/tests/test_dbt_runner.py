"""dbt runner contract with a stand-in executable (#146); the real run is test_dbt_integration."""

import json
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dbt_runner as dr  # noqa: E402

FAKE = """#!{python}
import json, os, sys
args = sys.argv[1:]
mode = os.environ["FAKE_MODE"]
keys = ("ELT_RAW", "ELT_MARTS", "DBT_DUCKDB_PATH")
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps({{"args": args, "env": {{k: os.environ.get(k) for k in keys}}}}) + "\\n")
if args[0] == "--version":
    print("Core:\\n  - installed: 9.9.9")
    sys.exit(0)
target = args[args.index("--target-path") + 1]
os.makedirs(target, exist_ok=True)
if args[0] == "build":
    if mode == "exit1":
        sys.exit(1)
    if mode == "no_results":
        sys.exit(0)
    status = "fail" if mode in ("fail_node", "fail_two") else "pass"
    results = [
        {{"unique_id": "model.orders.a", "status": "success" if mode != "fail_two" else "error"}},
        {{"unique_id": "test.orders.b", "status": status}},
    ]
    json.dump({{"metadata": {{"invocation_id": "inv-1"}}, "results": results}},
              open(target + "/run_results.json", "w"))
    sys.exit(1 if status == "fail" else 0)
if mode == "docs_fail":
    sys.exit(2)
json.dump({{"parent_map": {{"test.orders.b": ["model.orders.a"], "model.orders.a": []}}}},
          open(target + "/manifest.json", "w"))
json.dump({{"nodes": {{}}}}, open(target + "/catalog.json", "w"))
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    path = tmp_path / "dbt"
    path.write_text(FAKE.format(python=sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    out = tmp_path / "elt"
    out.mkdir()
    (out / "manifest.json").write_text(json.dumps({"run_id": "elt-run"}))
    monkeypatch.setenv("FAKE_MODE", "ok")
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "calls.jsonl"))
    return path, out


def test_a_passing_build_writes_a_record_with_invocation_lineage_and_artifact_hashes(fake):
    path, out = fake
    record = dr.run_dbt(out, str(path))
    assert record["elt_run_id"] == "elt-run"
    assert record["invocation_id"] == "inv-1"
    assert record["nodes"] == {"model.orders.a": "success", "test.orders.b": "pass"}
    assert record["lineage"] == {"model.orders.a": [], "test.orders.b": ["model.orders.a"]}
    assert "installed: 9.9.9" in record["dbt_version"]
    assert set(record["artifacts"]) == set(dr.ARTIFACTS)
    assert all(len(h) == 64 for h in record["artifacts"].values())
    written = (out / "dbt" / "dbt_run.json").read_text()
    assert written == json.dumps(record, indent=1, sort_keys=True) + "\n"


def test_dbt_gets_the_project_the_stage_paths_and_the_target_through_arguments_and_environment(
    fake, tmp_path
):
    path, out = fake
    dr.run_dbt(out, str(path))
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [call["args"][0] for call in calls] == ["build", "docs", "--version"]
    flags = [
        "--project-dir",
        str(dr.PROJECT),
        "--profiles-dir",
        str(dr.PROJECT),
        "--target-path",
        str(out.resolve() / "dbt" / "target"),
        "--log-path",
        str(out.resolve() / "dbt" / "logs"),
    ]
    assert calls[0]["args"] == ["build", *flags]
    assert calls[1]["args"] == ["docs", "generate", *flags]
    assert calls[2]["args"] == ["--version"]
    for call in calls:
        assert call["env"] == {
            "ELT_RAW": str(out.resolve() / "raw" / "orders.parquet"),
            "ELT_MARTS": str(out.resolve() / "marts" / "orders_by_tier.parquet"),
            "DBT_DUCKDB_PATH": str(out.resolve() / "dbt" / "orders.duckdb"),
        }


def test_a_second_run_over_the_same_output_succeeds(fake):
    path, out = fake
    first = dr.run_dbt(out, str(path))
    assert dr.run_dbt(out, str(path)) == first


def test_a_failed_node_is_an_error_that_names_it_and_writes_no_record(fake, monkeypatch):
    path, out = fake
    monkeypatch.setenv("FAKE_MODE", "fail_node")
    with pytest.raises(dr.DbtError, match=r"^dbt build failed \(exit 1\): test.orders.b$"):
        dr.run_dbt(out, str(path))
    assert not (out / "dbt" / "dbt_run.json").exists()


def test_every_failed_node_is_named(fake, monkeypatch):
    path, out = fake
    monkeypatch.setenv("FAKE_MODE", "fail_two")
    with pytest.raises(dr.DbtError, match=r": model.orders.a, test.orders.b$"):
        dr.run_dbt(out, str(path))


def test_a_build_without_results_is_an_error(fake, monkeypatch):
    path, out = fake
    monkeypatch.setenv("FAKE_MODE", "no_results")
    with pytest.raises(dr.DbtError, match="^dbt wrote no run_results.json$"):
        dr.run_dbt(out, str(path))


def test_a_crashed_build_is_an_error(fake, monkeypatch):
    path, out = fake
    monkeypatch.setenv("FAKE_MODE", "exit1")
    with pytest.raises(dr.DbtError, match=r"^dbt build failed \(exit 1\): no node result$"):
        dr.run_dbt(out, str(path))


def test_a_failed_docs_generation_is_an_error(fake, monkeypatch):
    path, out = fake
    monkeypatch.setenv("FAKE_MODE", "docs_fail")
    with pytest.raises(dr.DbtError, match=r"^dbt docs generate failed \(exit 2\)$"):
        dr.run_dbt(out, str(path))


def test_the_executable_comes_from_the_argument_then_the_environment(monkeypatch):
    monkeypatch.setenv("DBT_BIN", "from-env")
    assert dr.dbt_command("given") == "given"
    assert dr.dbt_command(None) == "from-env"
    monkeypatch.delenv("DBT_BIN")
    with pytest.raises(dr.DbtUnavailable, match="^no dbt executable: set DBT_BIN or pass --dbt$"):
        dr.dbt_command(None)


def test_an_executable_that_cannot_start_is_unavailable(fake, tmp_path):
    _, out = fake
    with pytest.raises(dr.DbtUnavailable, match="^cannot start dbt"):
        dr.run_dbt(out, str(tmp_path / "missing"))


def test_an_elt_output_without_a_manifest_is_refused(tmp_path):
    with pytest.raises(dr.DbtError, match="holds no ELT manifest; run elt_duckdb first"):
        dr.run_dbt(tmp_path, "unused")


def test_the_archived_evidence_paths_are_refused(fake):
    path, _ = fake
    with pytest.raises(dr.elt.ArchivedPathError):
        dr.run_dbt(dr.elt.ROOT / "verification" / "evidence" / "x", str(path))


def test_a_timeout_is_reported_as_an_error(monkeypatch):
    import subprocess

    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired("dbt", 1)

    monkeypatch.setattr(dr.subprocess, "run", slow)
    with pytest.raises(dr.DbtError, match=f"^dbt timed out after {dr.TIMEOUT} s: build$"):
        dr._invoke("dbt", ["build"], {})


def test_the_command_line_prints_the_record(fake, capsys):
    path, out = fake
    assert dr.main(["--elt-out", str(out), "--dbt", str(path)]) == 0
    printed = capsys.readouterr().out
    record = json.loads(printed)
    assert record["invocation_id"] == "inv-1"
    assert printed == json.dumps(record, indent=1, sort_keys=True) + "\n"


def test_the_command_requires_the_elt_output():
    with pytest.raises(SystemExit):
        dr.main([])


def test_the_subprocess_is_bounded_captured_and_never_raises_on_a_bad_exit(monkeypatch):
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return "done"

    monkeypatch.setattr(dr.subprocess, "run", run)
    assert dr._invoke("dbt", ["build"], {"A": "1"}) == "done"
    assert seen == {
        "command": ["dbt", "build"],
        "env": {"A": "1"},
        "capture_output": True,
        "text": True,
        "timeout": dr.TIMEOUT,
        "check": False,
    }
