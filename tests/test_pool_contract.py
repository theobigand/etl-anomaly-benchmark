"""The local pool files must match the pinned manifest (pool_extension.md, P6)."""

import hashlib
import json
import runpy
from pathlib import Path

import pytest

from verification import pool_contract as pc

ROOT = Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pool(tmp_path):
    adbench, pool = tmp_path / "adbench", tmp_path / "pool"
    adbench.mkdir()
    pool.mkdir()
    (adbench / "2_annthyroid.npz").write_bytes(b"array")
    (pool / "222.csv").write_bytes(b"a,b\n1,2\n")
    manifest = [
        {"id": "adbench:annthyroid", "sha256": _sha(b"array")},
        {"id": "uci:222", "sha256": _sha(b"a,b\n1,2\n")},
    ]
    return manifest, adbench, pool


def test_a_file_is_hashed_in_blocks(tmp_path):
    path = tmp_path / "big.bin"
    path.write_bytes(b"x" * ((1 << 20) + 5))
    assert pc.sha256_file(path) == _sha(b"x" * ((1 << 20) + 5))


def test_every_matching_file_is_ok(tmp_path):
    manifest, adbench, pool = _pool(tmp_path)
    report = pc.check_pool(manifest, adbench, pool)
    assert report == [
        {"id": "adbench:annthyroid", "status": "ok"},
        {"id": "uci:222", "status": "ok"},
    ]
    assert pc.summarize(report) == {"datasets": 2, "counts": {"ok": 2}, "all_ok": True}


def test_a_changed_file_and_a_missing_file_are_reported_apart(tmp_path):
    manifest, adbench, pool = _pool(tmp_path)
    (pool / "222.csv").write_bytes(b"a,b\n1,3\n")
    (adbench / "2_annthyroid.npz").unlink()
    report = pc.check_pool(manifest, adbench, pool)
    assert {r["id"]: r["status"] for r in report} == {
        "adbench:annthyroid": "missing",
        "uci:222": "changed",
    }
    assert not pc.summarize(report)["all_ok"]


def test_an_ambiguous_adbench_name_is_missing_not_guessed(tmp_path):
    manifest, adbench, pool = _pool(tmp_path)
    (adbench / "9_annthyroid.npz").write_bytes(b"other")
    assert pc.local_path("adbench:annthyroid", adbench, pool) is None
    assert pc.local_path("adbench:annthyroid", tmp_path / "nowhere", pool) is None


def test_the_command_writes_a_report_and_fails_on_a_difference(tmp_path, capsys):
    manifest, adbench, pool = _pool(tmp_path)
    file = tmp_path / "manifest.json"
    file.write_text(json.dumps(manifest))
    out = tmp_path / "out" / "report.json"
    args = ["--manifest", str(file), "--adbench", str(adbench), "--pool", str(pool)]
    assert pc.main([*args, "--output", str(out)]) == 0
    assert json.loads(out.read_text())["summary"]["all_ok"]
    (pool / "222.csv").write_bytes(b"changed")
    assert pc.main(args) == 1
    assert '"all_ok": false' in capsys.readouterr().out


def test_running_the_module_as_a_script_exits_with_the_check_status(tmp_path, monkeypatch):
    manifest, adbench, pool = _pool(tmp_path)
    file = tmp_path / "manifest.json"
    file.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        "sys.argv",
        ["pool_contract", "--manifest", str(file), "--adbench", str(adbench), "--pool", str(pool)],
    )
    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(Path(pc.__file__)), run_name="__main__")
    assert raised.value.code == 0


@pytest.mark.real
def test_every_file_of_the_pool_matches_the_pinned_manifest():
    pool, adbench = ROOT / "data" / "pool", ROOT / "data" / "adbench"
    if not pool.is_dir() or not adbench.is_dir():
        pytest.skip("the pool is not downloaded on this machine")
    manifest = json.loads(
        (ROOT / "verification/evidence/dataset_registry/pool_manifest.json").read_text()
    )
    report = pc.check_pool(manifest, adbench, pool)
    assert len(report) == 152
    assert [r for r in report if r["status"] != "ok"] == []
