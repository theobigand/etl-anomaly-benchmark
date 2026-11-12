#!/usr/bin/env python3
"""Build slides/thesis_progress.html (raking-light deck) from slide definitions.

Run from the repository root:  python3 slides/build_deck.py
Figures come from paper/figures, photographs from slides/art/assets/web (see slides/art/PROVENANCE.md).
Numbers are copied from paper/main.tex and verification/ notes; see slides/README.md.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).parent
CSS = (HERE / "deck.css").read_text()
SLIDES = []


def D(x, y, w=None, h=None, cls="", inner="", style=""):
    pos = f"left:{x}px;top:{y}px;"
    if w is not None:
        pos += f"width:{w}px;"
    if h is not None:
        pos += f"height:{h}px;"
    return f'<div class="{cls}" style="{pos}{style}">{inner}</div>'


def slide(sec, body, tone="dark", cls=""):
    SLIDES.append((sec, tone, cls, body))


def tbl(head, rows, hot=(), cool=(), dim=(), text_cols=(), compact=False, extra=""):
    h = "".join(f'<th class="{"t" if i in text_cols else ""}">{c}</th>' for i, c in enumerate(head))
    fs = {0: "", 1: ' style="font-size:16px"', 2: ' style="font-size:15px"'}[int(compact)]
    out = [f"<table{fs}><tr>{h}</tr>"]
    for r, row in enumerate(rows):
        if isinstance(row, str):
            out.append(f'<tr class="grp"><td colspan="{len(head)}">{row}</td></tr>')
            continue
        cells = []
        for c, v in enumerate(row):
            k = ""
            if (r, c) in hot:
                k = "hot"
            elif (r, c) in cool:
                k = "cool"
            elif (r, c) in dim:
                k = "dim"
            if c in text_cols:
                k += " t"
            pad = {0: "", 1: ' style="padding:4px 12px"', 2: ' style="padding:1px 12px"'}[int(compact)]
            cells.append(f'<td class="{k.strip()}"{pad}>{v}</td>')
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "".join(out) + extra


def photo(x, y, w, h, pos="50% 50%", size="cover", img="cover-plate", dim=0):
    shade = f"linear-gradient(rgba(10,10,10,{dim}),rgba(10,10,10,{dim})),"
    return D(x, y, w, h, "ph", "", f"background-image:{shade if dim else ''}url(art/assets/web/{img}.jpg);background-position:{pos};background-size:{size}")


def glyph(kind, x, y, s=120, light=True):
    """Pad glyph on a 3x3 grid. Light from the lower left, shadows to the right."""
    pad, step = s / 4.6, s / 3.0
    parts = []
    for r in range(3):
        for c in range(3):
            px, py = c * step + step * 0.12, r * step + step * 0.12
            k = None
            if (r, c) == (1, 1):
                k = kind
            fill, sh, hh = "#2b2d30", 3, 0
            if k == "missing":
                parts.append(f'<rect x="{px}" y="{py}" width="{pad}" height="{pad}" fill="#0b0b0c"/><rect x="{px}" y="{py}" width="{pad*0.22}" height="{pad}" fill="#000"/>')
                continue
            if k == "duplicate":
                pass
            if k == "univariate":
                sh, hh, fill = pad * 1.9, 5, "#4a4439"
            if k == "multivariate":
                fill = "#2b2d30"
            if k == "drift":
                fill = "#2b2d30"
            parts.append(f'<rect x="{px+sh}" y="{py+2}" width="{pad}" height="{pad}" fill="#000" opacity=".55"/>')
            parts.append(f'<rect x="{px}" y="{py-hh}" width="{pad}" height="{pad}" fill="{fill}"/>')
            parts.append(f'<rect x="{px}" y="{py-hh}" width="1.6" height="{pad}" fill="#eaa24f"/><rect x="{px}" y="{py-hh}" width="{pad}" height="1.2" fill="#eaa24f" opacity=".6"/>')
    extra = ""
    if kind == "duplicate":
        extra = f'<rect x="{step*0.12+step}" y="{step*0.12+step}" width="{pad}" height="{pad}" fill="none"/>'
    if kind == "multivariate":
        extra = f'<rect x="{step*1.12+pad*0.35}" y="{step*1.12+pad*0.35}" width="{pad*0.3}" height="{pad*0.3}" fill="#eaa24f"/>'
    if kind == "drift":
        extra = "".join(f'<rect x="{c*step+step*0.12}" y="{(2)*step+step*0.12+pad+2}" width="{pad}" height="{2+c*2}" fill="#eaa24f" opacity="{.35+c*.25}"/>' for c in range(3))
    if kind == "invalid":
        parts.append(f'<rect x="{step*1.12}" y="{step*1.12}" width="{pad}" height="{pad}" fill="#2b2d30"/><path d="M{step*1.12} {step*1.12} L{step*1.12+pad} {step*1.12+pad}" stroke="#eaa24f" stroke-width="1.6"/>')
    if kind == "duplicate":
        parts.append(f'<rect x="{step*1.12+pad+3}" y="{step*1.12}" width="{pad}" height="{pad}" fill="#2b2d30" stroke="#eaa24f" stroke-width="1.2"/>')
    return f'<svg style="position:absolute;left:{x}px;top:{y}px" width="{s}" height="{s}" viewBox="0 0 {s} {s}" aria-hidden="true">{"".join(parts)}{extra}</svg>'


def foot(src, n=None):
    return D(64, 684, 1100, None, "src foot", src, "position:absolute;left:64px;bottom:auto;top:678px")


# ---------------------------------------------------------------- 1 cover
slide("Cover", "".join([
    photo(0, 0, 1280, 720, "100% 35%", "150%"),
    D(0, 0, 1280, 720, "scrim", "", "background:linear-gradient(90deg,rgba(10,10,10,0) 40%,rgba(10,10,10,.8) 56%,rgba(10,10,10,.88) 100%)"),
    D(716, 58, 500, None, "k", "ESILV Data &amp; AI &nbsp;·&nbsp; master thesis"),
    D(716, 112, 500, None, "", "<h1 style='font-size:68px;line-height:1.0'>Anomaly detection for data quality, <span class='ember'>measured</span> inside the ETL pipeline</h1>"),
    D(716, 396, 500, None, "", "<p style='font-size:21px;color:var(--paper-soft)'>Rules, classical and neural detectors run through one pipeline and compared per anomaly type. Living progress deck, 2026-11-12.</p>"),
    D(716, 560, 500, None, "note", "Illustration, not data: a generated still life. One pad of 312 stands proud; the low light finds it."),
    D(716, 612, 500, None, "k", "17 detectors &nbsp; 6 anomaly types &nbsp; 152 datasets"),
    D(716, 648, 500, None, "src", "Theo Bigand &nbsp;·&nbsp; github.com/theobigand/etl-anomaly-benchmark"),
]))

# ---------------------------------------------------------------- 2 question
slide("The question", "".join([
    D(64, 56, 600, None, "k", "The question"),
    D(64, 108, 1060, None, "", "<h1 style='font-size:84px;line-height:1.0'>Does machine learning in an ETL pipeline beat plain rules, and for <span class='ember'>which anomalies</span>?</h1>"),
    D(64, 392, 560, None, "", "<p class='lede' style='font-size:23px'>Rules are the industry default: auditable, cheap, and blind to what the author did not anticipate. Recent work puts ML detectors inside the flow, but on one algorithm and one dataset. This thesis builds the missing head-to-head benchmark and breaks the result down by anomaly type.</p>"),
    D(704, 400, 1, 250, "vr", "", "left:688px;"),
    D(724, 396, 500, None, "", "<div class='k' style='margin-bottom:14px'>What generic benchmarks leave out</div>"
        "<p style='font-size:19px;margin-bottom:12px'><b>Pipeline.</b> Algorithms are scored outside any pipeline; integration cost is not measured.</p>"
        "<p style='font-size:19px;margin-bottom:12px'><b>Rules.</b> The declarative baseline that dominates production is absent.</p>"
        "<p style='font-size:19px;margin-bottom:12px'><b>Types.</b> One aggregate score per dataset hides which family finds which defect.</p>"
        "<p style='font-size:19px'><b>Threshold.</b> One flag threshold, not the precision-recall trade-off.</p>"),
    D(64, 678, 1100, None, "src", "paper/main.tex, IMRaD experimental paper"),
]))

# ---------------------------------------------------------------- 3 related work
slide("Related work", "".join([
    D(64, 48, 900, None, "k", "Related work &nbsp;·&nbsp; issue #68"),
    D(64, 80, 1150, None, "", "<h2 style='font-size:46px;line-height:1.05'>Benchmarks rank detectors. Few report their decisions</h2>"),
    D(64, 252, 760, None, "sheet", tbl(["Work", "Time order", "At a threshold"], [
        ["ADBench, 30 algorithms, 57 sets", "not found", "not found (AUC)"],
        ["Agyemang 2024, one simulated set", "none", "precision, recall, F1"],
        ["AnoShift, Kyoto 2006 to 2015", "IID, NEAR, FAR", "not found (AUC)"],
        ["FedAD-Bench, federated deep", "not found", "F1-optimal threshold"],
        ["Sun et al. 2024, online thresholds", "shift in a stream", "error-rate guarantees"],
    ], text_cols=(1, 2)), "padding:8px 10px"),
    D(64, 560, 760, None, "legend", "&quot;Not found&quot; means absent from the text I read, not proven absent. This thesis: six fault types, a controlled generator and real tables, decisions and pipeline cost."),
    D(884, 252, 330, None, "", "<p style='font-size:22px;line-height:1.4'>In the texts I read, ADBench and AnoShift report AUC only, and none of these works breaks results down by data-quality fault.</p>"
        "<p class='note' style='margin-top:18px;font-size:16px'>The scan is not systematic: this is a gap I did not find filled, not a proof that nothing exists. References were checked against a primary source or the DOI registry.</p>"),
    D(64, 678, 1100, None, "src", "verification/references.md, bibliography verified against primary sources"),
], ), tone="bone")

# ---------------------------------------------------------------- 4 research questions
rq = [
    ("RQ1", "Rules, classical and neural detectors in one pipeline", "examples, 100 labelled problems", "historical ranking, train-only replay pending"),
    ("RQ2", "Which anomaly type each family finds", "synthetic matrix, schemas, 42 UCI tables", "narrow competence; values do not transfer"),
    ("RQ3", "Operating point and time", "contamination, label-free threshold, chronological split", "a threshold fixed on the past fails when prevalence moves"),
    ("RQ4", "Cost in the pipeline", "cost study, ETL run on 152 sets", "neural 10 to 100 times column-wise"),
]
body = [D(64, 52, 900, None, "k", "Research questions"),
        D(64, 84, 1100, None, "", "<h2 style='font-size:50px;line-height:1.04'>Four questions, one study each, hypotheses written first</h2>")]
for i, (a, q, s, ans) in enumerate(rq):
    y = 214 + i * 108
    body.append(D(64, y, 1152, 1, "hair"))
    body.append(D(64, y + 14, 130, None, "", f"<span class='num ember' style='font-size:56px'>{a}</span>"))
    body.append(D(214, y + 14, 480, None, "", f"<p style='font-size:24px;line-height:1.2;font-family:var(--cond);font-weight:600'>{q}</p>"))
    body.append(D(214, y + 64, 480, None, "note", s))
    body.append(D(730, y + 18, 486, None, "", f"<p style='font-size:20px;color:var(--ember)'>{ans}</p>"))
body.append(D(64, 650, 1152, None, "note", "Every study has a protocol and hypotheses committed before its runs. A hypothesis that fails is reported as failed: three of the six on the whole pool do."))
body.append(D(64, 684, 800, None, "src", "paper, Introduction and Methods; pre-registered in verification/*.md"))
slide("Research questions", "".join(body))

# ---------------------------------------------------------------- 5 six types
types = [
    ("missing", "missing value", "one or two feature cells set to null"),
    ("duplicate", "exact duplicate", "a clean row copied, same business attributes"),
    ("univariate", "univariate outlier", "one numeric field pushed far out of range"),
    ("multivariate", "multivariate outlier", "every field in range, the combination not"),
    ("drift", "temporal drift", "recent signups whose income and balance have shifted up"),
    ("invalid", "invalid format", "malformed e-mail, out-of-domain country code, impossible age"),
]
body = [D(64, 52, 700, None, "k", "The original contribution"),
        D(64, 84, 540, None, "", "<h2 style='font-size:46px;line-height:1.03'>A controlled dataset that labels six anomaly types separately</h2>"),
        D(64, 300, 520, None, "", "<p style='font-size:22px'>12,360 records generated with Faker and NumPy, six types injected at 3% each, every row tagged with its category. Recall and precision are reported per type, which generic benchmarks that publish one aggregate score do not provide.</p>"),
        D(64, 560, 520, None, "note", "The magnitudes are one severity multiplier, so the choice is swept rather than fixed. Glyphs: a pad that is missing, doubled, raised, shifted, sloping or cracked."),
        D(64, 678, 700, None, "src", "make synthetic &nbsp;·&nbsp; make severity &nbsp;·&nbsp; generator is deterministic, dataset not committed")]
for i, (k, name, desc) in enumerate(types):
    c, r = i % 2, i // 2
    x, y = 664 + c * 290, 70 + r * 200
    body.append(glyph(k, x, y, 110))
    body.append(D(x, y + 120, 270, None, "", f"<div class='cond' style='font-size:25px;font-weight:600'>{name}</div><div class='note' style='margin-top:4px;font-size:15px'>{desc}</div>"))
slide("Contribution", "".join(body))

# ---------------------------------------------------------------- 6 system
slide("System", "".join([
    D(64, 52, 700, None, "k", "The system"),
    D(64, 84, 1100, None, "", "<h2 style='font-size:50px'>One interface, one measured path</h2>"),
    D(64, 178, 1152, 150, "", "".join([
        f"<div style='position:absolute;left:{x}px;top:0;width:250px;height:92px;border:2px solid {'var(--ember-ink)' if hot else 'var(--ink)'};background:{'var(--ember-wash)' if hot else 'transparent'};padding:14px 18px'><div class='cond' style='font-size:34px;font-weight:700'>{t}</div><div class='note' style='font-size:14px'>{s}</div></div>"
        for x, t, s, hot in [(0, "extract", "read the table", False), (300, "transform", "exact dedup, clean", False), (600, "detect", "fit + predict + score", True), (900, "load", "write the files", False)]]
        + ["<div style='position:absolute;left:250px;top:44px;width:50px;height:2px;background:var(--ink)'></div><div style='position:absolute;left:550px;top:44px;width:50px;height:2px;background:var(--ink)'></div><div style='position:absolute;left:850px;top:44px;width:50px;height:2px;background:var(--ink)'></div>",
           "<div class='note' style='position:absolute;left:600px;top:104px;width:250px'>latency is measured here, in the real in-pipeline time</div>"])),
    D(64, 356, 560, None, "", "<p style='font-size:20px'>The demo and every benchmark call the same <code style='font-family:var(--mono)'>detect()</code> stage. A continuous <code style='font-family:var(--mono)'>score()</code> on top of the boolean <code style='font-family:var(--mono)'>predict()</code> makes ROC-AUC and AP computable; <code style='font-family:var(--mono)'>detect(fit_df=...)</code> fits on the train slice and scores the test set.</p>"
        "<p class='note' style='margin-top:14px;font-size:16px'>Exact deduplication belongs to the ordinary transform. Typed injected duplicates remain in their separate evaluation with transform_dedup.</p>"),
    D(668, 336, 548, 326, "sheet", "<pre style='padding:14px 18px;font-size:14px;line-height:1.42'>"
        "<span style='color:#8b887f'># every detector, one contract</span>\nclass Detector(ABC):\n    name: str\n    def fit(self, df) -&gt; Self: ...\n    def predict(self, df) -&gt; Series:  <span style='color:#8b887f'># bool/row</span>\n        ...\n    def score(self, df) -&gt; Series:    <span style='color:#8b887f'># graded</span>\n        return self.predict(df).astype(float)\n\n<span style='color:#8b887f'># classical ML: adapt PyOD, do not reimplement</span>\nclass PyODDetector(Detector): ...\n\n<span style='color:#8b887f'># registry: one line per detector</span>\n\"isolation_forest\": lambda: IsolationForestDetector(),</pre>"),
    D(64, 678, 1152, None, "src", "src/etl_benchmark/pipeline.py &nbsp;·&nbsp; quality/base.py, interface modelled on PyOD BaseDetector"),
], ), tone="bone")

# ---------------------------------------------------------------- 7 AP
slide("Metric", "".join([
    D(64, 52, 700, None, "k", "Metric interpretation"),
    D(64, 84, 1100, None, "", "<h2 style='font-size:50px'>Average Precision measures the ranking</h2>"),
    D(64, 196, 1152, None, "", "<div class='num' style='font-size:128px;font-weight:700'>AP <span class='ember'>=</span> &Sigma; &Delta;R &middot; P</div>"),
    D(64, 340, 900, None, "note", "precision, weighted by each recall increment, over distinct score cutoffs from high to low; tied scores enter together. AP uses continuous anomaly scores. Precision, recall, F1 and the flagged share use a selected threshold."),
    D(64, 452, 360, None, "", "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>Non-interpolated</div><p style='font-size:18px;margin-top:8px'>AP differs from trapezoidal precision-recall area.</p>"),
    D(464, 452, 360, None, "", "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>Prevalence matters</div><p style='font-size:18px;margin-top:8px'>Prevalence is the no-skill reference. Constant scores give AP equal to prevalence.</p>"),
    D(864, 452, 352, None, "", "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>Decisions apart from scores</div><p style='font-size:18px;margin-top:8px'>Changing only the flag threshold leaves AP and ROC-AUC unchanged; neither fixes a useful operating point.</p>"),
    D(64, 600, 1152, None, "note", "Historical naming: stored pr_auc fields and remaining AP labels in archived figures and the paper denote this same AP quantity."),
    D(64, 678, 1152, None, "src", "paper/main.tex, Evaluation protocol, equation (3) &nbsp;·&nbsp; scikit-learn average_precision_score"),
]))

# ---------------------------------------------------------------- 8 detectors
dets = [
    ["Z-score", "rule", "flag |z| &gt; 3 on any column", "mean and std inflated by outliers"],
    ["IQR", "rule", "Tukey fences, k = 1.5", "fires often in high dimension"],
    ["Great Expectations", "rule", "null checks, fitted 0.1% / 99.9% bounds", "generic suite, no domain rules"],
    ["Isolation Forest", "joint", "isolation depth under random splits", "axis-aligned splits, weak on nulls"],
    ["LOF", "joint", "local density against 20 neighbours", "cost grows with the scored set"],
    ["One-Class SVM", "joint", "RBF boundary around the bulk", "quadratic training"],
    ["ECOD", "column-wise", "empirical tail probabilities, summed", "no explicit cross-feature dependence"],
    ["COPOD", "column-wise", "max of skew term and mean log tails", "same"],
    ["HBOS", "column-wise", "histogram per column, inverse bin height", "independent columns, coarse bins"],
    ["KNN", "joint", "distance to the 5th neighbour", "quadratic, skipped above 50k rows"],
    ["PCA", "joint", "reconstruction error, 95% of variance", "misses a shift inside the kept space"],
    ["drift", "time-aware", "recent-window mean shift", "per row, so diluted drift is invisible"],
]
slide("Detectors", "".join([
    D(64, 44, 700, None, "k", "Three families, eleven row-level detectors"),
    D(64, 72, 1100, None, "", "<h2 style='font-size:44px'>Rules and classical models, one contract</h2>"),
    D(64, 138, 1152, None, "sheet", tbl(["Detector", "Family", "Principle", "Main limit"], dets, text_cols=(1, 2, 3), compact=True), "padding:4px 10px"),
    D(64, 618, 1152, None, "note", "PyOD or the recorded protocol adaptations; flag threshold from training prevalence. Numeric columns only, while Great Expectations separately checks nulls on all columns: an explicit information asymmetry. The time-aware drift detector is opt-in and synthetic only."),
    D(64, 686, 1152, None, "src", "src/etl_benchmark/quality/ml.py, rules.py, gx.py &nbsp;·&nbsp; ECOD/COPOD use training ranks and frozen skew signs"),
]), tone="bone")

# ---------------------------------------------------------------- 9 fitted rules
slide("Fitted rules", "".join([
    D(64, 52, 700, None, "k", "Fitted rules"),
    D(64, 84, 1100, None, "", "<h2 style='font-size:50px'>Column bounds do not fix row alert rates</h2>"),
    D(64, 258, 360, None, "", "<div class='cond' style='font-size:36px;font-weight:700;color:var(--ember)'>Z-score</div><p style='font-size:19px;margin-top:10px'>Maximum |x &minus; training mean| / sample standard deviation. Flag above 3; constant columns contribute zero.</p>"),
    D(444, 258, 360, None, "", "<div class='cond' style='font-size:36px;font-weight:700;color:var(--ember)'>IQR</div><p style='font-size:19px;margin-top:10px'>Training fences Q1 &minus; 1.5 IQR and Q3 + 1.5 IQR. Flag strictly outside; zero-IQR columns contribute zero.</p>"),
    D(824, 258, 392, None, "", "<div class='cond' style='font-size:36px;font-weight:700;color:var(--ember)'>Great Expectations</div><p style='font-size:19px;margin-top:10px'>Not-null on all columns; inclusive training quantiles 0.1% and 99.9%. Score: fraction of active checks violated.</p>"),
    D(64, 470, 1152, 1, "hair"),
    D(64, 490, 560, None, "", "<div class='k'>Gaussian reference only</div><p style='font-size:21px;margin-top:8px'>Per-column tails: <b>0.27%</b> beyond 3&sigma;, <b>0.70%</b> beyond the IQR fences (about 2.7&sigma;). Fitted bounds and several columns change row-level rates.</p>"),
    D(664, 490, 552, None, "", "<div class='k'>Scope</div><p style='font-size:21px;margin-top:8px'>All statistics come from training data. The evaluated Great Expectations suite is a generic statistical baseline: no domain-specific category, format or cross-field rules.</p>"),
    D(64, 678, 1152, None, "src", "paper/main.tex, Methods, rule-based detectors"),
]))

# ---------------------------------------------------------------- 10 neural
neural = [
    ["Autoencoder", "rebuild standardized rows through a bottleneck", "MLP from scikit-learn"],
    ["VAE", "Gaussian code, rebuild, reconstruction error", "scored with the code mean; PyOD draws one"],
    ["Deep SVDD", "map normal rows near a centre, distance", "weakest on most types"],
    ["DIF", "isolation forests on random neural features", "training representation scaler reused"],
    ["AE1SVM", "autoencoder + random-Fourier one-class SVM", "singleton padding changes training weight"],
    ["LUNAR", "network learns the score from neighbour distances", "best on drift, many false alarms"],
]
slide("Neural detectors", "".join([
    D(64, 48, 700, None, "k", "Six neural models, opt-in"),
    D(64, 80, 1100, None, "", "<h2 style='font-size:50px'>Neural detectors behind the same contract</h2>"),
    D(64, 168, 760, None, "sheet", tbl(["Detector", "Principle", "Fixed or noted"], neural, text_cols=(1, 2)), "padding:6px 10px"),
    D(868, 168, 348, None, "", "<p style='font-size:21px;line-height:1.4'>PyOD 3.6.7 with recorded adaptations, CPU, seeded, fitted on at most 20,000 rows.</p><p style='font-size:19px;margin-top:16px;line-height:1.4'>Frozen representation scaling and latent-mean scoring change the evaluated algorithms. They do not establish equivalence to upstream defaults.</p><p class='note' style='margin-top:16px;font-size:16px'>The LSTM autoencoder reads windows of ordered rows and stays outside the registry.</p>"),
    D(64, 678, 1152, None, "src", "verification/detector_inventory.md &nbsp;·&nbsp; full_registry.md &nbsp;·&nbsp; 17 row-level detectors tested for batch independence"),
]), tone="bone")

# ---------------------------------------------------------------- 11 variants
slide("Evaluated variants", "".join([
    D(64, 52, 700, None, "k", "Evaluated variants"),
    D(64, 84, 1100, None, "", "<h2 style='font-size:48px'>Stable row scores require explicit adaptations</h2>"),
    D(64, 232, 560, None, "", "<p class='lede' style='font-size:23px'>A fitted ETL detector must score a row without consulting other evaluation rows. Contract tests check the 17 row-level detectors; the time-window monitor has a different contract.</p>"),
    D(704, 236, 512, None, "", "<div class='cond' style='font-size:28px;font-weight:600;color:var(--ember)'>ECOD and COPOD</div><p style='font-size:18px;margin:6px 0 20px'>PyOD 3.6.7 recomputes tails and skew with the evaluated batch. Here ranks and skew signs are frozen from training.</p>"
        "<div class='cond' style='font-size:28px;font-weight:600;color:var(--ember)'>Copula motivation versus score</div><p style='font-size:18px;margin:6px 0 20px'>COPOD adds marginal contributions: it is not a fitted general joint copula. ECOD takes the max of both log tails and the skew term.</p>"
        "<div class='cond' style='font-size:28px;font-weight:600;color:var(--ember)'>Neural scoring</div><p style='font-size:18px;margin:6px 0 0'>VAE decodes the latent mean; DIF reuses a training scaler; AE1SVM padding reweights its last row. These are algorithm changes.</p>"),
    D(64, 470, 560, None, "", "<div class='k'>Evidence boundary</div><p style='font-size:20px;margin-top:8px'>Bounded tests support batch independence, not universal equivalence. Separate ablations remain open; historical results keep their actual adapted configurations.</p>"),
    D(64, 678, 1152, None, "src", "paper/main.tex, Classical and deep detectors &nbsp;·&nbsp; PyOD 3.6.7 &nbsp;·&nbsp; paired adaptation ablations remain open"),
]))

# ---------------------------------------------------------------- 12 exploratory correction
slide("Exploratory correction", "".join([
    D(64, 48, 800, None, "k", "Exploratory correction &nbsp;<span class='ember'>· not a replacement of archived results</span>"),
    D(64, 80, 1152, None, "", "<h2 style='font-size:48px'>Historical pool preparation needs revalidation</h2>"),
    D(64, 200, 560, None, "", "<div class='cond' style='font-size:30px;font-weight:700'>Historical path</div><div class='hair' style='margin:10px 0 14px;position:relative'></div>"
        "<p style='font-size:19px'>Column filtering, category vocabulary and conflicting-label removal happen <b>before</b> the split. Training-only medians and scaling do not isolate those earlier decisions.</p>"
        "<p style='font-size:19px;margin-top:14px'>Constructed negative controls: changing only the evaluation categories changes the encoded width from 5 to 3; an evaluation duplicate's label can remove a reference row. The effect on AP is not yet quantified.</p>"),
    D(664, 200, 552, None, "", "<div class='cond' style='font-size:30px;font-weight:700;color:var(--ember)'>pool-train-only-v1</div><div class='hair' style='margin:10px 0 14px;position:relative'></div>"
        "<p style='font-size:19px'>Consumes source-bound frozen positions. Fitted schema, imputation and scaling use training rows only. Cross-partition duplicates are rejected; evaluation rows are retained. Targets are excluded from preparation.</p>"
        "<p style='font-size:19px;margin-top:14px'>Bounded checks enforce full line and branch coverage for the two new modules and detect three leakage defects.</p>"),
    D(64, 520, 1152, 1, "hair"),
    D(64, 536, 1152, None, "", "<div class='k ember'>Still outstanding</div><p style='font-size:20px;margin-top:8px'>Historical memberships were recomputed (not originally archived) and replay-validated: the Z-score reproduces all 100 archived per-seed results. <b>Replaying the studies on the train-only path remains outstanding.</b> Old protocols and results are preserved, and no corrected pool-performance claim is available.</p>"),
    D(64, 678, 1152, None, "src", "research/pool_preprocessing.py &nbsp;·&nbsp; pool_train_only.py &nbsp;·&nbsp; exploratory path"),
]))


# ---------------------------------------------------------------- parts 2 and 3 share this namespace
for _part in ("deck_part2.py", "deck_part3.py"):
    exec(compile((HERE / _part).read_text(), _part, "exec"))

if __name__ == "__main__":
    assemble()
