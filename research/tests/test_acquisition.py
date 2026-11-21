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


# --- exact behaviour: manifests, retries, limits, paths, planning, expansion, command line --------


def test_the_manifest_and_the_stored_file_have_exactly_the_documented_content(tmp_path):
    calls = []

    def opener(url, limit):
        calls.append((url, limit))
        return b"abc"

    snap = aq.Snapshot(tmp_path, SPEC, "snap1", opener=opener, sleep=lambda s: None)
    entry = snap.fetch("https://example.org/a/b.json", "dir/b.json", observed="2024-01")
    assert calls == [("https://example.org/a/b.json", 100)]
    assert set(entry) == {"name", "url", "sha256", "bytes", "collected", "observed"}
    assert entry["name"] == "dir/b.json" and entry["url"] == "https://example.org/a/b.json"
    assert entry["bytes"] == 3 and entry["observed"] == "2024-01"
    assert entry["collected"].endswith("+00:00") and "T" in entry["collected"]
    manifest_path = tmp_path / "demo" / "snap1" / "manifest.json"
    text = manifest_path.read_text()
    manifest = json.loads(text)
    assert manifest == {"source": "demo", "snapshot": "snap1", "files": [entry]}
    assert text == json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    assert (tmp_path / "demo" / "snap1" / "raw" / "dir" / "b.json").read_bytes() == b"abc"
    # a second file in the same directory and a second file in a new directory both work
    snap.fetch("https://example.org/c", "dir/c.json", observed=None)
    snap.fetch("https://example.org/d", "d.json", observed=None)
    assert [f["name"] for f in json.loads(manifest_path.read_text())["files"]] == [
        "dir/b.json",
        "dir/c.json",
        "d.json",
    ]


def test_directories_have_the_exact_documented_names(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "s9", opener=lambda u, n: b"x", sleep=lambda s: None)
    assert snap.raw == tmp_path / "demo" / "s9" / "raw"
    assert str(snap.manifest_path).endswith("demo/s9/manifest.json")
    assert snap.snapshot_id == "s9" and snap.directory == tmp_path / "demo" / "s9"
    snap.fetch("https://example.org/x", "x", observed=None)
    assert sorted(p.name for p in (tmp_path / "demo" / "s9").iterdir()) == ["manifest.json", "raw"]


def test_retries_back_off_exponentially_and_report_the_last_error(tmp_path):
    waits = []
    errors = [OSError("one"), OSError("two"), OSError("three")]

    def failing(url, limit):
        raise errors.pop(0)

    spec = {**SPEC, "min_interval": 1.0, "retries": 2}
    snap = aq.Snapshot(tmp_path, spec, "r", opener=failing, sleep=waits.append)
    with pytest.raises(aq.AcquisitionError) as info:
        snap.fetch("https://example.org/a", "a", observed=None)
    # pacing before each attempt (1.0) and then 2, 4, 8 after each failure
    assert waits == [1.0, 2.0, 1.0, 4.0, 1.0, 8.0]
    assert "three" in str(info.value) and "after 3 attempts" in str(info.value)
    assert "https://example.org/a" in str(info.value)


def test_a_body_exactly_at_the_limit_is_accepted_and_one_byte_more_is_not(tmp_path):
    at_limit = aq.Snapshot(
        tmp_path, SPEC, "a", opener=lambda u, n: b"x" * 100, sleep=lambda s: None
    )
    assert at_limit.fetch("https://example.org/x", "x", observed=None)["bytes"] == 100
    over = aq.Snapshot(tmp_path, SPEC, "b", opener=lambda u, n: b"x" * 101, sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError, match="larger than 100 bytes"):
        over.fetch("https://example.org/x", "x", observed=None)


def test_the_error_messages_name_the_url_the_host_and_the_file(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "m", opener=lambda u, n: b"x", sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError) as host:
        snap.fetch("https://evil.net/x", "x", observed=None)
    assert "https://evil.net/x" in str(host.value) and "demo" in str(host.value)
    with pytest.raises(aq.AcquisitionError) as scheme:
        snap.fetch("http://example.org/x", "x", observed=None)
    assert str(scheme.value) == "http://example.org/x: https only"
    with pytest.raises(aq.AcquisitionError) as name:
        snap.fetch("https://example.org/x", "a b", observed=None)
    assert "'a b'" in str(name.value)
    for bad in ("../x", "/abs", "a//b", ".hidden", "a/../b"):
        with pytest.raises(aq.AcquisitionError):
            snap.fetch("https://example.org/x", bad, observed=None)
    for good in ("a", "a.json", "a_b-c.1", "d/e/f.csv"):
        snap.fetch("https://example.org/x", good, observed=None)
    with pytest.raises(aq.AcquisitionError) as klass:
        aq.Snapshot(tmp_path, {**SPEC, "licence_class": "restricted"}, "s")
    assert str(klass.value) == "licence class 'restricted' is not collectable"
    for ok in ("open", "research_only"):
        aq.Snapshot(tmp_path, {**SPEC, "licence_class": ok}, "s")


def test_planning_keeps_every_field_of_fixed_files_and_pages():
    spec = {
        "files": [{"url": "https://e.org/f", "name": "f", "observed": "2024", "extra": 1}],
        "pages": {
            "url": "https://e.org/p?n={n}&n1={n1}&skip={skip}",
            "name": "p{n}.json",
            "count": 2,
            "size": 50,
            "observed": "2023",
        },
    }
    got = aq.plan(spec)
    assert got[0] == {"url": "https://e.org/f", "name": "f", "observed": "2024", "extra": 1}
    assert got[1] == {
        "url": "https://e.org/p?n=0&n1=1&skip=0",
        "name": "p0.json",
        "observed": "2023",
    }
    assert got[2] == {
        "url": "https://e.org/p?n=1&n1=2&skip=50",
        "name": "p1.json",
        "observed": "2023",
    }
    assert aq.plan({}) == []
    nopages = aq.plan({"pages": {"url": "https://e.org/{n}", "name": "{n}", "count": 1, "size": 1}})
    assert nopages[0]["observed"] is None
    numbers = {
        "url": "https://e.org/?p={n}",
        "name": "x{n}",
        "count": 9,
        "size": 10,
        "numbers": [4],
    }
    assert aq.plan({"pages": numbers})[0]["url"] == "https://e.org/?p=4"


def test_expansion_walks_lists_and_objects_and_keeps_observed(tmp_path):
    raw = tmp_path
    (raw / "a.json").write_text(
        json.dumps({"r": [{"x": [{"id": "https://h/A/2"}, {"id": "https://h/A/1"}]}]})
    )
    (raw / "b.json").write_text(json.dumps({"r": [{"x": {"id": "https://h/A/3"}}]}))
    stage = {
        "from": "*.json",
        "path": "r.x.id",
        "batch": 10,
        "url": "https://e.org/?i={ids}",
        "name": "e{n}",
        "join": ",",
        "observed": "2023",
    }
    full = aq.expand(stage, raw)
    assert full == [
        {
            "url": "https://e.org/?i=https://h/A/1,https://h/A/2,https://h/A/3",
            "name": "e0",
            "observed": "2023",
        }
    ]
    short = aq.expand({**stage, "short": True}, raw)
    assert short[0]["url"] == "https://e.org/?i=1,2,3"  # only the last path segment is kept
    assert (
        aq.expand({k: v for k, v in stage.items() if k != "observed"}, raw)[0]["observed"] is None
    )
    deep = tmp_path / "d"
    deep.mkdir()
    (deep / "a.json").write_text(json.dumps({"r": [{"x": [{"id": "a/b/c"}]}]}))
    assert aq.expand({**stage, "short": True}, deep)[0]["url"] == "https://e.org/?i=c"
    (deep / "a.json").write_text(json.dumps({"r": [1, None, {"x": None}, {"y": 1}]}))
    assert aq.expand(stage, deep) == []
    (deep / "a.json").write_text(json.dumps({"r": [{"x": [{"id": None}, {"id": "k"}]}]}))
    assert aq.expand(stage, deep)[0]["url"] == "https://e.org/?i=k"


def test_open_url_sends_the_user_agent_and_reads_at_most_limit_plus_one(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            seen["read"] = n
            return b"data"

    def fake(request, timeout):
        seen["agent"] = request.get_header("User-agent")
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(aq.urllib.request, "urlopen", fake)
    assert aq.open_url("https://example.org/z", 10) == b"data"
    assert seen == {
        "agent": aq.USER_AGENT,
        "url": "https://example.org/z",
        "timeout": 120,
        "read": 11,
    }
    assert aq.USER_AGENT == "etl-benchmark-acquisition (academic research)"


def test_the_command_line_fetches_pages_then_stages_and_reports_the_count(
    tmp_path, monkeypatch, capsys
):
    sources = tmp_path / "sources.json"
    spec = {
        **SPEC,
        "id": "cli",
        "files": [{"url": "https://example.org/f", "name": "f.json", "observed": None}],
        "pages": {"url": "https://example.org/p{n}", "name": "p{n}.json", "count": 1, "size": 1},
        "stages": [
            {
                "from": "p*.json",
                "path": "ids",
                "batch": 5,
                "url": "https://example.org/s?i={ids}",
                "name": "s{n}.json",
                "join": "|",
            }
        ],
    }
    sources.write_text(json.dumps({"sources": [spec, {**SPEC, "id": "other"}]}))
    monkeypatch.setattr(aq, "SOURCES", sources)
    monkeypatch.setattr(aq, "open_url", lambda url, limit: b'{"ids": ["a", "b"]}')
    real = aq.Snapshot.__init__

    def init(self, root, spec, snapshot_id, opener=aq.open_url, sleep=aq.time.sleep):
        real(
            self,
            root,
            spec,
            snapshot_id,
            opener=lambda u, n: b'{"ids": ["a", "b"]}',
            sleep=lambda s: None,
        )

    monkeypatch.setattr(aq.Snapshot, "__init__", init)
    assert aq.main(["cli", "--snapshot", "t1", "--root", str(tmp_path / "out")]) == 0
    assert capsys.readouterr().out == "cli/t1: 3 files, mismatches []\n"
    raw = tmp_path / "out" / "cli" / "t1" / "raw"
    assert sorted(p.name for p in raw.iterdir()) == ["f.json", "p0.json", "s0.json"]
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        aq.main(["cli"])  # the snapshot id is required


def test_short_ids_without_a_slash_stay_whole(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"r": [{"id": "A2"}, {"id": "A1"}]}))
    stage = {"from": "a.json", "path": "r.id", "batch": 9, "url": "https://e.org/?i={ids}",
             "name": "e{n}", "join": "|", "short": True}  # fmt: skip
    assert aq.expand(stage, tmp_path)[0]["url"] == "https://e.org/?i=A1|A2"


def test_the_command_line_keeps_observation_times_uses_its_default_root_and_adds_the_source_path(
    tmp_path, monkeypatch, capsys
):
    import sys

    spec = {
        **SPEC,
        "id": "cli2",
        "files": [{"url": "https://example.org/f", "name": "f.json", "observed": "2020-01"}],
        "pages": {
            "url": "https://example.org/p{n}",
            "name": "p{n}.json",
            "count": 1,
            "size": 1,
            "observed": "2021",
        },
        "stages": [
            {
                "from": "p*.json",
                "path": "ids",
                "batch": 5,
                "url": "https://example.org/s?i={ids}",
                "name": "s{n}.json",
                "join": "|",
                "observed": "2022",
            }
        ],
    }
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": [spec]}))
    monkeypatch.setattr(aq, "SOURCES", sources)
    monkeypatch.setattr(aq, "DEFAULT_ROOT", tmp_path / "default")
    real = aq.Snapshot.__init__

    def init(self, root, spec, snapshot_id, opener=aq.open_url, sleep=aq.time.sleep):
        real(
            self,
            root,
            spec,
            snapshot_id,
            opener=lambda u, n: b'{"ids": ["z"]}',
            sleep=lambda s: None,
        )

    monkeypatch.setattr(aq.Snapshot, "__init__", init)
    before = list(sys.path)
    assert aq.main(["cli2", "--snapshot", "t"]) == 0
    assert sys.path[0].endswith("/src") and sys.path[1:] == before
    sys.path[:] = before
    manifest = json.loads((tmp_path / "default" / "cli2" / "t" / "manifest.json").read_text())
    observed = {f["name"]: f["observed"] for f in manifest["files"]}
    assert observed == {"f.json": "2020-01", "p0.json": "2021", "s0.json": "2022"}
    spec_without_stages = {k: v for k, v in spec.items() if k != "stages"}
    sources.write_text(json.dumps({"sources": [spec_without_stages]}))
    assert aq.main(["cli2", "--snapshot", "u", "--root", str(tmp_path / "other")]) == 0
    sys.path[:] = before
    assert "cli2/u: 2 files" in capsys.readouterr().out
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        aq.main(["--help"])
    assert "Lightweight, reproducible acquisition" in capsys.readouterr().out
