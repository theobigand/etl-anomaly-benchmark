LEG_BEST = "<div class='legend'><span class='sw hot'></span>best of column</div>"


def opener(num, title, sub, pos, size):
    return "".join([
        photo(0, 0, 1280, 720, pos, size),
        D(0, 0, 1280, 720, "scrim", "", "background:linear-gradient(90deg,rgba(10,10,10,.9) 0%,rgba(10,10,10,.72) 55%,rgba(10,10,10,.2) 100%)"),
        D(64, 56, 600, None, "k", f"Part {num}"),
        D(64, 250, 900, None, "", f"<h1 style='font-size:96px;line-height:.98'>{title}</h1>"),
        D(64, 520, 640, None, "", f"<p class='lede' style='color:var(--paper-soft)'>{sub}</p>"),
    ])


# ---------------------------------------------------------------- opener: examples and types
slide("Part 2", opener("2 of 4", "What the detectors <span class='ember'>actually find</span>", "Three example datasets, then six anomaly types on a controlled generator and on real tables.", "0% 85%", "175%"))

# ---------------------------------------------------------------- 13 three examples
slide("Three examples", "".join([
    D(64, 48, 700, None, "k", "Three examples, one synthetic set"),
    D(64, 80, 1100, None, "", "<h2 style='font-size:48px'>Three example datasets bracket the method</h2>"),
    D(64, 172, 780, None, "sheet", tbl(["Dataset", "Rows", "Feat.", "Anom.", "Role"], [
        ["Credit Card Fraud", "283,726", "30", "0.17%", "rare, but a mixed-defect label"],
        ["Cardio", "1,831", "21", "9.6%", "rare and outlying, the fitting regime"],
        ["Water Quality", "3,276", "9", "61%", "target class common, wrong regime"],
        ["Synthetic per-type", "12,360", "9", "17.5%", "controlled, 6 labelled types"],
    ], text_cols=(4,)), "padding:8px 10px"),
    D(64, 436, 780, None, "", "<p style='font-size:20px'>Stratified 70 / 15 / 15 split, fit on train, every number reported on the held-out test set. Five seeds, mean &plusmn; std. The ML contamination is read from the train-set prevalence, not fixed at 10%.</p>"),
    D(64, 560, 780, None, "note", "LOF and One-Class SVM run everywhere except Credit Card Fraud, where neither scales to 284k rows in the pipeline."),
    D(880, 172, 336, None, "stat", "<span class='num ember' style='font-size:66px'>0.01&rarr;0.20</span><span class='lab'>Isolation Forest fraud precision, from the contamination change alone</span>", "font-size:1px"),
    D(64, 678, 1152, None, "src", "src/etl_benchmark/datasets.py &nbsp;·&nbsp; config.BENCHMARK_SEEDS &nbsp;·&nbsp; data/*.csv gitignored"),
]), tone="bone")

# ---------------------------------------------------------------- 14 injection
inj = [
    ["missing value", "1 to 2 of {income, balance, avg amount, tenure, n txn, email, country} set to null"],
    ["duplicate", "exact copy of a sampled clean row, id included (appended, not replaced)"],
    ["univariate", "one numeric column &times; U(15, 45) &times; severity"],
    ["multivariate", "marginals at the (1 &minus; 0.03 / severity) percentile of the clean data"],
    ["temporal drift", "signup in the last 80 days; income &times; (1 + 0.55 &middot; severity), similar for balance and amount"],
    ["invalid format", "email malformed; age impossible; country out of domain"],
]
slide("Injection", "".join([
    D(64, 48, 700, None, "k", "How each type is injected"),
    D(64, 80, 1152, None, "", "<h2 style='font-size:46px'>The magnitudes are a swept parameter, not a fixed choice</h2>"),
    D(64, 232, 1152, None, "sheet", tbl(["Type", "Injection"], inj, text_cols=(1,)), "padding:8px 10px"),
    D(64, 556, 1152, None, "", "<p style='font-size:20px;max-width:1000px'>Severity 1.0 is the reference dataset. Missing values, duplicates and invalid formats have no magnitude to scale. Five types replace clean rows; duplicates are appended. Sweeping the multiplier turns &quot;we picked the magnitudes&quot; into a curve, and the per-type ranking does not change (severity slide).</p>"),
    D(64, 678, 1152, None, "src", "src/etl_benchmark/synthetic.py &nbsp;·&nbsp; seed-reproducible, tested"),
]), tone="bone")

# ---------------------------------------------------------------- 15 pivot
slide("The pivot", "".join([
    D(64, 56, 700, None, "k", "The pivot"),
    D(64, 150, 1100, None, "", "<h1 style='font-size:112px;line-height:.96'>Aggregate scores do not establish equivalence.</h1>"),
    D(64, 470, 760, None, "", "<p class='lede' style='font-size:34px;font-family:var(--cond);font-weight:500;color:var(--ember)'>Per-type results show different competencies.</p>"),
    D(64, 600, 900, None, "note", "F1 spans 0.22 to 0.59 over the seventeen detectors on the synthetic set, and the per-type competences barely overlap."),
]))

# ---------------------------------------------------------------- 16 fraud
slide("Credit card fraud", "".join([
    D(64, 48, 700, None, "k", "Real fraud data"),
    D(64, 80, 1100, None, "", "<h2 style='font-size:48px'>The operating point decides the outcome</h2>"),
    D(64, 172, 780, None, "sheet", tbl(["Detector", "Prec", "Rec", "F1", "ROC", "PR", "Flag %", "Time"], [
        ["Z-score", "0.011", "0.870", "0.021", "0.926", "0.078", "13.4", "0.03 s"],
        ["IQR", "0.003", "0.966", "0.007", "0.911", "0.018", "48.6", "0.12 s"],
        ["Great Expectations", "0.037", "0.676", "0.070", "0.830", "0.182", "3.1", "1.37 s"],
        ["Isolation Forest", "0.202", "0.206", "0.203", "0.934", "0.120", "0.2", "1.78 s"],
    ], hot={(3, 1), (1, 2), (3, 3), (3, 4), (2, 5)}), "padding:8px 10px"),
    D(64, 420, 780, None, "", LEG_BEST),
    D(64, 454, 780, None, "", "<p style='font-size:20px'>The statistical rules recover most frauds at precision below 0.04. Isolation Forest changes once its contamination matches the prevalence: it flags 0.17% of rows and reaches the first usable precision, at recall 0.21 and with real seed variance (F1 = 0.20 &plusmn; 0.07). Great Expectations leads AP.</p>"),
    D(904, 172, 312, None, "stat", "<span class='num ember'>0.20</span><span class='lab'>Isolation Forest precision (0.01 at contamination 0.10)</span>"),
    D(904, 372, 312, None, "stat", "<span class='num'>0.182</span><span class='lab'>Great Expectations AP, the best on this dataset</span>"),
    D(64, 640, 1152, None, "note", "Mean over 5 seeds, 15% held-out test split. LOF and One-Class SVM do not scale to 284k rows here."),
    D(64, 678, 1152, None, "src", "experiments/run_benchmark.py &nbsp;·&nbsp; make benchmark &nbsp;·&nbsp; the metric that matters here: AP"),
]), tone="bone")

# ---------------------------------------------------------------- 17 cardio
slide("Cardio", "".join([
    D(64, 48, 700, None, "k", "Genuinely imbalanced real data"),
    D(64, 80, 1152, None, "", "<h2 style='font-size:46px'>When anomalies are rare and outlying, the learned detectors work</h2>"),
    D(64, 214, 780, None, "sheet", tbl(["Detector", "Prec", "Rec", "F1", "ROC", "PR", "Flag %"], [
        ["Z-score", "0.49", "0.82", "0.61", "0.93", "0.61", "16.6"],
        ["IQR", "0.21", "0.90", "0.34", "0.78", "0.30", "43.4"],
        ["Great Expectations", "0.51", "0.21", "0.29", "0.59", "0.19", "4.6"],
        ["Isolation Forest", "0.64", "0.62", "0.62", "0.95", "0.70", "9.9"],
        ["LOF", "0.25", "0.27", "0.26", "0.62", "0.24", "10.7"],
        ["One-Class SVM", "0.56", "0.61", "0.58", "0.94", "0.63", "10.7"],
    ], hot={(3, 1), (1, 2), (3, 3), (3, 4), (3, 5)}, compact=True), "padding:4px 10px"),
    D(64, 482, 780, None, "", LEG_BEST),
    D(64, 512, 780, None, "", "<p style='font-size:19px'>Isolation Forest reaches F1 0.62 and AP 0.70, with ECOD, COPOD and DIF close behind (AP 0.69, 0.69, 0.67). Z-score also does well: the 21 features are standardized and anomalies stand out on several at once.</p>"),
    D(904, 214, 312, None, "stat", "<span class='num ember'>0.62</span><span class='lab'>Isolation Forest F1</span>"),
    D(904, 384, 312, None, "stat", "<span class='num ember'>0.70</span><span class='lab'>Isolation Forest AP</span>"),
    D(64, 646, 1152, None, "note", "Cardiotocography, 1,831 rows, 9.6% anomalies. Mean over 5 seeds, test split. Wide seed spread on this small set (ML F1 std up to 0.17)."),
    D(64, 678, 1152, None, "src", "make benchmark-cardio &nbsp;·&nbsp; the regime the detectors are built for"),
]), tone="bone")

# ---------------------------------------------------------------- 18 synthetic aggregate
slide("Synthetic aggregate", "".join([
    D(64, 36, 700, None, "k", "Synthetic dataset, aggregate"),
    D(64, 62, 1152, None, "", "<h2 style='font-size:42px'>Aggregate scores hide different trade-offs</h2>"),
    D(64, 124, 700, None, "sheet", tbl(["Detector", "Prec", "Rec", "F1", "ROC", "PR"], [
        "rules and classical",
        ["Z-score", "1.000", "0.196", "0.328", "0.742", "0.544"],
        ["IQR", "0.584", "0.396", "0.472", "0.675", "0.452"],
        ["Isolation Forest", "0.495", "0.499", "0.497", "0.735", "0.485"],
        ["One-Class SVM", "0.478", "0.485", "0.481", "0.722", "0.520"],
        ["ECOD", "0.341", "0.341", "0.341", "0.675", "0.283"],
        ["HBOS", "1.000", "0.204", "0.339", "0.602", "0.343"],
        ["KNN", "0.466", "0.469", "0.467", "0.745", "0.520"],
        "neural",
        ["VAE", "0.502", "0.507", "0.504", "0.742", "0.548"],
        ["DIF", "0.589", "0.582", "0.585", "0.772", "0.648"],
        ["LUNAR", "0.345", "0.668", "0.410", "0.728", "0.495"],
    ], hot={(1, 1), (5, 1), (10, 3), (10, 4), (10, 5), (11, 2)}, compact=True), "padding:2px 10px"),
    D(64, 640, 700, None, "", LEG_BEST),
    D(800, 124, 416, None, "", "<p style='font-size:22px;line-height:1.38'>Z-score and HBOS reach a perfect precision by firing only on extreme rows (recall 0.20). DIF has the best F1 and AP, the VAE matches Isolation Forest, LUNAR has the best recall with a low precision.</p>"),
    D(800, 372, 416, None, "stat", "<span class='num ember' style='font-size:60px'>0.22 to 0.59</span><span class='lab'>F1 range across the seventeen detectors</span>"),
    D(800, 520, 416, None, "note", "Mean over 5 seeds, test split. 12,360 rows, 17.5% anomalous. All 17 detectors are in the paper, table tab:synthetic. The per-type view shows the opposite."),
    D(64, 678, 1152, None, "src", "verification/evidence/full_registry &nbsp;·&nbsp; paper, tab:synthetic"),
]), tone="bone")

# ---------------------------------------------------------------- 19 per-type matrix
M = json.loads((HERE / "art/recall_matrix.json").read_text())
cols = ["missing", "duplicate", "univariate", "multivariate", "drift", "invalid"]
rows_n = M["order"]
cw, rh, x0, y0 = 84, 29, 700, 150
cells = []
for j, c in enumerate(cols):
    cells.append(f"<text x='{x0+j*cw+cw/2}' y='{y0-12}' fill='#a9a498' font-family='Avenir Next' font-size='14' text-anchor='middle'>{c}</text>")
for i, r in enumerate(rows_n):
    cells.append(f"<text x='{x0-10}' y='{y0+i*rh+rh/2+5}' fill='#ece6da' font-family='Avenir Next' font-size='15' text-anchor='end'>{r}</text>")
    for j, c in enumerate(cols):
        v = M["data"][r][c]
        a = 0.08 + 0.92 * v
        fill = f"rgba(234,162,79,{a:.2f})"
        tc = "#141516" if v > 0.3 else "#a9a498"
        cells.append(f"<rect x='{x0+j*cw+2}' y='{y0+i*rh+2}' width='{cw-4}' height='{rh-4}' fill='{fill}'><title>{r}, {c}: recall {v:.2f}</title></rect>")
        cells.append(f"<text x='{x0+j*cw+cw/2}' y='{y0+i*rh+rh/2+5}' fill='{tc}' font-family='SF Mono, Menlo, monospace' font-size='14' text-anchor='middle'>{v:.2f}</text>")
slide("Per type", "".join([
    D(64, 52, 560, None, "k", "Per type, the contribution"),
    D(64, 84, 560, None, "", "<h2 style='font-size:50px;line-height:1.03'>Each method has a narrow competence</h2>"),
    D(64, 262, 560, None, "", "<p style='font-size:20px'><b>Z-score</b> owns univariate outliers (0.93). <b>Great Expectations</b> owns missing values (1.00). <b>Deduplication</b> owns exact duplicates.</p><p style='font-size:20px;margin-top:14px'>Isolation Forest (0.89) and the One-Class SVM (0.90) are the only first-six methods with real recall on multivariate outliers; every rule stays at 0.04 or below.</p><p style='font-size:20px;margin-top:14px;color:var(--ember)'>Broad coverage needs several families, not the single best one.</p>"),
    f"<svg style='position:absolute;left:0;top:0' width='1280' height='720' viewBox='0 0 1280 720' role='img' aria-label='Mean recall of 17 detectors on six injected anomaly types, synthetic customer table'>{''.join(cells)}</svg>",
    D(64, 640, 560, None, "note", "Amber intensity is mean recall, 0 to 1."),
    D(64, 678, 1152, None, "src", "paper, Appendix C, tab:m-customer &nbsp;·&nbsp; synthetic customer table, mean recall over 5 seeds &nbsp;·&nbsp; duplicates need the transform stage"),
]))

# ---------------------------------------------------------------- 20 gamed
slide("Gaming detection rate", "".join([
    D(64, 56, 700, None, "k", "Recall and precision, per type"),
    D(64, 88, 1100, None, "", "<h1 style='font-size:76px;line-height:1.0'>Detection rate alone can be <span class='ember'>gamed</span></h1>"),
    D(64, 262, 540, None, "", "<div class='cond' style='font-size:30px;font-weight:600;color:var(--ember)'>A wide net</div><div class='num' style='font-size:110px;margin-top:6px'>0.89<span style='font-size:42px;font-weight:500'> recall</span></div><div class='num' style='font-size:110px;margin-top:6px'>~0.22<span style='font-size:42px;font-weight:500'> precision</span></div><p style='font-size:20px;margin-top:16px'>Isolation Forest and the One-Class SVM on multivariate outliers: they cast a wide net that also catches clean rows.</p>"),
    D(704, 262, 512, None, "", "<div class='cond' style='font-size:30px;font-weight:600;color:var(--steel)'>A narrow one</div><div class='num' style='font-size:110px;margin-top:6px'>1.00<span style='font-size:42px;font-weight:500'> precision</span></div><div class='num' style='font-size:110px;margin-top:6px'>0.20<span style='font-size:42px;font-weight:500'> recall</span></div><p style='font-size:20px;margin-top:16px'>Z-score fires only when it is certain: on the whole synthetic set its precision is 1.00 and its recall 0.196.</p>"),
    D(64, 640, 1152, None, "note", "Clean rows are the only negatives. Both views are needed: neither number alone ranks the detectors."),
    D(64, 678, 1152, None, "src", "paper, per-type results and tab:synthetic &nbsp;·&nbsp; synthetic customer table, 5 seeds"),
]))

# ---------------------------------------------------------------- 21 PR curves
slide("PR curves", "".join([
    D(64, 44, 700, None, "k", "Precision-recall curves"),
    D(64, 72, 1100, None, "", "<h2 style='font-size:46px'>One threshold hides the whole trade-off</h2>"),
    D(64, 150, 630, 504, "sheet", "", "overflow:hidden"),
    D(64, 150, 630, 504, "", "<img style='width:100%;height:100%;object-fit:contain' src='../paper/figures/pr_curves.png' alt='precision-recall curves per dataset'>"),
    D(740, 160, 476, None, "", "<p style='font-size:21px'>On <b>Cardio</b> the Isolation Forest and One-Class SVM curves stay high (AP 0.80, 0.76). On <b>Water Quality</b> every curve hugs the 0.61 base-rate line. On <b>Credit Card Fraud</b> two methods dominate but neither clears precision 0.4 except at negligible recall.</p>"),
    D(740, 460, 476, None, "stat", "<span class='num ember' style='font-size:72px'>0.37&rarr;0.008</span><span class='lab'>Isolation Forest fraud precision as recall goes 0.23 to 0.92</span>"),
    D(64, 678, 1152, None, "src", "experiments/run_curves.py &nbsp;·&nbsp; make curves &nbsp;·&nbsp; reading prevalence lands near the knee where one exists"),
]))

# ---------------------------------------------------------------- 22 severity
slide("Severity", "".join([
    D(64, 44, 700, None, "k", "Detection rate against injection severity"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:44px'>The per-type ranking is stable as the magnitudes scale</h2>"),
    D(64, 140, 1152, 330, "sheet", "", ""),
    D(64, 140, 1152, 330, "", "<img style='width:100%;height:100%;object-fit:contain' src='../paper/figures/severity_curves.png' alt='per-type recall against injection severity'>"),
    D(64, 500, 700, None, "", "<p style='font-size:20px'>Univariate outliers are saturated already at severity 0.5. Multivariate outliers show a threshold. Temporal drift climbs roughly linearly for the distributional detectors: the reference drift is below every method's floor, not a property of the methods. The same families lead the same columns at every severity.</p>"),
    D(820, 500, 396, None, "stat", "<span class='num ember' style='font-size:66px'>&le;0.3&rarr;0.85</span><span class='lab'>temporal-drift recall from severity 1 to 3</span>"),
    D(64, 678, 1152, None, "src", "experiments/run_severity.py &nbsp;·&nbsp; make severity &nbsp;·&nbsp; answers the &quot;we picked the magnitudes&quot; threat"),
]))

# ---------------------------------------------------------------- opener: pool
slide("Part 3", opener("3 of 4", "From three examples to <span class='ember'>a pool of 152</span>", "Real tables, pinned and checked; what holds, what fails, and what changes with time.", "0% 20%", "240%"))

# ---------------------------------------------------------------- 23 funnel (reconciled)
def box(x, y, w, h, t, s, hot=False, steel=False):
    b = "var(--ember-ink)" if hot else ("var(--steel-ink)" if steel else "var(--ink)")
    bg = "var(--ember-wash)" if hot else ("var(--steel-wash)" if steel else "transparent")
    return f"<div style='position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;border:2px solid {b};background:{bg};padding:8px 12px;overflow:hidden'><div class='num' style='font-size:40px'>{t}</div><div style='font:500 15px/1.25 var(--sans);margin-top:4px'>{s}</div></div>"


def arrow(x, y, w):
    return f"<div style='position:absolute;left:{x}px;top:{y}px;width:{w}px;height:2px;background:var(--ink)'></div>"


funnel = "".join([
    "<div class='k' style='position:absolute;left:0;top:0'>ADBench</div>",
    box(0, 26, 190, 104, "47", "tabular sets in the commit"), arrow(190, 78, 40), box(230, 26, 190, 104, "36", "kept: terms read and open", steel=True),
    "<div style='position:absolute;left:440px;top:52px;font:500 15px var(--sans);color:var(--ink-soft)'>11 excluded: no open licence or terms forbid use<br>(celeba, mammography, vowels ...)</div>",
    "<div class='k' style='position:absolute;left:0;top:150px'>UCI repository</div>",
    box(0, 178, 190, 104, "689", "catalogue entries"), arrow(190, 230, 40), box(230, 178, 190, 104, "133", "pass metadata and licence filters"), arrow(420, 230, 40), box(460, 178, 190, 104, "116", "kept after curation", steel=True),
    "<div style='position:absolute;left:670px;top:196px;font:500 15px var(--sans);color:var(--ink-soft)'>17 removed with a reason<br>(version duplicates, rule-labelled, boards)</div>",
])
slide("The pool", "".join([
    D(64, 44, 700, None, "k", "Real data at scale &nbsp;·&nbsp; issue #66"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:46px'>A pool of 152 open datasets, pinned and checked</h2>"),
    D(64, 176, 1000, 290, "", funnel),
    D(64, 478, 1152, 1, "hair"),
    D(64, 494, 330, None, "stat sm", "<span class='num'>36 + 116</span><span class='lab'>= <b>152</b> pinned datasets: ADBench kept plus UCI curated</span>"),
    D(424, 494, 360, None, "stat sm", "<span class='num'>116</span><span class='lab'>UCI tables as clean carriers for typed injection</span>"),
    D(814, 494, 402, None, "stat sm", "<span class='num ember'>36 + 64</span><span class='lab'>= <b>100</b> labelled problems; rule fixed before any detector: the rarest class is the anomaly</span>"),
    D(64, 626, 1152, None, "note", "One normalisation policy for all sets, applied in order. 19 sources appear in both lists with a different derivation. Raw data stays out of the repository; checksums, licences and reports are archived. A download check of every set runs manually and monthly."),
    D(64, 678, 1152, None, "src", "verification/dataset_pool.md &nbsp;·&nbsp; research/build_pool.py &nbsp;·&nbsp; the pool is what makes the per-type result general"),
]), tone="bone")

# ---------------------------------------------------------------- 24 whole pool
pool = [
    ["ECOD", "100", "0.240 [0.191, 0.305]", "0.656", "7.0"], ["One-Class SVM", "84", "0.240 [0.177, 0.307]", "0.670", "8.0"],
    ["HBOS", "100", "0.237 [0.176, 0.311]", "0.663", "8.0"], ["DIF", "100", "0.226 [0.173, 0.272]", "0.639", "8.0"],
    ["VAE", "100", "0.216 [0.163, 0.279]", "0.676", "7.0"], ["COPOD", "100", "0.216 [0.162, 0.314]", "0.691", "7.0"],
    ["Isolation Forest", "100", "0.215 [0.158, 0.293]", "0.677", "7.0"], ["AE1SVM", "100", "0.210 [0.172, 0.253]", "0.635", "8.0"],
    ["Autoencoder", "100", "0.205 [0.150, 0.240]", "0.631", "8.0"], ["Z-score", "100", "0.203 [0.164, 0.279]", "0.626", "9.0"],
    ["KNN", "92", "0.203 [0.172, 0.284]", "0.658", "8.0"], ["LUNAR", "100", "0.183 [0.153, 0.225]", "0.615", "10.0"],
    ["Deep SVDD", "100", "0.181 [0.147, 0.226]", "0.619", "10.0"], ["PCA", "100", "0.178 [0.152, 0.219]", "0.581", "10.0"],
    ["LOF", "92", "0.165 [0.153, 0.237]", "0.588", "10.0"], ["IQR", "100", "0.144 [0.117, 0.191]", "0.556", "12.0"],
    ["Great Expectations", "100", "0.115 [0.105, 0.123]", "0.508", "16.0"],
]
slide("Whole pool", "".join([
    D(64, 30, 700, None, "k", "The whole labelled pool &nbsp;<span class='ember'>· historical run, needs train-only replay</span>"),
    D(64, 54, 760, None, "", "<h2 style='font-size:36px;line-height:1.04'>Historical pool rankings need train-only revalidation</h2>"),
    D(64, 124, 700, None, "sheet", tbl(["Detector", "Problems", "AP median [95%]", "ROC-AUC", "Rank"], pool, compact=2), "padding:0 8px"),
    D(804, 128, 412, None, "", "<p style='font-size:19px;line-height:1.38'>Three rules, eight classical and six neural detectors, five seeds, on 36 ADBench and 64 UCI problems. The table is retained as recorded.</p>"
        "<p style='font-size:17px;line-height:1.38;margin-top:12px;color:var(--ember-ink)'>Schema and row filtering precede the split, so these descriptive rankings still need train-only replay.</p>"
        "<p style='font-size:17px;line-height:1.38;margin-top:12px'>The 100 problems come from 80 sources; a source-clustered re-analysis changes no sign (only Great Expectations is clearly below Isolation Forest). Label-rule sensitivity and unrecorded PyOD convergence diagnostics remain open.</p>"),
    D(804, 500, 190, None, "stat sm", "<span class='num'>17</span><span class='lab' style='font-size:15px'>detectors; no neural exception</span>"),
    D(1016, 500, 200, None, "stat sm", "<span class='num'>13</span><span class='lab' style='font-size:15px'>problems won by DIF, the most</span>"),
    D(804, 616, 412, None, "note", "Median over problems, sorted by AP. LOF and KNN are skipped above 50,000 training rows, One-Class SVM above 20,000; neural models fit on at most 20,000 rows."),
    D(64, 690, 1152, None, "src", "verification/full_registry.md &nbsp;·&nbsp; research/labelled_benchmark.py &nbsp;·&nbsp; labels from a rare class, not from data-quality defects"),
]), tone="bone")

# ---------------------------------------------------------------- 25 two examples
slide("Two more examples", "".join([
    D(64, 44, 700, None, "k", "Two more examples from the pool"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:46px'>Two regimes the three examples do not show</h2>"),
    D(64, 196, 780, None, "sheet", tbl(["AP", "Credit Card", "Cardio", "Annthyroid", "Mushroom"], [
        ["Z-score", "0.10", "0.61", "0.18", "0.44"], ["IQR", "0.02", "0.30", "0.61", "0.10"], ["Isolation Forest", "0.13", "0.70", "0.29", "0.63"],
        ["ECOD", "0.21", "0.69", "0.28", "0.41"], ["HBOS", "0.26", "0.58", "0.24", "0.50"], ["Autoencoder", "0.11", "0.35", "0.14", "0.68"],
        ["DIF", "0.27", "0.67", "0.23", "0.45"], ["LUNAR", "0.15", "0.33", "0.20", "0.96"],
    ], hot={(4, 1), (2, 2), (1, 3), (7, 4)}, compact=True), "padding:2px 10px"),
    D(64, 520, 780, None, "", LEG_BEST),
    D(64, 552, 780, None, "", "<p style='font-size:18px'>Chosen after the results, as illustrations, not as a test. Mean over 5 seeds, as run in the pool. All 17 detectors are in the paper.</p>"),
    D(904, 196, 312, None, "stat", "<span class='num ember'>0.61</span><span class='lab'>IQR rule on Annthyroid (best learned model 0.31)</span>"),
    D(904, 392, 312, None, "stat", "<span class='num ember'>0.96</span><span class='lab'>LUNAR on Mushroom, where the IQR rule is at chance (0.10); label derived by a rule</span>"),
    D(64, 678, 1152, None, "src", "verification/full_registry_results.md &nbsp;·&nbsp; no universal detector, even at the scale of one dataset"),
]), tone="bone")

# ---------------------------------------------------------------- 26 typed on real tables
slide("Typed real tables", "".join([
    D(64, 44, 700, None, "k", "The six types on real tables &nbsp;·&nbsp; issue #65"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:44px'>The synthetic pattern does not simply carry over</h2>"),
    D(64, 144, 500, 520, "sheet", "", ""),
    D(64, 144, 500, 520, "", "<img style='width:100%;height:100%;object-fit:contain' src='../paper/figures/typed_pooled.png' alt='median detection rate per method and anomaly type over 42 real datasets'>"),
    D(620, 160, 596, None, "", "<p style='font-size:21px'>Six anomaly types injected into 42 real UCI tables (3% of rows per type, same split and settings as the synthetic run). Protocol and five hypotheses were written first. <b>Two rows hold everywhere:</b> Great Expectations finds all missing values, deduplication all duplicates. <b>Three hypotheses are not supported.</b></p>"),
    D(620, 456, 280, None, "stat sm", "<span class='num ember'>0.37</span><span class='lab' style='font-size:15px'>Isolation Forest, multivariate (0.89 synthetic)</span>"),
    D(930, 456, 286, None, "stat sm", "<span class='num ember'>24%</span><span class='lab' style='font-size:15px'>median clean rows flagged by LUNAR</span>"),
    D(620, 610, 596, None, "note", "Median over 42 UCI tables; injected, not natural. LUNAR is best on multivariate (0.63) and drift (0.78)."),
    D(64, 678, 1152, None, "src", "research/ typed benchmark &nbsp;·&nbsp; verification/typed_injection.md"),
]))

# ---------------------------------------------------------------- 27 explained failures
slide("Explained failures", "".join([
    D(64, 52, 700, None, "k", "Reading the typed result"),
    D(64, 84, 1152, None, "", "<h2 style='font-size:48px'>Two failures that are explained, not hidden</h2>"),
    D(64, 196, 560, None, "", "<div class='num ember' style='font-size:96px'>0.00</div><div class='cond' style='font-size:28px;font-weight:600;margin-top:8px'>Z-score, univariate outliers</div><p style='font-size:19px;margin-top:10px'>Median 0.00 against 0.93 synthetic. A check made after seeing it, so exploratory: invalid rows in the training split inflate the standard deviation (<b>masking</b>). Without them the Z-score finds every univariate outlier on all 42 tables.</p>"),
    D(664, 196, 552, None, "", "<div class='num ember' style='font-size:96px'>22%</div><div class='cond' style='font-size:28px;font-weight:600;margin-top:8px'>clean rows flagged by IQR</div><p style='font-size:19px;margin-top:10px'>The IQR fences reach the best detection rate on several types, but only by flagging a median 22% of clean rows; the false positive rate reaches 99% on some wide tables. Detection rate has to be read next to it.</p>"),
    D(64, 520, 1152, 1, "hair"),
    D(64, 540, 360, None, "stat sm", "<span class='num'>0.83</span><span class='lab' style='font-size:15px'>mean rank correlation between two tables (0.70 for drift, partly mechanical)</span>"),
    D(464, 540, 360, None, "stat sm", "<span class='num'>&minus;0.96</span><span class='lab' style='font-size:15px'>Isolation Forest univariate detection against the number of columns</span>"),
    D(864, 540, 352, None, "note", "Injected anomalies, one severity. Deep rows are added on a later slide."),
    D(64, 678, 1152, None, "src", "verification/typed_injection.md &nbsp;·&nbsp; non-robust statistics on a contaminated training set, not a weakness of the Z-score as such"),
]))

# ---------------------------------------------------------------- 28 chronological
slide("Chronological", "".join([
    D(64, 44, 700, None, "k", "Chronological split"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:44px'>Time changes the answer: a threshold from training does not travel</h2>"),
    D(64, 220, 700, None, "sheet", tbl(["Detector", "PR strat.", "PR chrono", "ROC chrono", "Flag %"], [
        ["Z-score", "0.078", "0.048", "0.935", "12.8"], ["IQR", "0.018", "0.013", "0.917", "47.1"],
        ["Great Expectations", "0.183", "0.045", "0.758", "3.5"], ["Isolation Forest", "0.110", "0.035", "0.936", "0.08"],
    ], ), "padding:8px 10px"),
    D(64, 436, 700, None, "note", "Average precision on the test split; the paper gives a 95% block-bootstrap interval for the chronological arm. The window monitor detects mean shifts of 1 and 2 standard deviations, not 0.5."),
    D(804, 220, 412, None, "", "<p style='font-size:20px'>Credit Card is the only dataset with a clock. Detectors are fitted on the first 70% of time and scored on the last 15% (52 frauds). Average precision drops for all four detectors, but the interval excludes the stratified mean only for Great Expectations and Isolation Forest.</p><p style='font-size:19px;margin-top:12px;color:var(--ember-ink)'>Prevalence also changes between partitions, so the pilot does not separate it from the effect of time.</p>"),
    D(64, 520, 330, None, "stat", "<span class='num'>0.936</span><span class='lab'>Isolation Forest ROC-AUC, chronological</span>"),
    D(434, 520, 330, None, "stat", "<span class='num ember'>0.08%</span><span class='lab'>future rows it flags: none of the 52 frauds</span>"),
    D(64, 678, 1152, None, "src", "verification/temporal_pilot.md &nbsp;·&nbsp; one two-day dataset: a direction, not a rule"),
]), tone="bone")

# ---------------------------------------------------------------- 29 prevalence
slide("Decisions under shift", "".join([
    D(64, 44, 700, None, "k", "Decisions under shift &nbsp;·&nbsp; issue #63"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:46px'>Part of the gap is only the prevalence</h2>"),
    D(64, 170, 700, None, "sheet", tbl(["F1 at the threshold", "P0 training", "P2 rolling"], [
        ["Bank, Z-score", "0.51", "0.02"], ["Bank, Isolation Forest", "0.41", "0.11"],
        ["Credit Card, Z-score", "0.00", "0.09"], ["Credit Card, Great Expectations", "0.00", "0.09"],
    ]), "padding:8px 10px"),
    D(64, 400, 700, None, "note", "Test period, threshold at the training prevalence. Rank correlation of the detector order, stratified against chronological: 0.80 on Bank Marketing, 0.40 on Credit Card. Kyoto-2006+ left out: rights and download not verified."),
    D(804, 170, 412, None, "", "<p style='font-size:20px'>Credit Card and Bank Marketing (UCI, ordered by date 2008 to 2010), four detectors, three label-free thresholds. On Bank Marketing the prevalence goes from <b>5.8%</b> in training to <b>39.3%</b> in test: matching the stratified control to it removes most of the gap. A rolling threshold that keeps the training prevalence cannot follow it.</p><p style='font-size:19px;margin-top:12px'>One hypothesis of four holds.</p>"),
    D(64, 500, 330, None, "stat", "<span class='num ember'>0.26&rarr;0.06</span><span class='lab'>median AP gap on Bank Marketing after prevalence matching</span>"),
    D(64, 678, 1152, None, "src", "verification/temporal_decision.md &nbsp;·&nbsp; research/temporal_decision.py &nbsp;·&nbsp; Credit Card results were known before the protocol"),
]), tone="bone")

# ---------------------------------------------------------------- 30 alert budget
slide("Alert budget", "".join([
    D(64, 40, 900, None, "k", "Exploratory deployment thresholds, issue #94 &nbsp;<span class='ember'>· exploratory, one machine</span>"),
    D(64, 68, 1152, None, "", "<h2 style='font-size:44px'>A nominal alert budget is not a promise</h2>"),
    D(64, 138, 700, None, "sheet", tbl(["Change at a 2% budget", "&Delta; alert / budget [95%]", "&Delta; ROC-AUC"], [
        ["Evaluated scores shifted +1 &sigma;", "+4.09 [3.50, 4.77]", "0.000"], ["Evaluated scores scaled &times;2", "+4.86 [4.57, 5.19]", "0.000"],
        ["Noise of 1 &sigma; on the scores", "+1.55 [1.32, 1.81]", "&minus;0.038"], ["Every feature drifted &frac12; &sigma;", "+20.90 [17.39, 24.55]", "&minus;0.051"],
        ["Monotone change of fit and test scores", "+0.001 [0.000, 0.003]", "0.000"],
    ], compact=True), "padding:3px 10px"),
    D(64, 456, 700, None, "note", "Five classical detectors, 98 problems from 78 sources, sources resampled whole, Holm-adjusted. Prevalence reweighted under a label-shift assumption: 0.83 to 1.83 times the budget at 0.5% prevalence, 1.15 to 2.73 times at 20%."),
    D(804, 138, 412, None, "", "<p style='font-size:20px'>Budgets of 0.5 to 10% are set from training scores only, on 100 labelled problems. Held-out alert volume was <b>1.05 to 1.36</b> times the nominal 1% budget for classical detectors and <b>1.13 to 2.87</b> times for neural ones.</p>"),
    D(804, 360, 412, None, "stat", "<span class='num ember'>+4.1</span><span class='lab'>budgets of added alert volume at 2% (about 5 times nominal) for a 1 &sigma; score shift; ROC-AUC unchanged</span>"),
    D(64, 560, 700, None, "note", "The 30-expected-alert rule for monitoring was chosen after the false alarms were seen. Not promoted to the main tables."),
    D(64, 678, 1152, None, "src", "docs/thesis-remediation/SCORE_SHIFT_T170_T171_2026-11-11.md &nbsp;·&nbsp; research/score_shift.py"),
]), tone="bone")

# ---------------------------------------------------------------- 31 deeper studies
hyp = [
    ["P1", "label-free threshold lowers F1", "holds", "14 of 17 detectors"],
    ["P2", "curve ranking = AP ranking", "fails", "Spearman 0.90 (&lt; 0.99)"],
    ["P3", "recall rises with severity", "fails", "13 of 17; column-wise rules stay at 0"],
    ["P4", "detection share of the pipeline", "holds", "62% (IF), 4% (Z-score), 14 datasets"],
    ["P5", "chronological AP lower", "fails", "31 of 64 pairs; Bank Marketing 0/16"],
    ["P6", "files match the manifest", "holds", "152 of 152"],
]
slide("Deeper studies", "".join([
    D(64, 44, 700, None, "k", "Every study on the whole pool"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:46px'>The deeper studies, run on all 152 datasets</h2>"),
    D(64, 168, 780, None, "sheet", tbl(["", "Hypothesis", "Result", "Value"], [[a, b, f"<b>{c}</b>", d] for a, b, c, d in hyp],
        hot={(1, 2), (2, 2), (4, 2)}, cool={(0, 2), (3, 2), (5, 2)}, text_cols=(1, 3)), "padding:8px 10px"),
    D(64, 456, 780, None, "", "<div class='legend'><span class='sw cool'></span>holds &nbsp;&nbsp; <span class='sw hot'></span>fails, reported as failed</div>"),
    D(64, 492, 780, None, "note", "Chronology needs a real time variable: 5 labelled datasets qualify (ADBench has none). Each study ran on every dataset where it is defined; the others are listed with a reason, never silently."),
    D(904, 168, 312, None, "stat", "<span class='num' style='font-size:68px'>58 / 152</span><span class='lab'>tables eligible for typed injection and severity</span>"),
    D(904, 330, 312, None, "stat", "<span class='num' style='font-size:68px'>290 / 304</span><span class='lab'>end-to-end pipeline runs that completed</span>"),
    D(64, 678, 1152, None, "src", "verification/pool_extension_results.md &nbsp;·&nbsp; six hypotheses written first: three hold, three do not"),
]), tone="bone")

# ---------------------------------------------------------------- 32 LSTM
slide("LSTM", "".join([
    D(64, 52, 700, None, "k", "First deep model &nbsp;·&nbsp; issue #52"),
    D(64, 84, 1152, None, "", "<h2 style='font-size:48px'>An LSTM autoencoder is comparable, not clearly better</h2>"),
    D(64, 236, 360, None, "stat", "<span class='num ember'>0.875</span><span class='lab'>LSTM AP on the synthetic stream with broken continuity (row autoencoder 0.006)</span>"),
    D(464, 236, 360, None, "stat", "<span class='num'>0.037</span><span class='lab'>LSTM AP on real Credit Card frauds (row autoencoder 0.024)</span>"),
    D(864, 236, 352, None, "", "<p style='font-size:19px'>Against Isolation Forest (0.035) and Great Expectations (0.045) it is <b>comparable</b>. Paired bootstrap, main seed: +0.021 [+0.005, +0.044]; on the other four seeds the interval includes 0.</p>"),
    D(64, 470, 1152, 1, "hair"),
    D(64, 488, 560, None, "", "<p style='font-size:20px'>The window is the ten previous rows of the global stream, since Credit Card has no cardholder. Protocol and a CPU budget of 20 epochs were fixed beforehand.</p>"),
    D(664, 488, 552, None, "", "<p style='font-size:20px;color:var(--ember)'>None of five trainings converged within the 20-epoch budget. Recall of frauds in the later period is at most 0.02. In the per-type matrix the LSTM does not fix drift.</p>"),
    D(64, 678, 1152, None, "src", "verification/lstm_pilot.md &nbsp;·&nbsp; research/lstm_pilot.py &nbsp;·&nbsp; an indication from a budget-limited pilot, not a ranking"),
]))

# ---------------------------------------------------------------- 33 two schemas (claim now visible in the table)
slide("Two schemas", "".join([
    D(64, 44, 700, None, "k", "Two more schemas &nbsp;·&nbsp; issue #67"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:46px'>The profile carries over, the values do not</h2>"),
    D(64, 196, 780, None, "sheet", tbl(["Mean recall, 5 seeds", "customers", "transactions", "sensors"], [
        "carries over exactly",
        ["Great Expectations, missing values", "1.00", "1.00", "1.00"],
        "does not carry over",
        ["Isolation Forest, multivariate", "0.89", "0.49", "0.32"],
        ["One-Class SVM, multivariate", "0.90", "0.18", "0.33"],
        ["best detector, drift", "0.50", "0.38", "0.96"],
    ], cool={(1, 1), (1, 2), (1, 3)}, hot={(3, 2), (3, 3), (4, 2), (4, 3), (5, 3)}), "padding:6px 10px"),
    D(64, 520, 780, None, "", "<div class='legend'><span class='sw cool'></span>identical on all three &nbsp;&nbsp; <span class='sw hot'></span>depends on the schema</div>"),
    D(64, 552, 780, None, "note", "Transactions and sensor readings get the same six types and the same protocol as the customer table. Same generator logic for all three: the agreement shows the profile does not depend on one table, not that it holds on real data. The drift detector flags nothing on any schema."),
    D(904, 196, 312, None, "stat", "<span class='num ember'>0.93</span><span class='lab'>mean rank correlation between schemas, first six detectors (0.89 with all seventeen)</span>"),
    D(904, 392, 312, None, "note", "Two of four hypotheses hold: the structural rows and the rank stability. Drift and multivariate values depend on how columns are scaled and correlated."),
    D(64, 678, 1152, None, "src", "verification/multi_schema.md &nbsp;·&nbsp; research/multi_schema.py &nbsp;·&nbsp; paper, Section RQ2 transfer"),
]), tone="bone")

# ---------------------------------------------------------------- 34 full registry
slide("Full registry", "".join([
    D(64, 36, 700, None, "k", "Every detector in the per-type matrix"),
    D(64, 62, 1152, None, "", "<h2 style='font-size:42px'>More detectors, same competence map, one exception</h2>"),
    D(64, 128, 520, 540, "sheet", "", ""),
    D(64, 128, 520, 540, "", "<img style='width:100%;height:100%;object-fit:contain' src='../paper/figures/heatmap_full.png' alt='per-type recall of every detector of the registry and the LSTM autoencoder'>"),
    D(640, 134, 576, None, "", "<p style='font-size:21px'>Eleven rows added to the synthetic matrix, with three hypotheses written beforehand; <b>none holds</b>. ECOD and COPOD find 0.5 of the multivariate outliers although they read one column at a time; PCA reaches 0.48 against 0.83 for the autoencoder.</p><p style='font-size:21px;margin-top:12px'>LUNAR catches 0.65 of the drifted rows (LOF 0.50) while flagging 41% of clean rows. The LSTM still does not fix drift.</p>"),
    D(640, 470, 280, None, "stat sm", "<span class='num ember'>0.65</span><span class='lab' style='font-size:15px'>LUNAR drift recall, 41% clean flagged</span>"),
    D(950, 470, 266, None, "stat sm", "<span class='num'>1.00</span><span class='lab' style='font-size:15px'>DIF recall on multivariate</span>"),
    D(640, 610, 576, None, "note", "Synthetic customers are independent rows: drift is not a sequence here."),
    D(64, 678, 1152, None, "src", "verification/full_registry.md &nbsp;·&nbsp; research/full_registry.py"),
]))

# ---------------------------------------------------------------- 35 cost
slide("Cost", "".join([
    D(64, 36, 700, None, "k", "What detection costs &nbsp;·&nbsp; issue #53"),
    D(64, 62, 1152, None, "", "<h2 style='font-size:42px'>Detection latency is not pipeline latency</h2>"),
    D(64, 128, 720, None, "sheet", tbl(["Detector", "10k rows", "100k rows", "300k rows", "Memory MB"], [
        ["Z-score", "0.002 s", "0.013 s", "0.039 s", "70"], ["IQR", "0.004 s", "0.029 s", "0.086 s", "116"],
        ["Isolation Forest", "0.16 s", "1.09 s", "3.2 s", "140"], ["LOF", "0.73 s", "18.0 s", "133 s", "405"],
        ["One-Class SVM", "5.6 s", "&gt;300 s", "not run", "788"], ["ECOD / COPOD", "0.045 s", "0.68 s", "2.4 s", "186"],
        ["KNN", "0.45 s", "11 s", "68 s", "148"], ["VAE", "6.8 s", "69 s", "209 s", "105"], ["DIF", "23 s", "262 s", "&gt;300 s", "2,748"],
    ], hot={(3, 3), (4, 2), (7, 3), (8, 2), (8, 3)}, compact=True), "padding:3px 10px"),
    D(64, 500, 720, None, "", "<div class='legend'><span class='sw hot'></span>100 s or more</div>"),
    D(64, 532, 720, None, "note", "Median detection-stage time, 8 features; synthetic matrices from 1,000 to 300,000 rows, a fresh process per measurement so peak memory belongs to that run, 300 s budget. Five of the ten newer detectors shown; the paper has all. Single machine, not isolated, not a general ranking."),
    D(824, 128, 392, None, "", "<p style='font-size:20px'>On the full Credit Card file the Z-score pipeline takes <b>4.8 s</b>, of which detection is 3%. Isolation Forest takes <b>8.5 s</b>, with detection at 43 to 45%.</p>"),
    D(824, 290, 392, None, "stat", "<span class='num ember'>133 s</span><span class='lab'>LOF at 300,000 rows (exponent 1.51)</span>"),
    D(824, 446, 392, None, "stat", "<span class='num ember'>&gt;300 s</span><span class='lab'>One-Class SVM at 100,000 rows</span>"),
    D(64, 678, 1152, None, "src", "verification/cost_study.md"),
]), tone="bone")

# ---------------------------------------------------------------- 36 type to method
slide("Type to method", "".join([
    D(64, 44, 700, None, "k", "The practical output"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:46px'>Anomaly type to method</h2>"),
    D(64, 150, 1152, None, "sheet", tbl(["Anomaly type", "Use", "Recall", "Why"], [
        ["missing value", "Great Expectations", "1.00", "not-null expectation, exact"],
        ["exact duplicate", "transform dedup stage", "1.00", "row equality, not a detector's job"],
        ["univariate outlier", "any statistical rule", "0.93 to 0.99", "a single-column band is enough"],
        ["multivariate outlier", "Isolation Forest or One-Class SVM", "0.89 to 0.90", "only the joint models see it (precision about 0.22)"],
        ["temporal drift", "windowed monitor", "per-row at most 0.65", "sub-threshold per row; LUNAR 0.65 flags 41% of clean rows"],
        ["invalid format", "IQR for the numeric part", "1.00 (IQR)", "numeric part caught; malformed strings need a format rule"],
    ], text_cols=(1, 3)), "padding:8px 10px"),
    D(64, 530, 1152, None, "", "<p style='font-size:22px;max-width:980px'>Two of six types are not a per-row detector problem at all: duplicates belong to the transform stage, drift to a windowed monitor. A single aggregate ranking would never surface that.</p>"),
    D(64, 678, 1152, None, "src", "paper, Section V &nbsp;·&nbsp; synthetic customer table, mean recall over 5 seeds &nbsp;·&nbsp; rules and ML are complementary, not competing"),
]), tone="bone")

# ---------------------------------------------------------------- 37 regimes
slide("Regimes", "".join([
    D(64, 52, 900, None, "k", "Across the three example datasets"),
    D(64, 84, 1152, None, "", "<h1 style='font-size:60px;line-height:1.0'>Unsupervised detection works in <span class='ember'>one of three</span> regimes</h1>"),
    D(64, 290, 360, None, "", "<div class='cond' style='font-size:34px;font-weight:700'>Fraud</div><div class='k ember' style='margin:4px 0 10px'>too extreme</div><p style='font-size:19px'>0.17% positives, and the label mixes every defect. Best F1 of seventeen detectors is 0.35 (Deep SVDD), best precision 0.34 (HBOS).</p>"),
    D(464, 290, 360, None, "", "<div class='cond' style='font-size:34px;font-weight:700'>Cardio</div><div class='k ember' style='margin:4px 0 10px'>the fit</div><p style='font-size:19px'>9.6%, rare and distinct. Isolation Forest F1 0.62, AP 0.70. The regime the detectors are built for.</p>"),
    D(864, 290, 352, None, "", "<div class='cond' style='font-size:34px;font-weight:700'>Water</div><div class='k ember' style='margin:4px 0 10px'>wrong regime</div><p style='font-size:19px'>61% majority target. Every ROC-AUC 0.45 to 0.51: the detectors are at chance. A useful negative result.</p>"),
    D(64, 520, 1152, 1, "hair"),
    D(64, 540, 1152, None, "", "<p style='font-size:20px;max-width:1000px'>The question is less &quot;rules or ML&quot; than &quot;does this dataset have rare, outlying anomalies at all&quot;. The synthetic dataset sits in the middle at 17.5% and is where the per-type structure is measured. Pipeline cost narrows the shortlist: One-Class SVM and LOF do not survive the full fraud dataset.</p>"),
    D(64, 678, 1152, None, "src", "paper, discussion"),
]))

# ---------------------------------------------------------------- 38 findings
slide("Findings", "".join([
    D(64, 44, 700, None, "k", "What was harder than the plan assumed"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:44px'>Findings from the build</h2>"),
    D(64, 138, 560, None, "", "<p style='font-size:19px'>Each of these became a paragraph in the paper. The recurring lesson: the setup around a detector, the operating point, the regime and the pipeline cost matter as much as the algorithm.</p>"),
    D(64, 262, 560, None, "", "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>The operating point is a lever</div><p style='font-size:17px;margin:4px 0 14px'>Contamination equal to prevalence instead of a fixed 10% moves Isolation Forest fraud precision from 0.01 to 0.20.</p>"
        "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>One regime out of three</div><p style='font-size:17px;margin:4px 0 14px'>Cardio F1 0.62. Fraud, mixed label: nothing usable. Water Quality: at chance.</p>"
        "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>ML is weak on missing values</div><p style='font-size:17px;margin:4px 0 0'>Imputing removes the signal a not-null rule catches for free: GX recall 1.00 against 0.07 to 0.28.</p>"),
    D(664, 140, 552, None, "", "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>GX 1.x is a full API rewrite</div><p style='font-size:17px;margin:4px 0 14px'>Per-row failures need the COMPLETE result format plus an explicit index column; found by probing the installed library.</p>"
        "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>PyOD scores can depend on the batch</div><p style='font-size:17px;margin:4px 0 14px'>ECOD, COPOD and DIF use the scored rows for their statistics, the VAE draws a random code, AE1SVM crashes on a last batch of one row. Recorded adaptations, with 17 batch-independence checks; not upstream-equivalence claims.</p>"
        "<div class='cond' style='font-size:26px;font-weight:600;color:var(--ember)'>Drift is not a per-row problem</div><p style='font-size:17px;margin:4px 0 0'>Once diluted by clean recent rows, the window mean has moved by about a tenth of a standard deviation.</p>"),
    D(64, 678, 1152, None, "src", "build notes kept per session"),
]))
