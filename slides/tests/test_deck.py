# ruff: noqa: E501
"""Regression tests for the slide generator and its layout checker.

They protect two failures that earlier reviews missed: text colliding on the cover when the
preferred fonts are missing, and six different anomaly types drawn with near-identical pictograms.
The browser-based tests skip when no Chromium binary is available.
"""

import collections
import pathlib
import re
import sys

import pytest

SLIDES = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SLIDES))

import check_layout  # noqa: E402
import deck_lib  # noqa: E402

KINDS = ["missing", "duplicate", "univariate", "multivariate", "drift", "invalid"]
CHROME = check_layout.find_chrome()
needs_chrome = pytest.mark.skipif(CHROME is None, reason="no Chromium binary available")


def _signature(svg):
    """Shape vocabulary of an icon: counts of element types, ignoring colours and coordinates."""
    return collections.Counter(re.findall(r"<(rect|circle|line|path|polyline|polygon|text)\b", svg))


def test_type_icons_differ_in_structure_not_only_colour():
    icons = {k: deck_lib.type_icon(k, 0, 0) for k in KINDS}
    assert len({v for v in icons.values()}) == len(KINDS)
    sigs = {k: _signature(v) for k, v in icons.items()}
    for a in KINDS:
        for b in KINDS:
            if a < b:
                assert sigs[a] != sigs[b], f"{a} and {b} use the same shape vocabulary"


def test_type_icons_carry_a_text_cue_besides_colour():
    for k in KINDS:
        svg = deck_lib.type_icon(k, 0, 0)
        assert len(re.findall(r"<text\b", svg)) >= 2, f"{k} has no word marking the defect"


def test_type_icons_do_not_reuse_the_pad_glyph_motif():
    pad = deck_lib.glyph("missing", 0, 0, 100)
    assert pad not in deck_lib.type_icon("missing", 0, 0)


FIXTURE = """<!doctype html><html><head><meta charset='utf-8'><style>
body{{margin:0}} .slide{{position:relative;width:1280px;height:720px}} .slide>*{{position:absolute}}
</style></head><body>
<section class='slide on'>{body}</section>
<script>{probe}</script></body></html>"""


def _run(tmp_path, body, stress=False):
    page = tmp_path / "page.html"
    page.write_text(
        FIXTURE.format(body=body, probe=(check_layout.HERE / "layout_probe.js").read_text())
    )
    return check_layout.probe(page, CHROME, stress)


@needs_chrome
def test_probe_detects_overlapping_text(tmp_path):
    bad = "<p style='left:60px;top:100px;width:400px;font:30px Arial'>First block of text</p><p style='left:60px;top:105px;width:400px;font:30px Arial'>Second block of text</p>"
    assert any(i["kind"] == "text-overlap" for i in _run(tmp_path, bad))


@needs_chrome
def test_probe_detects_text_leaving_the_slide(tmp_path):
    bad = "<p style='left:1100px;top:100px;width:400px;font:30px Arial;white-space:nowrap'>Runs past the right edge</p>"
    assert any(i["kind"] == "outside-slide" for i in _run(tmp_path, bad))


@needs_chrome
def test_probe_accepts_clean_and_layered_content(tmp_path):
    ok = "<div style='left:0;top:0;width:1280px;height:720px;background:#333'></div><p style='left:60px;top:100px;width:400px;font:30px Arial'>Text over a background layer</p><p style='left:60px;top:200px;width:400px;font:30px Arial'>Separate block</p>"
    assert _run(tmp_path, ok) == []


def _deck_issues(stress):
    import build_deck

    build_deck.assemble()
    return check_layout.probe(SLIDES / "thesis_progress.html", CHROME, stress)


@needs_chrome
@pytest.mark.parametrize("stress", [False, True], ids=["preferred fonts", "fallback fonts"])
def test_cover_and_type_slide_have_no_collisions(stress):
    issues = [i for i in _deck_issues(stress) if i["slide"] in (1, 5)]
    assert issues == []


@needs_chrome
def test_whole_deck_has_no_layout_issues():
    assert _deck_issues(False) == []
