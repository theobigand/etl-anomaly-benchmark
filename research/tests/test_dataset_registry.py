"""Pool of public tabular datasets: pinned download, verification and per-file diagnostics."""

import hashlib
import io
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dataset_registry as dr  # noqa: E402


def _npz(x, y):
    buffer = io.BytesIO()
    np.savez_compressed(buffer, X=np.asarray(x, dtype=float), y=np.asarray(y))
    return buffer.getvalue()


def test_the_pool_lists_the_47_tabular_adbench_sets_with_unique_names():
    names = [entry["name"] for entry in dr.ADBENCH_TABULAR]
    assert len(names) == 47 == len(set(names))
    assert "fraud" in names and "mnist" in names and "CIFAR10" not in names
    assert all(entry["file"].endswith(".npz") for entry in dr.ADBENCH_TABULAR)


def test_the_diagnostics_describe_what_the_normalisation_policy_must_handle():
    x = np.array([[1.0, 5.0, np.nan], [1.0, 5.0, np.nan], [2.0, 5.0, 3.0], [4.0, 5.0, 7.0]])
    y = np.array([0, 0, 1, 0])
    info = dr.diagnose(x, y)
    assert info["rows"] == 4 and info["features"] == 3
    assert info["anomalies"] == 1 and info["anomaly_rate"] == pytest.approx(0.25)
    assert info["exact_duplicate_rows"] == 1
    assert info["constant_features"] == 1
    assert info["nan_cells"] == 2 and info["features_with_nan"] == 1


def test_labels_must_be_binary():
    with pytest.raises(ValueError, match="binary"):
        dr.diagnose(np.zeros((3, 2)), np.array([0, 1, 2]))
    with pytest.raises(ValueError, match="both classes"):
        dr.diagnose(np.zeros((3, 2)), np.array([0, 0, 0]))


def test_a_download_is_kept_only_when_it_matches_the_pinned_checksum(tmp_path):
    payload = _npz([[1, 2], [3, 4], [5, 6]], [0, 1, 0])
    good = hashlib.sha256(payload).hexdigest()
    path = dr.fetch(
        "https://raw.githubusercontent.com/x", good, tmp_path / "a.npz", opener=lambda u, n: payload
    )
    assert path.read_bytes() == payload
    with pytest.raises(dr.RegistryError, match="checksum"):
        dr.fetch(
            "https://raw.githubusercontent.com/x",
            "0" * 64,
            tmp_path / "b.npz",
            opener=lambda u, n: payload,
        )
    assert not (tmp_path / "b.npz").exists()


def test_without_a_pinned_checksum_the_first_download_is_recorded_not_trusted(tmp_path):
    payload = _npz([[1, 2], [3, 4]], [0, 1])
    path, digest = dr.fetch_unpinned(
        "https://raw.githubusercontent.com/x", tmp_path / "c.npz", opener=lambda u, n: payload
    )
    assert digest == hashlib.sha256(payload).hexdigest() and path.is_file()


@pytest.mark.parametrize(
    "url", ["http://raw.githubusercontent.com/x", "https://evil.example/x", "file:///etc/passwd"]
)
def test_only_https_urls_on_allowed_hosts_are_fetched(tmp_path, url):
    with pytest.raises(dr.RegistryError, match="not allowed"):
        dr.fetch_unpinned(url, tmp_path / "d.npz", opener=lambda u, n: b"")


def test_an_oversized_download_is_refused(tmp_path):
    with pytest.raises(dr.RegistryError, match="larger"):
        dr.fetch_unpinned(
            "https://raw.githubusercontent.com/x",
            tmp_path / "e.npz",
            opener=lambda u, n: b"x" * 20,
            limit=10,
        )


def test_the_inventory_row_carries_provenance_and_rights_fields_to_complete(tmp_path):
    payload = _npz(np.arange(12).reshape(6, 2), [0, 0, 0, 0, 1, 0])
    path = tmp_path / "t.npz"
    path.write_bytes(payload)
    row = dr.inventory_row(
        {"name": "toy", "file": "t.npz", "domain": "Test"},
        path,
        "https://raw.githubusercontent.com/x/t.npz",
    )
    assert row["sha256"] == hashlib.sha256(payload).hexdigest()
    assert row["source_url"].endswith("t.npz") and row["packaging_licence"] == "BSD-2-Clause"
    assert row["underlying_terms"] == "TO_CHECK" and row["decision"] == "PENDING"
    assert row["rows"] == 6 and row["anomalies"] == 1


# --- rights: UCI pages carry their licence in the page text ---

PAGE = (
    "<html>...This dataset is licensed under a Creative Commons Attribution 4.0 "
    "International (CC BY 4.0) license. This allows for the sharing...</html>"
)


def test_the_uci_licence_sentence_is_read_from_the_page():
    found = dr.uci_licence(PAGE)
    assert found["licence"] == "CC BY 4.0"
    assert "Creative Commons Attribution 4.0 International" in found["text"]


def test_a_page_without_a_licence_is_not_treated_as_open():
    found = dr.uci_licence("<html>nothing about terms</html>")
    assert found["licence"] is None


def test_the_uci_name_is_checked_against_the_api_before_the_licence_is_trusted():
    api = {"data": {"uci_id": 193, "name": "Cardiotocography", "dataset_doi": "10.24432/C51S4N"}}
    assert dr.check_uci_identity(api, 193, "Cardiotocography")["doi"] == "10.24432/C51S4N"
    with pytest.raises(dr.RegistryError, match="expected"):
        dr.check_uci_identity(api, 193, "Wine")


def test_rights_are_applied_to_the_inventory_without_inventing_terms():
    rows = [
        {"name": "cardio", "underlying_terms": "TO_CHECK", "decision": "PENDING"},
        {"name": "celeba", "underlying_terms": "TO_CHECK", "decision": "PENDING"},
    ]
    seen = {
        "cardio": {
            "licence": "CC BY 4.0",
            "text": "Creative Commons",
            "doi": "10.1/x",
            "url": "u",
            "checked": "2026-10-20",
        }
    }
    out = dr.apply_rights(rows, seen)
    assert out[0]["decision"] == "INCLUDE" and out[0]["underlying_terms"].startswith(
        "CC BY 4.0 (u, doi 10.1/x, read 2026-10-20"
    )
    assert out[1]["decision"] == "PENDING" and out[1]["underlying_terms"] == "TO_CHECK"


def test_every_uci_mapping_names_an_adbench_dataset():
    names = {e["name"] for e in dr.ADBENCH_TABULAR}
    assert set(dr.UCI_SOURCES) <= names and len(dr.UCI_SOURCES) >= 30
