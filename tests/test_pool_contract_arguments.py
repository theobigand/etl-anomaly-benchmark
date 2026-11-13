"""Block reading, id parsing, defaults and report format of the pool contract check."""

import hashlib
import json
from pathlib import Path

import pytest

from verification import pool_contract as pc

ROOT = Path(__file__).resolve().parents[1]


class _Stream:
    def __init__(self, data: bytes) -> None:
        self.data, self.sizes = data, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size):
        self.sizes.append(size)
        if len(self.sizes) > 6:
            raise AssertionError("the read loop does not stop at the end of the file")
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk


def test_a_file_is_read_in_one_mebibyte_blocks_until_it_ends(monkeypatch, tmp_path):
    data = b"x" * ((1 << 20) + 5)
    stream = _Stream(data)
    monkeypatch.setattr(Path, "open", lambda self, mode: stream)
    assert pc.sha256_file(tmp_path / "f") == hashlib.sha256(data).hexdigest()
    assert stream.sizes == [1 << 20, 1 << 20, 1 << 20]


def test_an_entry_id_is_split_at_its_first_colon_and_a_missing_uci_file_is_none(tmp_path):
    (tmp_path / "a:b.csv").write_bytes(b"1")
    assert pc.local_path("uci:a:b", tmp_path / "none", tmp_path) == tmp_path / "a:b.csv"
    assert pc.local_path("uci:absent", tmp_path / "none", tmp_path) is None
    assert pc.local_path("adbench:x", tmp_path / "not-a-directory", tmp_path) is None


def test_the_summary_counts_every_status_and_is_ok_only_when_all_match():
    assert pc.summarize([{"status": "ok"}, {"status": "ok"}]) == {
        "datasets": 2,
        "counts": {"ok": 2},
        "all_ok": True,
    }
    mixed = pc.summarize([{"status": "ok"}, {"status": "changed"}, {"status": "changed"}])
    assert mixed == {"datasets": 3, "counts": {"ok": 1, "changed": 2}, "all_ok": False}
    assert pc.summarize([{"status": "missing"}])["all_ok"] is False
    assert pc.summarize([])["all_ok"] is True


def test_the_defaults_point_at_the_repository_and_the_help_is_the_module_description(
    monkeypatch, tmp_path, capsys
):
    seen = {}
    monkeypatch.setattr(Path, "read_text", lambda self: seen.setdefault("manifest", self) and "[]")
    monkeypatch.setattr(
        pc, "check_pool", lambda manifest, adbench, pool: seen.update(paths=(adbench, pool)) or []
    )
    assert pc.main([]) == 0
    assert seen["manifest"] == ROOT / "verification/evidence/dataset_registry/pool_manifest.json"
    assert seen["paths"] == (ROOT / "data" / "adbench", ROOT / "data" / "pool")
    with pytest.raises(SystemExit):
        pc.main(["--help"])
    assert "Every local file of the dataset pool" in " ".join(capsys.readouterr().out.split())


def test_the_report_file_is_sorted_one_space_indented_and_created_under_new_directories(
    monkeypatch, tmp_path
):
    manifest = tmp_path / "m.json"
    manifest.write_text("[]")
    output = tmp_path / "new" / "deeper" / "out.json"
    assert pc.main(["--manifest", str(manifest), "--output", str(output)]) == 0
    expected = {"summary": {"datasets": 0, "counts": {}, "all_ok": True}, "report": []}
    assert output.read_text() == json.dumps(expected, indent=1, sort_keys=True) + "\n"
    assert pc.main(["--manifest", str(manifest), "--output", str(output)]) == 0
