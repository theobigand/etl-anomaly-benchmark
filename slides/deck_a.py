# ruff: noqa: E501
"""Slides for the question, the instrument and the three examples."""

import math

from deck_lib import (
    BONE,
    DARK,
    MATRIX,
    TYPES,
    D,
    flow,
    foot,
    hbars,
    matrix,
    mono,
    padfield,
    photo,
    pr_panels,
    pr_scatter,
    severity_panels,
    slide,
    svg,
    tbl,
    txt,
    type_icon,
)

EM = "class='em'"


def kicker(s, tone_cls=""):
    return D(64, 44, 900, None, "k", s)


def title(s, size=46, y=70, w=1152):
    return D(
        64,
        y + 8,
        w,
        None,
        "",
        f"<h2 class='fit1' style='font-size:{size}px;line-height:1.04'>{s}</h2>",
    )


# 1 ------------------------------------------------------------------ cover
slide(
    "Cover",
    "".join(
        [
            photo(0, 0, 1280, 720, "100% 38%", "128%"),
            D(
                0,
                0,
                1280,
                720,
                "scrim",
                "",
                "background:linear-gradient(90deg,rgba(10,10,10,0) 44%,rgba(10,10,10,.82) 60%,rgba(10,10,10,.9) 100%)",
            ),
            flow(
                704,
                52,
                528,
                [
                    "<div class='k'>ESILV Data &amp; AI &nbsp;·&nbsp; master thesis</div>",
                    "<h1 style='font-size:54px;line-height:1.04'>Anomaly detection for data quality, <span class='em'>measured</span> inside the ETL pipeline</h1>",
                    "<p style='font-size:20px;color:#c4bfb3'>Rules, classical and neural detectors run through one pipeline and compared per anomaly type. Living progress deck, 2026-11-12.</p>",
                    "<div class='note'>Illustration, not data: a generated still life. One pad stands proud; the low light finds it.</div>",
                    "<div class='k'>17 detectors &nbsp; 6 types &nbsp; 152 datasets</div>",
                    "<div class='src'>Theo Bigand<br>github.com/theobigand/etl-anomaly-benchmark</div>",
                ],
                maxh=616,
                gap=22,
            ),
        ]
    ),
    role="cover",
    family="image-led",
    dominant="photograph",
    density="low",
    image="photo 1672px, 128% crop",
    light="raking, lower left",
    colour="neutral + amber highlight in photo",
)

# 2 ------------------------------------------------------------------ question
slide(
    "The question",
    "".join(
        [
            flow(
                64,
                92,
                1152,
                [
                    "<div class='k'>The question</div>",
                    "<h1 style='font-size:64px;line-height:1.04;max-width:1060px'>Does machine learning in an ETL pipeline beat plain rules, and for <span class='em'>which anomalies</span>?</h1>",
                    "<div style='display:flex;gap:40px;align-items:flex-start'>"
                    "<p class='lede' style='font-size:22px;flex:1'>Rules are the industry default: auditable, cheap, and blind to what the author did not anticipate. Recent work puts ML detectors inside the flow, but on one algorithm and one dataset. This thesis builds the missing head-to-head benchmark and breaks the result down by anomaly type.</p>"
                    "<div style='flex:1;border-left:2px solid var(--graphite-line);padding-left:36px'>"
                    "<div class='k' style='margin-bottom:12px'>What generic benchmarks leave out</div>"
                    "<p style='font-size:18px;margin-bottom:10px'><b>Pipeline.</b> Algorithms are scored outside any pipeline; integration cost is not measured.</p>"
                    "<p style='font-size:18px;margin-bottom:10px'><b>Rules.</b> The declarative baseline that dominates production is absent.</p>"
                    "<p style='font-size:18px;margin-bottom:10px'><b>Types.</b> One aggregate score per dataset hides which family finds which defect.</p>"
                    "<p style='font-size:18px'><b>Threshold.</b> One flag threshold, not the precision-recall trade-off.</p></div></div>",
                ],
                maxh=580,
                gap=28,
            ),
            foot("paper/main.tex, IMRaD experimental paper"),
        ]
    ),
    role="claim",
    family="typographic statement",
    dominant="headline",
    density="medium",
)

# 3 ------------------------------------------------------------------ related work: evidence grid, no card
works = [
    (
        "ADBench, 30 algorithms, 57 sets",
        0,
        "not found (ranking metrics)",
        0,
        "not found (ranking metrics)",
    ),
    ("Agyemang 2024, one simulated set", 0, "none", 1, "precision, recall, F1"),
    ("AnoShift, Kyoto 2006 to 2015", 1, "IID, NEAR, FAR splits", 0, "not found (ranking metrics)"),
    ("FedAD-Bench, federated deep", 0, "not found", 1, "F1-optimal threshold"),
    ("Sun et al. 2024, online thresholds", 1, "shift in a stream", 1, "error-rate guarantees"),
]
rows = []
for i, (nm, a, at, b, bt) in enumerate(works):
    y = 224 + i * 62
    rows.append(D(64, y, 400, None, "", f"<div style='font:600 21px var(--sans)'>{nm}</div>"))
    rows.append(
        D(
            500,
            y,
            330,
            None,
            "",
            f"<span style='font:700 26px var(--sans)' class='{'ok' if a else ''}'>{'&#9679;' if a else '&#9675;'}</span> <span style='font:500 18px var(--sans);margin-left:6px'>{at}</span>",
        )
    )
    rows.append(
        D(
            850,
            y,
            366,
            None,
            "",
            f"<span style='font:700 26px var(--sans)' class='{'ok' if b else ''}'>{'&#9679;' if b else '&#9675;'}</span> <span style='font:500 18px var(--sans);margin-left:6px'>{bt}</span>",
        )
    )
    rows.append(D(64, y - 14, 1152, 1, "hair"))
rows.append(D(64, 224 + 5 * 62 - 14, 1152, 2, "", "", "background:var(--ink)"))
rows.append(
    D(
        64,
        224 + 5 * 62,
        400,
        None,
        "",
        "<div class='cond' style='font-size:30px;font-weight:700'>This thesis</div>",
    )
)
rows.append(
    D(
        500,
        224 + 5 * 62,
        330,
        None,
        "",
        "<span style='font:700 26px var(--sans)' class='ok'>&#9679;</span> <span style='font:500 18px var(--sans);margin-left:6px'>six fault types, controlled generator</span>",
    )
)
rows.append(
    D(
        850,
        224 + 5 * 62,
        366,
        None,
        "",
        "<span style='font:700 26px var(--sans)' class='ok'>&#9679;</span> <span style='font:500 18px var(--sans);margin-left:6px'>decisions at a threshold, cost</span>",
    )
)
slide(
    "Related work",
    "".join(
        [
            kicker("Related work &nbsp;·&nbsp; issue #68"),
            D(
                64,
                72,
                1152,
                None,
                "",
                "<h2 class='fit1' style='font-size:48px;line-height:1.04'>Benchmarks rank detectors. Few report their decisions</h2>",
            ),
            D(500, 184, 330, None, "k", "reports time order?"),
            D(850, 184, 366, None, "k", "reports decisions at a threshold?"),
            *rows,
            flow(
                64,
                600,
                1152,
                [
                    "<div class='legend' style='position:static'><span class='ok'>&#9679;</span> found in the text I read &nbsp;&nbsp; &#9675; not found, which is not proof of absence. The scan is not systematic: this is a gap I did not find filled.</div>",
                    "<div class='note' style='position:static'>In the texts I read, ADBench and AnoShift report ranking metrics only (AUC and AP), and none of these works breaks results down by data-quality fault. References checked against a primary source or the DOI registry.</div>",
                ],
                maxh=72,
                gap=6,
            ),
            foot("verification/references.md, bibliography verified against primary sources"),
        ]
    ),
    tone="bone",
    role="context",
    family="evidence grid (no card)",
    dominant="symbol columns",
    density="medium",
    colour="steel for found",
)

# 4 ------------------------------------------------------------------ research questions
rq = [
    (
        "RQ1",
        "Rules, classical and neural detectors in one pipeline",
        "examples, 100 labelled problems",
        "historical ranking, train-only replay pending",
    ),
    (
        "RQ2",
        "Which anomaly type each family finds",
        "synthetic matrix, schemas, 42 UCI tables",
        "narrow competence; values do not transfer",
    ),
    (
        "RQ3",
        "Operating point and time",
        "contamination, label-free threshold, chronological split",
        "a threshold fixed on the past fails when prevalence moves",
    ),
    (
        "RQ4",
        "Cost in the pipeline",
        "cost study, ETL run on 152 sets",
        "neural 10 to 100 times column-wise",
    ),
]
body = [
    kicker("Research questions"),
    title("Four questions, one study each, hypotheses written first", 50, 84),
]
for i, (a, q, s, ans) in enumerate(rq):
    y = 214 + i * 108
    body += [
        D(64, y, 1152, 1, "hair"),
        D(64, y + 14, 130, None, "", f"<span class='num' style='font-size:56px'>{a}</span>"),
        flow(
            214,
            y + 14,
            480,
            [
                f"<p style='font-size:24px;line-height:1.2;font-family:var(--cond);font-weight:600'>{q}</p>",
                f"<div class='note'>{s}</div>",
            ],
            maxh=92,
            gap=6,
        ),
        D(730, y + 18, 486, None, "", f"<p style='font-size:20px'>{ans}</p>"),
    ]
body += [
    D(
        64,
        626,
        1152,
        None,
        "note",
        "Each main study has a protocol and hypotheses committed before its runs; post-hoc analyses are labelled exploratory. A failed hypothesis is reported as failed: three of the six on the whole pool",
    ),
    foot("paper, Introduction and Methods; protocols in verification/*.md"),
]
slide(
    "Research questions",
    "".join(body),
    role="structure",
    family="typographic index",
    dominant="RQ numerals",
    density="medium",
)

# 5 ------------------------------------------------------------------ six types, one diagram each
types = [
    ("missing", "missing value", "one or two feature cells set to null"),
    ("duplicate", "exact duplicate", "a clean row copied, same business attributes"),
    ("univariate", "univariate outlier", "one numeric field pushed far out of range"),
    ("multivariate", "multivariate outlier", "every field in range, the combination not"),
    ("drift", "temporal drift", "recent signups whose income and balance shifted up"),
    ("invalid", "invalid format", "malformed e-mail, bad country code, impossible age"),
]
body = [
    kicker("The original contribution"),
    title("A controlled dataset that labels six anomaly types separately", 42, 62, 1152),
]
for i, (k, nm, ds) in enumerate(types):
    x, y = 64 + (i % 3) * 394, 134 + (i // 3) * 238
    body += [
        type_icon(k, x, y, 364, 170),
        D(
            x,
            y + 178,
            364,
            None,
            "",
            f"<div class='cond' style='font-size:25px;font-weight:600;line-height:1.1'>{nm}</div><div class='note' style='font-size:15px;margin-top:3px'>{ds}</div>",
        ),
    ]
body += [
    D(
        64,
        624,
        1152,
        None,
        "note",
        "12,360 records, Faker and NumPy, six types injected at 3% each, every row tagged. Recall and precision are reported per type. Severity is one multiplier, so the magnitude is swept. Diagrams are illustrative examples, not data.",
    ),
    foot(
        "make synthetic &nbsp;·&nbsp; make severity &nbsp;·&nbsp; generator is deterministic, dataset not committed"
    ),
]
slide(
    "Contribution",
    "".join(body),
    role="definition",
    family="six distinct diagrams",
    dominant="table, rows, number line, scatter, distributions, form",
    density="medium",
    colour="amber on the defect with a label",
)

# 6 ------------------------------------------------------------------ system
slide(
    "System",
    "".join(
        [
            kicker("The system"),
            title("One interface, one measured path", 50, 76),
            D(
                64,
                178,
                1152,
                150,
                "",
                "".join(
                    [
                        f"<div style='position:absolute;left:{x}px;top:0;width:250px;height:92px;border:2px solid {'var(--steel-ink)' if hot else 'var(--ink)'};background:{'var(--steel-wash)' if hot else 'transparent'};padding:14px 18px'><div class='cond' style='font-size:34px;font-weight:700'>{t}</div><div class='note' style='font-size:14px'>{s}</div></div>"
                        for x, t, s, hot in [
                            (0, "extract", "read the table", False),
                            (300, "transform", "exact dedup, clean", False),
                            (600, "detect", "fit + predict + score", True),
                            (900, "load", "write the files", False),
                        ]
                    ]
                    + [
                        "<div style='position:absolute;left:250px;top:44px;width:50px;height:2px;background:var(--ink)'></div><div style='position:absolute;left:550px;top:44px;width:50px;height:2px;background:var(--ink)'></div><div style='position:absolute;left:850px;top:44px;width:50px;height:2px;background:var(--ink)'></div>",
                        "<div class='note' style='position:absolute;left:600px;top:104px;width:260px'>the stage whose latency is measured, in real in-pipeline time</div>",
                    ]
                ),
            ),
            D(
                64,
                356,
                560,
                None,
                "",
                "<p style='font-size:20px'>The demo and every benchmark call the same <code style='font-family:var(--mono)'>detect()</code> stage. A continuous <code style='font-family:var(--mono)'>score()</code> on top of the boolean <code style='font-family:var(--mono)'>predict()</code> makes ROC-AUC and AP computable; <code style='font-family:var(--mono)'>detect(fit_df=...)</code> fits on the train slice and scores the test set.</p>"
                "<p class='note' style='margin-top:14px;font-size:16px'>Exact deduplication belongs to the ordinary transform. Typed injected duplicates remain in their separate evaluation with transform_dedup.</p>",
            ),
            D(
                668,
                336,
                548,
                326,
                "sheet",
                "<pre style='padding:14px 18px;font-size:14px;line-height:1.42'><span style='color:#8b887f'># every detector, one contract</span>\nclass Detector(ABC):\n    name: str\n    def fit(self, df) -&gt; Self: ...\n    def predict(self, df) -&gt; Series:  <span style='color:#8b887f'># bool/row</span>\n        ...\n    def score(self, df) -&gt; Series:    <span style='color:#8b887f'># graded</span>\n        return self.predict(df).astype(float)\n\n<span style='color:#8b887f'># classical ML: adapt PyOD, do not reimplement</span>\nclass PyODDetector(Detector): ...\n\n<span style='color:#8b887f'># registry: one line per detector</span>\n\"isolation_forest\": lambda: IsolationForestDetector(),</pre>",
            ),
            foot(
                "src/etl_benchmark/pipeline.py &nbsp;·&nbsp; quality/base.py, interface modelled on PyOD BaseDetector"
            ),
        ]
    ),
    tone="bone",
    role="mechanism",
    family="process diagram + code",
    dominant="pipeline",
    density="medium",
    colour="steel on the measured stage",
)

# 7 ------------------------------------------------------------------ AP
slide(
    "Metric",
    "".join(
        [
            kicker("Metric interpretation"),
            title("Average Precision measures the ranking", 50, 76),
            D(
                64,
                196,
                1152,
                None,
                "",
                "<div class='num' style='font-size:128px;font-weight:700'>AP <span style='opacity:.7'>=</span> &Sigma; &Delta;R &middot; P</div>",
            ),
            D(
                64,
                340,
                900,
                None,
                "note",
                "precision, weighted by each recall increment, over distinct score cutoffs from high to low; tied scores enter together. AP uses continuous anomaly scores. Precision, recall, F1 and the flagged share use a selected threshold.",
            ),
            D(
                64,
                452,
                360,
                None,
                "",
                "<div class='cond' style='font-size:26px;font-weight:600'>Non-interpolated</div><p style='font-size:18px;margin-top:8px'>AP differs from trapezoidal precision-recall area.</p>",
            ),
            D(
                464,
                452,
                360,
                None,
                "",
                "<div class='cond' style='font-size:26px;font-weight:600'>Prevalence matters</div><p style='font-size:18px;margin-top:8px'>Prevalence is the no-skill reference. Constant scores give AP equal to prevalence.</p>",
            ),
            D(
                864,
                452,
                352,
                None,
                "",
                "<div class='cond' style='font-size:26px;font-weight:600'>Decisions apart from scores</div><p style='font-size:18px;margin-top:8px'>Changing only the flag threshold leaves AP and ROC-AUC unchanged; neither fixes a useful operating point.</p>",
            ),
            D(
                64,
                600,
                1152,
                None,
                "note",
                "Historical naming: stored pr_auc fields and remaining AP labels in archived figures and the paper denote this same AP quantity.",
            ),
            foot(
                "paper/main.tex, Evaluation protocol, equation (3) &nbsp;·&nbsp; scikit-learn average_precision_score"
            ),
        ]
    ),
    role="definition",
    family="typographic formula",
    dominant="equation",
    density="low",
)

# 8 ------------------------------------------------------------------ detectors: lanes
lanes = [
    (
        "rules",
        [
            ("Z-score", "flag |z| &gt; 3 on any column", "mean and std inflated by outliers"),
            ("IQR", "Tukey fences, k = 1.5", "fires often in high dimension"),
            (
                "Great Expectations",
                "null checks, fitted 0.1% / 99.9% bounds",
                "generic suite, no domain rules",
            ),
        ],
    ),
    (
        "joint models",
        [
            ("Isolation Forest", "isolation depth under random splits", "weak on nulls"),
            ("LOF", "local density, 20 neighbours", "cost grows with scored set"),
            ("One-Class SVM", "RBF boundary around the bulk", "quadratic training"),
            ("KNN", "distance to the 5th neighbour", "skipped above 50k rows"),
            ("PCA", "reconstruction error, 95% variance", "misses shifts inside the kept space"),
        ],
    ),
    (
        "column-wise",
        [
            ("ECOD", "empirical tail probabilities, summed", "no cross-feature dependence"),
            ("COPOD", "max of skew term and mean log tails", "same"),
            (
                "HBOS",
                "histogram per column, inverse bin height",
                "independent columns, coarse bins",
            ),
        ],
    ),
    (
        "time-aware",
        [("drift", "recent-window mean shift", "per row, so diluted drift is invisible")],
    ),
]
body = [
    kicker("Three families, eleven row-level detectors"),
    title("Rules and classical models, one contract", 42, 66),
]
y = 132
for name, chips in lanes:
    body.append(
        D(
            64,
            y,
            130,
            None,
            "",
            f"<div class='cond' style='font-size:23px;font-weight:700;line-height:1.1'>{name}</div>",
        )
    )
    body.append(D(64, y - 8, 1152, 1, "hair"))
    for j, (n, pr, lim) in enumerate(chips):
        body.append(
            D(
                210 + j * 202,
                y,
                192,
                None,
                "",
                f"<div style='font:700 17px var(--sans)'>{n}</div><div style='font:400 15px/1.3 var(--sans);margin-top:3px'>{pr}</div><div class='note' style='font-size:14px;margin-top:3px'>limit: {lim}</div>",
            )
        )
    y += 126 if len(chips) > 1 else 100
body += [
    D(
        64,
        628,
        1152,
        None,
        "note",
        "PyOD or the recorded protocol adaptations; flag threshold from training prevalence. Numeric columns only, while Great Expectations separately checks nulls on all columns: an explicit information asymmetry. The time-aware drift detector is opt-in and synthetic only.",
    ),
    foot(
        "src/etl_benchmark/quality/ml.py, rules.py, gx.py &nbsp;·&nbsp; ECOD/COPOD use training ranks and frozen skew signs"
    ),
]
slide(
    "Detectors",
    "".join(body),
    tone="bone",
    role="inventory",
    family="lanes by family",
    dominant="four lanes",
    density="high",
)

# 9 ------------------------------------------------------------------ fitted rules: distribution
pts = []
W, H0 = 560, 250
sx = lambda z: 20 + (z + 4) / 8 * (W - 40)  # noqa: E731
sy = lambda z: H0 - 20 - 190 * math.exp(-z * z / 2)  # noqa: E731
curve = " ".join(f"{sx(-4 + k * 0.05):.1f},{sy(-4 + k * 0.05):.1f}" for k in range(161))


HALO = "style='paint-order:stroke;stroke:#141516;stroke-width:6px;stroke-linejoin:round'"


def tail(z0, z1, op):
    zs = [z0 + (z1 - z0) * k / 40 for k in range(41)]
    return f"<polygon points='{' '.join(f'{sx(z):.1f},{sy(z):.1f}' for z in zs)} {sx(z1):.1f},{H0 - 20} {sx(z0):.1f},{H0 - 20}' fill='#eaa24f' opacity='{op}'/>"


dist = "".join(
    [
        tail(2.698, 4, 0.5),
        tail(-4, -2.698, 0.5),
        tail(3, 4, 0.95),
        tail(-4, -3, 0.95),
        f"<polyline points='{curve}' fill='none' stroke='#ece6da' stroke-width='2.5'/>",
        *[
            f"<polyline points='{' '.join(f'{sx(a + k * (b - a) / 20):.1f},{sy(a + k * (b - a) / 20):.1f}' for k in range(21))}' fill='none' stroke='#eaa24f' stroke-width='5' stroke-linecap='round'/>"
            for a, b in ((2.698, 4), (-4, -2.698))
        ],
        f"<line x1='20' x2='{W - 20}' y1='{H0 - 20}' y2='{H0 - 20}' stroke='#ece6da' opacity='.6'/>",
        *[
            f"<line x1='{sx(z)}' x2='{sx(z)}' y1='24' y2='{H0 - 20}' stroke='#ece6da' stroke-dasharray='4 4' opacity='.7'/>"
            for z in (-3, -2.698, 2.698, 3)
        ],
        txt(sx(3), 16, "Z-score +3", 14, "#ece6da", "middle"),
        txt(sx(-3), 16, "Z-score -3", 14, "#ece6da", "middle"),
        txt(sx(-2.698) + 4, 40, "IQR fence", 14, "#ece6da", "start", extra=HALO),
        txt(sx(2.698) - 4, 40, "IQR fence", 14, "#ece6da", "end", extra=HALO),
        txt(sx(0), H0, "training mean", 14, "#a9a498", "middle"),
        f"<line x1='{sx(3.4)}' x2='{sx(3.4)}' y1='{H0 - 62}' y2='{sy(3.4) - 6}' stroke='#eaa24f'/>",
        txt(sx(3.4), H0 - 68, "flagged tails", 14, "#eaa24f", "middle", 700, extra=HALO),
    ]
)
slide(
    "Fitted rules",
    "".join(
        [
            kicker("Fitted rules"),
            title("Column bounds do not fix row alert rates", 50, 76),
            svg(
                64,
                186,
                W,
                H0 + 10,
                dist,
                "standard normal curve with the 3 sigma and IQR fence tails shaded",
            ),
            D(
                64,
                446,
                560,
                None,
                "",
                "<p style='font-size:21px'>Per-column tails under a Gaussian: <b>0.27%</b> beyond 3&sigma;, <b>0.70%</b> beyond the IQR fences (about 2.7&sigma;). Fitted bounds and several columns change row-level rates.</p><p class='note' style='margin-top:10px'>Amber: the region a rule flags. Gaussian reference only.</p>",
            ),
            D(
                680,
                186,
                536,
                None,
                "",
                "<div class='cond' style='font-size:32px;font-weight:700'>Z-score</div><p style='font-size:18px;margin:4px 0 16px'>Max |x &minus; training mean| / sample standard deviation. Flag above 3; constant columns contribute zero.</p>"
                "<div class='cond' style='font-size:32px;font-weight:700'>IQR</div><p style='font-size:18px;margin:4px 0 16px'>Training fences Q1 &minus; 1.5 IQR and Q3 + 1.5 IQR. Flag strictly outside; zero-IQR columns contribute zero.</p>"
                "<div class='cond' style='font-size:32px;font-weight:700'>Great Expectations</div><p style='font-size:18px;margin:4px 0 0'>Not-null on all columns; inclusive training quantiles 0.1% and 99.9%. Score: fraction of active checks violated. A generic statistical baseline: no domain-specific category, format or cross-field rules.</p>",
            ),
            foot(
                "paper/main.tex, Methods, rule-based detectors &nbsp;·&nbsp; all statistics come from training data"
            ),
        ]
    ),
    role="mechanism",
    family="diagram-led",
    dominant="distribution with shaded tails",
    density="medium",
    colour="amber on the flagged region",
)

# 10 ----------------------------------------------------------------- neural: specimen list
neural = [
    ("Autoencoder", "rebuild standardized rows through a bottleneck", "MLP from scikit-learn"),
    (
        "VAE",
        "Gaussian code, rebuild, reconstruction error",
        "scored with the code mean; PyOD draws one",
    ),
    ("Deep SVDD", "map normal rows near a centre, distance", "weakest on most types"),
    ("DIF", "isolation forests on random neural features", "training representation scaler reused"),
    (
        "AE1SVM",
        "autoencoder + random-Fourier one-class SVM",
        "singleton padding changes training weight",
    ),
    (
        "LUNAR",
        "network learns the score from neighbour distances",
        "best on drift, many false alarms",
    ),
]
body = [
    kicker("Six neural models, opt-in"),
    title("Neural detectors behind the same contract", 48, 70),
]
for i, (n, p, f) in enumerate(neural):
    y = 168 + i * 72
    body += [
        D(64, y - 8, 760, 1, "hair"),
        D(
            64,
            y,
            250,
            None,
            "",
            f"<div class='cond' style='font-size:34px;font-weight:700'>{n}</div>",
        ),
        D(350, y + 4, 290, None, "", f"<div style='font:500 17px/1.3 var(--sans)'>{p}</div>"),
        D(650, y + 4, 180, None, "", f"<div class='note' style='font-size:14px'>{f}</div>"),
    ]
body += [
    D(
        880,
        168,
        336,
        None,
        "",
        "<p style='font-size:21px;line-height:1.4'>PyOD 3.6.7 with recorded adaptations, CPU, seeded, fitted on at most 20,000 rows.</p><p style='font-size:19px;margin-top:16px;line-height:1.4'>Frozen representation scaling and latent-mean scoring change the evaluated algorithms. They do not establish equivalence to upstream defaults.</p><p class='note' style='margin-top:16px'>The LSTM autoencoder reads windows of ordered rows and stays outside the registry.</p>",
    ),
    foot(
        "verification/detector_inventory.md &nbsp;·&nbsp; full_registry.md &nbsp;·&nbsp; 17 row-level detectors tested for batch independence"
    ),
]
slide(
    "Neural detectors",
    "".join(body),
    role="inventory",
    family="specimen list",
    dominant="names",
    density="medium",
)

# 11 ----------------------------------------------------------------- variants
slide(
    "Evaluated variants",
    "".join(
        [
            kicker("Evaluated variants"),
            title("Stable row scores require explicit adaptations", 48, 70),
            flow(
                64,
                172,
                1152,
                [
                    "<p class='lede' style='font-size:24px;max-width:1040px'>A fitted ETL detector must score a row without consulting other evaluation rows. Contract tests check the 17 row-level detectors; the time-window monitor has a different contract.</p>",
                    "<div style='display:grid;grid-template-columns:340px 1fr;border-top:1px solid var(--line)'>"
                    + "".join(
                        f"<div class='cond' style='font-size:28px;font-weight:600;padding:12px 0;border-bottom:1px solid var(--line)'>{a}</div>"
                        f"<p style='font-size:21px;line-height:1.32;margin:0;padding:14px 0 12px;border-bottom:1px solid var(--line)'>{b}</p>"
                        for a, b in [
                            (
                                "ECOD and COPOD",
                                "PyOD 3.6.7 recomputes tails and skew with the evaluated batch. Here ranks and skew signs are frozen from training.",
                            ),
                            (
                                "Copula motivation versus score",
                                "COPOD adds marginal contributions: it is not a fitted general joint copula. ECOD takes the max of both log tails and the skew term.",
                            ),
                            (
                                "Neural scoring",
                                "VAE decodes the latent mean; DIF reuses a training scaler; AE1SVM padding reweights its last row. These are algorithm changes.",
                            ),
                        ]
                    )
                    + "</div>",
                    "<div style='display:grid;grid-template-columns:340px 1fr'><div class='k'>Evidence boundary</div><p style='font-size:20px;margin:0'>Bounded tests support batch independence, not universal equivalence. Separate ablations remain open; historical results keep their actual adapted configurations.</p></div>",
                ],
                maxh=500,
                gap=22,
            ),
            foot(
                "paper/main.tex, Classical and deep detectors &nbsp;·&nbsp; PyOD 3.6.7 &nbsp;·&nbsp; paired adaptation ablations remain open"
            ),
        ]
    ),
    role="caveat",
    family="ledger of adaptations",
    dominant="ledger rows",
    density="medium",
)

# 12 ----------------------------------------------------------------- exploratory correction
slide(
    "Exploratory correction",
    "".join(
        [
            D(
                64,
                44,
                900,
                None,
                "k",
                "Exploratory correction &nbsp;<span class='tag anom'>not a replacement of archived results</span>",
            ),
            D(
                64,
                80,
                1152,
                None,
                "",
                "<h2 class='fit1' style='font-size:48px'>Historical pool preparation needs revalidation</h2>",
            ),
            D(
                64,
                186,
                560,
                None,
                "",
                "<div class='cond' style='font-size:30px;font-weight:700'>Historical path</div><div style='height:1px;background:var(--graphite-line);margin:10px 0 14px'></div><p style='font-size:19px'>Column filtering, category vocabulary and conflicting-label removal happen <b>before</b> the split. Training-only medians and scaling do not isolate those earlier decisions.</p><p style='font-size:19px;margin-top:14px'>Constructed negative controls: changing only the evaluation categories changes the encoded width from 5 to 3; an evaluation duplicate's label can remove a reference row. The effect on AP is not yet quantified.</p>",
            ),
            D(
                664,
                186,
                552,
                None,
                "",
                "<div class='cond' style='font-size:30px;font-weight:700'>pool-train-only-v1</div><div style='height:1px;background:var(--graphite-line);margin:10px 0 14px'></div><p style='font-size:19px'>Consumes source-bound frozen positions. Fitted schema, imputation and scaling use training rows only. Cross-partition duplicates are rejected; evaluation rows are retained. Targets are excluded from preparation.</p><p style='font-size:19px;margin-top:14px'>Bounded checks enforce full line and branch coverage for the two new modules and detect three leakage defects.</p>",
            ),
            D(64, 520, 1152, 1, "hair"),
            D(
                64,
                536,
                1152,
                None,
                "",
                "<div class='k anom'>Still outstanding</div><p style='font-size:20px;margin-top:8px'>Historical memberships were recomputed (not originally archived) and replay-validated: the Z-score reproduces all 100 archived per-seed results. <b>Replaying the studies on the train-only path remains outstanding.</b> Old protocols and results are preserved, and no corrected pool-performance claim is available.</p>",
            ),
            foot(
                "research/pool_preprocessing.py &nbsp;·&nbsp; pool_train_only.py &nbsp;·&nbsp; exploratory path"
            ),
        ]
    ),
    role="caveat",
    family="two-column comparison",
    dominant="comparison",
    density="high",
    colour="amber for outstanding",
)

# 13 ----------------------------------------------------------------- opener part 2: the six defects on one plate
slide(
    "Part 2",
    "".join(
        [
            padfield(
                14,
                8,
                {(9, 2): "raised"},
                seed=11,
            ),
            D(
                0,
                0,
                1280,
                720,
                "scrim",
                "",
                "background:linear-gradient(0deg,rgba(10,10,10,.9) 0,rgba(10,10,10,.72) 24%,rgba(10,10,10,0) 48%),linear-gradient(90deg,rgba(10,10,10,.78) 0%,rgba(10,10,10,.35) 50%,rgba(10,10,10,0) 100%)",
            ),
            D(64, 56, 600, None, "k", "Part 2 of 4"),
            flow(
                64,
                262,
                760,
                [
                    "<h1 style='font-size:92px;line-height:.98'>What the detectors <span class='em'>actually find</span></h1>",
                    "<p class='lede' style='margin-top:62px;color:#c4bfb3'>Three example datasets, then six anomaly types on a controlled generator and on real tables.</p>",
                ],
                maxh=380,
                gap=0,
            ),
            D(
                64,
                664,
                700,
                None,
                "note",
                "Illustration: a regular plate of pads under low light; the one raised pad casts a shadow. Coded SVG, not data.",
            ),
        ]
    ),
    role="transition",
    family="coded plate",
    dominant="plate with six defects",
    density="low",
    image="SVG plate",
    light="raking, lower left",
    colour="amber on defects",
)

# 14 ----------------------------------------------------------------- examples on a log prevalence axis
ax0, ax1 = 70, 1080
px = lambda p: ax0 + (math.log10(p) - math.log10(0.1)) / 3 * (ax1 - ax0)  # noqa: E731
ds = [
    (
        "Credit Card Fraud",
        0.17,
        "283,726 rows, 30 features",
        "rare, but a mixed-defect label",
        "up",
    ),
    ("Cardio", 9.6, "1,831 rows, 21 features", "rare and outlying, the fitting regime", "down"),
    ("Synthetic per-type", 17.5, "12,360 rows, 9 features", "controlled, 6 labelled types", "up"),
    (
        "Water Quality",
        61,
        "3,276 rows, 9 features",
        "target class common, the wrong regime",
        "down",
    ),
]
ch = [f"<line x1='{ax0}' x2='{ax1}' y1='150' y2='150' stroke='#151617' stroke-width='2'/>"]
for g, lab in [(0.1, "0.1%"), (1, "1%"), (10, "10%"), (100, "100%")]:
    ch += [
        f"<line x1='{px(g)}' x2='{px(g)}' y1='140' y2='160' stroke='#151617'/>",
        txt(px(g), 128, lab, 15, "#55534d", "middle"),
    ]
ch.append(
    txt(
        (ax0 + ax1) / 2,
        206,
        "share of rows labelled anomalous (log scale)",
        14,
        "#55534d",
        "middle",
    )
)
DX = {"Cardio": -70}  # keeps the two lower captions from running into each other
for n, p, a, b, side in ds:
    x = px(p)
    ch.append(f"<circle cx='{x}' cy='150' r='11' fill='#151617'/>")
    if side == "up":
        ch += [
            f"<line x1='{x}' x2='{x}' y1='139' y2='96' stroke='#151617' opacity='.5'/>",
            txt(x, 28, n, 24, "#151617", "middle", 700, "Avenir Next Condensed, sans-serif"),
            txt(x, 52, f"{p:g}% anomalous", 17, "#151617", "middle", 600),
            txt(x, 74, a, 15, "#55534d", "middle"),
            txt(x, 94, b, 15, "#55534d", "middle"),
        ]
    else:
        ch += [f"<line x1='{x}' x2='{x}' y1='161' y2='222' stroke='#151617' opacity='.5'/>"]
slide(
    "Three examples",
    "".join(
        [
            kicker("Three examples, one synthetic set"),
            title("Three example datasets bracket the method", 48, 66),
            svg(
                64,
                160,
                1152,
                330,
                "".join(ch)
                + "".join(
                    txt(
                        px(p) + DX.get(n, 0),
                        250,
                        n,
                        24,
                        "#151617",
                        "middle",
                        700,
                        "Avenir Next Condensed, sans-serif",
                    )
                    + txt(
                        px(p) + DX.get(n, 0), 276, f"{p:g}% anomalous", 17, "#151617", "middle", 600
                    )
                    + txt(px(p) + DX.get(n, 0), 298, a, 15, "#55534d", "middle")
                    + txt(px(p) + DX.get(n, 0), 318, b, 15, "#55534d", "middle")
                    for n, p, a, b, side in ds
                    if side == "down"
                ),
                "datasets placed on a log axis of anomaly share",
            ),
            flow(
                64,
                508,
                700,
                [
                    "<p style='font-size:20px'>Stratified 70 / 15 / 15 split, fit on train, every number reported on the held-out test set. Five seeds, mean &plusmn; std. The ML contamination is read from the train-set prevalence, not fixed at 10%.</p>",
                    "<div class='note' style='position:static'>LOF and One-Class SVM run everywhere except Credit Card Fraud, where they were expected to be too costly at 284k rows; not measured.</div>",
                ],
                maxh=166,
                gap=14,
            ),
            flow(
                820,
                508,
                396,
                [
                    "<div class='stat sm' style='position:static'><span class='num'>0.01 &rarr; 0.28</span><span class='lab' style='font-size:16px'>Isolation Forest fraud precision from the contamination change alone (one seed; 0.20 on average over five)</span></div>"
                ],
                maxh=166,
                gap=14,
            ),
            foot(
                "src/etl_benchmark/datasets.py &nbsp;·&nbsp; config.BENCHMARK_SEEDS &nbsp;·&nbsp; data/*.csv gitignored"
            ),
        ]
    ),
    tone="bone",
    role="context",
    family="log-axis diagram",
    dominant="axis with four datasets",
    density="medium",
)

# 15 ----------------------------------------------------------------- injection: glyph + formula lines
inj = [
    (
        "missing",
        "missing value",
        "1 to 2 of {income, balance, avg amount, tenure, n txn, email, country} set to null",
    ),
    (
        "duplicate",
        "duplicate",
        "exact copy of a sampled clean row, id included (appended, not replaced)",
    ),
    ("univariate", "univariate", "one numeric column &times; U(15, 45) &times; severity"),
    (
        "multivariate",
        "multivariate",
        "marginals at the (1 &minus; 0.03 / severity) percentile of the clean data",
    ),
    (
        "drift",
        "temporal drift",
        "signup in the last 80 days; income &times; (1 + 0.55 &middot; severity), similar for balance and amount",
    ),
    ("invalid", "invalid format", "email malformed; age impossible; country out of domain"),
]
body = [
    kicker("How each type is injected"),
    title("The magnitudes are a swept parameter, not a fixed choice", 40, 66),
]
SCALES = {"univariate": True, "multivariate": True, "drift": True}
body += [
    D(330, 140, 540, None, "k", "how it is injected"),
    D(900, 140, 190, None, "k", "scaled by severity"),
    D(1110, 140, 106, None, "k", "rows"),
]
for i, (k, n, f) in enumerate(inj):
    y = 176 + i * 66
    scaled = SCALES.get(k, False)
    body += [
        D(64, y - 8, 1152, 1, "hair"),
        D(
            64,
            y + 4,
            250,
            None,
            "",
            f"<div class='cond' style='font-size:30px;font-weight:700'>{n}</div>",
        ),
        D(330, y + 4, 540, None, "", f"<div style='font:400 18px/1.3 var(--sans)'>{f}</div>"),
        D(
            900,
            y + 8,
            190,
            None,
            "",
            f"<span class='{'ok' if scaled else ''}' style='font:700 22px var(--sans)'>{'&#9679;' if scaled else '&#9675;'}</span> <span style='font:500 17px var(--sans);margin-left:6px'>{'yes' if scaled else 'no magnitude'}</span>",
        ),
        D(
            1110,
            y + 10,
            106,
            None,
            "",
            f"<span style='font:500 17px var(--sans)'>{'appended' if k == 'duplicate' else 'replaced'}</span>",
        ),
    ]
body += [D(64, 176 + 6 * 66 - 8, 1152, 1, "hair")]
body += [
    D(
        64,
        620,
        1152,
        None,
        "note",
        "Severity 1.0 is the reference dataset. Sweeping the multiplier turns &quot;we picked the magnitudes&quot; into a curve (severity slide).",
    ),
    foot("src/etl_benchmark/synthetic.py &nbsp;·&nbsp; seed-reproducible, tested"),
]
slide(
    "Injection",
    "".join(body),
    tone="bone",
    role="method",
    family="four-column ledger",
    dominant="injection rules",
    density="medium",
)

# 16 ----------------------------------------------------------------- pivot
slide(
    "The pivot",
    "".join(
        [
            flow(
                64,
                56,
                1152,
                [
                    "<div class='k'>The pivot</div>",
                    "<h1 style='font-size:104px;line-height:.98;margin-top:40px'>Aggregate scores do not establish equivalence.</h1>",
                    "<p style='font-size:36px;font-family:var(--cond);font-weight:500;margin-top:44px'>Per-type results show different competencies.</p>",
                    "<p class='note' style='margin-top:40px'>F1 spans 0.22 to 0.59 over the seventeen detectors on the synthetic set, and the per-type competences barely overlap.</p>",
                ],
                maxh=620,
                gap=0,
            ),
        ]
    ),
    role="turn",
    family="typographic statement",
    dominant="headline",
    density="low",
)

# 17 ----------------------------------------------------------------- fraud: bars
fr, h1 = hbars(
    64,
    190,
    760,
    [
        ("Z-score", 0.078, "n"),
        ("IQR", 0.018, "n"),
        ("Great Expectations", 0.182, "best"),
        ("Isolation Forest", 0.120, "n"),
    ],
    0.2,
    "bone",
    ref=0.0017,
    ref_label="prevalence 0.17%",
)
pr, h2 = hbars(
    64,
    420,
    760,
    [
        ("Z-score", 0.011, "n"),
        ("IQR", 0.003, "n"),
        ("Great Expectations", 0.037, "n"),
        ("Isolation Forest", 0.202, "best"),
    ],
    0.25,
    "bone",
)
slide(
    "Credit card fraud",
    "".join(
        [
            kicker("Real fraud data"),
            title("The operating point decides the outcome", 48, 66),
            D(64, 160, 760, None, "k", "average precision (ranking)"),
            fr,
            D(64, 392, 760, None, "k", "precision at the flag threshold (decision)"),
            pr,
            D(
                64,
                626,
                780,
                None,
                "legend",
                "<span class='ok'>&#9679;</span> best of its chart. Mean over 5 seeds, 15% held-out test split. LOF and One-Class SVM were not run here (expected too costly at 284k rows; not measured). The two charts use different scales.",
            ),
            flow(
                870,
                190,
                346,
                [
                    "<p style='font-size:19px'>The statistical rules recover most frauds (recall 0.87 and 0.97) at precision below 0.04. Isolation Forest changes once its contamination matches the prevalence: it flags 0.17% of rows and reaches the first usable precision, at recall 0.21 (F1 = 0.20 &plusmn; 0.07). Great Expectations leads AP, at precision 0.04.</p>",
                    "<div class='stat sm' style='position:static'><span class='num'>0.01 &rarr; 0.28</span><span class='lab' style='font-size:16px'>Isolation Forest precision when contamination goes from 0.10 to the prevalence (one seed; 0.20 on average over five)</span></div>",
                ],
                maxh=430,
                gap=14,
            ),
            foot(
                "experiments/run_benchmark.py &nbsp;·&nbsp; make benchmark &nbsp;·&nbsp; the metric that matters here: AP"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="paired bar charts",
    dominant="two bar charts",
    density="medium",
    colour="steel for best",
)

# 18 ----------------------------------------------------------------- cardio: bars
cd = [
    ("Z-score", 0.61, 0.61),
    ("IQR", 0.33, 0.30),
    ("Great Expectations", 0.29, 0.19),
    ("Isolation Forest", 0.62, 0.70),
    ("LOF", 0.26, 0.24),
    ("One-Class SVM", 0.58, 0.63),
]
f1c, hf = hbars(
    64,
    190,
    560,
    [(n, f, "best" if n == "Isolation Forest" else "n") for n, f, a in cd],
    0.8,
    "bone",
    digits=2,
)
apc, ha = hbars(
    656,
    190,
    560,
    [(n, a, "best" if n == "Isolation Forest" else "n") for n, f, a in cd],
    0.8,
    "bone",
    ref=0.096,
    ref_label="prevalence 9.6%",
    digits=2,
)
slide(
    "Cardio",
    "".join(
        [
            kicker("Genuinely imbalanced real data"),
            title("When anomalies are rare and outlying, several learned detectors work", 44, 66),
            D(64, 160, 560, None, "k", "F1 at the flag threshold"),
            f1c,
            D(656, 160, 560, None, "k", "average precision"),
            apc,
            D(
                64,
                480,
                1152,
                None,
                "",
                "<p style='font-size:20px;max-width:1000px'>Isolation Forest reaches F1 0.62 and AP 0.70, with ECOD, COPOD and DIF close behind (AP 0.69, 0.69, 0.67). Z-score also does well: the 21 features are standardized and anomalies stand out on several at once. This is the counterpoint to a 0.17% mixed label and a 61% majority.</p>",
            ),
            D(
                64,
                590,
                1152,
                None,
                "legend",
                "<span class='ok'>&#9679;</span> best of its chart. Cardiotocography, 1,831 rows, 9.6% anomalies. Mean over 5 seeds, test split. Wide seed spread on this small set (ML F1 std up to 0.17).",
            ),
            foot("make benchmark-cardio &nbsp;·&nbsp; the regime the detectors are built for"),
        ]
    ),
    tone="bone",
    role="evidence",
    family="paired bar charts",
    dominant="two bar charts",
    density="medium",
    colour="steel for best",
)

# 19 ----------------------------------------------------------------- synthetic aggregate: precision/recall scatter
pts = [
    ("Z-score", 1.0, 0.196, "n", (-12, 24, "end")),
    ("HBOS", 1.0, 0.204, "n", (12, 24, "start")),
    ("IQR", 0.584, 0.396, "n"),
    ("Isolation Forest", 0.495, 0.499, "n", (14, 20, "start")),
    ("One-Class SVM", 0.478, 0.485, "n", (-18, 24, "end")),
    ("KNN", 0.466, 0.469, "n", (-12, -4, "end")),
    ("VAE", 0.502, 0.507, "n", (12, -8, "start")),
    ("DIF", 0.589, 0.582, "best"),
    ("ECOD", 0.341, 0.341, "n"),
    ("LUNAR", 0.345, 0.668, "n"),
]
slide(
    "Synthetic aggregate",
    "".join(
        [
            kicker("Synthetic dataset, aggregate"),
            title("Aggregate scores hide different trade-offs", 46, 66),
            pr_scatter(64, 150, pts, "bone", 640, 500),
            flow(
                760,
                160,
                456,
                [
                    "<p style='font-size:22px;line-height:1.38'>Z-score and HBOS reach a perfect precision by firing only on extreme rows (recall 0.20). DIF has the best F1 and AP; the VAE matches Isolation Forest; LUNAR has the best recall with a low precision.</p>",
                    "<div class='stat sm' style='position:static'><span class='num'>F1 0.22 to 0.59</span><span class='lab' style='font-size:16px'>range across the seventeen detectors</span></div>",
                    "<div class='note' style='position:static'>Ten of the seventeen detectors shown, mean over 5 seeds, test split, 12,360 rows, 17.5% anomalous. Dashed lines are constant F1. <span class='ok'>&#9679;</span> best F1. All 17 are in the synthetic table of the paper.</div>",
                ],
                maxh=480,
                gap=24,
            ),
            foot("verification/evidence/full_registry &nbsp;·&nbsp; paper, tab:synthetic"),
        ]
    ),
    tone="bone",
    role="evidence",
    family="scatter with iso-F1 curves",
    dominant="scatter",
    density="medium",
    colour="steel for best",
)

# 20 ----------------------------------------------------------------- per-type matrix, cividis
names = MATRIX["order"]
data = [[MATRIX["data"][n][t] for t in TYPES] for n in names]
mx, mh = matrix(660, 100, names, TYPES, data, 86, 26, "dark", font=14, label_w=84)
slide(
    "Per type",
    "".join(
        [
            D(64, 52, 560, None, "k", "Per type, the contribution"),
            D(
                64,
                84,
                560,
                None,
                "",
                "<h2 class='fit1' style='font-size:50px;line-height:1.03'>Each method has a narrow competence</h2>",
            ),
            D(
                64,
                262,
                540,
                None,
                "",
                "<p style='font-size:20px'>Rules and most joint and neural detectors all find univariate outliers (Z-score 0.93, IQR 0.99). Only <b>Great Expectations</b> finds missing values (1.00), and <b>deduplication</b> owns exact duplicates.</p><p style='font-size:20px;margin-top:14px'>Isolation Forest (0.89) and the One-Class SVM (0.90) are the only first-six methods with real recall on multivariate outliers; every rule stays at 0.04 or below.</p><p style='font-size:20px;margin-top:14px'>Broad coverage needs several families, not the single best one.</p>",
            ),
            mx,
            D(
                64,
                640,
                540,
                None,
                "note",
                "Mean recall, 17 detectors, 5 seeds. Scale: cividis, 0 to 1.",
            ),
            foot(
                "paper, Appendix C, tab:m-customer &nbsp;·&nbsp; duplicates need the transform stage"
            ),
        ]
    ),
    role="evidence",
    family="matrix",
    dominant="17 by 6 matrix",
    density="high",
    colour="cividis scale",
)

# 21 ----------------------------------------------------------------- gamed
slide(
    "Gaming detection rate",
    "".join(
        [
            D(64, 56, 700, None, "k", "Recall and precision, per type"),
            D(
                64,
                88,
                1100,
                None,
                "",
                "<h1 style='font-size:76px;line-height:1.0'>Detection rate alone can be <span class='em'>gamed</span></h1>",
            ),
            D(
                64,
                262,
                540,
                None,
                "",
                "<div class='cond' style='font-size:30px;font-weight:600'>A wide net</div><div class='num' style='font-size:110px;margin-top:6px'>0.89<span style='font-size:42px;font-weight:500'> recall</span></div><div class='num' style='font-size:110px;margin-top:6px'>~0.22<span style='font-size:42px;font-weight:500'> precision</span></div><p style='font-size:20px;margin-top:16px'>Isolation Forest and the One-Class SVM on multivariate outliers: they cast a wide net that also catches clean rows.</p>",
            ),
            D(
                704,
                262,
                512,
                None,
                "",
                "<div class='cond' style='font-size:30px;font-weight:600'>A narrow one</div><div class='num' style='font-size:110px;margin-top:6px'>1.00<span style='font-size:42px;font-weight:500'> precision</span></div><div class='num' style='font-size:110px;margin-top:6px'>0.20<span style='font-size:42px;font-weight:500'> recall</span></div><p style='font-size:20px;margin-top:16px'>Z-score fires only when it is certain: on the whole synthetic set its precision is 1.00 and its recall 0.196.</p>",
            ),
            D(
                64,
                640,
                1152,
                None,
                "note",
                "Clean rows are the only negatives. Both views are needed: neither number alone ranks the detectors.",
            ),
            foot(
                "paper, per-type results and tab:synthetic &nbsp;·&nbsp; synthetic customer table, 5 seeds"
            ),
        ]
    ),
    role="argument",
    family="typographic contrast",
    dominant="paired numerals",
    density="low",
)

# 22 ----------------------------------------------------------------- PR curves
slide(
    "PR curves",
    "".join(
        [
            D(64, 44, 700, None, "k", "Precision-recall curves"),
            D(
                64,
                72,
                1100,
                None,
                "",
                "<h2 class='fit1' style='font-size:46px'>One threshold hides the whole trade-off</h2>",
            ),
            pr_panels(64, 138, "bone", 700, 520)[0],
            flow(
                800,
                160,
                416,
                [
                    "<p style='font-size:19px;line-height:1.36'>On <b>Cardio</b> the top four of eleven stay high (ECOD 0.83, Isolation Forest 0.80, COPOD 0.79, One-Class SVM 0.76). On <b>Water Quality</b> every curve stays near the 0.61 base rate. On <b>Credit Card Fraud</b> the highest AP is COPOD 0.28 (Great Expectations 0.23, Isolation Forest 0.17), and no curve holds precision much above 0.4 once recall reaches 0.3.</p>",
                    "<div class='stat sm' style='position:static'><span class='num'>0.37 &rarr; 0.008</span><span class='lab' style='font-size:17px'>Isolation Forest fraud precision as contamination goes from 0.001 to 0.20, while recall rises from 0.23 to 0.92</span></div>",
                    "<p class='note' style='font-size:15px'>Per panel, among the detectors drawn (no neural models): highest AP dark, lowest dashed grey, others light grey. Dashed line: base rate. PCA differs from the paper figure on two panels.</p>",
                ],
                maxh=480,
                gap=22,
            ),
            foot(
                "slides/art/data/pr_curves.json &nbsp;·&nbsp; AP of one run (seed 42), not the 5-seed means of slides 17 and 18"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="native small multiples",
    dominant="curves",
    density="medium",
)

# 23 ----------------------------------------------------------------- severity
slide(
    "Severity",
    "".join(
        [
            D(64, 44, 700, None, "k", "Detection rate against injection severity"),
            D(
                64,
                72,
                1152,
                None,
                "",
                "<h2 class='fit1' style='font-size:44px'>The ranking moves with severity</h2>",
            ),
            severity_panels(
                64,
                146,
                1152,
                304,
                "dark",
                {
                    "univariate_outlier": [("knn", "A"), ("lof", "B"), ("great_expectations", "C")],
                    "multivariate_outlier": [
                        ("isolation_forest", "A"),
                        ("iqr", "B"),
                        ("ocsvm", "E"),
                    ],
                    "temporal_drift": [
                        ("isolation_forest", "A"),
                        ("lof", "B"),
                        ("iqr", "C"),
                        ("ocsvm", "E"),
                        ("drift", "D"),
                    ],
                },
            ),
            flow(
                64,
                462,
                820,
                [
                    "<p style='font-size:19px;line-height:1.38'>Univariate outliers are saturated at severity 0.5 for IQR, Isolation Forest, One-Class SVM, KNN and PCA; LOF and Great Expectations are not. Multivariate outliers show a threshold: Isolation Forest and the One-Class SVM climb to recall 1.0, and IQR jumps from 0.04 to 1.0 once the injected percentile crosses its fence. Temporal drift becomes easier for IQR, Isolation Forest and the One-Class SVM, while LOF peaks earlier and then falls. The row-level drift detector does not respond.</p>",
                    "<p class='note' style='font-size:15px'>Mean over three seeds, synthetic data. Grey: the other methods. Dashed vertical line: the reference severity 1.</p>",
                ],
                maxh=206,
                gap=10,
            ),
            flow(
                908,
                462,
                308,
                [
                    "<div class='stat sm' style='position:static'><span class='num'>0.28 &rarr; 0.65</span><span class='lab' style='font-size:17px'>Isolation Forest recall on temporal drift, severity 1 to 3</span></div>"
                ],
                maxh=190,
            ),
            foot(
                "verification/evidence/severity.csv &nbsp;·&nbsp; experiments/run_severity.py &nbsp;·&nbsp; answers the &quot;we picked the magnitudes&quot; threat"
            ),
        ]
    ),
    role="evidence",
    family="native small multiples, three panels",
    dominant="curves",
    density="medium",
)

_unused = (BONE, DARK, tbl, mono)
