import json
import sys
from pathlib import Path

import pandas as pd
import pytest

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
    nested, awards, contracts = ev.ocds_view(releases, salt="s", keep_modulo=1)
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
    a, _, _ = ev.ocds_view(releases, salt="s", keep_modulo=10)
    b, _, _ = ev.ocds_view(list(reversed(releases)), salt="s", keep_modulo=10)
    assert sorted(r["ocid"] for r in a) == sorted(r["ocid"] for r in b)
    assert 10 < len(a) < 90
    assert [r["date"] for r in a] == sorted(r["date"] for r in a)  # fixed chronological order


def test_ocds_contracts_link_to_their_awards_and_a_process_without_awards_adds_no_rows():
    r = _release(1)
    r["contracts"] = [
        {"id": "c1", "awardID": "a1", "dateSigned": "2022-06-01T00:00:00Z", "title": "Jean T",
         "value": {"amount": 90.0, "currency": "CAD"}},
        {"id": "c2", "awardID": "zzz", "value": {"amount": 5.0, "currency": "CAD"}},
    ]  # fmt: skip
    bare = {
        "id": "r2",
        "ocid": "oc-bare",
        "date": "2022-01-01",
        "buyer": {"id": "b1"},
        "parties": [],
    }
    nested, awards, contracts = ev.ocds_view([r, bare], salt="s", keep_modulo=1)
    assert len(nested) == 2 and len(awards) == 1
    assert list(contracts.columns) == list(ev.CONTRACT_COLUMNS) and len(contracts) == 2
    assert contracts["award_id"].tolist() == ["a1", "zzz"]
    assert "Jean T" not in json.dumps(nested)  # titles are free text
    assert contracts.loc[0, "amount"] == 90.0 and contracts.loc[0, "date_signed"].startswith(
        "2022-06-01"
    )


def test_trip_views_drop_coordinates_and_names_and_derive_the_duration_without_hiding_bad_rows():
    raw = pd.DataFrame(
        {
            "ride_id": ["a", "b", "c"],
            "rideable_type": ["classic_bike", "electric_bike", "classic_bike"],
            "started_at": ["2024-09-01 10:00:00", "2024-09-01 11:00:00", "2024-09-01 12:00:00"],
            "ended_at": ["2024-09-01 10:30:00", "2024-09-01 10:00:00", "not a time"],
            "start_station_name": ["X st", "Y st", "Z st"],
            "start_station_id": ["31001", "31002", None],
            "end_station_name": ["A", "B", "C"],
            "end_station_id": ["31005", None, None],
            "start_lat": [38.9, 38.8, 38.7],
            "start_lng": [-77.0, -77.1, -77.2],
            "end_lat": [38.9, None, None],
            "end_lng": [-77.0, None, None],
            "member_casual": ["member", "casual", "member"],
        }
    )
    out = ev.trip_view(raw)
    assert list(out.columns) == list(ev.TRIP_COLUMNS)
    text = out.to_csv()
    for word in ("X st", "38.9", "-77"):
        assert word not in text
    assert len(out) == 3  # nothing is silently dropped
    assert out["duration_min"].iloc[0] == 30.0
    assert out["duration_min"].iloc[1] == -60.0  # an impossible trip stays visible
    assert pd.isna(out["duration_min"].iloc[2])
    import pytest

    with pytest.raises(ev.ViewError, match="columns"):
        ev.trip_view(pd.DataFrame({"x": [1]}))


def test_zip_members_skip_macos_resource_forks_and_keep_real_csv_files():
    names = ["a.csv", "__MACOSX/._a.csv", "dir/._b.csv", "dir/b.csv", "readme.txt"]
    assert ev.csv_members(names) == ["a.csv", "dir/b.csv"]


# --- every builder, on a tiny raw tree, with exact outputs and exact input paths ---------------

SNAP = "2026-11-21"


def _w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _ocds_release(i, supplier="s1"):
    return {
        "id": f"r{i}",
        "ocid": f"oc-{i}",
        "date": f"2022-05-{i % 28 + 1:02d}",
        "buyer": {"id": "b"},
        "awards": [
            {
                "id": f"a{i}",
                "date": "2022-05-30",
                "value": {"amount": 10.0, "currency": "CAD"},
                "suppliers": [{"id": supplier}],
            }
        ],
        "parties": [{"id": "b"}, {"id": supplier}],
    }


def _raw_tree(tmp_path, monkeypatch):
    import gzip
    import json
    import subprocess
    import zipfile
    from pathlib import Path

    root = tmp_path / "acquired"
    raw = root / "openalex_works" / SNAP / "raw"
    _w(
        raw / "works_1.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/W2",
                        "publication_year": 2022,
                        "type": "article",
                        "cited_by_count": 1,
                        "language": "fr",
                        "open_access": {"is_oa": False},
                        "referenced_works": [],
                        "primary_location": None,
                        "authorships": [],
                    }
                ]
            }
        ),
    )
    _w(
        raw / "works_0.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/W1",
                        "publication_year": 2023,
                        "type": "article",
                        "cited_by_count": 3,
                        "language": "en",
                        "open_access": {"is_oa": True},
                        "referenced_works": ["x", "y"],
                        "primary_location": {"source": {"id": "https://o/S1"}},
                        "authorships": [
                            {
                                "author_position": "first",
                                "author": {"id": "https://o/A1", "display_name": "Ann"},
                                "institutions": [{"id": "https://o/I1"}],
                            }
                        ],
                    }
                ]
            }
        ),
    )
    _w(
        raw / "authors_0.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/A1",
                        "works_count": 4,
                        "cited_by_count": 9,
                        "display_name": "Ann",
                    }
                ]
            }
        ),
    )
    _w(
        raw / "institutions_0.json",
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://o/I1",
                        "country_code": "FR",
                        "type": "education",
                        "works_count": 7,
                    }
                ]
            }
        ),
    )
    _w(
        raw / "sources_0.json",
        json.dumps(
            {
                "results": [
                    {"id": "https://o/S1", "type": "journal", "works_count": 5, "is_oa": False}
                ]
            }
        ),
    )
    tsf = (
        "@attribute series_name string\n@attribute start_timestamp date\n@frequency hourly\n@data\n"
    )
    tsf += "a:2020-01-01 00-00-00:1,2\nb:2020-01-01 01-00-00:5,6\n"
    archive = root / "monash_zenodo" / SNAP / "raw" / "4656626_pedestrian_counts_dataset.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x.tsf", tsf)
    events = root / "openfda_drug_event" / SNAP / "raw"
    _w(
        events / "event_1.json",
        json.dumps(
            {
                "results": [
                    {
                        "safetyreportid": "2",
                        "receivedate": "20240102",
                        "companynumb": "c",
                        "patient": {"s": 1},
                    }
                ]
            }
        ),
    )
    _w(
        events / "event_0.json",
        json.dumps(
            {"results": [{"safetyreportid": "1", "receivedate": "20240101", "authoritynumb": "a"}]}
        ),
    )
    head = "LineId,Time,Level,Content,EventId,EventTemplate\n"
    _w(tmp_path / "loghub" / "B.csv", head + "1,t,info,from 10.0.0.1,E1,from <*>\n")
    _w(tmp_path / "loghub" / "A.csv", head + "1,t,warn,x,E2,x\n2,t2,warn,y,E3,y\n")
    food = root / "openfoodfacts_products" / SNAP / "raw" / "d.json.gz"
    food.parent.mkdir(parents=True)
    with gzip.open(food, "wt") as handle:
        handle.write(
            json.dumps({"_id": "2", "creator": "bob", "a": {"uploader": "u", "k": 1}}) + "\n\n"
        )
        handle.write(json.dumps({"_id": "1", "owner": "o"}) + "\n")
    dump = root / "stackexchange_dump" / SNAP / "raw"
    dump.mkdir(parents=True)
    (dump / "zed.stackexchange.com.7z").write_bytes(b"x")
    (dump / "abc.stackexchange.com.7z").write_bytes(b"x")
    xml = {
        "Users": '<users><row Id="5" DisplayName="Ann" Reputation="10" CreationDate="d" Views="1" UpVotes="2" DownVotes="3"/></users>',  # noqa: E501
        "Posts": '<posts><row Id="1" PostTypeId="1" OwnerUserId="5" Title="t" Body="b" Score="3" CreationDate="d"/></posts>',  # noqa: E501
    }

    def fake_run(command, check):
        target = Path(command[command.index("-C") + 1])
        for name, text in xml.items():
            (target / f"{name}.xml").write_text(text)

    monkeypatch.setattr(subprocess, "run", fake_run)
    for source in ("ocds_montreal", "ocds_georgia", "ocds_zambia"):
        path = root / source / SNAP / "raw" / "full.jsonl.gz"
        path.parent.mkdir(parents=True)
        with gzip.open(path, "wt") as handle:
            for i in range(60):
                handle.write(json.dumps(_ocds_release(i)) + "\n")
    csv = (
        "ride_id,rideable_type,started_at,ended_at,start_station_id,end_station_id,member_casual\n"
    )
    csv += "r2,e,2024-09-02 10:00:00,2024-09-02 10:10:00,1,2,member\n"
    csv += "r1,c,2024-09-01 09:00:00,2024-09-01 09:30:00,3,,casual\n"
    for source in ("bikeshare_capital", "bikeshare_jc"):
        folder = root / source / SNAP / "raw"
        folder.mkdir(parents=True)
        with zipfile.ZipFile(folder / "b.zip", "w") as z:
            z.writestr("a.csv", csv)
            z.writestr("__MACOSX/._a.csv", "junk")
        with zipfile.ZipFile(folder / "a.zip", "w") as z:
            z.writestr("c.csv", csv.replace("r2", "r3"))
    import io
    import tarfile

    jobs = root / "slurm_ccin2p3" / SNAP / "raw"
    jobs.mkdir(parents=True)
    data = _jobs().to_csv(sep="\t", index=False).encode()
    with tarfile.open(jobs / "07.tsv.tar.gz", "w:gz") as tar:
        info = tarfile.TarInfo("07.tsv")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    _w(
        root / "clinicaltrials_v2" / SNAP / "raw" / "studies_2023-01.json",
        json.dumps({"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}]}),
    )
    _w(
        root / "crossref_works" / SNAP / "raw" / "sample_00.json",
        json.dumps({"message": {"items": [{"DOI": "10.1/a"}]}}),
    )
    import gzip as _gzip

    borg = root / "google_cluster_2019a" / SNAP / "raw"
    borg.mkdir(parents=True)
    (borg / "collection_events_head.json.gz").write_bytes(
        _gzip.compress((_collection_line(1, 1, 0) + "\n").encode())
    )
    (borg / "instance_events_head.json.gz").write_bytes(
        _gzip.compress((_instance_line(1, 0, 1, 0) + "\n").encode())
    )
    good = "Department family,Entity,Date,Expense type,Expense area,Supplier,Transaction number,Amount\n"  # noqa: E501
    good += 'D,E,01/02/2024,Fees,A,Acme,2,"£1,000.50"\nD,E,03/02/2024,Fees,A,Beta,1,30\n'
    _w(root / "ukspend_mhra" / SNAP / "raw" / "00.csv", good)
    _w(
        root / "ukspend_nhsbsa" / SNAP / "raw" / "00.csv",
        "Banner\n" + good.replace("Department family", "Dept"),
    )
    (root / "ukspend_nice" / SNAP / "raw").mkdir(parents=True)
    (root / "ukspend_nice" / SNAP / "raw" / "00.csv").write_bytes(b"PK\x03\x04")
    _w(root / "ukspend_ofsted" / SNAP / "raw" / "00.csv", "a,b\n1,2\n")
    return root


def _accessed(monkeypatch, root):
    """Exact path strings under ``root`` that the code opens or lists."""
    import builtins
    import os

    seen = []
    real_open = builtins.open
    base = str(root.parent)

    def spy_open(file, *a, **k):
        if isinstance(file, str | os.PathLike) and str(file).startswith(base):
            seen.append(str(file)[len(base) + 1 :])
        return real_open(file, *a, **k)

    import io

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(io, "open", spy_open)
    return seen


def _sha(path):
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_openalex_builder_writes_five_sorted_tables_and_reads_the_documented_paths(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_openalex(root, out, manifest)
    reads = sorted(set(p for p in seen if p.startswith("acquired/")))
    base = "acquired/openalex_works/2026-11-21/raw"
    assert reads == sorted(
        [
            *(f"{base}/{n}_0.json" for n in ("authors", "institutions", "sources", "works")),
        ]
        + [f"{base}/works_1.json"]
    )
    texts = {f.name: f.read_text() for f in (out / "openalex").glob("*.csv")}
    assert texts == {
        "authors.csv": "author_id,works_count,cited_by_count\nd62d7796a28c16a2,4,9\n",
        "authorships.csv": "work_id,author_id,institution_id,position\nW1,d62d7796a28c16a2,I1,first\n",  # noqa: E501
        "institutions.csv": "institution_id,country_code,type,works_count\nI1,FR,education,7\n",
        "sources.csv": "source_id,type,works_count,is_oa\nS1,journal,5,False\n",
        "works.csv": "work_id,year,type,cited_by_count,language,is_oa,source_id,n_references,n_authors\n"  # noqa: E501
        "W1,2023,article,3,en,True,S1,2,1\nW2,2022,article,1,fr,False,,0,0\n",
    }
    view = manifest["openalex"]
    assert view["files"] == {
        n: {"sha256": _sha(out / "openalex" / n), "rows": rows}
        for n, rows in (
            ("authors.csv", 1),
            ("authorships.csv", 1),
            ("institutions.csv", 1),
            ("sources.csv", 1),
            ("works.csv", 2),
        )
    }
    assert {k: v for k, v in view.items() if k != "files"} == {
        "dropped": ["display_name", "orcid", "observed_orcids", "raw works ids of authors"],
        "pseudonymised": ["author_id"],
        "salt_label": ev.SALT,
        "source_snapshot": "openalex_works/2026-11-21",
    }
    assert list(manifest) == ["openalex"]


def _record_of(manifest, view, out_dir):
    entry = manifest[view]
    return {n: {"sha256": _sha(out_dir / n), "rows": f["rows"]} for n, f in entry["files"].items()}


def test_the_monash_faers_and_log_builders_have_exact_outputs_and_manifests(tmp_path, monkeypatch):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_monash(root, out, manifest)
    ev._build_faers(root, out, manifest)
    ev._build_loghub(root, out, manifest)
    reads = sorted(set(seen))
    assert "acquired/monash_zenodo/2026-11-21/raw/4656626_pedestrian_counts_dataset.zip" in reads
    assert "acquired/openfda_drug_event/2026-11-21/raw/event_0.json" in reads
    assert "acquired/openfda_drug_event/2026-11-21/raw/event_1.json" in reads
    assert "loghub/A.csv" in reads and "loghub/B.csv" in reads
    assert (out / "monash_pedestrian" / "wide.csv").read_text() == (
        "timestamp,a,b\n2020-01-01 00:00:00,1.0,\n2020-01-01 01:00:00,2.0,5.0\n2020-01-01 02:00:00,,6.0\n"  # noqa: E501
    )
    assert (out / "openfda_drug_event" / "events.jsonl").read_text() == (
        '{"receivedate": "20240101", "safetyreportid": "1"}\n'
        '{"patient": {"s": 1}, "receivedate": "20240102", "safetyreportid": "2"}\n'
    )
    assert (
        out / "loghub" / "A.csv"
    ).read_text() == "LineId,Time,Level,EventId\n1,t,warn,E2\n2,t2,warn,E3\n"
    assert (out / "loghub" / "B.csv").read_text() == "LineId,Time,Level,EventId\n1,t,info,E1\n"
    assert manifest["monash_pedestrian"] == {
        "files": _record_of(manifest, "monash_pedestrian", out / "monash_pedestrian")
        | {"wide.csv": {"sha256": _sha(out / "monash_pedestrian" / "wide.csv"), "rows": 3}},
        "dropped": [],
        "pseudonymised": [],
        "source_snapshot": "monash_zenodo/2026-11-21",
    }
    assert manifest["openfda_drug_event"]["files"] == {
        "events.jsonl": {"sha256": _sha(out / "openfda_drug_event" / "events.jsonl"), "rows": 2}
    }
    assert {k: v for k, v in manifest["openfda_drug_event"].items() if k != "files"} == {
        "dropped": ["companynumb", "authoritynumb"],
        "pseudonymised": [],
        "source_snapshot": "openfda_drug_event/2026-11-21",
    }
    assert manifest["loghub"]["files"] == {
        "A.csv": {"sha256": _sha(out / "loghub" / "A.csv"), "rows": 2},
        "B.csv": {"sha256": _sha(out / "loghub" / "B.csv"), "rows": 1},
    }
    assert {k: v for k, v in manifest["loghub"].items() if k != "files"} == {
        "dropped": ["Content", "EventTemplate"],
        "pseudonymised": [],
        "source_snapshot": "loghub@dd61d09",
    }


def test_the_food_and_stack_builders_have_exact_outputs_and_manifests(tmp_path, monkeypatch):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_food(root, out, manifest)
    ev._build_stack(root, out, manifest)
    assert "acquired/openfoodfacts_products/2026-11-21/raw/d.json.gz" in seen
    assert (
        out / "openfoodfacts" / "products.jsonl"
    ).read_text() == '{"_id": "1"}\n{"_id": "2", "a": {"k": 1}}\n'
    assert manifest["openfoodfacts"]["files"]["products.jsonl"]["rows"] == 2
    assert {k: v for k, v in manifest["openfoodfacts"].items() if k != "files"} == {
        "dropped": sorted(ev.OFF_DROP),
        "pseudonymised": [],
        "source_snapshot": "openfoodfacts_products/2026-11-21",
    }
    for site in ("abc", "zed"):
        folder = out / "stackexchange" / site
        assert (folder / "Users.csv").read_text() == (
            "user_id,reputation,creation_date,views,up_votes,down_votes\n3e9ef5a6b3d5aa75,10,d,1,2,3\n"
        )
        assert (folder / "Posts.csv").read_text() == (
            "post_id,post_type_id,parent_id,accepted_answer_id,creation_date,score,view_count,answer_count,"
            "comment_count,tags,owner_user_id\n1,1,,,d,3,,,,,3e9ef5a6b3d5aa75\n"
        )
        assert (folder / "Votes.csv").read_text() == "vote_id,post_id,vote_type_id,creation_date\n"
    files = manifest["stackexchange"]["files"]
    assert list(files) == [
        f"{s}/{t}.csv"
        for s in ("abc", "zed")
        for t in ("Users", "Posts", "Comments", "Votes", "Badges", "PostLinks")
    ]
    assert files["abc/Users.csv"] == {
        "sha256": _sha(out / "stackexchange" / "abc" / "Users.csv"),
        "rows": 1,
    }
    assert files["zed/Comments.csv"]["rows"] == 0
    assert {k: v for k, v in manifest["stackexchange"].items() if k != "files"} == {
        "dropped": [
            "Title",
            "Body",
            "Text",
            "DisplayName",
            "Location",
            "AboutMe",
            "WebsiteUrl",
            "profile fields",
        ],
        "pseudonymised": ["user_id", "owner_user_id"],
        "salt_label": ev.SALT,
        "source_snapshot": "stackexchange_dump/2026-11-21",
        "notes": "CC BY-SA: a redistributed derived database needs attribution and the same licence",  # noqa: E501
    }
    assert (
        "acquired/stackexchange_dump/2026-11-21/raw/abc.stackexchange.com.7z" not in seen
    )  # extractor is mocked


def test_the_procurement_builder_writes_three_sources_with_whole_hash_sampled_processes(
    tmp_path, monkeypatch
):
    import json

    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    manifest = {}
    ev._build_ocds(root, out, manifest)
    assert list(manifest) == ["ocds_montreal", "ocds_georgia", "ocds_zambia"]
    for source in manifest:
        folder = out / source
        releases = [
            json.loads(line) for line in (folder / "releases.jsonl").read_text().splitlines()
        ]
        assert [r["date"] for r in releases] == sorted(r["date"] for r in releases)
        assert 1 <= len(releases) < 60 and all("name" not in r["buyer"] for r in releases)
        assert (folder / "awards.csv").read_text().splitlines()[0] == (
            "ocid,award_id,date,amount,currency,supplier_id,buyer_id,method"
        )
        assert (
            folder / "contracts.csv"
        ).read_text() == "ocid,contract_id,award_id,date_signed,amount,currency\n"
        files = manifest[source]["files"]
        assert list(files) == ["releases.jsonl", "awards.csv", "contracts.csv"]
        assert files["releases.jsonl"] == {
            "sha256": _sha(folder / "releases.jsonl"),
            "rows": len(releases),
        }
        assert files["awards.csv"]["rows"] == len(releases) and files["contracts.csv"]["rows"] == 0
        assert {k: v for k, v in manifest[source].items() if k != "files"} == {
            "dropped": sorted(ev.OCDS_DROP),
            "pseudonymised": ["party ids"],
            "salt_label": ev.SALT,
            "sampling": "contracting processes with sha256(ocid) % 10 == 0, whole processes, by date",  # noqa: E501
            "source_snapshot": f"{source}/2026-11-21",
        }


def test_the_bikeshare_builder_skips_resource_forks_and_sorts_by_start_then_ride(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_bikeshare(root, out, manifest)
    expected = (
        "ride_id,rideable_type,started_at,ended_at,duration_min,start_station_id,end_station_id,member_casual\n"
        "r1,c,2024-09-01 09:00:00,2024-09-01 09:30:00,30.0,3,,casual\n"
        "r1,c,2024-09-01 09:00:00,2024-09-01 09:30:00,30.0,3,,casual\n"
        "r2,e,2024-09-02 10:00:00,2024-09-02 10:10:00,10.0,1,2,member\n"
        "r3,e,2024-09-02 10:00:00,2024-09-02 10:10:00,10.0,1,2,member\n"
    )
    for source in ("bikeshare_capital", "bikeshare_jc"):
        assert (out / source / "trips.csv").read_text() == expected
        assert manifest[source]["files"] == {
            "trips.csv": {"sha256": _sha(out / source / "trips.csv"), "rows": 4}
        }
        assert {k: v for k, v in manifest[source].items() if k != "files"} == {
            "dropped": ["station names", "start and end coordinates"],
            "pseudonymised": [],
            "source_snapshot": f"{source}/2026-11-21",
        }
        assert f"acquired/{source}/2026-11-21/raw/a.zip" in seen
        assert f"acquired/{source}/2026-11-21/raw/b.zip" in seen
    assert list(manifest) == ["bikeshare_capital", "bikeshare_jc"]


def test_the_spending_builder_reports_files_it_cannot_read_instead_of_hiding_them(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "out"
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_ukspend(root, out, manifest)
    rows = "organisation,date,expense_type,expense_area,supplier_id,transaction_no,amount\n"
    for org in ("mhra", "nhsbsa"):
        assert (out / "ukspend" / f"{org}.csv").read_text() == (
            rows + f"{org},2024-02-01,Fees,A,4f37571c7ae9051b,2,1000.5\n"
            f"{org},2024-02-03,Fees,A,7f062e7195549622,1,30.0\n"
        )
    assert sorted(p.name for p in (out / "ukspend").iterdir()) == ["mhra.csv", "nhsbsa.csv"]
    view = manifest["ukspend"]
    assert list(view["files"]) == ["mhra.csv", "nhsbsa.csv"]
    assert view["files"]["mhra.csv"] == {"sha256": _sha(out / "ukspend" / "mhra.csv"), "rows": 2}
    assert view["skipped"] == {
        "nice": ["00.csv: a spreadsheet saved with a .csv name"],
        "ofsted": ["00.csv: no header line with a supplier column in the first 15 lines"],
    }
    assert {k: v for k, v in view.items() if k not in ("files", "skipped")} == {
        "dropped": [
            "Description",
            "post code",
            "supplier type",
            "VAT number",
            "contract and project codes",
        ],
        "pseudonymised": ["supplier_id"],
        "salt_label": ev.SALT,
        "source_snapshot": "ukspend_*/2026-11-21",
    }
    for org in ("mhra", "nhsbsa", "nice", "ofsted"):
        assert f"acquired/ukspend_{org}/2026-11-21/raw/00.csv" in seen
    assert not any(
        "charity_commission" in p and p.endswith(".csv") for p in seen
    )  # no files: nothing read


def test_build_runs_every_builder_in_order_and_main_writes_the_manifest(
    tmp_path, monkeypatch, capsys
):
    import json

    root = _raw_tree(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ev, "SERIES_SPECS", {"uci:5": {"dir": "pool", "time": ["t"], "format": "%Y-%m-%d"}}
    )
    _w(tmp_path / "pool" / "5.csv", "t,v\n2020-01-01,1\n")
    _w(root / "zen_p" / SNAP / "raw" / "p.csv", "d,k,v\n2020-01-01,a,1\n")
    monkeypatch.setattr(
        ev,
        "PANEL_SPECS",
        {
            "p": {
                "source": "zen_p",
                "file": "p.csv",
                "sep": ",",
                "time": ["d"],
                "format": "%Y-%m-%d",
                "keys": ["k"],
            }
        },
    )
    _w(root / "zen_t" / SNAP / "raw" / "a.csv", "k\tv\n1\t2\n")
    monkeypatch.setattr(
        ev,
        "TABLE_SETS",
        {"zen_t": {"dropped": [], "tables": {"a": {"keep": ["k"]}}, "relations": []}},
    )
    import zipfile as _zf

    import pyarrow as _pa
    import pyarrow.parquet as _pq

    surf = root / "zen_surf_lisa_slurm" / SNAP / "raw"
    surf.mkdir(parents=True)
    _pq.write_table(
        _pa.Table.from_pandas(_surf_frame(), preserve_index=False), tmp_path / "s.parquet"
    )
    with _zf.ZipFile(surf / "slurm_table_cleaned.zip", "w") as _z:
        _z.write(tmp_path / "s.parquet", "d.parquet/part-00001-x.parquet")
    fz = root / "zen_fdata_fugaku" / SNAP / "raw"
    fz.mkdir(parents=True)
    _pq.write_table(
        _pa.Table.from_pandas(_fdata_frame(), preserve_index=False), fz / "21_04.parquet"
    )
    mz = root / "zen_metropt2" / SNAP / "raw"
    mz.mkdir(parents=True)
    (mz / "MetroPT2_head.csv").write_bytes(b"timestamp,TP2\n2022-04-28 12:33:29.120,1.0\n")
    import gzip as _g

    ol = root / "openlibrary_dump" / SNAP / "raw"
    ol.mkdir(parents=True)
    (ol / "editions_head.txt.gz").write_bytes(_g.compress((_ol_line(1) + "\n").encode()))
    import zipfile as _zz

    ag = root / "zen_aegis_vehicle" / SNAP / "raw"
    ag.mkdir(parents=True)
    with _zz.ZipFile(ag / "Automotive-ResearchDataSet-VIF-AEGIS.zip", "w") as _a:
        _a.writestr(
            "obdData.csv",
            '"obdData_id","trip_id","obdPid","data","timestamp"\n"1","3","0C","9","2017-01-19 16:19:03.0"\n',  # noqa: E501
        )
    import zipfile as _zc

    cl = root / "zen_clue_lds" / SNAP / "raw"
    cl.mkdir(parents=True)
    with _zc.ZipFile(cl / "clue_head.zip", "w", _zc.ZIP_DEFLATED) as _c:
        _c.writestr("clue.json", _clue(1) + "\n")
    monkeypatch.setattr(ev, "XES_SPECS", {})
    monkeypatch.setattr(ev, "CSV_EVENT_SPECS", {})
    _fs = tmp_path / "flat_sel.json"
    _fs.write_text('{"views": []}')
    monkeypatch.setattr(ev, "FLAT_SELECTION", _fs)
    _w(root / "met_museum_objects" / SNAP / "raw" / "obj_1.json", '{"objectID": 1}')
    import gzip as _gz

    dv = root / "dgfip_dvf" / SNAP / "raw"
    dv.mkdir(parents=True)
    (dv / "dvf_69_2024.csv.gz").write_bytes(_gz.compress(_dvf_frame().to_csv(index=False).encode()))
    _w(root / "hmlr_price_paid" / SNAP / "raw" / "pp-2024_head.csv", PPD_HEAD)
    (tmp_path / "uci_wave2").mkdir(exist_ok=True)
    _retail_frame().to_csv(tmp_path / "uci_wave2" / "352.csv", index=False)
    import pyarrow as _pa
    import pyarrow.parquet as _pq

    pb = root / "zen_pbdb" / SNAP / "raw"
    pb.mkdir(parents=True)
    _pq.write_table(
        _pa.Table.from_pandas(_pbdb_frame(), preserve_index=False), tmp_path / "pb.parquet"
    )
    with _zc.ZipFile(pb / "pbdb_parquet.zip", "w") as _p:
        _p.write(tmp_path / "pb.parquet", "pbdb_occs.parquet")
    monkeypatch.setattr(ev, "EA_STATIONS", ["s"])
    _w(
        root / "ea_hydrology_flow" / SNAP / "raw" / "flow_s.csv",
        "date,value,completeness\n2020-01-01,1,Complete\n",
    )
    out = tmp_path / "out"
    manifest = ev.build(root, out)
    assert list(manifest) == [
        "openalex", "monash_pedestrian", "openfda_drug_event", "loghub", "openfoodfacts", "stackexchange",  # noqa: E501
        "ocds_montreal", "ocds_georgia", "ocds_zambia", "bikeshare_capital", "bikeshare_jc",
        "slurm_ccin2p3", "clinicaltrials_v2", "crossref_works", "google_cluster_2019a", "panels", "zen_t", "zen_surf_lisa_slurm", "zen_fdata_fugaku", "zen_metropt2", "openlibrary_dump", "zen_aegis_vehicle", "zen_clue_lds", "met_museum_objects", "ea_hydrology_flow", "dgfip_dvf", "hmlr_price_paid", "uci_online_retail", "zen_pbdb", "series", "ukspend",  # noqa: E501
    ]  # fmt: skip
    target = tmp_path / "m.json"
    assert (
        ev.main(["--root", str(root), "--out", str(tmp_path / "out2"), "--manifest", str(target)])
        == 0
    )
    text = target.read_text()
    assert json.loads(text) == json.loads(json.dumps(manifest))
    assert text == json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    printed = capsys.readouterr().out.strip()
    assert printed == str(
        {k: sum(f["rows"] for f in v["files"].values()) for k, v in manifest.items()}
    )
    assert ev.SNAPSHOT == "2026-11-21" and ev.SALT == "etl-benchmark-views-v1"


# --- remaining exact behaviours -------------------------------------------------------------------


def _rich_release(ocid="oc-1", with_award_date=True):
    award = {
        "id": "a1",
        "value": {"amount": 12.5, "currency": "GEL"},
        "suppliers": [{"id": "s1", "name": "Sup One"}, {"id": "s2"}],
        "items": [{"id": "i", "description": "text"}],
    }
    if with_award_date:
        award["date"] = "2021-02-03"
    return {
        "id": "r1",
        "ocid": ocid,
        "date": "2021-02-01",
        "buyer": {"id": "b1", "name": "Buyer"},
        "tender": {
            "title": "t",
            "procurementMethod": "open",
            "procuringEntity": {"id": "p1", "name": "Entity"},
            "documents": [{"url": "x"}],
        },
        "parties": [
            {"id": "b1", "name": "Buyer", "address": {"x": 1}, "roles": ["buyer"]},
            {"id": "s1", "identifier": {"id": "slug"}, "roles": ["supplier"]},
        ],
        "awards": [award],
        "contracts": [
            {
                "id": "c1",
                "awardID": "a1",
                "dateSigned": "2021-03-01",
                "value": {"amount": 9.0, "currency": "GEL"},
            }
        ],
    }


def test_ocds_view_maps_every_field_of_awards_contracts_parties_and_tenders_exactly():
    nested, awards, contracts = ev.ocds_view([_rich_release()], salt="k", keep_modulo=1)
    pid = lambda v: ev.pseudonym(v, "k")  # noqa: E731
    assert nested == [
        {
            "id": "r1",
            "ocid": "oc-1",
            "date": "2021-02-01",
            "buyer": {"id": pid("b1")},
            "tender": {"procurementMethod": "open", "procuringEntity": {"id": pid("p1")}},
            "parties": [
                {"id": pid("b1"), "roles": ["buyer"]},
                {"id": pid("s1"), "roles": ["supplier"]},
            ],
            "awards": [
                {
                    "id": "a1",
                    "value": {"amount": 12.5, "currency": "GEL"},
                    "suppliers": [{"id": pid("s1")}, {"id": pid("s2")}],
                    "items": [{"id": "i"}],
                    "date": "2021-02-03",
                }
            ],
            "contracts": [
                {
                    "id": "c1",
                    "awardID": "a1",
                    "dateSigned": "2021-03-01",
                    "value": {"amount": 9.0, "currency": "GEL"},
                }
            ],
        }
    ]
    assert awards.to_dict("records") == [
        {
            "ocid": "oc-1", "award_id": "a1", "date": "2021-02-03", "amount": 12.5, "currency": "GEL",  # noqa: E501
            "supplier_id": pid("s1"), "buyer_id": pid("b1"), "method": "open",
        }
    ]  # fmt: skip
    assert contracts.to_dict("records") == [
        {
            "ocid": "oc-1",
            "contract_id": "c1",
            "award_id": "a1",
            "date_signed": "2021-03-01",
            "amount": 9.0,
            "currency": "GEL",
        }
    ]
    assert ev.CONTRACT_COLUMNS == (
        "ocid",
        "contract_id",
        "award_id",
        "date_signed",
        "amount",
        "currency",
    )
    assert ev.AWARD_COLUMNS == (
        "ocid",
        "award_id",
        "date",
        "amount",
        "currency",
        "supplier_id",
        "buyer_id",
        "method",
    )
    assert (
        frozenset(
            [
                "name",
                "address",
                "contactPoint",
                "description",
                "legalName",
                "identifier",
                "title",
                "documents",
            ]
        )
        == ev.OCDS_DROP
    )


def test_ocds_view_falls_back_on_the_release_date_and_tolerates_missing_parts():
    release = _rich_release(with_award_date=False)
    release["awards"][0]["suppliers"] = []
    del release["buyer"], release["tender"], release["parties"]
    nested, awards, _ = ev.ocds_view([release], salt="k", keep_modulo=1)
    assert awards.loc[0, "date"] == "2021-02-01"  # the award has no date: the release date
    assert awards.loc[0, "supplier_id"] is None or pd.isna(awards.loc[0, "supplier_id"])
    assert pd.isna(awards.loc[0, "buyer_id"]) and pd.isna(awards.loc[0, "method"])
    assert nested[0]["parties"] == [] and "buyer" not in nested[0]
    bare = {"id": "r", "ocid": "oc-9", "date": "d"}
    nested, awards, contracts = ev.ocds_view([bare], salt="k", keep_modulo=1)
    assert nested == [{"id": "r", "ocid": "oc-9", "date": "d", "parties": []}]
    assert len(awards) == 0 and len(contracts) == 0
    no_tender = {"id": "r", "ocid": "oc-8", "date": "d", "tender": {"procurementMethod": "m"}}
    assert ev.ocds_view([no_tender], salt="k", keep_modulo=1)[0][0]["tender"] == {
        "procurementMethod": "m"
    }


def test_the_ocds_sample_is_a_stable_hash_of_the_first_eight_hex_digits_modulo_the_divisor():
    import hashlib

    releases = [{"id": f"r{i}", "ocid": f"oc-{i}", "date": "d"} for i in range(300)]
    for modulo in (10, 7, 1):
        expected = sorted(
            r["ocid"]
            for r in releases
            if int(hashlib.sha256(r["ocid"].encode()).hexdigest()[:8], 16) % modulo == 0
        )
        got, _, _ = ev.ocds_view(releases, keep_modulo=modulo)
        assert sorted(r["ocid"] for r in got) == expected
    default, _, _ = ev.ocds_view(releases)
    assert len(default) == len(ev.ocds_view(releases, keep_modulo=10)[0]) and 5 < len(default) < 60
    assert (
        ev.ocds_view(releases, salt="a", keep_modulo=1)[0][0]
        == ev.ocds_view(releases, keep_modulo=1, salt="a")[0][0]
    )


def test_spend_views_handle_mixed_date_formats_bad_dates_optional_columns_and_missing_suppliers():
    raw = pd.DataFrame(
        {
            "Transaction No.": ["1", "2", "3", "4", "5"],
            "Date": ["01/02/2024", "2024-02-03", "not a date", "05/02/2024", "06/02/2024"],
            "Supplier": ["A", "B", "C", None, "A"],
            "Amount (GBP)": ["10", "20", "30", "40", "oops"],
        }
    )
    out = ev.spend_view(raw, "org", salt="x")
    assert out["transaction_no"].tolist() == [
        "1",
        "2",
        "4",
    ]  # bad date and bad amount rows are dropped
    assert out["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-02-01",
        "2024-02-03",
        "2024-02-05",
    ]
    assert out["expense_type"].isna().all() and out["expense_area"].isna().all()
    assert out["supplier_id"].tolist()[:2] == [ev.pseudonym("a", "x"), ev.pseudonym("b", "x")]
    assert out["supplier_id"].isna().tolist() == [False, False, True]
    assert ev.spend_view(raw, "org")["supplier_id"].iloc[0] == ev.pseudonym("a")  # the default salt
    only_amount_bad = raw.assign(Date="01/02/2024", **{"Amount (GBP)": ["10", "x", "x", "x", "x"]})
    assert len(ev.spend_view(only_amount_bad, "o")) == 1
    only_date_bad = raw.assign(Date=["01/02/2024", "x", "x", "x", "x"], **{"Amount (GBP)": "5"})
    assert len(ev.spend_view(only_date_bad, "o")) == 1
    wide = pd.DataFrame({f"c{i}": [1] for i in range(10)})
    with pytest.raises(ev.ViewError) as info:
        ev.spend_view(wide, "o")
    assert str(info.value) == "required columns not found in ['c0', 'c1', 'c2', 'c3', 'c4', 'c5']"
    full = pd.DataFrame({"Expense type": ["T"], "Expense area": ["Z"], "Date": ["01/02/2024"], "Supplier": ["S"],  # noqa: E501
                         "Transaction No": ["9"], "Amount": ["1"]})  # fmt: skip
    kept = ev.spend_view(full, "o")
    assert kept.loc[0, "expense_type"] == "T" and kept.loc[0, "expense_area"] == "Z"
    assert list(ev.SPEND_COLUMNS) == [
        "organisation", "date", "expense_type", "expense_area", "supplier_id", "transaction_no", "amount",  # noqa: E501
    ]  # fmt: skip


def test_read_spend_decodes_both_encodings_keeps_text_and_skips_broken_rows():
    header = "Supplier,Amount,Date,Transaction No\n"
    latin = (header + "Café,007,01/01/2024,9\nBroken,1,2,3,4,5\nOk,2,01/01/2024,10\n").encode(
        "latin-1"
    )
    frame = ev.read_spend(latin)
    assert frame["Supplier"].tolist() == [
        "Café",
        "Ok",
    ]  # decoded as latin-1, extra-field row skipped
    assert frame["Amount"].tolist() == ["007", "2"]  # text, not numbers
    bom = ("﻿" + header + "A,1,d,1\n").encode("utf-8")
    assert list(ev.read_spend(bom).columns)[0] == "Supplier"  # a UTF-8 BOM is not part of the name
    lines = ["banner"] * 14 + [header.strip(), "A,1,d,1"]
    assert ev.read_spend("\n".join(lines).encode())["Supplier"].tolist() == [
        "A"
    ]  # header on line 15
    lines = ["banner"] * 15 + [header.strip(), "A,1,d,1"]
    with pytest.raises(ev.ViewError, match="first 15 lines"):
        ev.read_spend("\n".join(lines).encode())  # the header on line 16 is out of range


def test_small_view_helpers_have_exact_edge_behaviour():
    assert ev.csv_members(["__macosx/a.csv", "x/__MACOSX/b.csv", "__MACOSX/c.csv", "d/._e.csv", "d/f._g.csv", "h.CSV"]) == [  # noqa: E501
        "__macosx/a.csv", "d/f._g.csv", "x/__MACOSX/b.csv",
    ]  # fmt: skip
    assert (
        ev._short("https://a/b/c") == "c"
        and ev._short("plain") == "plain"
        and ev._short(None) is None
    )
    wide = ev.tsf_wide(
        {
            "frequency": "daily",
            "series": [{"name": "a", "start": "2020-01-01 00-00-00", "values": [None, None]}],
        }
    )
    assert str(wide["a"].dtype) == "float64"
    assert [
        r["safetyreportid"]
        for r in ev.faers_view(
            [{"safetyreportid": "1", "receivedate": "20240101"}, {"safetyreportid": "2"}]
        )
    ] == ["2", "1"]
    shape = ev.openalex_views([{"id": "https://o/W1"}], [], [], [], salt="s")
    assert shape["works"].loc[0, "n_authors"] == 0 and shape["authorships"].empty
    raw = pd.DataFrame({c: ["x"] for c in "abcdefgh"})
    with pytest.raises(ev.ViewError) as info:
        ev.trip_view(raw)
    assert str(info.value) == "trip columns not found in ['a', 'b', 'c', 'd', 'e', 'f']"
    bad_start = pd.DataFrame({"ride_id": ["r"], "started_at": ["nope"], "ended_at": ["2024-01-01"],
                              "start_station_id": ["1"], "end_station_id": ["2"]})  # fmt: skip
    assert pd.isna(ev.trip_view(bad_start)["duration_min"].iloc[0])


def test_every_builder_creates_missing_parents_runs_twice_and_writes_to_the_exact_paths(
    tmp_path, monkeypatch
):
    root = _raw_tree(tmp_path, monkeypatch)
    out = tmp_path / "o" / "deep"
    written = []
    import builtins
    import io

    real_open = builtins.open

    def spy(file, mode="r", *a, **k):
        if "w" in mode and str(file).startswith(str(out)):
            written.append(str(file)[len(str(out)) + 1 :])
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    for step in (
        ev._build_openalex, ev._build_monash, ev._build_faers, ev._build_loghub, ev._build_food,
        ev._build_stack, ev._build_ocds, ev._build_bikeshare, ev._build_ukspend,
    ):  # fmt: skip
        fresh = {}
        step(root, out, fresh)
        step(root, out, fresh)  # a second run over existing directories
    names = sorted(set(written))
    expected = (
        [
            f"openalex/{n}.csv"
            for n in ("authors", "authorships", "institutions", "sources", "works")
        ]
        + ["monash_pedestrian/wide.csv", "openfda_drug_event/events.jsonl"]
        + ["loghub/A.csv", "loghub/B.csv", "openfoodfacts/products.jsonl"]
        + [
            f"stackexchange/{s}/{t}.csv"
            for s in ("abc", "zed")
            for t in ("Badges", "Comments", "PostLinks", "Posts", "Users", "Votes")
        ]
        + [
            f"{s}/{f}"
            for s in ("ocds_georgia", "ocds_montreal", "ocds_zambia")
            for f in ("awards.csv", "contracts.csv", "releases.jsonl")
        ]
        + [
            "bikeshare_capital/trips.csv",
            "bikeshare_jc/trips.csv",
            "ukspend/mhra.csv",
            "ukspend/nhsbsa.csv",
        ]
    )
    assert names == sorted(expected)


def test_json_lines_views_sort_keys_and_the_tsf_decoder_replaces_bad_bytes(tmp_path, monkeypatch):
    import gzip
    import json
    import zipfile

    root = tmp_path / "acquired"
    gz = root / "openfoodfacts_products" / SNAP / "raw" / "d.json.gz"
    gz.parent.mkdir(parents=True)
    with gzip.open(gz, "wt") as handle:
        handle.write(json.dumps({"b": 1, "_id": "1", "a": {"z": 1, "y": 2}}) + "\n")
    events = root / "openfda_drug_event" / SNAP / "raw"
    _w(
        events / "event_0.json",
        json.dumps({"results": [{"safetyreportid": "1", "receivedate": "20240101", "a": 1}]}),
    )
    ev._build_food(root, tmp_path / "o", {})
    ev._build_faers(root, tmp_path / "o", {})
    assert (
        tmp_path / "o" / "openfoodfacts" / "products.jsonl"
    ).read_text() == '{"_id": "1", "a": {"y": 2, "z": 1}, "b": 1}\n'
    assert (
        tmp_path / "o" / "openfda_drug_event" / "events.jsonl"
    ).read_text() == '{"a": 1, "receivedate": "20240101", "safetyreportid": "1"}\n'
    archive = root / "monash_zenodo" / SNAP / "raw" / "4656626_pedestrian_counts_dataset.zip"
    archive.parent.mkdir(parents=True)
    tsf = b"# caf\xff\n@attribute series_name string\n@attribute start_timestamp date\n@frequency hourly\n@data\na:2020-01-01 00-00-00:1\n"  # noqa: E501
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x.tsf", tsf)
    ev._build_monash(root, tmp_path / "o2", {})
    assert (
        tmp_path / "o2" / "monash_pedestrian" / "wide.csv"
    ).read_text() == "timestamp,a\n2020-01-01,1.0\n"


def test_dates_are_parsed_iso_as_written_and_everything_else_day_first():
    values = pd.Series(
        [
            "2024-02-03",
            "03/02/2024",
            "2024-02-03T10:30:00",
            None,
            "garbage",
            "2024-13-45",
            "12/25/2024",
        ],
        index=[10, 11, 12, 13, 14, 15, 16],
    )
    out = ev._parse_dates(values)
    assert out.index.tolist() == [10, 11, 12, 13, 14, 15, 16]
    assert str(out.dtype) == "datetime64[ns]"
    assert out.iloc[0] == pd.Timestamp("2024-02-03") and out.iloc[1] == pd.Timestamp("2024-02-03")
    assert out.iloc[2] == pd.Timestamp("2024-02-03 10:30:00")
    assert out.iloc[3:6].isna().all()  # missing, unreadable, an impossible ISO date
    assert out.iloc[6] == pd.Timestamp(
        "2024-12-25"
    )  # day-first falls back when the day is not valid
    assert ev._parse_dates(pd.Series(["01/02/2024"])).iloc[0] == pd.Timestamp("2024-02-01")
    assert ev._parse_dates(pd.Series([], dtype=object)).empty
    only_iso = ev._parse_dates(pd.Series(["2024-02-03", "2024-03-04"]))
    assert only_iso.tolist() == [pd.Timestamp("2024-02-03"), pd.Timestamp("2024-03-04")]
    unreadable_iso = ev._parse_dates(pd.Series(["2024-99-99"]))
    assert unreadable_iso.isna().all()


def test_log_views_keep_text_values_and_missing_markers_as_they_are(tmp_path):
    root = tmp_path / "acquired"
    _w(
        tmp_path / "loghub" / "X.csv",
        "LineId,Time,Level,Content,EventId,EventTemplate\n007,NA,NA,c,E1,t\n",
    )
    for n in range(3):
        out = tmp_path / f"o{n}" / "deep"  # a fresh, not yet existing output directory each time
        ev._build_loghub(root, out, {})
    text = (tmp_path / "o2" / "deep" / "loghub" / "X.csv").read_text()
    assert text == "LineId,Time,Level,EventId\n007,NA,NA,E1\n"  # not 7, not an empty cell


def test_the_research_directory_is_on_the_import_path_once_and_the_monash_builder_runs(tmp_path):
    import sys
    import zipfile
    from pathlib import Path

    here = str(Path(ev.__file__).resolve().parent)
    assert here in sys.path and str(ev._HERE) == here  # sibling modules import by name
    root = tmp_path / "acquired"
    archive = root / "monash_zenodo" / SNAP / "raw" / "4656626_pedestrian_counts_dataset.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("x.tsf", "@attribute n s\n@frequency daily\n@data\n")
    before = list(sys.path)
    manifest: dict = {}
    ev._build_monash(root, tmp_path / "o", manifest)
    assert (
        sys.path == before and "monash_pedestrian" in manifest
    )  # a builder no longer edits the path


def test_the_stack_builder_runs_the_extractor_with_the_documented_command(tmp_path, monkeypatch):
    import subprocess

    root = tmp_path / "acquired"
    dump = root / "stackexchange_dump" / SNAP / "raw"
    dump.mkdir(parents=True)
    (dump / "abc.stackexchange.com.7z").write_bytes(b"x")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda command, check: calls.append((command, check)))
    ev._build_stack(root, tmp_path / "o" / "deep", {})
    ((command, check),) = calls
    assert command[:3] == ["bsdtar", "-xf", str(dump / "abc.stackexchange.com.7z")]
    assert command[3] == "-C" and check is True and len(command) == 5
    assert (tmp_path / "o" / "deep" / "stackexchange" / "abc").is_dir()


def test_main_has_repository_defaults_a_description_and_path_options(tmp_path, monkeypatch, capsys):
    import json
    from pathlib import Path

    seen = {}

    def fake_build(root, out):
        seen.update(root=root, out=out)
        return {"v": {"files": {"a": {"rows": 2}}}}

    monkeypatch.setattr(ev, "build", fake_build)
    fake = tmp_path / "repo" / "research" / "experimental_views.py"
    fake.parent.mkdir(parents=True)
    default_manifest = tmp_path / "repo" / "verification" / "evidence" / "dataset_registry_v2"
    default_manifest.mkdir(parents=True)
    monkeypatch.setattr(ev, "__file__", str(fake))
    assert ev.main([]) == 0
    assert seen["root"] == tmp_path / "repo" / "data" / "acquired"
    assert seen["out"] == tmp_path / "repo" / "data" / "experimental"
    written = default_manifest / "experimental_views.json"
    assert json.loads(written.read_text()) == {"v": {"files": {"a": {"rows": 2}}}}
    assert capsys.readouterr().out.strip() == "{'v': 2}"
    assert (
        ev.main(
            [
                "--root",
                str(tmp_path / "r"),
                "--out",
                str(tmp_path / "o"),
                "--manifest",
                str(tmp_path / "m.json"),
            ]
        )
        == 0
    )
    assert isinstance(seen["root"], Path) and isinstance(seen["out"], Path)
    assert seen["root"] == tmp_path / "r" and (tmp_path / "m.json").exists()
    with pytest.raises(SystemExit):
        ev.main(["--help"])
    assert "Experimental views of acquired data" in capsys.readouterr().out


# --- HPC job records (CC-IN2P3) -----------------------------------------------------------------


def _jobs(n=6):
    return pd.DataFrame(
        {
            "jobid": [str(100 + i) for i in range(n)],
            "state": ["completed", "failed", "timeout", "cancelled", "completed", "node_fail"][:n],
            "account": [f"account{i % 2:03d}" for i in range(n)],
            "user": [f"user{i:04d}" for i in range(n)],
            "partition": ["htc", "gpu"] * (n // 2),
            "submit": [str(1000 + 10 * (n - i)) for i in range(n)],  # newest id first
            "eligible": ["1"] * n,
            "start": [str(1100 + 10 * (n - i)) if i != 1 else "" for i in range(n)],
            "end": [str(1200 + 10 * (n - i)) for i in range(n)],
            "timelimit": ["60"] * n,
            "elapsed": ["100"] * n,
            "allocmem": ["2000"] * n,
            "maxrss": ["5"] * n,
            "alloccpus": ["1"] * n,
            "totalcpu": ["9"] * n,
            "allocgpus": ["0"] * n,
            "started": ["1"] * n,
            "maxdiskwrite": ["2"] * n,
            "nsteps": ["1"] * n,
            "el9": ["0"] * n,
            "hostnames": ["b009"] * n,
        }
    )


def test_job_views_keep_the_scheduler_columns_drop_hosts_and_derive_the_waiting_time():
    out = ev.slurm_view(_jobs(), keep_modulo=1)
    assert list(out.columns) == list(ev.SLURM_COLUMNS)
    assert ev.SLURM_COLUMNS == (
        "jobid", "state", "account", "user", "partition", "submit", "start", "end", "timelimit",
        "elapsed", "allocmem", "alloccpus", "allocgpus", "wait_s",
    )  # fmt: skip
    assert out["jobid"].tolist() == ["105", "104", "103", "102", "101", "100"]  # by submit time
    assert out["submit"].tolist() == [1010, 1020, 1030, 1040, 1050, 1060]
    assert out["wait_s"].isna().tolist() == [False, False, False, False, True, False]
    assert out.loc[out["jobid"] == "100", "wait_s"].iloc[0] == 100.0
    assert "hostnames" not in out and "maxrss" not in out and "eligible" not in out
    assert (
        out["state"].tolist()[0] == "node_fail"
    )  # failures stay visible as the scheduler wrote them
    assert out["user"].tolist()[0] == "user0005"  # the producer's own pseudonym, not re-hashed


def test_job_sampling_keeps_every_nth_job_id_and_tolerates_missing_times():
    frame = _jobs()
    assert ev.slurm_view(frame, keep_modulo=2)["jobid"].tolist() == ["104", "102", "100"]
    assert ev.slurm_view(frame)["jobid"].tolist() == ["100"] and ev.SLURM_MODULO == 20
    assert ev.slurm_view(frame.iloc[0:0], keep_modulo=1).empty
    with pytest.raises(ev.ViewError, match="job columns"):
        ev.slurm_view(pd.DataFrame({"x": [1]}))


def test_the_job_builder_reads_each_month_from_its_archive_and_writes_one_sorted_table(
    tmp_path, monkeypatch
):
    import io
    import tarfile

    root = tmp_path / "acquired"
    raw = root / "slurm_ccin2p3" / SNAP / "raw"
    raw.mkdir(parents=True)
    for name, frame in (
        ("12.tsv.tar.gz", _jobs().assign(jobid=lambda f: f["jobid"].astype(int) + 100)),
        ("07.tsv.tar.gz", _jobs()),
    ):
        data = frame.to_csv(sep="\t", index=False).encode()
        with tarfile.open(raw / name, "w:gz") as tar:
            info = tarfile.TarInfo(name.replace(".tar.gz", ""))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    monkeypatch.setattr(ev, "SLURM_MODULO", 1)
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_slurm(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "slurm_ccin2p3" / "jobs.csv"
    table = pd.read_csv(target, dtype=str)
    assert len(table) == 12 and list(table.columns) == list(ev.SLURM_COLUMNS)
    assert table["submit"].astype(int).is_monotonic_increasing
    assert manifest["slurm_ccin2p3"]["files"] == {"jobs.csv": {"sha256": _sha(target), "rows": 12}}
    assert {k: v for k, v in manifest["slurm_ccin2p3"].items() if k != "files"} == {
        "dropped": [
            "hostnames",
            "eligible",
            "maxrss",
            "totalcpu",
            "started",
            "maxdiskwrite",
            "nsteps",
            "el9",
        ],
        "pseudonymised": [],
        "sampling": "jobs with job id % 1 == 0, by submit time",
        "source_snapshot": "slurm_ccin2p3/2026-11-21",
        "notes": "user and account names are the producer's pseudonyms",
    }
    for month in ("07", "12"):
        assert f"acquired/slurm_ccin2p3/2026-11-21/raw/{month}.tsv.tar.gz" in seen
    assert [s.__name__ for s in ev.BUILD_STEPS].count("_build_slurm") == 1


# --- generic nested views: clinical-trial records and bibliographic metadata ---------------------


def test_nested_views_drop_the_named_keys_at_every_depth_sort_and_do_not_modify_the_input():
    records = [
        {"id": "b", "x": {"name": "n", "keep": [{"name": "m", "k": 1}]}, "name": "top"},
        {"id": "a", "x": {"keep": []}},
    ]
    out = ev.nested_view(records, drop=frozenset(["name"]), key=lambda r: r["id"])
    assert out == [{"id": "a", "x": {"keep": []}}, {"id": "b", "x": {"keep": [{"k": 1}]}}]
    assert records[0]["name"] == "top" and records[0]["x"]["keep"][0]["name"] == "m"
    assert ev.nested_view([], drop=frozenset(), key=lambda r: 0) == []


def test_clinical_trial_views_remove_people_and_contact_details_but_keep_the_trial_structure():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT2", "organization": {"fullName": "Org A"}},
            "contactsLocationsModule": {
                "centralContacts": [{"name": "Ann", "email": "a@b"}],
                "overallOfficials": [{"name": "Bob", "affiliation": "U"}],
                "locations": [{"city": "Paris", "contacts": [{"name": "Cy", "phone": "1"}]}],
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Sponsor Inc", "class": "INDUSTRY"},
                "responsibleParty": {
                    "type": "PI",
                    "investigatorFullName": "Dee",
                    "investigatorTitle": "Dr",
                },
            },
        },
        "resultsSection": {"moreInfoModule": {"pointOfContact": {"email": "x@y"}}},
    }
    other = {"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}
    out = ev.clinical_trials_view([study, other])
    assert [s["protocolSection"]["identificationModule"]["nctId"] for s in out] == ["NCT1", "NCT2"]
    text = json.dumps(out)
    for word in (
        "Ann",
        "a@b",
        "Bob",
        "Cy",
        "Dee",
        "x@y",
        "centralContacts",
        "overallOfficials",
        "pointOfContact",
    ):
        assert word not in text
    kept = out[1]["protocolSection"]
    assert kept["contactsLocationsModule"]["locations"] == [{"city": "Paris"}]
    assert kept["sponsorCollaboratorsModule"]["leadSponsor"] == {
        "name": "Sponsor Inc",
        "class": "INDUSTRY",
    }
    assert kept["sponsorCollaboratorsModule"]["responsibleParty"] == {"type": "PI"}
    assert kept["identificationModule"]["organization"] == {"fullName": "Org A"}
    assert frozenset(
        ["centralContacts", "overallOfficials", "pointOfContact", "contacts", "investigatorFullName",  # noqa: E501
         "investigatorTitle", "investigatorAffiliation"]
    ) == ev.CT_DROP  # fmt: skip


def test_bibliographic_views_replace_authors_by_their_count_and_sort_by_doi_without_duplicates():
    works = [
        {
            "DOI": "10.2/b",
            "title": ["T"],
            "author": [{"name": "Ann", "ORCID": "o"}, {"name": "Bo"}],
            "reference": [{"DOI": "x"}],
        },
        {"DOI": "10.1/a", "title": ["U"]},
        {"DOI": "10.2/b", "title": ["T again"], "author": []},
    ]
    out = ev.crossref_view(works)
    assert [w["DOI"] for w in out] == ["10.1/a", "10.2/b"]  # one record per DOI
    assert out[0] == {"DOI": "10.1/a", "title": ["U"], "n_authors": 0}
    assert (
        out[1]["n_authors"] == 2
        and "author" not in out[1]
        and out[1]["reference"] == [{"DOI": "x"}]
    )
    assert "Ann" not in json.dumps(out) and "ORCID" not in json.dumps(out)


def test_the_study_and_bibliography_builders_write_sorted_json_lines_and_manifests(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    ct = root / "clinicaltrials_v2" / SNAP / "raw"
    _w(
        ct / "studies_2023-02.json",
        json.dumps(
            {
                "studies": [
                    {"protocolSection": {"identificationModule": {"nctId": "NCT2"}, "z": 1, "a": 2}}
                ]
            }
        ),
    )
    _w(
        ct / "studies_2023-01.json",
        json.dumps({"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}]}),
    )
    cr = root / "crossref_works" / SNAP / "raw"
    _w(
        cr / "sample_01.json",
        json.dumps({"message": {"items": [{"DOI": "10.9/z", "author": [{"name": "A"}]}]}}),
    )
    _w(
        cr / "sample_00.json",
        json.dumps({"message": {"items": [{"DOI": "10.1/a"}, {"DOI": "10.9/z"}]}}),
    )
    seen = _accessed(monkeypatch, root)
    manifest = {}
    out = tmp_path / "o" / "deep"
    ev._build_clinicaltrials(root, out, manifest)
    ev._build_crossref(root, out, manifest)
    lines = (out / "clinicaltrials_v2" / "studies.jsonl").read_text().splitlines()
    assert [json.loads(x)["protocolSection"]["identificationModule"]["nctId"] for x in lines] == [
        "NCT1",
        "NCT2",
    ]
    assert (
        lines[1]
        == '{"protocolSection": {"a": 2, "identificationModule": {"nctId": "NCT2"}, "z": 1}}'
    )
    dois = [
        json.loads(x)["DOI"]
        for x in (out / "crossref_works" / "works.jsonl").read_text().splitlines()
    ]
    assert dois == ["10.1/a", "10.9/z"]
    assert manifest["clinicaltrials_v2"]["files"] == {
        "studies.jsonl": {"sha256": _sha(out / "clinicaltrials_v2" / "studies.jsonl"), "rows": 2}
    }
    assert {k: v for k, v in manifest["clinicaltrials_v2"].items() if k != "files"} == {
        "dropped": sorted(ev.CT_DROP), "pseudonymised": [], "source_snapshot": "clinicaltrials_v2/2026-11-21",  # noqa: E501
    }  # fmt: skip
    assert manifest["crossref_works"]["files"]["works.jsonl"]["rows"] == 2
    assert {k: v for k, v in manifest["crossref_works"].items() if k != "files"} == {
        "dropped": ["author"], "pseudonymised": [], "source_snapshot": "crossref_works/2026-11-21",
        "notes": "authors are replaced by their count; one record per DOI",
    }  # fmt: skip
    assert "acquired/clinicaltrials_v2/2026-11-21/raw/studies_2023-01.json" in seen
    assert "acquired/crossref_works/2026-11-21/raw/sample_01.json" in seen


def test_email_addresses_in_free_text_are_redacted_at_every_depth_without_touching_other_text():
    node = {
        "a": "write to Jo.Doe+x@lab-1.example.co.uk or sam@x.org now",
        "b": [{"c": "no address, 3 @ 4"}, "plain@host"],
        "d": 5,
        "e": None,
        "f": {"g": "a@b.cd"},
    }
    assert ev.redact_emails(node) == {
        "a": "write to [email] or [email] now",
        "b": [{"c": "no address, 3 @ 4"}, "plain@host"],
        "d": 5,
        "e": None,
        "f": {"g": "[email]"},
    }
    assert node["a"].startswith("write to Jo.Doe")  # the input is not modified


def test_study_views_also_redact_addresses_written_in_data_sharing_statements():
    study = {
        "protocolSection": {
            "identificationModule": {"nctId": "N"},
            "ipdSharingStatementModule": {"description": "ask me@uni.edu"},
        }
    }
    out = ev.clinical_trials_view([study])
    assert out[0]["protocolSection"]["ipdSharingStatementModule"]["description"] == "ask [email]"


# --- time-series tables with a verified time column ---------------------------------------------


def test_series_views_parse_the_declared_format_drop_unreadable_times_and_keep_numeric_columns():
    raw = pd.DataFrame(
        {
            "Date": ["3/10/2004", "3/11/2004", "13/45/2004", "3/10/2004"],
            "Time": ["18:00:00", "19:00:00", "00:00:00", "17:00:00"],
            "CO": ["2.6", "2", "9", "x"],
            "label": ["a", "b", "c", "d"],
        }
    )
    spec = {"time": ["Date", "Time"], "format": "%m/%d/%Y %H:%M:%S"}
    out = ev.series_view(raw, spec)
    assert list(out.columns) == ["timestamp", "CO"]
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2004-03-10 17:00:00"),
        pd.Timestamp("2004-03-10 18:00:00"),
        pd.Timestamp("2004-03-11 19:00:00"),
    ]
    assert out["CO"].isna().tolist() == [True, False, False]  # an unreadable value stays missing
    assert out["CO"].iloc[1] == 2.6
    assert out.attrs == {"rows_dropped": 1}
    assert len(raw) == 4


def test_series_views_add_an_hour_column_and_handle_a_single_time_column():
    raw = pd.DataFrame(
        {"Date": ["1/12/2017", "1/12/2017"], "Hour": ["1", "0"], "Rented": ["10", "5"]}
    )
    spec = {"time": ["Date"], "format": "%d/%m/%Y", "hour": "Hour"}
    out = ev.series_view(raw, spec)
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2017-12-01 00:00"),
        pd.Timestamp("2017-12-01 01:00"),
    ]
    assert list(out.columns) == ["timestamp", "Rented"] and out["Rented"].tolist() == [5.0, 10.0]
    iso = pd.DataFrame(
        {"t": ["2019-11-06 11:37:13+01:00", "2019-11-06 11:37:12+01:00"], "v": ["1", "2"]}
    )
    parsed = ev.series_view(iso, {"time": ["t"], "format": "ISO8601"})
    assert parsed["v"].tolist() == [2.0, 1.0] and str(parsed["timestamp"].dtype).startswith(
        "datetime64"
    )
    bom = pd.DataFrame({"﻿date": ["01/01/2018 00:15"], "k": ["3"]})
    assert ev.series_view(bom, {"time": ["date"], "format": "%d/%m/%Y %H:%M"})["k"].tolist() == [
        3.0
    ]
    with pytest.raises(ev.ViewError, match="time column"):
        ev.series_view(raw, {"time": ["nope"], "format": "%d/%m/%Y"})


def test_the_series_builder_reads_pool_and_wave2_tables_and_writes_sorted_views(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    root.mkdir()
    specs = {
        "uci:5": {"dir": "pool", "time": ["date"], "format": "%Y-%m-%d %H:%M:%S"},
        "uci:6": {"dir": "uci_wave2", "time": ["d"], "format": "%m/%d/%Y"},
    }
    monkeypatch.setattr(ev, "SERIES_SPECS", specs)
    _w(tmp_path / "pool" / "5.csv", "id,date,v\n1,2015-02-04 17:52:00,2\n2,2015-02-04 17:51:00,1\n")
    _w(tmp_path / "uci_wave2" / "6.csv", "d,w\n1/2/1998,3\n1/1/1998,4\n")
    seen = _accessed(monkeypatch, root)
    manifest = {}
    ev._build_series(root, tmp_path / "o" / "deep", manifest)
    assert (
        tmp_path / "o" / "deep" / "series" / "uci_5.csv"
    ).read_text() == "timestamp,id,v\n2015-02-04 17:51:00,2,1\n2015-02-04 17:52:00,1,2\n"
    assert (
        tmp_path / "o" / "deep" / "series" / "uci_6.csv"
    ).read_text() == "timestamp,w\n1998-01-01,4\n1998-01-02,3\n"
    assert list(manifest["series"]["files"]) == ["uci_5.csv", "uci_6.csv"]
    assert manifest["series"]["files"]["uci_5.csv"] == {
        "sha256": _sha(tmp_path / "o" / "deep" / "series" / "uci_5.csv"),
        "rows": 2,
    }
    assert manifest["series"]["dropped"] == []
    assert (
        manifest["series"]["source_snapshot"]
        == "data/pool and data/uci_wave2 tables, pinned by the pool manifests"
    )
    assert manifest["series"]["rows_dropped"] == {"uci:5": 0, "uci:6": 0}
    assert "pool/5.csv" in seen and "uci_wave2/6.csv" in seen
    assert set(ev.SERIES_SPECS) == set(specs)


def test_the_new_builders_create_missing_parents_twice_and_write_exact_paths_and_sorted_keys(
    tmp_path, monkeypatch
):
    import builtins
    import io

    root = tmp_path / "acquired"
    ct = root / "clinicaltrials_v2" / SNAP / "raw"
    _w(
        ct / "studies_2023-01.json",
        json.dumps({"studies": [{"protocolSection": {"identificationModule": {"nctId": "N1"}}}]}),
    )
    cr = root / "crossref_works" / SNAP / "raw"
    _w(
        cr / "sample_00.json",
        json.dumps(
            {"message": {"items": [{"title": ["t"], "DOI": "10.1/a", "author": [{"name": "A"}]}]}}
        ),
    )
    _w(tmp_path / "pool" / "5.csv", "t,v\n2020-01-01,1\n")
    monkeypatch.setattr(
        ev, "SERIES_SPECS", {"uci:5": {"dir": "pool", "time": ["t"], "format": "%Y-%m-%d"}}
    )
    out = tmp_path / "o" / "deep"
    written = []
    real_open = builtins.open

    def spy(file, mode="r", *a, **k):
        if "w" in mode and str(file).startswith(str(out)):
            written.append(str(file)[len(str(out)) + 1 :])
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(io, "open", spy)
    for step in (ev._build_clinicaltrials, ev._build_crossref, ev._build_series):
        manifest = {}
        step(root, out, manifest)
        step(root, out, manifest)  # a second run over existing directories
    assert sorted(set(written)) == [
        "clinicaltrials_v2/studies.jsonl",
        "crossref_works/works.jsonl",
        "series/uci_5.csv",
    ]
    text = (out / "crossref_works" / "works.jsonl").read_text()
    assert text == '{"DOI": "10.1/a", "n_authors": 1, "title": ["t"]}\n'  # keys in sorted order


def test_series_edge_cases_stable_order_unreadable_hours_and_the_error_message():
    raw = pd.DataFrame(
        {
            "t": ["2020-01-01", "2020-01-01", "2020-01-01"],
            "k": ["a", "b", "c"],
            "v": ["3", "1", "2"],
        }
    )
    out = ev.series_view(raw, {"time": ["t"], "format": "%Y-%m-%d"})
    assert out["v"].tolist() == [3.0, 1.0, 2.0]  # equal timestamps keep their file order
    hours = pd.DataFrame({"d": ["01/01/2020", "01/01/2020"], "h": ["x", "2"], "v": ["1", "2"]})
    parsed = ev.series_view(hours, {"time": ["d"], "format": "%d/%m/%Y", "hour": "h"})
    assert parsed["v"].tolist() == [2.0] and parsed.attrs["rows_dropped"] == 1
    wide = pd.DataFrame({f"c{i}": [1] for i in range(8)})
    with pytest.raises(ev.ViewError) as info:
        ev.series_view(wide, {"time": ["missing"], "format": "%Y"})
    assert str(info.value) == "time column not found in ['c0', 'c1', 'c2', 'c3', 'c4', 'c5']"
    assert set(ev.SERIES_SPECS) == {
        "uci:357",
        "uci:360",
        "uci:374",
        "uci:560",
        "uci:799",
        "uci:849",
        "uci:851",
        "uci:172",
        "uci:492",
    }


# --- Borg cluster trace prefixes (event sequences) -----------------------------------------------


def _collection_line(cid, time, kind, **over):
    record = {
        "time": str(time), "type": str(kind), "collection_id": str(cid), "scheduling_class": "1",
        "collection_type": "0", "priority": "103", "user": "HASHED=", "collection_name": "HASHED2=",
        "collection_logical_name": "HASHED3=", "start_after_collection_ids": [], "vertical_scaling": "2",  # noqa: E501
        "scheduler": "1",
    }  # fmt: skip
    record.update(over)
    return json.dumps(record)


def _instance_line(cid, index, time, kind, machine="9"):
    return json.dumps(
        {"time": str(time), "type": str(kind), "collection_id": str(cid), "scheduling_class": "0",
         "collection_type": "0", "priority": "114", "instance_index": str(index), "machine_id": machine,  # noqa: E501
         "alloc_collection_id": "0", "alloc_instance_index": "-1", "missing_type": "1",
         "resource_request": {"cpus": 0.5, "memory": 0.25}, "constraint": []}
    )  # fmt: skip


def test_collection_event_views_keep_the_sequence_fields_drop_hashed_names_and_order_each_collection():  # noqa: E501
    lines = [
        _collection_line(2, 30, 6),
        _collection_line(1, 20, 3),
        _collection_line(1, 10, 0),
        "",
        _collection_line(2, 5, 0),
    ]
    out = ev.borg_collection_view(lines)
    assert list(out.columns) == list(ev.BORG_COLLECTION_COLUMNS)
    assert ev.BORG_COLLECTION_COLUMNS == (
        "collection_id", "time_us", "type", "collection_type", "priority", "scheduling_class",
        "scheduler", "vertical_scaling",
    )  # fmt: skip
    assert out["collection_id"].tolist() == [1, 1, 2, 2]
    assert out["time_us"].tolist() == [10, 20, 5, 30]  # time order inside each collection
    assert out["type"].tolist() == [0, 3, 0, 6]
    assert out.iloc[0].to_dict() == {
        "collection_id": 1,
        "time_us": 10,
        "type": 0,
        "collection_type": 0,
        "priority": 103,
        "scheduling_class": 1,
        "scheduler": 1,
        "vertical_scaling": 2,
    }
    assert "user" not in out and "collection_name" not in out
    assert len(ev.borg_collection_view([])) == 0
    missing = json.dumps({"time": "1", "type": "0", "collection_id": "7"})
    assert pd.isna(ev.borg_collection_view([missing])["priority"].iloc[0])


def test_instance_event_views_unpack_the_resource_request_and_order_each_instance():
    lines = [
        _instance_line(1, 1, 50, 6),
        _instance_line(1, 0, 40, 3),
        _instance_line(1, 1, 10, 0, machine=""),
    ]
    out = ev.borg_instance_view(lines)
    assert list(out.columns) == list(ev.BORG_INSTANCE_COLUMNS)
    assert out[["collection_id", "instance_index", "time_us", "type"]].values.tolist() == [
        [1, 0, 40, 3],
        [1, 1, 10, 0],
        [1, 1, 50, 6],
    ]
    assert out["cpus"].tolist() == [0.5, 0.5, 0.5] and out["memory"].tolist() == [0.25, 0.25, 0.25]
    assert out["machine_id"].tolist()[0] == 9 and pd.isna(out["machine_id"].iloc[1])
    bare = json.dumps({"time": "1", "type": "0", "collection_id": "1", "instance_index": "0"})
    row = ev.borg_instance_view([bare]).iloc[0]
    assert pd.isna(row["cpus"]) and pd.isna(row["memory"])


def test_the_borg_builder_reads_gzip_prefixes_records_the_cut_and_caps_the_rows(
    tmp_path, monkeypatch
):
    import gzip

    root = tmp_path / "acquired"
    raw = root / "google_cluster_2019a" / SNAP / "raw"
    raw.mkdir(parents=True)
    text = "\n".join(_collection_line(i % 7, 100 - i, i % 4) for i in range(60)) + "\n"
    blob = gzip.compress(text.encode())
    (raw / "collection_events_head.json.gz").write_bytes(blob[: len(blob) * 3 // 4])  # a cut stream
    text = "\n".join(_instance_line(i % 3, i % 5, 100 - i, i % 4) for i in range(40)) + "\n"
    (raw / "instance_events_head.json.gz").write_bytes(gzip.compress(text.encode()))
    monkeypatch.setattr(ev, "BORG_MAX_LINES", 25)
    manifest = {}
    ev._build_borg(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "google_cluster_2019a"
    assert len(pd.read_csv(folder / "collection_events.csv")) == 25  # capped, a prefix of the file
    assert len(pd.read_csv(folder / "instance_events.csv")) == 25
    view = manifest["google_cluster_2019a"]
    assert view["files"] == {
        "collection_events.csv": {"sha256": _sha(folder / "collection_events.csv"), "rows": 25},
        "instance_events.csv": {"sha256": _sha(folder / "instance_events.csv"), "rows": 25},
    }
    assert view["sampling"].startswith("prefix of one shard in file order")
    assert view["fragments"]["collection_events_head.json.gz"]["stream_complete"] is False
    assert view["fragments"]["instance_events_head.json.gz"]["stream_complete"] is True
    assert view["fragments"]["instance_events_head.json.gz"]["lines_read"] == 40
    assert {k: v for k, v in view.items() if k not in ("files", "fragments", "sampling")} == {
        "dropped": [
            "user",
            "collection_name",
            "collection_logical_name",
            "constraint",
            "alloc fields",
        ],
        "pseudonymised": [],
        "source_snapshot": "google_cluster_2019a/2026-11-21",
    }


# --- panels of series (RKI) and multi-table relational extracts (3PFL) ---------------------------


def test_panel_views_keep_key_columns_sort_by_key_then_time_and_read_na_markers_as_missing():
    raw = pd.DataFrame(
        {
            "date": ["2020-01-02", "2020-01-01", "2020-01-01", "bad"],
            "region": ["B", "B", "A", "A"],
            "cases": ["5", "NA", "3", "9"],
            "note": ["x", "y", "z", "w"],
        }
    )
    spec = {"time": ["date"], "format": "%Y-%m-%d", "keys": ["region"]}
    out = ev.panel_view(raw, spec)
    assert list(out.columns) == ["timestamp", "region", "cases"]
    assert out["region"].tolist() == ["A", "B", "B"]
    assert out["timestamp"].tolist() == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-02"),
    ]
    assert out["cases"].isna().tolist() == [False, True, False]
    assert out.attrs == {"rows_dropped": 1}
    with pytest.raises(ev.ViewError, match="key column"):
        ev.panel_view(raw, {**spec, "keys": ["zzz"]})


def _tables():
    return {
        "01_links": pd.DataFrame({"piid": ["p1", "p2", "p9"], "patent": ["10", "11", "12"]}),
        "02_orders": pd.DataFrame(
            {"piid": ["p1", "p2"], "vendor": ["v1", "v2"], "title": ["secret a", "secret b"]}
        ),
        "03_vendors": pd.DataFrame({"vendor": ["v1"], "street": ["1 rue"], "state": ["OH"]}),
    }


TABLE_SPEC = {
    "tables": {
        "01_links": {"keep": ["piid", "patent"]},
        "02_orders": {"keep": ["piid", "vendor"]},
        "03_vendors": {"keep": ["vendor", "state"]},
    },
    "relations": [
        ["01_links", "piid", "02_orders", "piid"],
        ["02_orders", "vendor", "03_vendors", "vendor"],
        ["01_links", "piid", "02_orders", "piid", {"where": ["patent", "10"]}],
    ],
}


def test_table_views_keep_only_listed_columns_and_measure_every_relation_with_its_orphans():
    out, relations = ev.tables_view(_tables(), TABLE_SPEC)
    assert list(out) == ["01_links", "02_orders", "03_vendors"]
    assert (
        list(out["02_orders"].columns) == ["piid", "vendor"] and "street" not in out["03_vendors"]
    )
    assert relations == [
        {
            "child": "01_links.piid",
            "parent": "02_orders.piid",
            "checked": 3,
            "orphans": 1,
            "share": 1 / 3,
        },
        {
            "child": "02_orders.vendor",
            "parent": "03_vendors.vendor",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        },
        {
            "child": "01_links.piid where patent=10",
            "parent": "02_orders.piid",
            "checked": 1,
            "orphans": 0,
            "share": 0.0,
        },
    ]
    with pytest.raises(ev.ViewError, match="column"):
        ev.tables_view(_tables(), {"tables": {"01_links": {"keep": ["nope"]}}, "relations": []})
    with pytest.raises(ev.ViewError, match="table"):
        ev.tables_view({}, TABLE_SPEC)


def test_the_panel_and_relational_builders_write_views_and_record_relations(tmp_path, monkeypatch):
    root = tmp_path / "acquired"
    raw = root / "zen_rki_notaufnahme" / SNAP / "raw"
    _w(
        raw / "Notaufnahmesurveillance_Zeitreihen_Syndrome.tsv",
        "date\tsyndrome\tn\n2019-01-02\tARI\t2\n2019-01-01\tARI\t1\n",
    )
    monkeypatch.setattr(
        ev,
        "PANEL_SPECS",
        {
            "rki_notaufnahme": {
                "source": "zen_rki_notaufnahme",
                "file": "Notaufnahmesurveillance_Zeitreihen_Syndrome.tsv",
                "sep": "\t",
                "time": ["date"],
                "format": "%Y-%m-%d",
                "keys": ["syndrome"],
            }
        },
    )
    manifest = {}
    ev._build_panels(root, tmp_path / "o" / "deep", manifest)
    ev._build_panels(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "panels" / "rki_notaufnahme.csv"
    assert target.read_text() == "timestamp,syndrome,n\n2019-01-01,ARI,1\n2019-01-02,ARI,2\n"
    assert manifest["panels"]["files"] == {
        "rki_notaufnahme.csv": {"sha256": _sha(target), "rows": 2}
    }
    assert manifest["panels"]["rows_dropped"] == {"rki_notaufnahme": 0}
    tables = root / "zen_3pfl" / SNAP / "raw"
    _w(tables / "01_links.csv", 'piid\tpatent\n"p1"\t"10"\n"p9"\t"12"\n')
    _w(tables / "02_orders.csv", 'piid\tvendor\ttitle\n"p1"\t"v1"\t"s"\n')
    monkeypatch.setattr(ev, "TABLE_SETS", {"zen_3pfl": {"dropped": ["names"],
        "tables": {"01_links": {"keep": ["piid", "patent"]}, "02_orders": {"keep": ["piid", "vendor"]}},  # noqa: E501
        "relations": [["01_links", "piid", "02_orders", "piid"]]}})  # fmt: skip
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "zen_3pfl"
    assert (
        folder / "01_links.csv"
    ).read_text() == "piid,patent\np1,10\np9,12\n"  # quotes are not data
    assert (folder / "02_orders.csv").read_text() == "piid,vendor\np1,v1\n"
    view = manifest["zen_3pfl"]
    assert view["relations"] == [
        {
            "child": "01_links.piid",
            "parent": "02_orders.piid",
            "checked": 2,
            "orphans": 1,
            "share": 0.5,
        }
    ]
    assert view["files"]["01_links.csv"] == {"sha256": _sha(folder / "01_links.csv"), "rows": 2}
    assert (
        view["notes"]
        == "relations are the source's own keys; orphans are natural incompleteness of the published extract"  # noqa: E501
    )


# --- SURF Lisa SLURM job table from a zipped Parquet part ----------------------------------------


def _surf_frame():
    return pd.DataFrame(
        {
            "id": pd.array([3, 1, 2], dtype="int32"),
            "start_date": pd.to_datetime(["2022-01-01 10:00:00", "2022-01-01 09:00:00", None]),
            "end_date": pd.to_datetime(["2022-01-01 10:30:00", "2022-01-01 09:10:00", None]),
            "node": ["r1n1", "r1n2", "r1n3"],
            "nodetypes": ["normal(1)", "gpu(1)", "normal(1)"],
            "numnodes": ["1", "2", "x"],
            "numcores": ["16", "32", "8"],
            "submit_date": pd.to_datetime(["2022-01-01 09:55:00", "2022-01-01 08:00:00", "2022-01-01 09:00:00"]),  # noqa: E501
            "state": ["COMPLETED", "FAILED", "CANCELLED"],
        }
    )  # fmt: skip


def test_surf_job_view_derives_wait_and_runtime_orders_by_submit_and_keeps_unstarted_jobs():
    out = ev.surf_slurm_view(_surf_frame())
    assert list(out.columns) == list(ev.SURF_COLUMNS)
    assert ev.SURF_COLUMNS == (
        "job_id", "submit_ts", "wait_s", "runtime_s", "nodes", "cores", "node_type", "state",
    )  # fmt: skip
    assert out["job_id"].tolist() == [1, 2, 3]  # submit order
    assert out["wait_s"].tolist()[0] == 3600.0 and out["runtime_s"].tolist()[0] == 600.0
    assert pd.isna(out["wait_s"].iloc[1]) and pd.isna(out["runtime_s"].iloc[1])  # never started
    assert out["wait_s"].iloc[2] == 300.0 and out["runtime_s"].iloc[2] == 1800.0
    assert out["nodes"].iloc[0] == 2 and pd.isna(
        out["nodes"].iloc[1]
    )  # unreadable count stays missing
    assert out["cores"].tolist() == [32, 8, 16]
    assert out["node_type"].tolist() == ["gpu", "normal", "normal"]
    assert out["state"].tolist() == ["FAILED", "CANCELLED", "COMPLETED"]
    assert "node" not in out  # host names are not experimental features
    with pytest.raises(ev.ViewError, match="column"):
        ev.surf_slurm_view(_surf_frame().drop(columns=["state"]))


def test_the_surf_builder_extracts_the_zipped_part_samples_with_a_stride_and_records_it(
    tmp_path, monkeypatch
):
    import zipfile

    import pyarrow as pa
    import pyarrow.parquet as pq

    root = tmp_path / "acquired"
    raw = root / "zen_surf_lisa_slurm" / SNAP / "raw"
    raw.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(
            pd.concat([_surf_frame()] * 4, ignore_index=True), preserve_index=False
        ),
        tmp_path / "p.parquet",
        row_group_size=5,
    )
    empty = tmp_path / "empty.parquet"
    pq.write_table(pa.Table.from_pandas(_surf_frame().iloc[:0], preserve_index=False), empty)
    with zipfile.ZipFile(raw / "slurm_table_cleaned.zip", "w") as z:
        z.write(empty, "slurm_table_cleaned.parquet/part-00000-x.snappy.parquet")
        z.write(tmp_path / "p.parquet", "slurm_table_cleaned.parquet/part-00003-x.snappy.parquet")
    monkeypatch.setattr(ev, "SURF_STRIDE", 3)
    manifest = {}
    ev._build_surf(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "zen_surf_lisa_slurm" / "jobs.csv"
    assert len(pd.read_csv(target)) == 4  # rows 0, 3, 6, 9 of 12
    view = manifest["zen_surf_lisa_slurm"]
    assert view["files"] == {"jobs.csv": {"sha256": _sha(target), "rows": 4}}
    assert view["sampling"] == {
        "method": "one row in 3 of the only non-empty Parquet part, from the first, in file order",
        "stride": 3, "rows_read": 12, "rows_kept": 4, "source_rows": 12, "truncated": False,
        "member": "slurm_table_cleaned.parquet/part-00003-x.snappy.parquet",
    }  # fmt: skip
    assert view["dropped"] == ["node host names"]


# --- Fugaku job records (Parquet) and the MetroPT2 time-ordered CSV prefix ------------------------


def _fdata_frame():
    return pd.DataFrame(
        {
            "jid": ["a", "b", "c"], "usr": ["u1", "u2", "u3"], "jnam": ["n1", "n2", "n3"],
            "cnumr": [48, 96, 48], "cnumat": [48, 96, 48], "nnumr": [1, 2, 1], "nnuma": [1, 2, 1],
            "adt": ["2021-04-02 10:00:00", "2021-04-01 09:00:00", "2021-04-03 08:00:00"],
            "sdt": ["2021-04-02 10:10:00", "2021-04-01 09:30:00", None],
            "edt": ["2021-04-02 11:10:00", "2021-04-01 09:40:00", None],
            "ec": [0, 1, 0], "elpl": [3600.0, 600.0, 60.0], "pri": [1, 2, 3],
            "econ": [5.0, 1.0, None], "avgpcon": [100.0, 90.0, None], "maxpcon": [120.0, 95.0, None],  # noqa: E501
            "mszl": [1.0, 2.0, 3.0], "msza": [1, 2, 3], "mmszu": [0.5, 1.0, None], "pclass": ["compute", "memory", None],  # noqa: E501
            "exit state": ["completed", "failed", "cancelled"], "duration": [3600.0, 600.0, None],
            "embedding": [[0.1], [0.2], [0.3]], "jobenv_req": ["x", "y", "z"],
        }
    )  # fmt: skip


def test_fugaku_job_view_drops_identifiers_and_text_derives_wait_and_orders_by_arrival():
    out = ev.fugaku_jobs_view(_fdata_frame())
    assert list(out.columns) == list(ev.FUGAKU_COLUMNS)
    assert out["submit_ts"].tolist() == sorted(out["submit_ts"].tolist())
    assert (
        out["wait_s"].iloc[0] == 1800.0
        and out["wait_s"].iloc[1] == 600.0
        and pd.isna(out["wait_s"].iloc[2])
    )
    assert out["state"].tolist() == ["failed", "completed", "cancelled"]
    for gone in ("jid", "usr", "jnam", "embedding", "jobenv_req"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="column"):
        ev.fugaku_jobs_view(_fdata_frame().drop(columns=["adt"]))


def test_csv_prefixes_keep_only_complete_lines_and_say_how_many_bytes_were_cut():
    blob = b"a,b\n1,2\n3,4\n5,"
    frame, cut = ev.csv_prefix(blob)
    assert frame.to_dict("list") == {"a": [1, 3], "b": [2, 4]} and cut == 2
    whole, none = ev.csv_prefix(b"a,b\n1,2\n")
    assert len(whole) == 1 and none == 0


def test_the_metropt_view_drops_gps_columns_and_keeps_time_order_and_sensors():
    raw = pd.DataFrame(
        {"timestamp": ["2022-04-28 12:33:30.111", "2022-04-28 12:33:29.120"], "TP2": [1.0, 2.0],
         "COMP": [0.0, 1.0], "gpsLat": [41.1, 41.2], "gpsLong": [-8.6, -8.7], "gpsSpeed": [1.0, 2.0], "gpsQuality": [1.0, 1.0]}  # noqa: E501
    )  # fmt: skip
    out = ev.metropt_view(raw)
    assert list(out.columns) == ["timestamp", "TP2", "COMP"]
    assert out["TP2"].tolist() == [2.0, 1.0]  # time order
    assert out["timestamp"].iloc[0] == pd.Timestamp("2022-04-28 12:33:29.120")


def test_the_fugaku_and_metropt_builders_write_views_with_sampling_records(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = tmp_path / "acquired"
    raw = root / "zen_fdata_fugaku" / SNAP / "raw"
    raw.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pandas(_fdata_frame(), preserve_index=False), raw / "21_04.parquet"
    )
    m = root / "zen_metropt2" / SNAP / "raw"
    m.mkdir(parents=True)
    (m / "MetroPT2_head.csv").write_bytes(
        b"timestamp,TP2,gpsLat\n2022-04-28 12:33:29.120,1.0,41.1\n2022-04-28 12:33:30.111,2.0,41.2\n2022-04-28 12:33:31.1"  # noqa: E501
    )
    manifest = {}
    ev._build_fugaku(root, tmp_path / "o" / "deep", manifest)
    ev._build_metropt(root, tmp_path / "o" / "deep", manifest)
    jobs = tmp_path / "o" / "deep" / "zen_fdata_fugaku" / "jobs.csv"
    assert len(pd.read_csv(jobs)) == 3
    f = manifest["zen_fdata_fugaku"]
    assert f["files"] == {"jobs.csv": {"sha256": _sha(jobs), "rows": 3}}
    assert f["sampling"] == {
        "method": "all rows of one monthly Parquet file (2021-04); the other months were not fetched",  # noqa: E501
        "rows_read": 3,
        "source_rows": 3,
        "truncated": False,
    }
    series = tmp_path / "o" / "deep" / "zen_metropt2" / "series.csv"
    assert (
        series.read_text().splitlines()[0] == "timestamp,TP2"
        and len(series.read_text().splitlines()) == 3
    )
    g = manifest["zen_metropt2"]
    assert g["sampling"] == {
        "method": "time-ordered prefix of the CSV (HTTP range from byte 0), not random",
        "bytes_cut_partial_line": 21,
        "rows_dropped": 0,
    }
    assert g["dropped"] == ["GPS position, speed and quality columns"]


# --- Open Library editions (complete nested catalogue records from a dump prefix) -----------------


def _ol_line(number, **extra):
    record = {"key": f"/books/OL{number}M", "type": {"key": "/type/edition"}, "title": f"t{number}",
              "authors": [{"key": "/authors/OL1A"}], "notes": {"type": "/type/text", "value": "free text"}, **extra}  # fmt: skip  # noqa: E501
    return f"/type/edition\t/books/OL{number}M\t3\t2020-01-01T00:00:00.1\t{json.dumps(record)}"


def test_open_library_view_keeps_a_deterministic_hash_subset_drops_free_text_and_sorts_by_key():
    lines = [_ol_line(n, description="d", publishers=["P"]) for n in (5, 3, 9, 1, 7, 2)]
    bad = ["", "only\ttwo", "/type/edition\tk\t1\t2020\tnot json"]
    kept, skipped = ev.open_library_view(lines + bad, modulo=1)
    assert [r["key"] for r in kept] == [f"/books/OL{n}M" for n in (1, 2, 3, 5, 7, 9)]
    assert (
        "notes" not in kept[0] and "description" not in kept[0] and kept[0]["publishers"] == ["P"]
    )
    assert (
        kept[0]["authors"] == [{"key": "/authors/OL1A"}] and skipped == 2
    )  # blank lines are not counted
    some, _ = ev.open_library_view(lines, modulo=2)
    import hashlib as _h

    expected = sorted(
        r
        for r in (f"/books/OL{n}M" for n in (5, 3, 9, 1, 7, 2))
        if int(_h.sha256(r.encode()).hexdigest(), 16) % 2 == 0
    )
    assert [r["key"] for r in some] == expected and 0 < len(some) < 6
    assert ev.open_library_view(lines, modulo=2)[0] == some  # same subset every time


def test_the_open_library_builder_reads_the_gzip_prefix_and_records_the_cut(tmp_path, monkeypatch):
    import gzip

    root = tmp_path / "acquired"
    raw = root / "openlibrary_dump" / SNAP / "raw"
    raw.mkdir(parents=True)
    blob = gzip.compress(("\n".join(_ol_line(n) for n in range(1, 30)) + "\n").encode())
    (raw / "editions_head.txt.gz").write_bytes(blob[: len(blob) * 4 // 5])
    monkeypatch.setattr(ev, "OPENLIBRARY_MODULO", 1)
    manifest = {}
    ev._build_openlibrary(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "openlibrary_dump" / "editions.jsonl"
    rows = [json.loads(x) for x in target.read_text().splitlines()]
    view = manifest["openlibrary_dump"]
    assert len(rows) == view["files"]["editions.jsonl"]["rows"] > 0 and "notes" not in rows[0]
    assert view["sampling"]["stream_complete"] is False and view["sampling"]["modulo"] == 1
    assert view["sampling"]["lines_read"] >= len(rows) and view["sampling"]["lines_skipped"] == 0
    assert view["sampling"]["method"].startswith(
        "gzip prefix of the editions dump in key-text order"
    )
    assert view["dropped"] == ["notes", "description", "first_sentence", "table_of_contents"]


def test_blank_keys_are_missing_not_orphans_in_relation_checks():
    tables = {
        "a": pd.DataFrame({"k": ["1", "", "9", None]}),
        "b": pd.DataFrame({"k": ["1", ""]}),
    }
    spec = {
        "tables": {"a": {"keep": ["k"]}, "b": {"keep": ["k"]}},
        "relations": [["a", "k", "b", "k"]],
    }
    _, relations = ev.tables_view(tables, spec)
    assert relations == [
        {"child": "a.k", "parent": "b.k", "checked": 2, "orphans": 1, "share": 0.5}
    ]


# --- AEGIS OBD signals: one value per pid and second, relative time, no dates or positions -------


def test_the_aegis_view_pivots_pids_to_seconds_since_trip_start_and_drops_absolute_time():
    raw = pd.DataFrame(
        {
            "obdData_id": range(1, 8),
            "trip_id": [2, 2, 2, 2, 1, 1, 1],
            "obdPid": ["0C", "0D", "0C", "0D", "0C", "0C", "0D"],
            "data": ["10", "20", "30", "40", "5", "7", "x"],
            "timestamp": ["2017-01-19 10:00:00.1", "2017-01-19 10:00:00.5", "2017-01-19 10:00:01.2",
                          "2017-01-19 10:00:01.6", "2017-02-01 08:00:00.0", "2017-02-01 08:00:00.9", "2017-02-01 08:00:02.0"],  # noqa: E501
        }
    )  # fmt: skip
    out = ev.aegis_obd_view(raw)
    assert list(out.columns) == ["trip_id", "t_s", "pid_0C", "pid_0D"]
    assert out[["trip_id", "t_s"]].values.tolist() == [[1, 0], [1, 2], [2, 0], [2, 1]]
    first = out.iloc[0]
    assert first["pid_0C"] == 6.0 and pd.isna(first["pid_0D"])  # mean of 5 and 7 inside second 0
    assert pd.isna(out.iloc[1]["pid_0D"])  # an unreadable value stays missing
    assert out.iloc[2]["pid_0C"] == 10.0 and out.iloc[3]["pid_0D"] == 40.0
    assert "timestamp" not in out
    with pytest.raises(ev.ViewError, match="column"):
        ev.aegis_obd_view(raw.drop(columns=["data"]))


def test_the_aegis_builder_reads_only_the_obd_member_and_records_what_was_dropped(tmp_path):
    import zipfile

    root = tmp_path / "acquired"
    raw = root / "zen_aegis_vehicle" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "Automotive-ResearchDataSet-VIF-AEGIS.zip", "w") as z:
        z.writestr(
            "obdData.csv",
            '"obdData_id","trip_id","obdPid","data","timestamp"\n"1","3","0C","9","2017-01-19 16:19:03.045593"\n',  # noqa: E501
        )
        z.writestr("positions.csv", '"lat","lon"\n"47.0","15.4"\n')
    manifest = {}
    ev._build_aegis(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "zen_aegis_vehicle" / "obd.csv"
    assert target.read_text() == "trip_id,t_s,pid_0C\n3,0,9.0\n"
    view = manifest["zen_aegis_vehicle"]
    assert view["files"] == {"obd.csv": {"sha256": _sha(target), "rows": 1}}
    assert view["dropped"] == [
        "positions",
        "gyroscopes",
        "accelerations",
        "absolute dates and times",
        "trip dates",
        "vehicle names",
    ]
    assert (
        view["notes"]
        == "one driver and one vehicle (35 trips); relative time inside each trip only"
    )


# --- CLUE-LDS user events from a zip prefix ------------------------------------------------------


def _clue(n, uid="u-a", kind="file_accessed", **over):
    record = {"params": {"path": "/secret/file"}, "type": kind, "time": f"2017-07-07T08:57:{n:02d}Z", "uid": uid, "id": n, "uidType": "name",  # noqa: E501
              "location": {"city": "Graz", "latitude": 47.0}, **over}  # fmt: skip
    return json.dumps(record)


def test_clue_view_keeps_type_time_role_and_pseudonymous_user_and_drops_params_and_location():
    lines = [
        _clue(2, uid="u-b", role="sales", isLocalIP=True),
        _clue(1),
        "",
        _clue(3, uid="1.2.3.4", uidType="ip"),
    ]
    out = ev.clue_events_view(lines)
    assert list(out.columns) == list(ev.CLUE_COLUMNS)
    assert ev.CLUE_COLUMNS == ("event_id", "time", "user", "type", "role", "is_local_ip")
    assert out["event_id"].tolist() == [1, 2, 3] and out["type"].tolist() == ["file_accessed"] * 3
    assert out["time"].iloc[0] == pd.Timestamp("2017-07-07 08:57:01", tz="UTC")
    assert out["user"].tolist() == [
        ev.pseudonym("u-a"),
        ev.pseudonym("u-b"),
        ev.pseudonym("1.2.3.4"),
    ]
    assert out["role"].tolist()[1] == "sales" and pd.isna(out["role"].iloc[0])
    assert out["is_local_ip"].tolist()[1] is True or out["is_local_ip"].iloc[1] == True  # noqa: E712
    assert "params" not in out and "location" not in out and "uid" not in out
    assert len(ev.clue_events_view([])) == 0


def test_the_clue_builder_reads_the_zip_prefix_caps_the_events_and_records_the_cut(
    tmp_path, monkeypatch
):
    import zipfile

    root = tmp_path / "acquired"
    raw = root / "zen_clue_lds" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "clue_head.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "clue.json", "\n".join(_clue(n % 50, uid=f"u{n % 4}") for n in range(400)) + "\n"
        )
    blob = (raw / "clue_head.zip").read_bytes()
    (raw / "clue_head.zip").write_bytes(blob[: len(blob) * 3 // 4])
    monkeypatch.setattr(ev, "CLUE_MAX_EVENTS", 100)
    manifest = {}
    ev._build_clue(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "zen_clue_lds" / "events.csv"
    assert len(pd.read_csv(target)) == 100
    view = manifest["zen_clue_lds"]
    assert view["files"] == {"events.csv": {"sha256": _sha(target), "rows": 100}}
    assert view["sampling"]["stream_complete"] is False and view["sampling"]["events_kept"] == 100
    assert view["sampling"]["events_read"] >= 100 and view["sampling"]["method"].startswith(
        "zip prefix of clue.json"
    )
    assert view["dropped"] == ["params (paths, groups)", "location", "uidType"]
    assert view["pseudonymised"] == ["user"]


# --- XES event logs (process-mining logs of real organisations) -----------------------------------

XES = """<?xml version="1.0" encoding="UTF-8"?>
<log xes.version="1.0">
 <trace><string key="concept:name" value="c1"/>
  <event><string key="concept:name" value="A"/>
   <date key="time:timestamp" value="2012-01-01T10:00:00.000+01:00"/>
   <string key="lifecycle:transition" value="START"/><string key="org:resource" value="r1"/>
   <float key="amount" value="5.5"/></event>
  <event><string key="concept:name" value="B"/>
   <date key="time:timestamp" value="2012-01-01T11:00:00.000+01:00"/></event>
 </trace>
 <trace><string key="concept:name" value="c2"/>
  <event><string key="concept:name" value="A"/>
   <date key="time:timestamp" value="2012-01-02T10:00:00.000+01:00"/>
   <int key="amount" value="7"/></event>
 </trace>
 <trace><string key="concept:name" value="c3"/>
  <event><string key="concept:name" value="C"/>
   <date key="time:timestamp" value="2012-01-03T10:00:00.000+01:00"/></event>
</log>
"""


def test_the_xes_view_flattens_events_orders_cases_by_hash_pseudonymises_resources_and_keeps_listed_numbers():  # noqa: E501
    import io

    import xes_stream

    fixed = XES.replace("</event>\n</log>", "</event></trace></log>")
    traces = xes_stream.read_traces(io.BytesIO(fixed.encode())).traces
    out = ev.xes_view(traces, modulo=1, numeric=["amount"])
    assert list(out.columns) == [
        "case_id",
        "position",
        "time",
        "activity",
        "transition",
        "resource",
        "amount",
    ]
    assert out["case_id"].tolist() == ["c1", "c1", "c2", "c3"] and out["position"].tolist() == [
        0,
        1,
        0,
        0,
    ]
    assert out["activity"].tolist() == ["A", "B", "A", "C"]
    assert out["time"].iloc[0] == pd.Timestamp("2012-01-01 09:00:00", tz="UTC")  # normalised to UTC
    assert out["resource"].iloc[0] == ev.pseudonym("r1") and pd.isna(out["resource"].iloc[1])
    assert out["transition"].iloc[0] == "START" and pd.isna(out["transition"].iloc[2])
    assert (
        out["amount"].tolist()[0] == 5.5
        and pd.isna(out["amount"].iloc[1])
        and out["amount"].iloc[2] == 7.0
    )
    import hashlib as _h

    some = ev.xes_view(traces, modulo=2, numeric=[])
    want = [c for c in ("c1", "c2", "c3") if int(_h.sha256(c.encode()).hexdigest(), 16) % 2 == 0]
    assert sorted(some["case_id"].unique().tolist()) == want and "amount" not in some


def test_the_xes_builder_reads_gz_and_plain_files_and_records_cut_and_sampling(
    tmp_path, monkeypatch
):
    import gzip

    root = tmp_path / "acquired"
    for name, raw_name, data in (
        (
            "4tu_a",
            "log.xes.gz",
            gzip.compress(XES.replace("</event>\n</log>", "</event></trace></log>").encode()),
        ),
        ("4tu_b", "head.xes", XES[: XES.index('value="c3"')].encode()),
    ):
        folder = root / name / SNAP / "raw"
        folder.mkdir(parents=True)
        (folder / raw_name).write_bytes(data)
    monkeypatch.setattr(ev, "XES_SPECS", {
        "4tu_a": {"file": "log.xes.gz", "modulo": 1, "numeric": ["amount"], "partial": False},
        "4tu_b": {"file": "head.xes", "modulo": 1, "numeric": [], "partial": True}})  # fmt: skip
    manifest = {}
    ev._build_xes(root, tmp_path / "o" / "deep", manifest)
    a, b = manifest["4tu_a"], manifest["4tu_b"]
    assert a["files"]["events.csv"]["rows"] == 4 and a["sampling"] == {"cases_read": 3, "cases_kept": 3, "modulo": 1, "stream_complete": True, "stop": "log_closed", "source_fragment": False, "selection": "complete traces in log order, then one case in 1 by case-name hash; a prefix of the log is not a random sample"}  # fmt: skip  # noqa: E501
    assert b["files"]["events.csv"]["rows"] == 3 and b["sampling"]["cases_read"] == 2
    assert b["sampling"]["stream_complete"] is False and b["sampling"]["source_fragment"] is True
    assert b["sampling"]["stop"] == "input_ended_before_log_closed"
    assert a["pseudonymised"] == ["resource"] and a["dropped"] == ["all trace and event attributes except activity, time, transition, resource and listed numbers"]  # fmt: skip  # noqa: E501


# --- CSV event logs with an explicit schema mapping (one row is one event) ------------------------

CSV_SPEC = {
    "case": "Incident ID", "activity": "Type", "time": "Stamp", "format": "%d-%m-%Y %H:%M:%S",
    "order": "Num", "resource": "Group", "modulo": 1, "sep": ";",
}  # fmt: skip


def _csv_events():
    return pd.DataFrame(
        {
            "Incident ID": ["I2", "I1", "I1", "I1", "I3"],
            "Type": ["Open", "Closed", "Open", "Assign", None],
            "Stamp": ["02-01-2013 10:00:00", "05-01-2013 09:00:00", "01-01-2013 08:00:00",
                      "01-01-2013 08:00:00", "03-01-2013 10:00:00"],
            "Num": ["002", "003", "001", "00A", "004"],
            "Group": ["T1", "T2", "T1", "T1", "T3"],
        }
    )  # fmt: skip


def test_csv_event_view_orders_each_case_by_time_then_the_source_sequence_and_drops_unusable_rows():
    out, info = ev.csv_event_view(_csv_events(), CSV_SPEC)
    assert list(out.columns) == [
        "case_id",
        "position",
        "time",
        "activity",
        "transition",
        "resource",
    ]
    assert out["case_id"].tolist() == ["I1", "I1", "I1", "I2"]
    assert out["activity"].tolist() == ["Open", "Assign", "Closed", "Open"]  # tie broken by Num
    assert out["position"].tolist() == [0, 1, 2, 0]
    assert out["time"].iloc[0] == pd.Timestamp("2013-01-01 08:00:00", tz="UTC")
    assert out["resource"].iloc[0] == ev.pseudonym("T1") and out["transition"].isna().all()
    assert info == {
        "rows": 5,
        "rows_without_activity": 1,
        "rows_without_time": 0,
        "cases": 3,
        "cases_kept": 2,
    }


def test_csv_event_view_counts_unreadable_times_and_selects_cases_by_hash():
    frame = _csv_events()
    frame.loc[0, "Stamp"] = "not a date"
    out, info = ev.csv_event_view(frame, {**CSV_SPEC, "modulo": 1})
    assert info["rows_without_time"] == 1 and "I2" not in out["case_id"].tolist()
    import hashlib as _h

    some, rep = ev.csv_event_view(_csv_events(), {**CSV_SPEC, "modulo": 2})
    want = {c for c in ("I1", "I2") if int(_h.sha256(c.encode()).hexdigest(), 16) % 2 == 0}
    assert set(some["case_id"]) == want and rep["cases_kept"] == len(want)
    with pytest.raises(ev.ViewError, match="column 'Stamp'"):
        ev.csv_event_view(frame.drop(columns=["Stamp"]), CSV_SPEC)


def test_the_csv_event_builder_reads_the_declared_file_and_records_the_mapping(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "4tu_csv" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "log.csv").write_text(
        "Incident ID;Type;Stamp;Num;Group\nI1;Open;01-01-2013 08:00:00;001;T1\nI1;Closed;02-01-2013 08:00:00;002;T1\n"  # noqa: E501
    )
    monkeypatch.setattr(ev, "CSV_EVENT_SPECS", {"4tu_csv": {**CSV_SPEC, "file": "log.csv"}})
    manifest = {}
    ev._build_csv_events(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "4tu_csv" / "events.csv"
    assert len(pd.read_csv(target)) == 2
    view = manifest["4tu_csv"]
    assert view["files"] == {"events.csv": {"sha256": _sha(target), "rows": 2}}
    assert view["sampling"]["cases_kept"] == 1 and view["sampling"]["rows_without_time"] == 0
    assert view["sampling"]["mapping"] == {"case": "Incident ID", "activity": "Type", "time": "Stamp", "order": "Num", "resource": "Group"}  # fmt: skip  # noqa: E501
    assert view["pseudonymised"] == ["resource"]


def test_table_sets_support_other_member_extensions_and_skip_missing_optional_tables(
    tmp_path, monkeypatch
):
    import zipfile

    root = tmp_path / "acquired"
    raw = root / "feed_a" / SNAP / "raw"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "gtfs.zip", "w") as z:
        z.writestr("routes.txt", "route_id,route_name\nR1,x\n")
        z.writestr("trips.txt", "trip_id,route_id\nT1,R1\nT2,R9\n")
    monkeypatch.setattr(ev, "TABLE_SETS", {"feed_a": {
        "archive": {"file": "gtfs.zip", "prefix": "", "ext": ".txt"}, "sep": ",", "quote_none": False,  # noqa: E501
        "dropped": ["names"],
        "tables": {"routes": {"keep": ["route_id"]}, "trips": {"keep": ["trip_id", "route_id"]},
                   "calendar": {"keep": ["service_id"], "optional": True}},
        "relations": [["trips", "route_id", "routes", "route_id"], ["trips", "service_id", "calendar", "service_id"]]}})  # fmt: skip  # noqa: E501
    manifest = {}
    ev._build_tables(root, tmp_path / "o" / "deep", manifest)
    folder = tmp_path / "o" / "deep" / "feed_a"
    assert sorted(p.name for p in folder.iterdir()) == [
        "routes.csv",
        "trips.csv",
    ]  # no calendar table
    view = manifest["feed_a"]
    assert sorted(view["files"]) == ["routes.csv", "trips.csv"]
    assert view["relations"] == [{"child": "trips.route_id", "parent": "routes.route_id", "checked": 2, "orphans": 1, "share": 0.5}]  # fmt: skip  # noqa: E501
    assert view["notes"].endswith("; optional tables absent from the archive: calendar")


# --- Met Museum catalogue records (nested JSON, one request per object) ----------------------------  # noqa: E501


def test_met_view_drops_biographies_and_images_deduplicates_and_sorts_by_object_id():
    records = [
        {"objectID": 9, "title": "b", "artistDisplayBio": "bio text", "primaryImage": "u", "additionalImages": ["x"],  # noqa: E501
         "constituents": [{"name": "n", "role": "Artist"}], "measurements": [{"elementName": "Overall", "elementMeasurements": {"Height": 1.5}}]},  # noqa: E501
        {"objectID": 3, "title": "a", "artistDisplayBio": "other", "tags": None},
        {"objectID": 9, "title": "b again"},
    ]  # fmt: skip
    out = ev.met_objects_view(records)
    assert [r["objectID"] for r in out] == [3, 9] and out[1][
        "title"
    ] == "b"  # first record per id wins
    assert (
        "artistDisplayBio" not in out[0]
        and "primaryImage" not in out[1]
        and "additionalImages" not in out[1]
    )
    assert out[1]["constituents"] == [{"name": "n", "role": "Artist"}]
    assert out[1]["measurements"][0]["elementMeasurements"] == {
        "Height": 1.5
    }  # nested values are kept
    assert records[0]["artistDisplayBio"] == "bio text"  # the input is untouched


def test_the_met_builder_reads_the_object_files_in_id_order_and_counts_unreadable_ones(tmp_path):
    root = tmp_path / "acquired"
    raw = root / "met_museum_objects" / SNAP / "raw"
    raw.mkdir(parents=True)
    for i in (20, 5, 11):
        (raw / f"obj_{i}.json").write_text(
            json.dumps({"objectID": i, "title": f"t{i}", "artistDisplayBio": "x"})
        )
    (raw / "obj_99.json").write_text("not json")
    (raw / "manifest.json").write_text("{}")  # not an object file
    manifest = {}
    ev._build_met(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "met_museum_objects" / "objects.jsonl"
    rows = [json.loads(x) for x in target.read_text().splitlines()]
    assert [r["objectID"] for r in rows] == [5, 11, 20] and "artistDisplayBio" not in rows[0]
    view = manifest["met_museum_objects"]
    assert view["files"] == {"objects.jsonl": {"sha256": _sha(target), "rows": 3}}
    assert view["sampling"] == {"object_files": 4, "unreadable": 1, "method": "object ids chosen as an even stride over the sorted listing, not random"}  # fmt: skip  # noqa: E501
    assert view["dropped"] == [
        "artistDisplayBio",
        "primaryImage",
        "primaryImageSmall",
        "additionalImages",
    ]


# --- Environment Agency daily river flow: one csv per station, one network -----------------------


def test_the_flow_builder_stacks_stations_into_a_panel_and_records_quality_shares(
    tmp_path, monkeypatch
):
    root = tmp_path / "acquired"
    raw = root / "ea_hydrology_flow" / SNAP / "raw"
    raw.mkdir(parents=True)
    head = '"measure","dateTime","date","value","completeness","quality","qcode"\n'
    (raw / "flow_s1.csv").write_text(
        head + '"m1","2020-01-02T09:00:00","2020-01-02","2.5","Complete","Good",""\n'
        '"m1","2020-01-01T09:00:00","2020-01-01","1.5","Incomplete","Estimated",""\n'
    )
    (raw / "flow_s2.csv").write_text(
        head + '"m2","2020-01-01T09:00:00","2020-01-01","","Complete","Unchecked",""\n'
    )
    monkeypatch.setattr(ev, "EA_STATIONS", ["s1", "s2"])
    manifest = {}
    ev._build_ea(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "ea_hydrology_flow" / "flow.csv"
    assert (
        target.read_text()
        == "timestamp,station,value\n2020-01-01,s1,1.5\n2020-01-02,s1,2.5\n2020-01-01,s2,\n"
    )
    view = manifest["ea_hydrology_flow"]
    assert view["files"] == {"flow.csv": {"sha256": _sha(target), "rows": 3}}
    assert view["sampling"] == {"stations": 2, "rows_dropped": 0, "complete_share": 0.6667, "missing_value_share": 0.3333,  # noqa: E501
                                "method": "daily mean flow of stations chosen as an even stride over the sorted measure list"}  # fmt: skip  # noqa: E501


# --- French property transactions (DVF): privacy-reduced sales rows --------------------------------  # noqa: E501


def _dvf_frame():
    return pd.DataFrame(
        {
            "id_mutation": ["2024-2", "2024-1", "2024-1", "2024-3"],
            "date_mutation": ["2024-01-03", "2024-01-02", "2024-01-02", "2024-02-01"],
            "nature_mutation": ["Vente", "Vente", "Vente", "Echange"],
            "valeur_fonciere": ["10000", "346.5", "346.5", ""],
            "adresse_nom_voie": ["RUE A", "RUE B", "RUE B", "RUE C"],
            "id_parcelle": ["p1", "p2", "p2", "p3"],
            "code_commune": ["69123", "69123", "69123", "69381"],
            "type_local": ["Maison", "Appartement", None, "Maison"],
            "surface_reelle_bati": ["100", "50", "", "80"],
            "nombre_pieces_principales": ["4", "2", "", "3"],
            "surface_terrain": ["500", "", "20", "300"],
            "longitude": ["4.8", "4.9", "4.9", "4.7"],
            "latitude": ["45.7", "45.8", "45.8", "45.6"],
        }
    )  # fmt: skip


def test_dvf_view_keeps_commercial_fields_pseudonymises_the_mutation_and_drops_addresses_and_positions():  # noqa: E501
    out = ev.dvf_view(_dvf_frame())
    assert list(out.columns) == list(ev.DVF_COLUMNS)
    assert ev.DVF_COLUMNS == (
        "mutation", "date", "nature", "value_eur", "commune", "local_type", "built_area_m2", "rooms", "land_area_m2",  # noqa: E501
    )  # fmt: skip
    assert out["date"].tolist() == sorted(out["date"].tolist())  # date order
    assert out["mutation"].iloc[0] == ev.pseudonym("2024-1") and out["mutation"].iloc[
        2
    ] == ev.pseudonym("2024-2")
    assert out["value_eur"].tolist()[:2] == [346.5, 346.5] and pd.isna(out["value_eur"].iloc[3])
    assert out["commune"].tolist()[0] == "69123" and out["local_type"].iloc[0] == "Appartement"
    assert pd.isna(out["rooms"].iloc[1]) and out["land_area_m2"].iloc[1] == 20.0
    for gone in ("adresse_nom_voie", "id_parcelle", "longitude", "latitude", "id_mutation"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="column 'valeur_fonciere'"):
        ev.dvf_view(_dvf_frame().drop(columns=["valeur_fonciere"]))


def test_the_dvf_builder_reads_the_gzip_csv_and_records_the_department_scope(tmp_path):
    import gzip

    root = tmp_path / "acquired"
    raw = root / "dgfip_dvf" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "dvf_69_2024.csv.gz").write_bytes(
        gzip.compress(_dvf_frame().to_csv(index=False).encode())
    )
    manifest = {}
    ev._build_dvf(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "dgfip_dvf" / "sales.csv"
    assert len(pd.read_csv(target)) == 4
    view = manifest["dgfip_dvf"]
    assert view["files"] == {"sales.csv": {"sha256": _sha(target), "rows": 4}}
    assert view["pseudonymised"] == ["mutation"] and "address" in view["dropped"][0]
    assert view["sampling"] == {"scope": "department 69 (Rhone), transactions of 2024 only", "rows": 4, "rows_without_value": 1}  # fmt: skip  # noqa: E501


def test_the_gtfs_template_keeps_only_keys_and_the_three_relations_and_registers_every_feed():
    spec = ev._gtfs_spec("feed.zip")
    assert spec == {
        "archive": {"file": "feed.zip", "prefix": "", "ext": ".txt"},
        "sep": ",",
        "quote_none": False,
        "dropped": ["stop and route names", "coordinates", "shapes", "fares", "free text"],
        "tables": {
            "routes": {"keep": ["route_id", "route_type"]},
            "trips": {"keep": ["trip_id", "route_id", "service_id"]},
            "stop_times": {"keep": ["trip_id", "stop_id", "stop_sequence"]},
            "stops": {"keep": ["stop_id"]},
            "calendar_dates": {"keep": ["service_id", "date", "exception_type"], "optional": True},
        },
        "relations": [
            ["trips", "route_id", "routes", "route_id"],
            ["stop_times", "trip_id", "trips", "trip_id"],
            ["stop_times", "stop_id", "stops", "stop_id"],
        ],
    }
    assert len(ev.GTFS_FEEDS) == 12 and all(
        name.endswith(".zip") for name in ev.GTFS_FEEDS.values()
    )
    assert all(
        source in ev.TABLE_SETS for source in ev.GTFS_FEEDS
    )  # the real registry holds every feed


# --- UK Price Paid Data (property sales of England and Wales) --------------------------------------  # noqa: E501

PPD_HEAD = (
    '"{A}","320000","2024-03-20 00:00","NR9 5FP","D","Y","F","24","","DUSTY MILLER DRIVE","EASTON",'
    '"NORWICH","SOUTH NORFOLK","NORFOLK","A","A"\n'
    '"{B}","291000","2024-01-26 00:00","NR20 3UF","S","N","L","8","FLAT 2","CLIFTONVILLE DRIVE","",'
    '"DEREHAM","BRECKLAND","NORFOLK","B","A"\n'
)


def test_price_paid_view_keeps_the_commercial_fields_a_postcode_district_and_a_salted_transaction_id():  # noqa: E501
    frame, cut = ev.csv_prefix_no_header(PPD_HEAD.encode() + b'"{C}","1","2024')
    assert cut == len(b'"{C}","1","2024') and len(frame) == 2
    out = ev.price_paid_view(frame)
    assert list(out.columns) == list(ev.PPD_COLUMNS)
    assert ev.PPD_COLUMNS == (
        "transaction", "price_gbp", "date", "postcode_district", "property_type", "new_build",
        "tenure", "county", "ppd_category", "status",
    )  # fmt: skip
    assert out["date"].tolist() == ["2024-01-26", "2024-03-20"]  # date order, time of day dropped
    assert out["price_gbp"].tolist() == [291000, 320000] and str(out["price_gbp"].dtype) == "int64"
    assert out["postcode_district"].tolist() == ["NR20", "NR9"]
    assert out["transaction"].tolist() == [ev.pseudonym("{B}"), ev.pseudonym("{A}")]
    assert out["property_type"].tolist() == ["S", "D"] and out["new_build"].tolist() == ["N", "Y"]
    assert out["tenure"].tolist() == ["L", "F"] and out["county"].tolist() == ["NORFOLK", "NORFOLK"]
    assert out["ppd_category"].tolist() == ["B", "A"] and out["status"].tolist() == ["A", "A"]
    for gone in ("street", "paon", "saon", "locality", "town", "district"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="16 columns"):
        ev.price_paid_view(frame.iloc[:, :10])


def test_the_price_paid_builder_reads_the_fragment_and_records_the_cut_and_the_scope(tmp_path):
    root = tmp_path / "acquired"
    raw = root / "hmlr_price_paid" / SNAP / "raw"
    raw.mkdir(parents=True)
    (raw / "pp-2024_head.csv").write_bytes(PPD_HEAD.encode() + b'"{C}","5000')
    manifest = {}
    ev._build_ppd(root, tmp_path / "o" / "deep", manifest)
    ev._build_ppd(root, tmp_path / "o" / "deep", manifest)
    target = tmp_path / "o" / "deep" / "hmlr_price_paid" / "sales.csv"
    assert len(pd.read_csv(target)) == 2
    view = manifest["hmlr_price_paid"]
    assert view["files"] == {"sales.csv": {"sha256": _sha(target), "rows": 2}}
    assert view["pseudonymised"] == ["transaction"] and view["salt_label"] == ev.SALT
    assert view["dropped"] == [
        "street, house number, flat, locality, town and district",
        "postcode unit",
    ]
    assert view["sampling"] == {"method": "first bytes of the 2024 file (HTTP range from byte 0), file order, not random", "rows": 2, "bytes_cut_partial_line": 11}  # fmt: skip  # noqa: E501


# --- Online Retail invoice lines (UK e-commerce) ----------------------------------------------------  # noqa: E501


def _retail_frame():
    return pd.DataFrame(
        {
            "InvoiceNo": ["536366", "C536379", "536365", "536365"],
            "StockCode": ["22633", "D", "85123A", "71053"],
            "Description": ["HAND WARMER", "Discount", "WHITE HANGING HEART", "WHITE METAL LANTERN"],  # noqa: E501
            "Quantity": ["6", "-1", "6", "x"],
            "InvoiceDate": ["12/1/2010 8:28", "12/1/2010 9:41", "12/1/2010 8:26", "12/1/2010 8:26"],
            "UnitPrice": ["1.85", "27.50", "2.55", "3.39"],
            "CustomerID": ["17850", None, "17850", "13047.0"],
            "Country": ["United Kingdom", "United Kingdom", "United Kingdom", "France"],
        }
    )  # fmt: skip


def test_retail_view_pseudonymises_invoices_and_customers_flags_cancellations_and_computes_line_values():  # noqa: E501
    out = ev.retail_view(_retail_frame())
    assert list(out.columns) == list(ev.RETAIL_COLUMNS)
    assert ev.RETAIL_COLUMNS == (
        "timestamp", "invoice", "stock_code", "quantity", "unit_price", "line_value", "customer", "country", "cancellation",  # noqa: E501
    )  # fmt: skip
    assert out["timestamp"].tolist() == sorted(out["timestamp"].tolist())
    assert out["invoice"].tolist()[:2] == [ev.pseudonym("536365")] * 2
    assert out["cancellation"].tolist() == [
        False,
        False,
        False,
        True,
    ]  # the invoice number starts with C
    assert out["customer"].iloc[0] == ev.pseudonym("17850") and pd.isna(out["customer"].iloc[3])
    assert out["customer"].iloc[1] == ev.pseudonym(
        "13047"
    )  # a float-formatted id is the same customer
    assert (
        out["line_value"].iloc[0] == pytest.approx(15.3)
        and out["quantity"].iloc[1] != out["quantity"].iloc[1]
    )  # x is missing
    assert pd.isna(out["line_value"].iloc[1])
    assert out["cancellation"].dtype == bool and out["stock_code"].tolist()[0] == "85123A"
    for gone in ("Description", "InvoiceNo", "CustomerID"):
        assert gone not in out
    with pytest.raises(ev.ViewError, match="column 'UnitPrice'"):
        ev.retail_view(_retail_frame().drop(columns=["UnitPrice"]))


def test_the_retail_builder_reads_the_pinned_table_and_records_what_it_dropped(tmp_path):
    root = tmp_path / "acquired"
    (tmp_path / "uci_wave2").mkdir()
    _retail_frame().to_csv(tmp_path / "uci_wave2" / "352.csv", index=False)
    manifest: dict = {}
    ev._build_retail(root, tmp_path / "o", manifest)
    ev._build_retail(root, tmp_path / "o", manifest)
    target = tmp_path / "o" / "uci_online_retail" / "lines.csv"
    assert len(pd.read_csv(target)) == 4 and target.read_text().splitlines()[0] == ",".join(
        ev.RETAIL_COLUMNS
    )
    view = manifest["uci_online_retail"]
    assert view["files"] == {"lines.csv": {"sha256": _sha(target), "rows": 4}}
    assert view["dropped"] == ["product description (free text)"] and view["pseudonymised"] == [
        "invoice",
        "customer",
    ]
    assert view["salt_label"] == ev.SALT and view["sampling"] == {
        "rows_in": 4,
        "cancellations": 1,
        "rows_without_customer": 1,
    }
    assert view["source_snapshot"] == "uci:352 (repository file pinned by checksum)"


def test_retail_view_turns_unreadable_prices_customers_and_dates_into_missing_values():
    raw = _retail_frame()
    raw.loc[0, "UnitPrice"] = "n/a"
    raw.loc[2, "CustomerID"] = "unknown"
    raw.loc[3, "InvoiceDate"] = "not a date"
    out = ev.retail_view(raw)
    assert out["timestamp"].isna().sum() == 1 and out["timestamp"].iloc[-1] is pd.NaT
    assert out["unit_price"].isna().sum() == 1 and out["line_value"].isna().sum() >= 1
    assert out["customer"].isna().sum() == 2  # the missing id and the unreadable one
    ok = ev.retail_view(
        pd.DataFrame({**_retail_frame().to_dict("list"), "InvoiceDate": ["13/01/2010 9:00"] * 4})
    )
    assert ok["timestamp"].isna().all()  # the declared month-first layout rejects a day-first date


def test_retail_view_reads_dates_in_the_declared_month_first_layout():
    raw = _retail_frame()
    raw["InvoiceDate"] = ["12/1/2010 8:28", "1/12/2011 9:41", "12/13/2010 8:26", "2/3/2011 8:26"]
    out = ev.retail_view(raw)
    assert sorted(out["timestamp"].dt.month) == [1, 2, 12, 12]
    assert out["timestamp"].min() == pd.Timestamp("2010-12-01 08:28")


def test_the_retail_builder_keeps_codes_with_leading_zeros_as_text(tmp_path):
    root = tmp_path / "acquired"
    (tmp_path / "uci_wave2").mkdir()
    frame = _retail_frame()
    frame["StockCode"] = ["00123", "0042", "85123", "0007"]
    frame.to_csv(tmp_path / "uci_wave2" / "352.csv", index=False)
    ev._build_retail(root, tmp_path / "o", {})
    out = pd.read_csv(tmp_path / "o" / "uci_online_retail" / "lines.csv", dtype=str)
    assert sorted(out["stock_code"]) == ["0007", "00123", "0042", "85123"]
    assert (
        out["quantity"].tolist().count("6.0") == 2
    )  # numbers were parsed by the view, not the reader


# --- Paleobiology Database occurrences ---------------------------------------------------------------  # noqa: E501


def _pbdb_frame():
    base = {c: ["x", " Mammalia ", "", None] for c in ev.PBDB_TEXT}
    base.update({c: ["1.5", "bad", "3", None] for c in ev.PBDB_NUMBER})
    base["occurrence_no"] = ["30", "10", "20", "x"]
    base["enterer"] = ["a person", "b", "c", "d"]  # contributor names must not reach the view
    base["collection_aka"] = ["free text"] * 4
    return pd.DataFrame(base)


def test_pbdb_view_keeps_the_named_columns_trims_text_and_turns_unreadable_numbers_into_missing():
    out = ev.pbdb_occurrence_view(_pbdb_frame())
    assert list(out.columns) == list(ev.PBDB_COLUMNS) and ev.PBDB_COLUMNS[0] == "occurrence_no"
    assert out["occurrence_no"].iloc[:3].tolist() == [10, 20, 30] and pd.isna(
        out["occurrence_no"].iloc[3]
    )
    assert out["class"].tolist() == [
        "Mammalia",
        pd.NA,
        "x",
        pd.NA,
    ]  # trimmed; blank and missing both missing
    assert out.loc[out["occurrence_no"] == 10, "max_ma"].isna().all()
    assert out.loc[out["occurrence_no"] == 30, "max_ma"].iloc[0] == 1.5
    assert "enterer" not in out and "collection_aka" not in out
    with pytest.raises(ev.ViewError, match="columns not found: .*'lat'"):
        ev.pbdb_occurrence_view(_pbdb_frame().drop(columns=["lat"]))
