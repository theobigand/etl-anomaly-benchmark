import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import experimental_views as ev  # noqa: E402


def test_pseudonyms_are_stable_salted_and_keep_missing_values_missing():
    a = ev.pseudonym("https://openalex.org/A1", "s1")
    assert a == ev.pseudonym("https://openalex.org/A1", "s1") and len(a) == 16
    assert a != ev.pseudonym("https://openalex.org/A1", "s2")
    assert a != ev.pseudonym("https://openalex.org/A2", "s1")
    assert ev.pseudonym(None, "s1") is None


WORKS = [
    {
        "id": "https://openalex.org/W1",
        "publication_year": 2023,
        "type": "article",
        "cited_by_count": 3,
        "language": "en",
        "open_access": {"is_oa": True},
        "referenced_works": ["x", "y"],
        "primary_location": {"source": {"id": "https://openalex.org/S1"}},
        "authorships": [
            {
                "author_position": "first",
                "author": {"id": "https://openalex.org/A1", "display_name": "Ann", "orcid": "o"},
                "institutions": [{"id": "https://openalex.org/I1", "display_name": "U"}],
            },
            {
                "author_position": "last",
                "author": {"id": "https://openalex.org/A2"},
                "institutions": [],
            },
        ],
    }
]
AUTHORS = [
    {"id": "https://openalex.org/A1", "works_count": 4, "cited_by_count": 9, "display_name": "Ann"},
    {"id": "https://openalex.org/A2", "works_count": 1, "cited_by_count": 0},
]
INSTS = [
    {"id": "https://openalex.org/I1", "country_code": "FR", "type": "education", "works_count": 7}
]
SRCS = [{"id": "https://openalex.org/S1", "type": "journal", "works_count": 5, "is_oa": False}]


def test_openalex_views_drop_names_and_orcid_and_keep_every_foreign_key_resolvable():
    tables = ev.openalex_views(WORKS, AUTHORS, INSTS, SRCS, salt="s")
    for frame in tables.values():
        assert not {"display_name", "orcid"} & set(frame.columns)
    assert set(tables) == {"works", "authorships", "authors", "institutions", "sources"}
    assert "A1" not in "".join(tables["authors"]["author_id"])  # pseudonymised
    assert set(tables["authorships"]["author_id"]) <= set(tables["authors"]["author_id"])
    assert set(tables["authorships"]["work_id"]) <= set(tables["works"]["work_id"])
    assert set(tables["authorships"]["institution_id"].dropna()) <= set(
        tables["institutions"]["institution_id"]
    )
    assert tables["works"].loc[0, "n_references"] == 2 and tables["works"].loc[0, "n_authors"] == 2
    assert len(tables["authorships"]) == 2  # an author without institution keeps one row


def test_a_tsf_becomes_a_wide_frame_on_a_regular_time_index():
    parsed = {
        "frequency": "hourly",
        "series": [
            {"name": "a", "start": "2020-01-01 00-00-00", "values": [1.0, 2.0, None]},
            {"name": "b", "start": "2020-01-01 01-00-00", "values": [5.0, 6.0]},
        ],
    }
    frame = ev.tsf_wide(parsed)
    assert list(frame.columns) == ["a", "b"]
    assert frame.index[0] == pd.Timestamp("2020-01-01 00:00") and len(frame) == 3
    assert pd.isna(frame.loc[pd.Timestamp("2020-01-01 00:00"), "b"])
    assert frame.loc[pd.Timestamp("2020-01-01 02:00"), "b"] == 6.0


def test_event_reports_lose_identifying_fields_and_sort_deterministically():
    records = [
        {
            "safetyreportid": "2",
            "receivedate": "20240102",
            "companynumb": "c",
            "authoritynumb": "a",
            "patient": {"patientsex": "1"},
        },
        {"safetyreportid": "1", "receivedate": "20240102", "companynumb": "c2"},
        {"safetyreportid": "0", "receivedate": "20240101"},
    ]
    out = ev.faers_view(records)
    assert [r["safetyreportid"] for r in out] == ["0", "1", "2"]
    assert all("companynumb" not in r and "authoritynumb" not in r for r in out)
    assert out[2]["patient"] == {"patientsex": "1"}


def test_log_views_drop_the_message_text_that_can_hold_addresses_and_hosts():
    frame = pd.DataFrame(
        {
            "LineId": [1],
            "Time": ["t"],
            "Level": ["info"],
            "Content": ["from 10.0.0.1"],
            "EventId": ["E1"],
            "EventTemplate": ["from <*>"],
        }
    )
    out = ev.loghub_view(frame)
    assert list(out.columns) == ["LineId", "Time", "Level", "EventId"]


def test_log_views_keep_only_the_listed_columns_that_exist_and_never_node_names():
    frame = pd.DataFrame(
        {
            "LineId": [1],
            "Label": ["-"],
            "Timestamp": [5],
            "Node": ["R01-M0"],
            "Content": ["x"],
            "EventId": ["E2"],
        }
    )
    assert list(ev.loghub_view(frame).columns) == ["LineId", "Label", "Timestamp", "EventId"]
