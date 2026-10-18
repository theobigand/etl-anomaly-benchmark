"""REAL on a hosted runner downloads the research datasets and refuses any substitute."""

import hashlib
import io
import json
import runpy
from pathlib import Path

import pytest

from verification import real_acquire as ra

ROOT = Path(__file__).resolve().parents[1]
CREDIT = b"Time,V1,Class\n0,1.0,0\n"
WATER = b"ph,Potability\n7.0,1\n"
CARDIO = b"f00,label\n1.0,0\n"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


MANIFEST = {
    "credit_card": {"sha256": _sha(CREDIT)},
    "water_quality": {"sha256": _sha(WATER), "source_url": "https://raw.githubusercontent.com/x/y"},
    "cardio": {"sha256": _sha(CARDIO), "source_url": "https://raw.githubusercontent.com/a/b.npz"},
}


def _opener(payloads):
    def open_url(url, limit):
        return io.BytesIO(payloads[url])

    return open_url


def _sources():
    return {
        "credit_card": ("https://storage.googleapis.com/c.csv", "creditcard.csv"),
        "water_quality": ("https://raw.githubusercontent.com/x/y", "water_quality.csv"),
    }


def _payloads():
    return {
        "https://storage.googleapis.com/c.csv": CREDIT,
        "https://raw.githubusercontent.com/x/y": WATER,
    }


def _cardio_writer(content=CARDIO):
    def fetch(destination):
        (destination / "cardio.csv").write_bytes(content)

    return fetch


def test_the_three_datasets_are_downloaded_verified_and_reported(tmp_path):
    report = ra.acquire(
        _sources(), MANIFEST, tmp_path, open_url=_opener(_payloads()), fetch_cardio=_cardio_writer()
    )
    assert (tmp_path / "creditcard.csv").read_bytes() == CREDIT
    assert (tmp_path / "water_quality.csv").read_bytes() == WATER
    assert (tmp_path / "cardio.csv").read_bytes() == CARDIO
    assert report["method"] == "public-download"
    assert set(report["datasets"]) == {"credit_card", "water_quality", "cardio"}
    assert report["datasets"]["credit_card"] == {
        "url": "https://storage.googleapis.com/c.csv",
        "sha256": _sha(CREDIT),
        "bytes": len(CREDIT),
    }
    assert report["datasets"]["cardio"]["url"] == "https://raw.githubusercontent.com/a/b.npz"
    assert "Time" not in json.dumps(report)


def test_a_substituted_file_is_refused_and_nothing_is_kept(tmp_path):
    payloads = _payloads() | {"https://storage.googleapis.com/c.csv": CREDIT + b"tampered"}
    with pytest.raises(ra.AcquisitionError, match="credit_card.*differs"):
        ra.acquire(
            _sources(),
            MANIFEST,
            tmp_path,
            open_url=_opener(payloads),
            fetch_cardio=_cardio_writer(),
        )
    assert list(tmp_path.iterdir()) == []


def test_a_cardio_conversion_that_differs_is_refused_and_removed(tmp_path):
    with pytest.raises(ra.AcquisitionError, match="cardio.*differs"):
        ra.acquire(
            _sources(),
            MANIFEST,
            tmp_path,
            open_url=_opener(_payloads()),
            fetch_cardio=_cardio_writer(b"other"),
        )
    assert not (tmp_path / "cardio.csv").exists()


def test_an_existing_different_file_is_never_overwritten(tmp_path):
    (tmp_path / "creditcard.csv").write_bytes(b"local copy")
    with pytest.raises(ra.AcquisitionError, match="already exists"):
        ra.acquire(
            _sources(),
            MANIFEST,
            tmp_path,
            open_url=_opener(_payloads()),
            fetch_cardio=_cardio_writer(),
        )
    assert (tmp_path / "creditcard.csv").read_bytes() == b"local copy"


@pytest.mark.parametrize(
    "url",
    ["http://storage.googleapis.com/c.csv", "https://evil.example/c.csv", "file:///etc/passwd"],
)
def test_only_https_urls_on_the_allowed_hosts_are_fetched(tmp_path, url):
    with pytest.raises(ra.AcquisitionError, match="not allowed"):
        ra.acquire(
            {"credit_card": (url, "creditcard.csv")},
            MANIFEST,
            tmp_path,
            open_url=_opener({}),
            fetch_cardio=_cardio_writer(),
        )


def test_an_oversized_download_is_refused(tmp_path):
    big = {"https://storage.googleapis.com/c.csv": b"x" * 20}
    with pytest.raises(ra.AcquisitionError, match="larger than"):
        ra.acquire(
            {"credit_card": ("https://storage.googleapis.com/c.csv", "creditcard.csv")},
            MANIFEST,
            tmp_path,
            open_url=_opener(big),
            fetch_cardio=_cardio_writer(),
            limit=10,
        )


def test_the_real_opener_reads_at_most_the_limit(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    seen = {}

    def fake(request, timeout):
        seen["url"], seen["timeout"] = request.full_url, timeout
        return Response(b"abcdef")

    monkeypatch.setattr(ra.urllib.request, "urlopen", fake)
    stream = ra.open_url("https://raw.githubusercontent.com/x/y", 4)
    assert stream.read() == b"abcd" + b"e" and seen["timeout"] == 60


def test_the_repository_sources_cover_the_manifest_datasets():
    manifest = json.loads((ROOT / "verification/evidence/manifest.json").read_text())["datasets"]
    assert set(ra.SOURCES) | {"cardio"} == {"credit_card", "water_quality", "cardio"}
    assert set(ra.SOURCES) | {"cardio"} <= set(manifest)
    for url, _ in ra.SOURCES.values():
        assert ra.allowed(url)


def test_the_command_line_writes_a_report_and_exits_nonzero_on_refusal(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        ra, "acquire", lambda *a, **k: {"method": "public-download", "datasets": {}}
    )
    out = tmp_path / "report.json"
    assert ra.main(["--destination", str(tmp_path / "data"), "--output", str(out)]) == 0
    assert json.loads(out.read_text())["method"] == "public-download"

    def refuse(*a, **k):
        raise ra.AcquisitionError("credit_card: differs")

    monkeypatch.setattr(ra, "acquire", refuse)
    assert ra.main(["--destination", str(tmp_path / "data"), "--output", str(out)]) == 1
    assert "refused: credit_card: differs" in capsys.readouterr().out


def test_the_module_runs_as_a_script(monkeypatch):
    monkeypatch.setattr("sys.argv", ["real_acquire", "--help"])
    with pytest.raises(SystemExit) as stop:
        runpy.run_path(str(Path(ra.__file__)), run_name="__main__")
    assert stop.value.code == 0


def test_the_cardio_conversion_runs_the_repository_script(tmp_path, monkeypatch):
    calls = []

    class Done:
        returncode = 0

    monkeypatch.setattr(ra.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)) or Done())
    ra.run_fetch_cardio(tmp_path)
    command, _ = calls[0]
    assert command[-1].endswith("experiments/fetch_cardio.py")
