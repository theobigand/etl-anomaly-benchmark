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
needs_chrome = pytest.mark.browser


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
def test_probe_detects_words_below_the_minimum_size(tmp_path):
    bad = "<p style='left:60px;top:100px;width:600px;font:11px Arial'>A caption that is too small to read</p>"
    assert any(i["kind"] == "small-text" for i in _run(tmp_path, bad))
    ok = "<p style='left:60px;top:100px;width:600px;font:14px Arial'>A caption at the minimum size</p>"
    assert _run(tmp_path, ok) == []


@needs_chrome
def test_probe_detects_text_crowding_the_source_line(tmp_path):
    bad = "<p style='left:60px;top:640px;width:600px;font:20px/1.4 Arial'>Body text that runs down to the footer line</p><div class='src' style='left:60px;top:678px;font:14px Arial'>source line</div>"
    assert any(i["kind"] == "crowds-footer" for i in _run(tmp_path, bad))
    ok = "<p style='left:60px;top:560px;width:600px;font:20px/1.4 Arial'>Body text that ends well above the footer</p><div class='src' style='left:60px;top:678px;font:14px Arial'>source line</div>"
    assert _run(tmp_path, ok) == []


@needs_chrome
def test_probe_detects_a_box_edge_running_through_text(tmp_path):
    # the failure of the routing slide: a stroked box drawn over the caption below it
    bad = "<svg style='left:60px;top:100px' width='500' height='200'><rect x='10' y='10' width='400' height='150' fill='none' stroke='#000' stroke-width='2'/><text x='20' y='164' font-size='18'>a caption cut by the bottom edge</text></svg>"
    assert any(i["kind"] == "box-crosses-text" for i in _run(tmp_path, bad))
    ok = "<svg style='left:60px;top:100px' width='500' height='200'><rect x='10' y='10' width='400' height='150' fill='none' stroke='#000' stroke-width='2'/><text x='20' y='60' font-size='18'>text inside the box</text><text x='20' y='190' font-size='18'>text below the box</text></svg>"
    assert _run(tmp_path, ok) == []


@needs_chrome
def test_probe_detects_text_hidden_behind_a_later_shape(tmp_path):
    # the Linux failure of slide 5: a title that wrapped to a second line behind a diagram panel
    bad = "<p style='left:60px;top:100px;width:500px;font:24px Arial'>A title whose second line is hidden</p><svg style='left:40px;top:90px' width='600' height='80'><rect x='0' y='0' width='600' height='80' fill='#222'/></svg>"
    assert any(i["kind"] == "text-occluded" for i in _run(tmp_path, bad))
    ok = "<svg style='left:40px;top:90px' width='600' height='80'><rect x='0' y='0' width='600' height='80' fill='#222'/></svg><p style='left:60px;top:100px;width:500px;font:24px Arial;color:#fff'>Text drawn over the panel</p>"
    assert _run(tmp_path, ok) == []


@needs_chrome
def test_single_line_titles_shrink_instead_of_wrapping(tmp_path):
    long_title = (
        "A controlled dataset that labels six anomaly types separately and then some more words"
    )
    page = FIXTURE.format(
        body=f"<h2 class='fit1' style='left:64px;top:60px;width:700px;margin:0;font:46px Arial'>{long_title}</h2><p style='left:64px;top:118px;width:700px;font:20px Arial'>Content that starts right below a one-line title</p>",
        probe=(check_layout.HERE / "layout_probe.js").read_text(),
    )
    page = page.replace(
        "<script>",
        "<script>window.fitFlow=function(s){s.querySelectorAll('.fit1').forEach(function(e){var b=parseFloat(getComputedStyle(e).fontSize);e.style.whiteSpace='nowrap';var k=e.clientWidth/e.scrollWidth;e.style.whiteSpace='';if(k<1)e.style.fontSize=b*Math.max(0.72,k)+'px';});};",
        1,
    )
    path = tmp_path / "t.html"
    path.write_text(page)
    assert check_layout.probe(path, CHROME) == []


@needs_chrome
def test_probe_detects_a_rotated_label_leaving_its_svg(tmp_path):
    bad = "<svg style='left:100px;top:100px' width='200' height='100'><text x='2' y='50' font-size='14' transform='rotate(-90 2 50)'>precision</text></svg>"
    assert any(i["kind"] == "outside-svg" for i in _run(tmp_path, bad))


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


FONT_IDS = [name for name, _ in check_layout.FONT_MATRIX]


def _deck_issues_for(opts):
    import build_deck

    build_deck.assemble()
    return check_layout.probe(
        SLIDES / "thesis_progress.html", CHROME, opts.get("stress", False), opts.get("fonts")
    )


@needs_chrome
@pytest.mark.parametrize("opts", [o for _, o in check_layout.FONT_MATRIX], ids=FONT_IDS)
def test_cover_and_type_slide_have_no_collisions(opts):
    issues = [i for i in _deck_issues_for(opts) if i["slide"] in (1, 5)]
    assert issues == []


@needs_chrome
@pytest.mark.parametrize("opts", [o for _, o in check_layout.FONT_MATRIX], ids=FONT_IDS)
def test_whole_deck_has_no_layout_issues_in_every_font_configuration(opts):
    assert _deck_issues_for(opts) == []


def test_matrix_cell_text_has_wcag_contrast_on_every_fill():
    worst = min(
        deck_lib.contrast(deck_lib.cividis(i / 100), deck_lib.text_on(deck_lib.cividis(i / 100)))
        for i in range(101)
    )
    assert worst >= 4.5, f"lowest matrix text contrast is {worst:.2f}"


def test_native_pr_curves_are_the_recorded_data():
    d = deck_lib.PR_DATA["datasets"]
    assert set(d) == {"credit_card", "water_quality", "cardio", "synthetic"}
    for ds in d.values():
        for m in ds["methods"].values():
            xs = [p[0] for p in m["points"]]
            assert xs == sorted(xs) and xs[0] == 0.0 and 0.0 <= m["ap"] <= 1.0
    assert round(d["cardio"]["methods"]["isolation_forest"]["ap"], 2) == 0.80


def test_severity_panels_use_only_methods_that_exist_in_the_csv():
    import csv

    methods = {r["method"] for r in csv.DictReader(deck_lib.SEVERITY_CSV.open())}
    svg = deck_lib.severity_panels(
        0, 0, 1152, 318, "dark", {"temporal_drift": [("isolation_forest", "A"), ("drift", "D")]}
    )
    assert {"isolation_forest", "drift"} <= methods and svg.count("<polyline") >= 12 * 3


def _slides_text():
    import build_deck  # noqa: F401  (importing registers the slides)

    return {i + 1: re.sub(r"<[^>]+>", " ", s["body"]) for i, s in enumerate(deck_lib.SLIDES)}


def test_severity_slide_does_not_claim_a_stable_ranking():
    # the paper says the ranking changes with severity; an earlier title said the opposite
    text = _slides_text()[23].lower()
    assert "stable" not in text and "same families lead the same columns" not in text


def test_pad_plates_state_their_role_and_the_lit_count_is_the_labelled_count():
    import deck_b

    assert len(deck_b.labelled) == 100 and len(deck_b._cells) == 152
    text = _slides_text()
    assert "illustration" in text[13].lower() and "not data" in text[13].lower()
    assert "arbitrary" in text[24].lower()


# Statements the paper or the committed evidence contradict. Each was on a slide once; the reason is the source.
FORBIDDEN = [
    (
        "do not scale to 284k",
        "paper: LOF and One-Class SVM were expected to be too costly, not measured",
    ),
    ("neither scales", "paper: LOF and One-Class SVM were expected to be too costly, not measured"),
    (
        "do not survive the full fraud",
        "paper: not measured; slide 37 shows LOF finishing 300,000 rows in 133 s",
    ),
    ("pre-registered", "paper: several analyses are post hoc or exploratory"),
    (
        "0.01 &rarr; 0.20",
        "paper: 0.01 to 0.28 on the seed of the table, 0.20 only as a five-seed mean",
    ),
    (
        "0.70 for drift",
        "paper: lowest rank correlation is drift at 0.63 with the seventeen detectors",
    ),
    (
        "Nine of 82",
        "six of the nine modules are not in the 82-module campaign inventory (risk-native-campaign-2026-11-07.json)",
    ),
    ("per-type ranking does not change", "paper: the ranking changes with severity"),
]


@pytest.mark.parametrize("phrase,reason", FORBIDDEN, ids=[f[0] for f in FORBIDDEN])
def test_deck_does_not_repeat_a_claim_the_sources_contradict(phrase, reason):
    import build_deck  # noqa: F401  (importing registers the slides)

    for n, s in enumerate(deck_lib.SLIDES, 1):
        assert phrase not in s["body"], f"slide {n}: {phrase!r} ({reason})"


def test_slide_47_counts_equal_the_focused_diagnostics_table():
    """Publication drift guard: the chart of slide 47 is the table of the diagnostics note."""
    import build_deck  # noqa: F401  (importing registers the slides)
    import deck_c

    note = (
        SLIDES.parent / "docs/thesis-remediation/MUTATION_FOCUSED_DIAGNOSTICS_2026-11-11.md"
    ).read_text()
    table = {}
    for line in note.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[0].startswith("`research/") and cells[1] == "L4":
            before, after = (re.search(r"(\d+)/(\d+)", c) for c in cells[2:4])
            if before and after:
                table[cells[0].strip("`").split("/")[-1][:-3]] = (
                    int(before[1]) / int(before[2]),
                    int(after[1]) / int(after[2]),
                )
    assert len(deck_c.mods) == 9
    for name, b, a in deck_c.mods:
        assert table[name] == pytest.approx((b, a)), f"slide 47 and the note disagree on {name}"
