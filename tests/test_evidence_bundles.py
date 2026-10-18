"""Evidence travels in bundles that can carry nothing but evidence."""

import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from verification import bundles

ROOT = Path(__file__).resolve().parents[1]
REAL = ("experiments/results/real_verification.json", "experiments/results/evidence/real.json")


def _write(root, relative, content='{"ok": true}'):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _bundle(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            data = content.encode() if isinstance(content, str) else content
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def test_a_real_bundle_holds_the_two_real_files_and_nothing_else(tmp_path):
    for name in REAL:
        _write(tmp_path / "src", name)
    _write(tmp_path / "src", "data/creditcard.csv", "a,b\n1,2\n")
    out = bundles.pack("real", tmp_path / "src", tmp_path / "real.tgz")
    with tarfile.open(out) as archive:
        assert sorted(archive.getnames()) == sorted(REAL)


def test_packing_refuses_a_missing_or_oversized_file(tmp_path):
    _write(tmp_path / "src", REAL[0])
    with pytest.raises(bundles.BundleError, match="missing"):
        bundles.pack("real", tmp_path / "src", tmp_path / "real.tgz")
    _write(tmp_path / "src", REAL[1], "x" * (bundles.MAX_MEMBER + 1))
    with pytest.raises(bundles.BundleError, match="larger"):
        bundles.pack("real", tmp_path / "src", tmp_path / "real.tgz")


def test_packing_refuses_a_file_that_is_not_json(tmp_path):
    for name in REAL:
        _write(tmp_path / "src", name)
    _write(tmp_path / "src", REAL[0], "id,amount\n1,2.5\n")
    with pytest.raises(bundles.BundleError, match="JSON"):
        bundles.pack("real", tmp_path / "src", tmp_path / "real.tgz")


def test_an_unknown_kind_cannot_be_packed(tmp_path):
    with pytest.raises(bundles.BundleError, match="kind"):
        bundles.pack("everything", tmp_path, tmp_path / "x.tgz")


def test_a_clean_bundle_is_unpacked_at_the_root(tmp_path):
    bundle = _bundle(tmp_path / "b.tgz", {name: '{"a": 1}' for name in REAL})
    names = bundles.unpack(bundle, tmp_path / "dest")
    assert sorted(names) == sorted(REAL)
    assert json.loads((tmp_path / "dest" / REAL[1]).read_text()) == {"a": 1}


@pytest.mark.parametrize(
    "member",
    [
        "data/creditcard.csv",
        "../escape.json",
        "/etc/passwd",
        "experiments/results/evidence/../../../x.json",
        "experiments/results/evidence/real.json.csv",
        "experiments/results/evidence/other.json",
    ],
)
def test_a_bundle_with_a_member_outside_the_allowlist_is_refused_whole(tmp_path, member):
    bundle = _bundle(tmp_path / "b.tgz", {REAL[1]: "{}", member: "x"})
    with pytest.raises(bundles.BundleError, match="allowed"):
        bundles.unpack(bundle, tmp_path / "dest")
    assert not (tmp_path / "dest").exists()


def test_links_and_devices_are_refused(tmp_path):
    path = tmp_path / "b.tgz"
    with tarfile.open(path, "w:gz") as archive:
        link = tarfile.TarInfo(REAL[1])
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        archive.addfile(link)
    with pytest.raises(bundles.BundleError, match="regular file"):
        bundles.unpack(path, tmp_path / "dest")


def test_an_oversized_member_is_refused(tmp_path):
    bundle = _bundle(tmp_path / "b.tgz", {REAL[1]: "x" * (bundles.MAX_MEMBER + 1)})
    with pytest.raises(bundles.BundleError, match="larger"):
        bundles.unpack(bundle, tmp_path / "dest")


def test_a_bundle_restricted_to_a_kind_refuses_the_files_of_other_kinds(tmp_path):
    bundle = _bundle(tmp_path / "b.tgz", {"experiments/results/evidence/fast.json": "{}"})
    with pytest.raises(bundles.BundleError, match="allowed"):
        bundles.unpack(bundle, tmp_path / "dest", kind="real")
    assert bundles.unpack(bundle, tmp_path / "dest", kind="fast")


def test_an_unreadable_archive_is_refused(tmp_path):
    path = tmp_path / "b.tgz"
    path.write_bytes(b"not a tarball")
    with pytest.raises(bundles.BundleError, match="archive"):
        bundles.unpack(path, tmp_path / "dest")


def test_every_evidence_kind_has_an_allowlist_covering_what_its_make_target_writes():
    assert set(bundles.KINDS) >= {"fast", "static", "reproduction", "faults", "deep", "real"}
    deep = bundles.KINDS["deep"]
    assert "mutants/results.txt" in deep and "experiments/results/evidence/deep.json" in deep
    assert bundles.KINDS["real"] == REAL


def test_the_command_packs_and_unpacks(tmp_path):
    for name in REAL:
        _write(tmp_path / "src", name)
    run = [sys.executable, "-m", "verification.bundles"]
    packed = subprocess.run(
        [*run, "pack", "real", "--root", str(tmp_path / "src"), "--output", str(tmp_path / "r")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert packed.returncode == 0, packed.stderr
    opened = subprocess.run(
        [*run, "unpack", str(tmp_path / "r"), "--root", str(tmp_path / "dest")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert opened.returncode == 0 and REAL[1] in opened.stdout
    bad = _bundle(tmp_path / "bad.tgz", {"data/x.csv": "a"})
    refused = subprocess.run(
        [*run, "unpack", str(bad), "--root", str(tmp_path / "dest2")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert refused.returncode == 1 and "REFUSED" in refused.stdout
    missing = subprocess.run(
        [*run, "pack", "real", "--root", str(tmp_path / "no"), "--output", str(tmp_path / "m")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert missing.returncode == 1 and "REFUSED" in missing.stdout


def test_a_failed_job_may_pack_what_it_has_with_allow_missing(tmp_path):
    _write(tmp_path / "src", REAL[1])
    out = bundles.pack("real", tmp_path / "src", tmp_path / "r.tgz", allow_missing=True)
    with tarfile.open(out) as archive:
        assert archive.getnames() == [REAL[1]]


def test_text_listings_are_packed_without_a_json_check(tmp_path):
    _write(tmp_path / "src", "mutants/results.txt", "pkg.x_f__mutmut_1: killed\n")
    out = bundles.pack("deep", tmp_path / "src", tmp_path / "d.tgz", allow_missing=True)
    with tarfile.open(out) as archive:
        assert archive.getnames() == ["mutants/results.txt"]


HOSTED = (*REAL, "experiments/results/real_acquisition.json")


def test_the_hosted_real_bundle_adds_only_the_acquisition_report(tmp_path):
    assert sorted(bundles.KINDS["real-hosted"]) == sorted(HOSTED)
    for name in HOSTED:
        _write(tmp_path / "src", name)
    _write(tmp_path / "src", "data/creditcard.csv", "a,b\n1,2\n")
    out = bundles.pack("real-hosted", tmp_path / "src", tmp_path / "h.tgz")
    with tarfile.open(out) as archive:
        assert sorted(archive.getnames()) == sorted(HOSTED)
    names = bundles.unpack(out, tmp_path / "dest")
    assert sorted(names) == sorted(HOSTED)
