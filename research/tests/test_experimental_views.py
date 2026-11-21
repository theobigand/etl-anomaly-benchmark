import json
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


def test_spend_views_share_one_schema_pseudonymise_suppliers_and_drop_free_text():
    raw = pd.DataFrame(
        {
            "﻿Department family": ["D", "D", None],
            "Entity": ["E", "E", "E"],
            "Paid Date": ["01/02/2024", "03/02/2024", None],
            "Expense type": ["Fees", "Fees", "x"],
            "Expense area": ["A", "A", "A"],
            "Supplier": ["Acme Ltd", "Acme Ltd", "J Smith"],
            "Transaction No": ["1", "2", "3"],
            "Amount": ["£1,200.50", "30", "bad"],
            "Description": ["john smith consulting", "x", "y"],
            "Post Code": ["AB1", "AB1", "CD2"],
        }
    )
    out = ev.spend_view(raw, "org")
    assert list(out.columns) == list(ev.SPEND_COLUMNS)
    assert len(out) == 2  # the row without a readable amount or date is dropped
    assert out["amount"].tolist() == [1200.5, 30.0]
    assert out["supplier_id"].nunique() == 1 and "Acme" not in out["supplier_id"].iloc[0]
    assert (out["organisation"] == "org").all()
    assert pd.api.types.is_datetime64_any_dtype(out["date"])


def test_spend_views_report_a_file_that_is_not_a_table_instead_of_guessing():
    import pytest

    with pytest.raises(ev.ViewError, match="columns"):
        ev.spend_view(pd.DataFrame({"x": [1]}), "org")


def test_read_spend_skips_banner_rows_and_refuses_spreadsheets_saved_as_csv():
    import pytest

    text = "Consolidated spend for May\n\nSupplier,Amount,Date,Transaction No\nA,1,01/01/2024,9\n"
    frame = ev.read_spend(text.encode("latin-1"))
    assert (
        list(frame.columns) == ["Supplier", "Amount", "Date", "Transaction No"] and len(frame) == 1
    )
    with pytest.raises(ev.ViewError, match="spreadsheet"):
        ev.read_spend(b"PK\x03\x04binary")
    with pytest.raises(ev.ViewError, match="header"):
        ev.read_spend(b"a,b\n1,2\n")


def test_food_views_drop_contributor_fields_at_every_depth_and_keep_the_structure():
    records = [
        {
            "_id": "2",
            "creator": "bob",
            "editors_tags": ["a"],
            "images": {"1": {"uploader": "bob", "sizes": {"100": {"h": 1}}}},
            "nutriments": {"fat": 1.0},
            "ingredients": [{"id": "x", "owner": "o"}, {"id": "y"}],
        },
        {"_id": "1", "last_editor": "al", "owner": "o"},
    ]
    out = ev.off_view(records)
    assert [r["_id"] for r in out] == ["1", "2"]
    text = json.dumps(out)
    for name in ("creator", "editors_tags", "uploader", "owner", "last_editor", "bob", "al"):
        assert name not in text
    assert out[1]["images"]["1"]["sizes"]["100"]["h"] == 1  # the nested structure stays
    assert out[1]["ingredients"] == [{"id": "x"}, {"id": "y"}]
    assert records[0]["creator"] == "bob"  # the input is not modified


def test_stack_views_drop_text_and_names_pseudonymise_users_and_keep_every_link():
    tables = {
        "Users": [
            {
                "Id": "5",
                "DisplayName": "Ann",
                "Location": "Paris",
                "AboutMe": "hi",
                "Reputation": "10",
                "CreationDate": "2020-01-01",
                "Views": "2",
                "UpVotes": "1",
                "DownVotes": "0",
            }
        ],
        "Posts": [
            {
                "Id": "1",
                "PostTypeId": "1",
                "OwnerUserId": "5",
                "Title": "t",
                "Body": "b",
                "Score": "3",
                "CreationDate": "2020-01-02",
                "AcceptedAnswerId": "2",
                "Tags": "|a|",
            },
            {
                "Id": "2",
                "PostTypeId": "2",
                "ParentId": "1",
                "OwnerUserId": "99",
                "Body": "c",
                "Score": "1",
                "CreationDate": "2020-01-03",
            },
        ],
        "Comments": [
            {
                "Id": "7",
                "PostId": "1",
                "UserId": "5",
                "Text": "secret",
                "Score": "0",
                "CreationDate": "x",
                "UserDisplayName": "Ann",
            }
        ],
        "Votes": [{"Id": "8", "PostId": "1", "VoteTypeId": "2", "CreationDate": "2020-01-04"}],
        "Badges": [{"Id": "9", "UserId": "5", "Name": "Teacher", "Date": "d", "Class": "3"}],
        "PostLinks": [
            {"Id": "3", "PostId": "1", "RelatedPostId": "2", "LinkTypeId": "1", "CreationDate": "d"}
        ],
    }
    views = ev.stack_views(tables, salt="s")
    text = "".join(f.to_csv() for f in views.values())
    for word in ("Ann", "Paris", "secret", "hi,", "Title"):
        assert word not in text
    assert "Body" not in views["Posts"].columns and "Text" not in views["Comments"].columns
    users = set(views["Users"]["user_id"])
    assert views["Posts"].loc[0, "owner_user_id"] in users  # a resolvable owner keeps its link
    assert (
        views["Comments"].loc[0, "user_id"] in users and views["Badges"].loc[0, "user_id"] in users
    )
    assert views["Posts"].loc[1, "owner_user_id"] == ev.pseudonym(
        "99", "s"
    )  # same mapping, orphan kept
    assert list(views["Votes"].columns) == ["vote_id", "post_id", "vote_type_id", "creation_date"]
    assert views["PostLinks"].loc[0, "related_post_id"] == "2"


def _release(i, supplier="s1", amount=100.0):
    return {
        "id": f"r{i}",
        "ocid": f"oc-{i}",
        "date": f"2022-05-{i % 28 + 1:02d}T00:00:00-04:00",
        "buyer": {"id": "b1", "name": "Dept"},
        "awards": [
            {
                "id": f"a{i}",
                "date": "2022-05-30T00:00:00-04:00",
                "items": [{"id": "", "quantity": 1, "description": "buy from Jean Tremblay"}],
                "value": {"amount": amount, "currency": "CAD"},
                "suppliers": [{"id": supplier, "name": "J Tremblay"}],
            }
        ],
        "tender": {"status": "complete", "procuringEntity": {"id": "p1", "name": "X"}},
        "parties": [
            {"id": "b1", "name": "Dept", "roles": ["buyer"], "address": {"streetAddress": "1 rue"}},
            {
                "id": supplier,
                "name": "J Tremblay",
                "roles": ["supplier"],
                "contactPoint": {"email": "a@b"},
            },
        ],
    }


def test_ocds_views_drop_names_addresses_and_free_text_but_keep_the_nesting_and_the_links():
    releases = [_release(i, supplier=f"s{i % 3}") for i in range(30)]
    nested, awards = ev.ocds_view(releases, salt="s", keep_modulo=1)
    text = json.dumps(nested)
    for word in (
        "Tremblay",
        "Dept",
        "rue",
        "a@b",
        "name",
        "address",
        "contactPoint",
        "description",
    ):
        assert word not in text
    first = nested[0]
    assert first["awards"][0]["value"]["amount"] == 100.0 and "items" in first["awards"][0]
    supplier = first["awards"][0]["suppliers"][0]["id"]
    assert supplier in {p["id"] for p in first["parties"]}  # the same pseudonym on both sides
    assert first["buyer"]["id"] == ev.pseudonym("b1", "s")
    assert list(awards.columns) == list(ev.AWARD_COLUMNS) and len(awards) == 30
    assert awards["supplier_id"].nunique() == 3 and awards["amount"].eq(100.0).all()


def test_ocds_sampling_keeps_whole_contracts_by_a_stable_hash_of_the_contract_id():
    releases = [_release(i) for i in range(400)]
    a, _ = ev.ocds_view(releases, salt="s", keep_modulo=10)
    b, _ = ev.ocds_view(list(reversed(releases)), salt="s", keep_modulo=10)
    assert sorted(r["ocid"] for r in a) == sorted(r["ocid"] for r in b)
    assert 10 < len(a) < 90
    assert [r["date"] for r in a] == sorted(r["date"] for r in a)  # fixed chronological order
