"""Messages, call arguments, fields and the command of the dataset registry."""

import io
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dataset_registry as dr  # noqa: E402
from test_dataset_registry import PAGE, _npz  # noqa: E402


def test_diagnose_states_its_refusals_exactly_and_counts_features_with_missing_cells():
    x = np.array([[1.0, np.nan, 3.0], [2.0, np.nan, 3.0], [np.nan, 5.0, 3.0]])
    with pytest.raises(ValueError) as refused:
        dr.diagnose(x, np.array([0, 2, 1]))
    assert str(refused.value) == "labels must be binary (0/1)"
    with pytest.raises(ValueError) as refused:
        dr.diagnose(x, np.array([1, 1, 1]))
    assert str(refused.value) == "both classes are required"
    stats = dr.diagnose(x, np.array([0, 1, 0]))
    assert stats["features_with_nan"] == 3 - 1 and stats["nan_cells"] == 3


def test_a_feature_with_one_observed_value_is_constant_and_missing_cells_do_not_hide_it():
    x = np.array([[np.nan, 1.0], [7.0, 2.0], [np.nan, 3.0]])
    stats = dr.diagnose(x, np.array([0, 1, 0]))
    assert stats["constant_features"] == 1


def test_manual_rights_apply_only_to_pending_sets_and_default_the_licence_wording():
    name = next(n for n, e in dr.MANUAL_RIGHTS.items() if "licence" not in e)
    entry = dr.MANUAL_RIGHTS[name]
    [done] = dr.apply_manual_rights([{"name": name, "decision": "PENDING"}])
    assert done["decision"] == entry["decision"]
    assert done["underlying_terms"].startswith("no open licence: ")
    assert done["underlying_terms"].endswith(f"({entry['source']}, read {dr._READ})")
    settled = {"name": name, "decision": "INCLUDE", "underlying_terms": "kept"}
    assert dr.apply_manual_rights([settled]) == [settled]
    unknown = {"name": "no-such-set", "decision": "PENDING"}
    assert dr.apply_manual_rights([unknown]) == [unknown]


def test_the_inventory_row_names_the_pinned_commit_and_the_byte_size(tmp_path):
    raw = _npz([[1.0, 2.0], [3.0, 4.0]], [0, 1])
    path = tmp_path / "a.npz"
    path.write_bytes(raw)
    row = dr.inventory_row({"name": "a", "file": "a.npz", "domain": "d"}, path, "https://x")
    assert row["source_commit"] == dr.ADBENCH_COMMIT and row["bytes"] == len(raw)
    assert row["source_url"] == "https://x" and row["decision"] == "PENDING"


def test_a_download_is_requested_with_the_limit_and_may_have_exactly_that_size():
    seen = []

    def opener(url, limit):
        seen.append((url, limit))
        return b"x" * limit

    url = "https://raw.githubusercontent.com/a/b"
    assert dr._download(url, opener, 5) == b"xxxxx"
    assert seen == [(url, 5)]
    with pytest.raises(dr.RegistryError) as refused:
        dr._download(url, lambda u, limit: b"x" * (limit + 1), 5)
    assert str(refused.value) == "the download is larger than 5 bytes"
    with pytest.raises(dr.RegistryError) as refused:
        dr._download("http://raw.githubusercontent.com/a", opener, 5)
    assert str(refused.value) == (
        "http://raw.githubusercontent.com/a is not allowed (https and a listed host only)"
    )


def test_a_page_with_no_licence_sentence_returns_both_fields_as_none():
    assert dr.uci_licence("<p>nothing here</p>") == {"licence": None, "text": None}
    assert dr.uci_licence(PAGE).keys() == {"licence", "text"}


def test_the_network_reader_sends_a_user_agent_and_a_minute_timeout_and_reads_one_past_the_limit(
    monkeypatch,
):
    seen = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(request, timeout=None):
        seen.update(request=request, timeout=timeout)
        return Response(b"abcdefg")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert dr.open_url("https://raw.githubusercontent.com/x", 3) == b"abcd"
    assert seen["timeout"] == 60
    assert seen["request"].get_header("User-agent") == "etl-benchmark-registry"
    assert seen["request"].full_url == "https://raw.githubusercontent.com/x"


def test_the_text_reader_accepts_only_https_pages_of_the_uci_host_and_decodes_leniently(
    monkeypatch,
):
    seen = []
    monkeypatch.setattr(dr, "open_url", lambda url, limit: seen.append((url, limit)) or b"ok\xff")
    page = f"https://{dr.UCI_HOST}/dataset/1"
    assert dr._text(page) == "ok�"
    assert dr._text(page, 10) == "ok�"
    assert seen == [(page, 5_000_000), (page, 10)]
    for bad in (f"http://{dr.UCI_HOST}/x", "https://example.com/x", f"ftp://{dr.UCI_HOST}/x"):
        with pytest.raises(dr.RegistryError) as refused:
            dr._text(bad)
        assert str(refused.value) == f"{bad} is not allowed"


def _uci_fetch(licence=True):
    def fetch_text(url):
        if "/api/dataset" in url:
            uci_id = int(url.rsplit("=", 1)[1])
            return json.dumps(
                {
                    "data": {
                        "uci_id": uci_id,
                        "name": dr._UCI_SETS[uci_id],
                        "dataset_doi": f"10.0/{uci_id}",
                        "repository_url": f"https://{dr.UCI_HOST}/dataset/{uci_id}",
                    }
                }
            )
        return PAGE if licence else "<p>none</p>"

    return fetch_text


def test_rights_are_collected_per_adbench_name_with_the_identity_check_and_the_read_date():
    found = dr.collect_uci_rights(_uci_fetch())
    assert set(found) == set(dr.UCI_SOURCES)
    today = datetime.now(UTC).date().isoformat()
    thyroid = found["annthyroid"]
    assert thyroid == {
        "licence": "CC BY 4.0",
        "text": thyroid["text"],
        "doi": "10.0/102",
        "url": f"https://{dr.UCI_HOST}/dataset/102",
        "checked": today,
    }
    assert found["thyroid"]["url"] == thyroid["url"]
    none = dr.collect_uci_rights(_uci_fetch(licence=False))
    assert none["annthyroid"]["licence"] is None


def test_a_uci_api_answer_for_another_dataset_stops_the_collection():
    def wrong(url):
        if "/api/dataset" in url:
            return json.dumps({"data": {"uci_id": 1, "name": "other", "repository_url": "u"}})
        return PAGE

    with pytest.raises(dr.RegistryError):
        dr.collect_uci_rights(wrong)


def test_the_inventory_downloads_only_missing_files_into_a_created_destination(tmp_path):
    calls = []

    def opener(url, limit):
        calls.append((url, limit))
        return _npz([[1.0, 2.0], [3.0, 4.0]], [0, 1])

    destination = tmp_path / "new" / "adbench"
    rows = dr.build_inventory(destination, opener=opener)
    assert len(rows) == len(dr.ADBENCH_TABULAR) == len(calls)
    assert calls[0] == (dr.ADBENCH_BASE + dr.ADBENCH_TABULAR[0]["file"], dr.MAX_BYTES)
    assert rows[0]["source_url"] == calls[0][0] and rows[0]["name"] == dr.ADBENCH_TABULAR[0]["name"]
    calls.clear()
    assert len(dr.build_inventory(destination, opener=opener)) == len(rows)
    assert calls == []


def test_the_command_writes_the_sorted_inventory_and_reports_its_size(
    tmp_path, monkeypatch, capsys
):
    rows = [{"b": 1, "a": 2}]
    seen = {}
    monkeypatch.setattr(
        dr, "build_inventory", lambda destination: seen.setdefault("d", destination) and rows
    )
    out = tmp_path / "x" / "inv.json"
    out.parent.mkdir()
    assert dr.main(["--output", str(out)]) == 0
    assert seen["d"] == dr.ROOT / "data" / "adbench"
    assert out.read_text() == json.dumps(rows, indent=2, sort_keys=True) + "\n"
    assert capsys.readouterr().out == "inventoried 1 datasets\n"
    with pytest.raises(SystemExit) as stop:
        dr.main([])
    assert stop.value.code == 2


def test_the_rights_option_applies_the_uci_statements_then_the_manual_decisions(
    tmp_path, monkeypatch
):
    order = []
    monkeypatch.setattr(dr, "build_inventory", lambda destination: [{"name": "r"}])
    monkeypatch.setattr(dr, "collect_uci_rights", lambda: order.append("collect") or {"seen": 1})
    monkeypatch.setattr(
        dr,
        "apply_rights",
        lambda rows, seen: order.append(("rights", seen)) or [{"name": "r", "s": 1}],
    )
    monkeypatch.setattr(
        dr, "apply_manual_rights", lambda rows: order.append("manual") or [{**rows[0], "m": 1}]
    )
    out = tmp_path / "inv.json"
    assert dr.main(["--output", str(out), "--rights", "--destination", str(tmp_path)]) == 0
    assert order == ["collect", ("rights", {"seen": 1}), "manual"]
    assert json.loads(out.read_text()) == [{"name": "r", "s": 1, "m": 1}]


def test_the_destination_is_read_as_a_path_and_the_rights_are_given_the_inventory(
    tmp_path, monkeypatch
):
    seen = {}
    monkeypatch.setattr(dr, "build_inventory", lambda destination: seen.update(d=destination) or [])
    monkeypatch.setattr(dr, "collect_uci_rights", lambda: {})
    monkeypatch.setattr(dr, "apply_rights", lambda rows, found: seen.update(rows=rows) or rows)
    monkeypatch.setattr(dr, "apply_manual_rights", lambda rows: rows)
    dr.main(["--output", str(tmp_path / "o.json"), "--destination", str(tmp_path), "--rights"])
    assert seen["d"] == tmp_path and isinstance(seen["d"], Path) and seen["rows"] == []


def test_the_help_describes_the_pool_and_the_rights_option(capsys, monkeypatch):
    monkeypatch.setenv("COLUMNS", "300")
    with pytest.raises(SystemExit):
        dr.main(["--help"])
    lines = [" ".join(line.split()) for line in capsys.readouterr().out.splitlines()]
    assert any(line.startswith("Pool of public tabular anomaly datasets") for line in lines)
    assert any(line.endswith("read the UCI licence statements") for line in lines)


def test_the_licence_is_dated_with_the_utc_day_it_was_read(monkeypatch):
    seen = []

    class Clock:
        @staticmethod
        def now(tz=None):
            seen.append(tz)
            return datetime(2026, 1, 2, 3, tzinfo=UTC)

    monkeypatch.setattr(dr, "datetime", Clock)
    monkeypatch.setattr(dr, "_UCI_SETS", {})
    monkeypatch.setattr(dr, "UCI_SOURCES", {})
    dr.collect_uci_rights(lambda url: "")
    assert seen == [UTC]
