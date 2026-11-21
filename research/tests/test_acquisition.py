import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import acquisition as aq  # noqa: E402

SPEC = {
    "id": "demo",
    "licence_class": "open",
    "hosts": ["example.org"],
    "min_interval": 0.0,
    "retries": 2,
    "max_bytes": 100,
}


def test_a_fetch_is_snapshotted_with_checksum_times_and_never_overwritten(tmp_path):
    calls = []

    def opener(url, limit):
        calls.append(url)
        return b'{"a": 1}'

    snap = aq.Snapshot(tmp_path, SPEC, "2026-11-21", opener=opener, sleep=lambda s: None)
    entry = snap.fetch("https://example.org/x.json", "x.json", observed="2026-11-20")
    assert entry["sha256"] == hashlib.sha256(b'{"a": 1}').hexdigest()
    assert entry["observed"] == "2026-11-20" and entry["collected"]
    assert (tmp_path / "demo" / "2026-11-21" / "raw" / "x.json").read_bytes() == b'{"a": 1}'
    again = snap.fetch("https://example.org/x.json", "x.json", observed="2026-11-20")
    assert again == entry and len(calls) == 1  # idempotent: a stored file is not fetched again
    manifest = json.loads((tmp_path / "demo" / "2026-11-21" / "manifest.json").read_text())
    assert [f["name"] for f in manifest["files"]] == ["x.json"]
    other = aq.Snapshot(tmp_path, SPEC, "2026-11-22", opener=opener, sleep=lambda s: None)
    other.fetch("https://example.org/x.json", "x.json", observed=None)
    assert (tmp_path / "demo" / "2026-11-21").exists()  # a new snapshot never touches the old one


def test_disallowed_hosts_oversized_bodies_and_restricted_sources_are_refused(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "s", opener=lambda u, n: b"x", sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError, match="host"):
        snap.fetch("https://evil.net/x", "x", observed=None)
    with pytest.raises(aq.AcquisitionError, match="https"):
        snap.fetch("http://example.org/x", "x", observed=None)
    big = aq.Snapshot(tmp_path, SPEC, "t", opener=lambda u, n: b"x" * 101, sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError, match="larger"):
        big.fetch("https://example.org/x", "x", observed=None)
    for klass in ("unclear", "restricted"):
        with pytest.raises(aq.AcquisitionError, match="licence"):
            aq.Snapshot(tmp_path, {**SPEC, "licence_class": klass}, "s")
    with pytest.raises(aq.AcquisitionError, match="name"):
        snap.fetch("https://example.org/x", "../escape", observed=None)


def test_transient_failures_are_retried_a_bounded_number_of_times_with_the_interval_kept(tmp_path):
    waits, attempts = [], []

    def flaky(url, limit):
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("boom")
        return b"ok"

    spec = {**SPEC, "min_interval": 1.5, "retries": 2}
    snap = aq.Snapshot(tmp_path, spec, "s", opener=flaky, sleep=waits.append)
    assert snap.fetch("https://example.org/a", "a", observed=None)["bytes"] == 2
    assert len(attempts) == 3 and all(w >= 1.5 for w in waits) and len(waits) >= 2
    dead = aq.Snapshot(
        tmp_path,
        spec,
        "u",
        opener=lambda u, n: 1 / 0 if False else (_ for _ in ()).throw(OSError("x")),
        sleep=waits.append,
    )
    with pytest.raises(aq.AcquisitionError, match="after 3 attempts"):
        dead.fetch("https://example.org/b", "b", observed=None)


def test_pages_stop_at_the_page_budget_or_when_a_page_is_empty(tmp_path):
    pages = {0: [1, 2], 1: [3], 2: []}
    got = list(aq.paginate(lambda i: pages.get(i, []), max_pages=5))
    assert got == [[1, 2], [3]]
    assert len(list(aq.paginate(lambda i: [i], max_pages=3))) == 3


def test_a_changed_stored_file_is_detected_when_the_snapshot_is_verified(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "s", opener=lambda u, n: b"abc", sleep=lambda s: None)
    snap.fetch("https://example.org/a", "a", observed=None)
    assert snap.verify() == []
    (tmp_path / "demo" / "s" / "raw" / "a").write_bytes(b"abd")
    assert snap.verify() == ["a"]


def test_a_plan_lists_fixed_files_then_numbered_pages():
    spec = {
        "files": [{"url": "https://example.org/f", "name": "f", "observed": None}],
        "pages": {
            "url": "https://example.org/p?skip={skip}&page={n1}",
            "name": "p{n}.json",
            "count": 2,
            "size": 100,
        },
    }
    got = aq.plan(spec)
    assert [r["name"] for r in got] == ["f", "p0.json", "p1.json"]
    assert got[2]["url"] == "https://example.org/p?skip=100&page=2"


def test_a_second_stage_requests_the_distinct_ids_found_in_the_first_stage_files(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "w0.json").write_text(
        json.dumps(
            {"results": [{"a": [{"id": "A2"}, {"id": "A1"}]}, {"a": [{"id": "A1"}, {"id": None}]}]}
        )
    )
    (raw / "w1.json").write_text(json.dumps({"results": [{"a": [{"id": "A3"}]}]}))
    stage = {
        "from": "w*.json",
        "path": "results.a.id",
        "batch": 2,
        "url": "https://example.org/e?ids={ids}",
        "name": "e{n}.json",
        "join": "|",
    }
    got = aq.expand(stage, raw)
    assert [r["name"] for r in got] == ["e0.json", "e1.json"]
    assert got[0]["url"] == "https://example.org/e?ids=A1|A2" and got[1]["url"].endswith("ids=A3")
    assert aq.expand({**stage, "path": "results.zzz"}, raw) == []


def test_short_ids_drop_the_url_prefix(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "w.json").write_text(
        json.dumps({"results": [{"id": "https://x.org/W2"}, {"id": "https://x.org/W1"}]})
    )
    stage = {"from": "w.json", "path": "results.id", "batch": 5, "url": "https://e.org/?i={ids}",
             "name": "e{n}", "join": "|", "short": True}  # fmt: skip
    assert aq.expand(stage, raw)[0]["url"] == "https://e.org/?i=W1|W2"


def test_explicit_page_numbers_replace_the_count():
    spec = {
        "pages": {
            "url": "https://e.org/?p={n1}",
            "name": "p{n}",
            "count": 99,
            "size": 1,
            "numbers": [7, 3],
        }
    }
    assert [r["url"] for r in aq.plan(spec)] == ["https://e.org/?p=8", "https://e.org/?p=4"]
