"""The bundle command packs and unpacks evidence, refuses anything else, and reports each step."""

import io
import json
import tarfile
from pathlib import Path

import pytest

from verification import bundles

REAL = ("experiments/results/real_verification.json", "experiments/results/evidence/real.json")


def _populate(root):
    for name in REAL:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": name}))


def test_packing_reports_the_kind_and_output_and_unpacking_reports_every_member(tmp_path, capsys):
    _populate(tmp_path / "src")
    out = tmp_path / "nested" / "real.tgz"
    assert (
        bundles.main(["pack", "real", "--root", str(tmp_path / "src"), "--output", str(out)]) == 0
    )
    assert capsys.readouterr().out == f"packed real evidence into {out}\n"
    assert (
        bundles.main(["unpack", str(out), "--root", str(tmp_path / "dest"), "--kind", "real"]) == 0
    )
    lines = capsys.readouterr().out.splitlines()
    assert sorted(lines) == sorted(f"unpacked {name}" for name in REAL)
    for name in REAL:
        assert (tmp_path / "dest" / name).is_file()


def test_a_refused_bundle_prints_the_reason_and_fails(tmp_path, capsys):
    assert (
        bundles.main(["pack", "real", "--root", str(tmp_path), "--output", str(tmp_path / "x")])
        == 1
    )
    assert capsys.readouterr().out.startswith("REFUSED: experiments/results")
    evil = tmp_path / "evil.tgz"
    with tarfile.open(evil, "w:gz") as archive:
        data = b"x"
        info = tarfile.TarInfo("../outside.txt")
        info.size = 1
        archive.addfile(info, io.BytesIO(data))
    assert bundles.main(["unpack", str(evil), "--root", str(tmp_path / "d")]) == 1
    assert "REFUSED: '../outside.txt' is not an allowed evidence file" in capsys.readouterr().out
    assert not (tmp_path / "outside.txt").exists()


def test_a_failed_job_can_pack_what_it_has_with_allow_missing(tmp_path, capsys):
    root = tmp_path / "src"
    path = root / REAL[0]
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    out = tmp_path / "partial.tgz"
    argv = ["pack", "real", "--root", str(root), "--output", str(out), "--allow-missing"]
    assert bundles.main(argv) == 0
    with tarfile.open(out) as archive:
        assert archive.getnames() == [REAL[0]]


def test_the_root_defaults_to_the_repository_and_the_command_is_required(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(bundles, "pack", lambda *args: seen.append(args) or tmp_path)
    assert bundles.main(["pack", "fast", "--output", "o.tgz"]) == 0
    assert seen == [("fast", bundles.ROOT, Path("o.tgz"), False)]
    monkeypatch.setattr(bundles, "unpack", lambda *args: seen.append(args) or [])
    assert bundles.main(["unpack", "b.tgz"]) == 0
    assert seen[1] == (Path("b.tgz"), bundles.ROOT, None)
    with pytest.raises(SystemExit) as stop:
        bundles.main([])
    assert stop.value.code == 2


def test_the_help_describes_each_command_and_option_and_the_output_is_required(capsys):
    with pytest.raises(SystemExit):
        bundles.main(["--help"])
    top = " ".join(capsys.readouterr().out.split())
    assert "archive the evidence files of one kind" in top
    assert "extract an archive that holds only evidence files" in top
    with pytest.raises(SystemExit):
        bundles.main(["pack", "--help"])
    assert "skip files a failed job lacks" in " ".join(capsys.readouterr().out.split())
    with pytest.raises(SystemExit) as stop:
        bundles.main(["pack", "real"])
    assert stop.value.code == 2
    with pytest.raises(SystemExit) as stop:
        bundles.main(["pack", "nonsense", "--output", "x"])
    assert stop.value.code == 2
