# ruff: noqa: E501
"""Slides for the pool, time and decisions, the deeper studies and the summary."""

import math
import pathlib
import random
import re

from deck_lib import (
    BONE,
    DARK,
    MATRIX,
    TYPES,
    D,
    cividis,
    flow,
    foot,
    hbars,
    interval_dots,
    matrix,
    mono,
    padfield,
    slide,
    svg,
    txt,
)

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent


def kicker(s):
    return D(64, 44, 900, None, "k", s)


def title(s, size=46, y=70, w=1152):
    return D(64, y + 8, w, None, "", f"<h2 style='font-size:{size}px;line-height:1.04'>{s}</h2>")


# 24 ----------------------------------------------------------------- opener part 3: 152 pads
kinds = {}
_cells = [(col, r) for r in range(8) for col in range(19)]
random.Random(24).shuffle(
    _cells
)  # which pads are lit is arbitrary; only the count (100 of 152) is data
labelled = set(_cells[:100])
slide(
    "Part 3",
    "".join(
        [
            padfield(19, 8, {}, seed=21, mark=labelled, dim_unmarked=True),
            D(
                0,
                0,
                1280,
                720,
                "scrim",
                "",
                "background:linear-gradient(0deg,rgba(10,10,10,.9) 0,rgba(10,10,10,.72) 24%,rgba(10,10,10,0) 48%),linear-gradient(90deg,rgba(10,10,10,.78) 0%,rgba(10,10,10,.4) 55%,rgba(10,10,10,0) 100%)",
            ),
            D(64, 56, 600, None, "k", "Part 3 of 4"),
            D(
                64,
                262,
                840,
                None,
                "",
                "<h1 style='font-size:92px;line-height:.98'>From three examples to <span class='em'>a pool of 152</span></h1>",
            ),
            D(
                64,
                520,
                640,
                None,
                "",
                "<p class='lede' style='color:#c4bfb3'>Real tables, pinned and checked; what holds, what fails, and what changes with time.</p>",
            ),
            D(
                64,
                664,
                900,
                None,
                "note",
                "Illustration: one pad per pool table (152); the 100 with a lit edge stand for the labelled problems. Which pads are lit is arbitrary. Coded SVG.",
            ),
        ]
    ),
    role="transition",
    family="coded plate",
    dominant="152 pads, 100 lit",
    density="low",
    image="SVG plate",
    light="raking, lower left",
    colour="amber edge = labelled",
)


# 25 ----------------------------------------------------------------- funnel (reconciled)
def box(x, y, w, h, t, s, ok=False):
    b = "var(--steel-ink)" if ok else "var(--ink)"
    bg = "var(--steel-wash)" if ok else "transparent"
    return f"<div style='position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;border:2px solid {b};background:{bg};padding:8px 12px;overflow:hidden'><div class='num' style='font-size:40px'>{t}</div><div style='font:500 15px/1.25 var(--sans);margin-top:4px'>{s}</div></div>"


def arrow(x, y, w):
    return f"<div style='position:absolute;left:{x}px;top:{y}px;width:{w}px;height:2px;background:var(--ink)'></div>"


funnel = "".join(
    [
        "<div class='k' style='position:absolute;left:0;top:0'>ADBench</div>",
        box(0, 26, 190, 104, "47", "tabular sets in the commit"),
        arrow(190, 78, 40),
        box(230, 26, 190, 104, "36", "kept: terms read and open", True),
        "<div style='position:absolute;left:440px;top:52px;font:500 15px var(--sans);color:var(--ink-soft)'>11 excluded: no open licence or terms forbid use<br>(celeba, mammography, vowels ...)</div>",
        "<div class='k' style='position:absolute;left:0;top:150px'>UCI repository</div>",
        box(0, 178, 190, 104, "689", "catalogue entries"),
        arrow(190, 230, 40),
        box(230, 178, 190, 104, "133", "pass metadata and licence filters"),
        arrow(420, 230, 40),
        box(460, 178, 190, 104, "116", "kept after curation", True),
        "<div style='position:absolute;left:670px;top:196px;font:500 15px var(--sans);color:var(--ink-soft)'>17 removed with a reason<br>(version duplicates, rule-labelled, boards)</div>",
    ]
)
slide(
    "The pool",
    "".join(
        [
            kicker("Real data at scale &nbsp;·&nbsp; issue #66"),
            title("A pool of 152 open datasets, pinned and checked", 46, 70),
            D(64, 176, 1000, 290, "", funnel),
            D(64, 478, 1152, 1, "hair"),
            D(
                64,
                494,
                330,
                None,
                "stat sm",
                "<span class='num'>36 + 116</span><span class='lab'>= <b>152</b> pinned datasets: ADBench kept plus UCI curated</span>",
            ),
            D(
                424,
                494,
                360,
                None,
                "stat sm",
                "<span class='num'>116</span><span class='lab'>UCI tables as clean carriers for typed injection</span>",
            ),
            D(
                814,
                494,
                402,
                None,
                "stat sm",
                "<span class='num'>36 + 64</span><span class='lab'>= <b>100</b> labelled problems; rule fixed before any detector: the rarest class is the anomaly</span>",
            ),
            D(
                64,
                626,
                1152,
                None,
                "note",
                "One normalisation policy for all sets, applied in order. 19 sources appear in both lists with a different derivation. Raw data stays out of the repository; checksums, licences and reports are archived. A download check of every set runs manually and monthly.",
            ),
            foot(
                "verification/dataset_pool.md &nbsp;·&nbsp; research/build_pool.py &nbsp;·&nbsp; the pool is what makes the per-type result general"
            ),
        ]
    ),
    tone="bone",
    role="context",
    family="flow diagram",
    dominant="funnel",
    density="high",
    colour="steel for kept",
)

# 26 ----------------------------------------------------------------- pool: interval dot plot
pool = [
    ("ECOD", 0.240, 0.191, 0.305),
    ("One-Class SVM", 0.240, 0.177, 0.307),
    ("HBOS", 0.237, 0.176, 0.311),
    ("DIF", 0.226, 0.173, 0.272),
    ("VAE", 0.216, 0.163, 0.279),
    ("COPOD", 0.216, 0.162, 0.314),
    ("Isolation Forest", 0.215, 0.158, 0.293),
    ("AE1SVM", 0.210, 0.172, 0.253),
    ("Autoencoder", 0.205, 0.150, 0.240),
    ("Z-score", 0.203, 0.164, 0.279),
    ("KNN", 0.203, 0.172, 0.284),
    ("LUNAR", 0.183, 0.153, 0.225),
    ("Deep SVDD", 0.181, 0.147, 0.226),
    ("PCA", 0.178, 0.152, 0.219),
    ("LOF", 0.165, 0.153, 0.237),
    ("IQR", 0.144, 0.117, 0.191),
    ("Great Expectations", 0.115, 0.105, 0.123),
]
slide(
    "Whole pool",
    "".join(
        [
            D(
                64,
                30,
                900,
                None,
                "k",
                "The whole labelled pool &nbsp;<span class='tag anom'>historical run, needs train-only replay</span>",
            ),
            D(
                64,
                62,
                1152,
                None,
                "",
                "<h2 style='font-size:38px;line-height:1.04'>Historical pool rankings need train-only revalidation</h2>",
            ),
            interval_dots(
                64,
                112,
                700,
                pool,
                "bone",
                vmin=0.09,
                vmax=0.33,
                row_h=27,
                hl=("Great Expectations",),
                axis_label="median AP, with 95% interval",
            ),
            D(
                64,
                626,
                700,
                None,
                "note",
                "Median AP, 95% interval, 100 problems. Intervals overlap: the order is descriptive. LOF, KNN and One-Class SVM skip large problems (92, 92, 84).",
            ),
            D(
                804,
                124,
                412,
                None,
                "",
                "<p style='font-size:19px;line-height:1.38'>Three rules, eight classical and six neural detectors, five seeds, on 36 ADBench and 64 UCI problems. The numbers are retained as recorded.</p>"
                "<p style='font-size:18px;line-height:1.38;margin-top:12px'><span class='tag anom'>open</span> Schema and row filtering precede the split, so these descriptive rankings still need train-only replay.</p>"
                "<p style='font-size:18px;line-height:1.38;margin-top:12px'>The 100 problems come from 80 sources; a post-hoc, exploratory source-clustered re-analysis changes no sign (only Great Expectations, in amber, is clearly below Isolation Forest). Label-rule sensitivity and unrecorded PyOD convergence diagnostics remain open.</p>",
            ),
            D(
                804,
                520,
                190,
                None,
                "stat sm",
                "<span class='num'>17</span><span class='lab' style='font-size:15px'>detectors; no neural exception</span>",
            ),
            D(
                1016,
                520,
                200,
                None,
                "stat sm",
                "<span class='num'>13</span><span class='lab' style='font-size:15px'>problems won by DIF, the most</span>",
            ),
            foot(
                "verification/full_registry.md &nbsp;·&nbsp; research/labelled_benchmark.py &nbsp;·&nbsp; labels from a rare class, not from data-quality defects"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="interval dot plot",
    dominant="17 intervals",
    density="high",
    colour="amber for the one clear gap",
)

# 27 ----------------------------------------------------------------- two examples: matrix
ex_rows = ["Z-score", "IQR", "Isolation Forest", "ECOD", "HBOS", "Autoencoder", "DIF", "LUNAR"]
ex_cols = ["Credit Card", "Cardio", "Annthyroid", "Mushroom"]
ex_data = [
    [0.10, 0.61, 0.18, 0.44],
    [0.02, 0.30, 0.61, 0.10],
    [0.13, 0.70, 0.29, 0.63],
    [0.21, 0.69, 0.28, 0.41],
    [0.26, 0.58, 0.24, 0.50],
    [0.11, 0.35, 0.14, 0.68],
    [0.27, 0.67, 0.23, 0.45],
    [0.15, 0.33, 0.20, 0.96],
]
best = {(max(range(8), key=lambda i: ex_data[i][j]), j) for j in range(4)}
mxx, mhh = matrix(
    64, 150, ex_rows, ex_cols, ex_data, 118, 46, "bone", best=best, font=17, label_w=150, unit="AP"
)
slide(
    "Two more examples",
    "".join(
        [
            kicker(
                "Two more examples from the pool &nbsp;<span class='tag anom'>historical run, needs train-only replay</span>"
            ),
            title("Two regimes the three examples do not show", 46, 66),
            mxx,
            D(
                780,
                160,
                436,
                None,
                "",
                "<p style='font-size:21px'>Among the 100 problems, the largest margin of the rules over the learned models is on <b>Annthyroid</b>: IQR 0.61, best learned 0.31. The largest margin of a neural model is on <b>Mushroom</b>: LUNAR 0.96, best classical 0.63 (label derived by a rule), where the IQR rule is at chance, 0.10.</p><p style='font-size:19px;margin-top:14px'>Chosen after the results, as illustrations, not as a test.</p>",
            ),
            D(
                780,
                470,
                436,
                None,
                "legend",
                "Average precision, mean over 5 seeds, as run in the pool. Circle: best of its column among the rows shown. Colour: cividis, 0 to 1. All 17 detectors are in the paper. Credit Card values come from the pool run and differ from slide 17.",
            ),
            foot(
                "verification/full_registry_results.md &nbsp;·&nbsp; no universal detector, even at the scale of one dataset"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="matrix",
    dominant="8 by 4 matrix",
    density="medium",
    colour="cividis scale",
)

# 28 ----------------------------------------------------------------- typed: synthetic vs real, side by side
summary = (ROOT / "verification/evidence/full_registry/summary.md").read_text().splitlines()
real = {}
for line in summary[4:23]:
    m = re.match(r"\| (\w+) \| (.*) \|$", line)
    if m:
        real[m.group(1)] = [
            float(re.match(r"([\d.]+)", c.strip()).group(1)) for c in m.group(2).split("|")
        ]
keys = [
    "zscore",
    "iqr",
    "great_expectations",
    "isolation_forest",
    "lof",
    "ocsvm",
    "ecod",
    "copod",
    "hbos",
    "knn",
    "pca",
    "autoencoder",
    "vae",
    "deep_svdd",
    "dif",
    "ae1svm",
    "lunar",
]
real_data = [real[k] for k in keys]
syn_data = [[MATRIX["data"][n][t] for t in TYPES] for n in MATRIX["order"]]
ABBR = ["miss.", "dup.", "univ.", "multi.", "drift", "inv."]
m1, h_m = matrix(
    64, 136, MATRIX["order"], ABBR, syn_data, 58, 24, "dark", font=13, label_w=76, legend=False
)
m2, _ = matrix(
    540, 136, MATRIX["order"], ABBR, real_data, 58, 24, "dark", font=13, label_w=76, legend=True
)
slide(
    "Typed real tables",
    "".join(
        [
            kicker("The six types on real tables &nbsp;·&nbsp; issue #65"),
            title("The synthetic pattern does not simply carry over", 40, 58),
            m1,
            m2,
            D(64, 114, 440, None, "k", "synthetic customers, mean recall"),
            D(540, 114, 440, None, "k", "42 real UCI tables, median recall"),
            D(
                1000,
                140,
                216,
                None,
                "",
                "<p style='font-size:17px;line-height:1.35'>Two rows hold everywhere: Great Expectations finds all missing values, deduplication all duplicates. <b>Three of five hypotheses are not supported.</b></p>",
            ),
            D(
                1000,
                340,
                216,
                None,
                "stat sm",
                "<span class='num' style='font-size:38px'>0.89 &rarr; 0.37</span><span class='lab' style='font-size:15px'>Isolation Forest, multivariate: synthetic to real</span>",
            ),
            D(
                1000,
                470,
                216,
                None,
                "stat sm",
                "<span class='num' style='font-size:52px'>24%</span><span class='lab' style='font-size:15px'>median clean rows flagged by LUNAR</span>",
            ),
            D(
                64,
                622,
                1000,
                None,
                "note",
                "Injected, not natural anomalies; protocol and five hypotheses written before any run. Same row order and the same cividis scale (0 to 1) in both matrices. Real-table rows from verification/evidence/full_registry/summary.md. The duplicate and drift detectors are omitted here.",
            ),
            foot("research/ typed benchmark &nbsp;·&nbsp; verification/typed_injection.md"),
        ]
    ),
    role="evidence",
    family="paired matrices",
    dominant="two matrices",
    density="high",
    colour="cividis scale",
)

# 29 ----------------------------------------------------------------- explained failures
slide(
    "Explained failures",
    "".join(
        [
            kicker("Reading the typed result"),
            title("Two failures that are explained, not hidden", 48, 60),
            D(
                64,
                186,
                560,
                None,
                "",
                "<div class='num' style='font-size:96px'>0.00</div><div class='cond' style='font-size:28px;font-weight:600;margin-top:8px'>Z-score, univariate outliers</div><p style='font-size:19px;margin-top:10px'>Median 0.00 against 0.93 synthetic. A check made after seeing it, so exploratory: invalid rows in the training split inflate the standard deviation (<b>masking</b>). Without them the Z-score finds every univariate outlier on all 42 tables.</p>",
            ),
            D(
                664,
                186,
                552,
                None,
                "",
                "<div class='num' style='font-size:96px'>22%</div><div class='cond' style='font-size:28px;font-weight:600;margin-top:8px'>clean rows flagged by IQR</div><p style='font-size:19px;margin-top:10px'>The IQR fences reach the best detection rate on several types, but only by flagging a median 22% of clean rows; the false positive rate reaches 99% on some wide tables. Detection rate has to be read next to it.</p>",
            ),
            D(64, 520, 1152, 1, "hair"),
            D(
                64,
                540,
                360,
                None,
                "stat sm",
                "<span class='num'>0.80</span><span class='lab' style='font-size:15px'>mean rank correlation between two tables, seventeen detectors (lowest for drift, 0.63; partly mechanical)</span>",
            ),
            D(
                464,
                540,
                360,
                None,
                "stat sm",
                "<span class='num'>&minus;0.96</span><span class='lab' style='font-size:15px'>Isolation Forest univariate detection against the number of columns</span>",
            ),
            D(
                864,
                540,
                352,
                None,
                "note",
                "Injected anomalies, one severity. Deep rows are added on a later slide.",
            ),
            foot(
                "verification/typed_injection.md &nbsp;·&nbsp; non-robust statistics on a contaminated training set, not a weakness of the Z-score as such"
            ),
        ]
    ),
    role="caveat",
    family="typographic pair",
    dominant="two numerals",
    density="medium",
)

# 30 ----------------------------------------------------------------- chronological: slope chart
sl = [
    ("Z-score", 0.078, 0.048),
    ("IQR", 0.018, 0.013),
    ("Great Expectations", 0.183, 0.045),
    ("Isolation Forest", 0.110, 0.035),
]
Y = lambda v: 210 - v / 0.2 * 190  # noqa: E731
o = [
    txt(260, 14, "stratified split", 15, "#55534d", "middle", 600),
    txt(540, 14, "chronological split", 15, "#55534d", "middle", 600),
    "<line x1='260' x2='260' y1='20' y2='212' stroke='#151617' opacity='.4'/><line x1='540' x2='540' y1='20' y2='212' stroke='#151617' opacity='.4'/>",
]
ends = sorted(((Y(b), n) for n, a, b in sl))
pos, last = {}, -99
for yy, n in ends:
    last = max(yy, last + 17)
    pos[n] = last
for n, a, b in sl:
    amb = n in ("Great Expectations", "Isolation Forest")
    col = "#94490a" if amb else "#151617"
    o += [
        f"<line x1='260' x2='540' y1='{Y(a)}' y2='{Y(b)}' stroke='{col}' stroke-width='2.5'/>",
        f"<circle cx='260' cy='{Y(a)}' r='5' fill='{col}'/><circle cx='540' cy='{Y(b)}' r='5' fill='{col}'/>",
        txt(248, Y(a) + 5, f"{n} {a:.3f}", 15, col, "end", 600),
        f"<line x1='545' x2='552' y1='{Y(b)}' y2='{pos[n]}' stroke='{col}' stroke-width='1.2'/>",
        txt(554, pos[n] + 5, f"{n} {b:.3f}", 15, col, "start", 600),
    ]
slide(
    "Chronological",
    "".join(
        [
            kicker("Chronological split"),
            title(
                "Time changes the answer: AP falls and a training threshold does not travel", 40, 60
            ),
            svg(
                64,
                170,
                760,
                240,
                "".join(o),
                "average precision, stratified against chronological split",
            ),
            D(
                64,
                424,
                600,
                None,
                "legend",
                "Average precision on the test split. <span class='anom'>Amber</span>: the 95% block-bootstrap interval excludes the stratified mean (Great Expectations, Isolation Forest). Scale 0 to 0.2.",
            ),
            D(
                64,
                480,
                330,
                None,
                "stat sm",
                "<span class='num'>0.936</span><span class='lab'>Isolation Forest ROC-AUC, chronological</span>",
            ),
            D(
                404,
                480,
                330,
                None,
                "stat sm",
                "<span class='num'>0.08%</span><span class='lab'>future rows it flags: none of the 52 frauds</span>",
            ),
            D(
                850,
                170,
                366,
                None,
                "",
                "<p style='font-size:19px'>Credit Card is the only one of the three examples with a clock. Detectors are fitted on the first 70% of time and scored on the last 15% (52 frauds). Average precision drops for all four detectors.</p><p style='font-size:19px;margin-top:12px'><span class='tag anom'>caveat</span> Prevalence also changes between partitions, so the pilot does not separate it from the effect of time.</p><p class='note' style='margin-top:12px'>The window monitor detects mean shifts of 1 and 2 standard deviations, not 0.5.</p>",
            ),
            foot(
                "verification/temporal_pilot.md &nbsp;·&nbsp; one two-day dataset: a direction, not a rule"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="slope chart",
    dominant="four slopes",
    density="medium",
    colour="amber for significant drop",
)


# 31 ----------------------------------------------------------------- prevalence: two pad grids
def grid(x, y, n_raised, label, sub):
    cells = list(range(100))
    random.Random(63 + n_raised).shuffle(cells)  # positions are arbitrary; only the count is data
    raised = {(c % 10, c // 10): "raised" for c in cells[:n_raised]}
    return padfield_box(x, y, raised) + D(
        x,
        y + 372,
        360,
        None,
        "",
        f"<div class='num' style='font-size:56px'>{label}</div><div class='note' style='font-size:15px'>{sub}</div>",
    )


def padfield_box(x, y, kinds):
    inner = padfield(10, 10, kinds, 360, 360, seed=40 + len(kinds))
    return inner.replace(
        "style='position:absolute;left:0px;top:0px'",
        f"style='position:absolute;left:{x}px;top:{y}px'",
    )


slide(
    "Decisions under shift",
    "".join(
        [
            kicker("Decisions under shift &nbsp;·&nbsp; issue #63"),
            title("Part of the gap is only the prevalence", 46, 60),
            grid(64, 150, 6, "5.8%", "anomalous in training, Bank Marketing"),
            grid(440, 150, 39, "39.3%", "anomalous in test, same dataset"),
            flow(
                832,
                150,
                384,
                [
                    "<p style='font-size:19px'>Credit Card and Bank Marketing (UCI, ordered by date 2008 to 2010), four detectors, three label-free thresholds. Matching the stratified control to the test prevalence removes most of the gap. A rolling threshold that keeps the training prevalence cannot follow it. One hypothesis of four holds.</p>",
                    "<div class='stat sm'><span class='num'>0.26 &rarr; 0.06</span><span class='lab' style='font-size:16px'>median AP gap on Bank Marketing after prevalence matching</span></div>",
                    "<div class='note'>F1 at the threshold, test period: Bank Z-score 0.51 (P0) against 0.02 (P2 rolling); Isolation Forest 0.41 against 0.11. Rank correlation of the detector order, stratified against chronological: 0.80 on Bank Marketing, 0.40 on Credit Card. Kyoto-2006+ left out: rights and download not verified.</div>",
                ],
                maxh=490,
                gap=16,
            ),
            D(
                64,
                630,
                800,
                None,
                "note",
                "Illustration: each grid is 100 pads; raised pads stand for the anomalous share (6 and 39 pads, rounded); where they stand is arbitrary.",
            ),
            foot(
                "verification/temporal_decision.md &nbsp;·&nbsp; research/temporal_decision.py &nbsp;·&nbsp; Credit Card results were known before the protocol"
            ),
        ]
    ),
    role="evidence",
    family="pad pictogram",
    dominant="two lit grids",
    density="medium",
    image="SVG pads",
    light="raking, lower left",
    colour="amber on raised pads",
)

# 32 ----------------------------------------------------------------- alert budget: intervals
ab = [
    ("scores shifted +1 sigma", 4.09, 3.50, 4.77),
    ("scores scaled x2", 4.86, 4.57, 5.19),
    ("noise of 1 sigma", 1.55, 1.32, 1.81),
    ("every feature drifted 1/2 sigma", 20.90, 17.39, 24.55),
    ("monotone change, fit and test", 0.001, 0.0, 0.003),
]
slide(
    "Alert budget",
    "".join(
        [
            D(
                64,
                40,
                900,
                None,
                "k",
                "Exploratory deployment thresholds, issue #94 &nbsp;<span class='tag anom'>exploratory, one machine</span>",
            ),
            title("A nominal alert budget is not a promise", 46, 68),
            D(
                64,
                140,
                900,
                None,
                "k",
                "added alert volume at a 2% budget, in budgets (95% interval)",
            ),
            interval_dots(
                64,
                160,
                1152,
                ab,
                "bone",
                vmin=0,
                vmax=26,
                row_h=44,
                label_w=300,
                ticks=(0, 5, 10, 15, 20, 25),
                fmt="{:g}",
                axis_label="added alert volume, in budgets (95% interval)",
            ),
            D(64, 440, 1152, 1, "hair"),
            D(
                64,
                462,
                250,
                None,
                "stat sm",
                "<span class='num'>+4.1</span><span class='lab' style='font-size:16px'>budgets of added alert volume at 2% (about 5 times nominal) for a 1 sigma score shift, with ROC-AUC unchanged</span>",
            ),
            flow(
                340,
                462,
                340,
                [
                    "<p style='font-size:19px'>Budgets of 0.5 to 10% are set from training scores only, on 100 labelled problems. Held-out alert volume was <b>1.05 to 1.36</b> times the nominal 1% budget for classical detectors and <b>1.13 to 2.87</b> times for neural ones.</p>"
                ],
                maxh=210,
            ),
            flow(
                710,
                462,
                506,
                [
                    "<p class='note' style='font-size:15px;line-height:1.4'>"
                    + "Five classical detectors, 98 problems from 78 sources, sources resampled whole, Holm-adjusted. Delta ROC-AUC is 0.000 for the shifts and scalings and the monotone change, -0.038 for noise and -0.051 for feature drift. Prevalence reweighted under a label-shift assumption: 0.83 to 1.83 times the budget at 0.5% prevalence, 1.15 to 2.73 times at 20%."
                    + "</p>",
                    "<p class='note' style='font-size:15px;line-height:1.4'>"
                    + "The 30-expected-alert rule for monitoring was chosen after the false alarms were seen. Not promoted to the main tables."
                    + "</p>",
                ],
                maxh=210,
                gap=10,
            ),
            foot(
                "docs/thesis-remediation/SCORE_SHIFT_T170_T171_2026-11-11.md &nbsp;·&nbsp; research/score_shift.py"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="wide interval chart over a three-part band",
    dominant="five intervals",
    density="medium",
    colour="neutral",
)

# 33 ----------------------------------------------------------------- hypotheses
hyp = [
    ("P1", "label-free threshold lowers F1", 1, "14 of 17 detectors"),
    ("P2", "curve ranking = AP ranking", 0, "Spearman 0.90 (&lt; 0.99)"),
    ("P3", "recall rises with severity", 0, "13 of 17; column-wise rules stay at 0"),
    ("P4", "detection share of the pipeline", 1, "62% (IF), 4% (Z-score), 14 datasets"),
    ("P5", "chronological AP lower", 0, "31 of 64 pairs; Bank Marketing 0/16"),
    ("P6", "files match the manifest", 1, "152 of 152"),
]
body = [
    kicker(
        "Every study on the whole pool &nbsp;<span class='tag anom'>historical run, needs train-only replay</span>"
    ),
    title("The deeper studies, run where they are defined on the 152-dataset pool", 40, 62),
]
for i, (p, h, ok, v) in enumerate(hyp):
    y = 150 + i * 56
    cls, word, sym = ("ok", "holds", "&#10003;") if ok else ("anom", "not supported", "&#10007;")
    body += [
        D(64, y - 6, 1152, 1, "hair"),
        D(64, y + 4, 80, None, "", f"<span class='num' style='font-size:36px'>{p}</span>"),
        D(160, y + 8, 470, None, "", f"<div style='font:500 23px var(--sans)'>{h}</div>"),
        D(650, y + 6, 220, None, "", f"<span class='tag {cls}'>{sym} {word}</span>"),
        D(900, y + 10, 316, None, "", f"<div style='font:500 17px/1.25 var(--sans)'>{v}</div>"),
    ]
body += [
    D(64, 150 + 6 * 56 - 6, 1152, 1, "hair"),
    D(
        64,
        520,
        330,
        None,
        "stat sm",
        "<span class='num'>58 / 152</span><span class='lab'>tables eligible for typed injection and severity</span>",
    ),
    D(
        420,
        520,
        330,
        None,
        "stat sm",
        "<span class='num'>290 / 304</span><span class='lab'>end-to-end pipeline runs that completed</span>",
    ),
    flow(
        790,
        524,
        426,
        [
            "<p class='note' style='font-size:15px;line-height:1.4'>Six hypotheses written first: three hold, three do not. Chronology needs a real time variable: 5 labelled datasets qualify (ADBench has none). Each study ran on every dataset where it is defined; the others are listed with a reason, never silently.</p>"
        ],
        maxh=140,
    ),
    foot("verification/pool_extension_results.md"),
]
slide(
    "Deeper studies",
    "".join(body),
    tone="bone",
    role="evidence",
    family="full-width hypothesis ledger with numeral band",
    dominant="verdict tags",
    density="medium",
    colour="steel holds, amber not supported",
)

# 34 ----------------------------------------------------------------- LSTM
syn, h1 = hbars(
    64,
    230,
    520,
    [("LSTM autoencoder", 0.875, "best"), ("row autoencoder", 0.006, "n")],
    1.0,
    "dark",
    label_w=190,
    digits=3,
)
real, h2 = hbars(
    640,
    230,
    576,
    [
        ("Great Expectations", 0.045, "best"),
        ("LSTM autoencoder", 0.037, "n"),
        ("Isolation Forest", 0.035, "n"),
        ("row autoencoder", 0.024, "n"),
    ],
    0.05,
    "dark",
    label_w=190,
    digits=3,
)
slide(
    "LSTM",
    "".join(
        [
            kicker("First deep model &nbsp;·&nbsp; issue #52"),
            title(
                "An LSTM autoencoder wins on a broken stream, only matches on real fraud", 40, 62
            ),
            D(64, 190, 520, None, "k", "synthetic stream with broken continuity, AP"),
            syn,
            D(
                640,
                190,
                576,
                None,
                "k",
                "real Credit Card frauds, AP (own scale)",
            ),
            real,
            D(
                64,
                420,
                520,
                None,
                "",
                "<p style='font-size:19px'>On a synthetic stream with broken continuity the LSTM wins by a wide margin. The window is the ten previous rows of the global stream, since Credit Card has no cardholder. Protocol and a CPU budget of 20 epochs were fixed beforehand.</p>",
            ),
            D(
                640,
                420,
                576,
                None,
                "",
                "<p style='font-size:19px'>On the real frauds it only matches Isolation Forest and Great Expectations. Paired bootstrap, main seed: +0.021 [+0.005, +0.044]; on the other four seeds the interval includes 0.</p>",
            ),
            D(64, 566, 1152, 1, "hair"),
            D(
                64,
                584,
                1152,
                None,
                "",
                "<p style='font-size:20px'><span class='tag anom'>limit</span> None of five trainings converged within the 20-epoch budget. Recall of frauds in the later period is at most 0.02, and in the per-type matrix the LSTM does not fix drift.</p>",
            ),
            foot(
                "verification/lstm_pilot.md &nbsp;·&nbsp; research/lstm_pilot.py &nbsp;·&nbsp; an indication from a budget-limited pilot, not a ranking"
            ),
        ]
    ),
    role="evidence",
    family="paired bar charts",
    dominant="two scales",
    density="medium",
    colour="neutral; amber for limit",
)

# 35 ----------------------------------------------------------------- schemas: strip plot
sch = [
    ("Great Expectations, missing values", (1.00, 1.00, 1.00), True),
    ("Isolation Forest, multivariate", (0.89, 0.49, 0.32), False),
    ("One-Class SVM, multivariate", (0.90, 0.18, 0.33), False),
    ("best detector, drift", (0.50, 0.38, 0.96), False),
]
X = lambda v: 330 + v * 560  # noqa: E731
o = []
for g in (0, 0.25, 0.5, 0.75, 1):
    o += [
        f"<line x1='{X(g)}' x2='{X(g)}' y1='0' y2='{len(sch) * 70}' stroke='#15161722'/>",
        txt(X(g), len(sch) * 70 + 22, f"{g:g}", 14, "#55534d", "middle"),
    ]
for i, (n, vals, same) in enumerate(sch):
    y = i * 70 + 36
    col = "#35505b" if same else "#151617"
    o.append(txt(316, y + 5, n, 18, "#151617", "end", 600))
    o.append(
        f"<line x1='{X(min(vals))}' x2='{X(max(vals))}' y1='{y}' y2='{y}' stroke='{col}' stroke-width='2' opacity='.5'/>"
    )
    for k, v in enumerate(vals):
        # identical values would draw one blob; stagger the three markers vertically to show all three
        yo = (k - 1) * 13 if same else 0
        yk = y + yo
        if k == 0:
            o.append(f"<circle cx='{X(v)}' cy='{yk}' r='8' fill='{col}'/>")
        elif k == 1:
            o.append(f"<rect x='{X(v) - 7.5}' y='{yk - 7.5}' width='15' height='15' fill='{col}'/>")
        else:
            o.append(
                f"<polygon points='{X(v)},{yk - 9} {X(v) + 9},{yk + 7} {X(v) - 9},{yk + 7}' fill='{col}'/>"
            )
    o.append(
        txt(
            X(max(vals)) + 18,
            y + 5,
            "identical on all three" if same else f"spread {max(vals) - min(vals):.2f}",
            14,
            "#35505b" if same else "#94490a",
            "start",
            700,
        )
    )
slide(
    "Two schemas",
    "".join(
        [
            kicker("Two more schemas &nbsp;·&nbsp; issue #67"),
            title("The profile carries over, the values do not", 46, 62),
            svg(64, 170, 1152, 330, "".join(o), "mean recall on three schemas"),
            D(
                64,
                510,
                700,
                None,
                "legend",
                "&#9679; customers &nbsp; &#9632; transactions &nbsp; &#9650; sensors. Mean recall over five seeds. Spread = highest minus lowest of the three.",
            ),
            D(
                64,
                566,
                700,
                None,
                "note",
                "Same generator logic for all three schemas: the agreement shows the profile does not depend on one table, not that it holds on real data. The drift detector flags nothing on any schema. Two of four hypotheses hold: the structural rows and the rank stability.",
            ),
            D(
                800,
                546,
                416,
                None,
                "stat sm",
                "<span class='num'>0.93</span><span class='lab' style='font-size:15px'>mean rank correlation between schemas, first six detectors (0.89 with all seventeen)</span>",
            ),
            foot(
                "verification/multi_schema.md &nbsp;·&nbsp; research/multi_schema.py &nbsp;·&nbsp; paper, Section RQ2 transfer"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="strip plot",
    dominant="three-schema strips",
    density="medium",
    colour="steel for identical, amber for spread",
)

# 36 ----------------------------------------------------------------- sorted multivariate recall
mv = sorted(((n, MATRIX["data"][n]["multivariate"]) for n in MATRIX["order"]), key=lambda t: -t[1])
col_wise = {"ECOD", "COPOD", "HBOS"}
_cw, _bw = 1152 / len(mv), 44
_col = []
for k, (n, v) in enumerate(mv):
    cx = k * _cw + _cw / 2
    top = 320 - 280 * v
    fill = "#ece6da" if n in col_wise else "#6f6b63"
    _col.append(
        f"<rect x='{cx - _bw / 2}' y='{top}' width='{_bw}' height='{320 - top}' fill='{fill}'><title>{n}: {v:.2f}</title></rect>"
    )
    _col.append(mono(cx, top - 8, f"{v:.2f}", 15, DARK["ink"], "middle", 600))
    _col.append(txt(cx, 346, n, 15, DARK["ink"], "middle", 600))
_col.append("<line x1='0' x2='1152' y1='320' y2='320' stroke='#ffffff40'/>")
bars = svg(64, 288, 1152, 366, "".join(_col), "multivariate recall by detector, sorted")
slide(
    "Full registry",
    "".join(
        [
            kicker("Every detector in the per-type matrix"),
            title("More detectors, same competence map, no hypothesis holds", 44, 60),
            bars,
            flow(
                64,
                146,
                700,
                [
                    "<p style='font-size:19px;line-height:1.38'>Eleven rows added to the synthetic matrix, with three hypotheses written beforehand; <b>none holds</b>. Recall on multivariate outliers, sorted: <span class='ok'>ECOD (0.52) and COPOD (0.51)</span> find half of them although they read one column at a time, and HBOS stays at 0; PCA reaches 0.48 against 0.83 for the autoencoder.</p>"
                ],
                maxh=150,
            ),
            flow(
                800,
                146,
                416,
                [
                    "<p style='font-size:19px;line-height:1.38'>LUNAR catches 0.65 of the drifted rows (LOF 0.50) while flagging 41% of clean rows. The LSTM still does not fix drift.</p>"
                ],
                maxh=150,
            ),
            flow(
                700,
                330,
                516,
                [
                    "<p class='note' style='font-size:15px;line-height:1.4'><span style='color:#ece6da'>&#9679;</span> light bars: column-wise detectors (ECOD, COPOD, HBOS), a family, not a result. Synthetic customers are independent rows: drift is not a sequence here.</p>",
                    "<p class='note' style='font-size:15px;line-height:1.4'>Mean recall on multivariate outliers, 17 detectors, 5 seeds. Full matrix on the per-type slide.</p>",
                ],
                maxh=120,
                gap=8,
            ),
            foot(
                "verification/full_registry.md &nbsp;·&nbsp; research/full_registry.py &nbsp;·&nbsp; paper, tab:m-customer"
            ),
        ]
    ),
    role="evidence",
    family="column chart with text above and notes in its empty corner",
    dominant="17 columns",
    density="medium",
    colour="light bars for column-wise detectors",
)

# 37 ----------------------------------------------------------------- cost: log bars
cost = [
    ("Z-score", 0.013, 0),
    ("IQR", 0.029, 0),
    ("ECOD / COPOD", 0.68, 0),
    ("Isolation Forest", 1.09, 0),
    ("KNN", 11, 0),
    ("LOF", 18.0, 0),
    ("VAE", 69, 0),
    ("DIF", 262, 1),
    ("One-Class SVM", 300, 2),
]
LX = lambda v: 220 + (math.log10(v) - math.log10(0.01)) / 5 * 520  # noqa: E731
o = []
for g, lab in [
    (0.01, "0.01 s"),
    (0.1, "0.1"),
    (1, "1"),
    (10, "10"),
    (100, "100"),
    (1000, "1000 s"),
]:
    o += [
        f"<line x1='{LX(g)}' x2='{LX(g)}' y1='0' y2='{len(cost) * 38}' stroke='#15161722'/>",
        txt(LX(g), len(cost) * 38 + 20, lab, 13, "#55534d", "middle"),
    ]
for i, (n, v, k) in enumerate(cost):
    y = i * 38 + 6
    col = "#151617" if k else "#55534d"
    o += [
        txt(206, y + 20, n, 17, "#151617", "end", 600),
        f"<line x1='220' x2='{LX(v)}' y1='{y + 14}' y2='{y + 14}' stroke='{col}' stroke-width='3' opacity='{0.95 if k else 0.6}'/><circle cx='{LX(v)}' cy='{y + 14}' r='8' fill='{col}' opacity='{0.95 if k else 0.75}'/>",
    ]
    o.append(mono(LX(v) + 16, y + 20, ("&gt;300 s" if k == 2 else f"{v:g} s"), 14, "#151617"))
o.append(
    f"<line x1='{LX(300)}' x2='{LX(300)}' y1='0' y2='{len(cost) * 38}' stroke='#151617' stroke-dasharray='4 4'/>"
)
slide(
    "Cost",
    "".join(
        [
            kicker("What detection costs &nbsp;·&nbsp; issue #53"),
            title("Detection latency is not pipeline latency", 44, 60),
            D(
                64,
                126,
                760,
                None,
                "k",
                "median detection-stage time at 100,000 rows, 8 features (log axis)",
            ),
            svg(
                64,
                150,
                800,
                len(cost) * 38 + 30,
                "".join(o),
                "detection time at 100,000 rows on a log axis",
            ),
            D(
                64,
                540,
                760,
                None,
                "legend",
                "&#9632; dark bars: over 100 s. Dashed: the 300 s budget. Fresh process per measurement so peak memory belongs to that run; synthetic matrices from 1,000 to 300,000 rows.",
            ),
            D(
                64,
                596,
                760,
                None,
                "note",
                "At 300,000 rows LOF takes 133 s (exponent 1.51) and DIF more than 300 s. Single machine, not isolated, not a general ranking. Five of the ten newer detectors shown; the paper has all.",
            ),
            D(
                900,
                150,
                316,
                None,
                "",
                "<p style='font-size:20px'>On the full Credit Card file the Z-score pipeline takes <b>4.8 s</b>, of which detection is 3%. Isolation Forest takes <b>8.5 s</b>, with detection at 43 to 45%.</p>",
            ),
            D(
                900,
                340,
                316,
                None,
                "stat sm",
                "<span class='num'>8.5 s</span><span class='lab' style='font-size:15px'>Isolation Forest pipeline, detection 43 to 45%</span>",
            ),
            foot("verification/cost_study.md"),
        ]
    ),
    tone="bone",
    role="evidence",
    family="log bar chart",
    dominant="nine log bars",
    density="medium",
    colour="amber for over 100 s",
)

# 38 ----------------------------------------------------------------- routing diagram
route = [
    ("exact duplicate", 0, "transform dedup stage", "1.00"),
    ("missing value", 0, "Great Expectations", "1.00"),
    ("univariate outlier", 1, "any statistical rule", "0.93 to 0.99"),
    (
        "multivariate outlier",
        1,
        "Isolation Forest or One-Class SVM",
        "0.89 to 0.90, precision about 0.22",
    ),
    ("invalid format", 1, "IQR for the numeric part", "1.00; malformed strings need a format rule"),
    ("temporal drift", 2, "windowed monitor", "per-row detectors at most 0.65"),
]
# rows are laid out so that boxes never touch each other or the note below (geometry checked by the layout probe)
LEFT_Y = [26 + i * 62 for i in range(6)]
BOXES = [
    ("stage 1: transform", 14, 84),
    ("stage 2: row-level detector", 114, 236),
    ("stage 3: windowed monitor", 364, 76),
]
TARGET_Y = {
    "exact duplicate": 66,
    "missing value": 164,
    "univariate outlier": 218,
    "multivariate outlier": 272,
    "invalid format": 326,
    "temporal drift": 412,
}
o = []
for i, (t, _ln, _m, _r) in enumerate(route):
    o.append(
        txt(240, LEFT_Y[i] + 6, t, 22, "#151617", "end", 700, "Avenir Next Condensed, sans-serif")
    )
for nm, y0, h in BOXES:
    o.append(
        f"<rect x='640' y='{y0}' width='490' height='{h}' fill='none' stroke='#151617' stroke-width='2'/>"
    )
    o.append(txt(654, y0 + 22, nm, 14, "#55534d", "start", 600))
for i, (t, ln, m, r) in enumerate(route):
    y = LEFT_Y[i]
    ty = TARGET_Y[t]
    o.append(
        f"<path d='M250 {y} C 440 {y}, 440 {ty}, 650 {ty}' fill='none' stroke='#151617' stroke-width='1.6' opacity='.55'/>"
    )
    o.append(f"<circle cx='250' cy='{y}' r='5' fill='#151617'/>")
    o.append(txt(664, ty - 2, m, 17, "#151617", "start", 700))
    o.append(txt(664, ty + 16, r, 14, "#35505b" if ln != 2 else "#94490a", "start", 600))
slide(
    "Type to method",
    "".join(
        [
            kicker("The practical output"),
            title("Anomaly type to method", 46, 60),
            svg(
                64, 134, 1152, 460, "".join(o), "routing of six anomaly types to stages and methods"
            ),
            D(
                64,
                608,
                1152,
                None,
                "note",
                "Two of six types are not a per-row detector problem at all: duplicates belong to the transform stage, drift to a windowed monitor. A single aggregate ranking would never surface that. Recall from the synthetic customer table, 5 seeds; it does not transfer to the real tables (slide 28). Steel text: recall reached, amber: per-row detectors only partly succeed.",
            ),
            foot("paper, Section V &nbsp;·&nbsp; rules and ML are complementary, not competing"),
        ]
    ),
    tone="bone",
    role="synthesis",
    family="routing diagram",
    dominant="curves from types to stages",
    density="medium",
    colour="steel recall, amber partial",
)

# 39 ----------------------------------------------------------------- regimes
slide(
    "Regimes",
    "".join(
        [
            kicker("Across the three example datasets"),
            D(
                64,
                76,
                1152,
                None,
                "",
                "<h1 style='font-size:64px;line-height:1.02'>Unsupervised detection works in<br><span class='em'>one of three</span> regimes</h1>",
            ),
            D(
                64,
                290,
                360,
                None,
                "",
                "<div class='cond' style='font-size:34px;font-weight:700'>Fraud</div><div class='k' style='margin:4px 0 10px'>too extreme</div><p style='font-size:19px'>0.17% positives, and the label mixes every defect. Best F1 of seventeen detectors is 0.35 (Deep SVDD), best precision 0.34 (HBOS).</p>",
            ),
            D(
                464,
                290,
                360,
                None,
                "",
                "<div class='cond' style='font-size:34px;font-weight:700'>Cardio</div><div class='k ok' style='margin:4px 0 10px'>the fit</div><p style='font-size:19px'>9.6%, rare and distinct. Isolation Forest F1 0.62, AP 0.70. The regime the detectors are built for.</p>",
            ),
            D(
                864,
                290,
                352,
                None,
                "",
                "<div class='cond' style='font-size:34px;font-weight:700'>Water</div><div class='k' style='margin:4px 0 10px'>wrong regime</div><p style='font-size:19px'>61% majority target. Every ROC-AUC 0.45 to 0.51: the detectors are at chance. A useful negative result.</p>",
            ),
            D(64, 520, 1152, 1, "hair"),
            D(
                64,
                540,
                1152,
                None,
                "",
                "<p style='font-size:20px;max-width:1000px'>The question is less &quot;rules or ML&quot; than &quot;does this dataset have rare, outlying anomalies at all&quot;. The synthetic dataset sits in the middle at 17.5% and is where the per-type structure is measured. Pipeline cost narrows the shortlist: LOF and One-Class SVM were not run on the full fraud dataset (expected to be too costly, not measured).</p>",
            ),
            foot("paper, discussion"),
        ]
    ),
    role="synthesis",
    family="typographic columns",
    dominant="headline",
    density="medium",
)

# 40 ----------------------------------------------------------------- findings
find = [
    (
        "The operating point is a lever",
        "Contamination equal to prevalence instead of a fixed 10% moves Isolation Forest fraud precision from 0.01 to 0.28 on the seed of the paper's table (0.20 on average over five seeds).",
    ),
    (
        "One regime out of three",
        "Cardio F1 0.62. Fraud, mixed label: nothing usable. Water Quality: at chance.",
    ),
    (
        "ML is weak on missing values",
        "Imputing removes the signal a not-null rule catches for free: GX recall 1.00 against 0.00 to 0.28 for the classical learned models.",
    ),
    (
        "GX 1.x is a full API rewrite",
        "Per-row failures need the COMPLETE result format plus an explicit index column; found by probing the installed library.",
    ),
    (
        "PyOD scores can depend on the batch",
        "ECOD, COPOD and DIF use the scored rows for their statistics, the VAE draws a random code, AE1SVM crashes on a last batch of one row. Recorded adaptations, with 17 batch-independence checks; not upstream-equivalence claims.",
    ),
    (
        "Drift is not a per-row problem",
        "Once diluted by clean recent rows, the window mean has moved by about a tenth of a standard deviation.",
    ),
]
body = [
    kicker("What was harder than the plan assumed"),
    title("Findings from the build", 44, 62),
    D(
        64,
        128,
        1152,
        None,
        "",
        "<p style='font-size:19px;max-width:900px'>Each of these became a paragraph in the paper. The recurring lesson: the setup around a detector, the operating point, the regime and the pipeline cost matter as much as the algorithm.</p>",
    ),
]
for i, (h, t) in enumerate(find):
    x, y = 64 + (i % 2) * 584, 214 + (i // 2) * 138
    body += [
        D(
            x,
            y,
            60,
            None,
            "",
            f"<span class='num' style='font-size:46px;opacity:.72'>{i + 1}</span>",
        ),
        D(
            x + 62,
            y,
            500,
            None,
            "",
            f"<div class='cond' style='font-size:26px;font-weight:600'>{h}</div><p style='font-size:17px;margin-top:4px;line-height:1.35'>{t}</p>",
        ),
    ]
body.append(foot("build notes kept per session"))
slide(
    "Findings",
    "".join(body),
    role="synthesis",
    family="numbered index",
    dominant="six findings",
    density="medium",
)

_unused = (BONE, DARK, cividis, padfield, svg)
