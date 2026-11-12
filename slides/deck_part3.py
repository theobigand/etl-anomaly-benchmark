# ---------------------------------------------------------------- opener: verification
slide("Part 4", "".join([
    photo(0, 0, 1280, 720, "50% 50%", "cover", "flush-plate"),
    D(0, 0, 1280, 720, "scrim", "", "background:linear-gradient(90deg,rgba(10,10,10,.9) 0%,rgba(10,10,10,.6) 50%,rgba(10,10,10,.1) 100%)"),
    D(64, 56, 600, None, "k", "Part 4 of 4"),
    D(64, 230, 900, None, "", "<h1 style='font-size:96px;line-height:.98'>What the tests <span class='ember'>protect</span>, and what they do not</h1>"),
    D(64, 540, 640, None, "", "<p class='lede' style='color:var(--paper-soft)'>Verification of the code that produces the numbers, and mutation testing as a way to see its blind spots.</p>"),
    D(64, 672, 600, None, "note", "Illustration, not data: a generated still life."),
]))

# ---------------------------------------------------------------- 39 historical verification
slide("Historical verification", "".join([
    D(64, 40, 700, None, "k", "Implemented, tested, verified &nbsp;<span class='ember'>· historical run, defined scope</span>"),
    D(64, 68, 1152, None, "", "<h2 style='font-size:44px'>Historical verification has a defined scope</h2>"),
    D(64, 144, 740, None, "sheet", tbl(["Check", "Result", "Scope"], [
        ["line coverage", "1,790 / 1,790", "pipeline modules and experiment scripts"],
        ["branch coverage", "350 / 350", "same scope"],
        ["mutation, computing code", "95.68%", "split, metrics, generator, detectors"],
        ["mutation, input / output", "98.87%", "readers, writers, scripts"],
        ["fault injection", "23 / 23", "four went through every earlier test"],
        ["real-data check", "pass", "three CSV files, manuscript tables match"],
    ], text_cols=(2,)), "padding:6px 10px"),
    D(64, 478, 740, None, "note", "Survivors (122) count as failures and were classified by reading the changes, not by proof."),
    D(844, 144, 372, None, "", "<p style='font-size:20px'>These measurements belong to local run <b>d4304c5</b>. They cover the core pipeline and experiment scripts, with separate verifier checks.</p><p style='font-size:19px;margin-top:12px;color:var(--ember-ink)'>They do not certify the new research modules or establish scientific validity. The run is not independently attested.</p>"),
    D(844, 400, 180, None, "stat sm", "<span class='num'>1,292</span><span class='lab' style='font-size:15px'>tests, plus 3 on full datasets</span>"),
    D(1040, 400, 176, None, "stat sm", "<span class='num'>97.61%</span><span class='lab' style='font-size:15px'>mutants killed, 4,980 of 5,102</span>"),
    D(64, 678, 1152, None, "src", "make verify-all &nbsp;·&nbsp; .github/workflows &nbsp;·&nbsp; main, local run sealed at d4304c5"),
]), tone="bone")

# ---------------------------------------------------------------- M1 what a mutant is
slide("Mutation: mutant", "".join([
    D(64, 52, 700, None, "k", "Mutation testing, 1 of 5"),
    D(64, 84, 1152, None, "", "<h2 style='font-size:48px'>A mutant is a deliberately broken copy of the code</h2>"),
    D(64, 232, 640, 270, "sheet", "<pre style='padding:26px 24px;font-size:22px;line-height:1.7'><span style='color:#8b887f'># research/alert_budget.py</span>\n<span class='del'>- flags = scores &gt; info[&quot;threshold&quot;]</span>\n<span class='add'>+ flags = scores &gt;= info[&quot;threshold&quot;]</span></pre>"
        "<div style='position:absolute;left:28px;top:170px;width:580px;font:400 18px/1.4 var(--sans)'>This mutant is real. If it were a bug, a score <b>equal</b> to the training threshold would raise an alert.</div>"),
    D(744, 232, 472, None, "", "<div class='cond' style='font-size:30px;font-weight:600;color:var(--ember)'>Why bother</div><p style='font-size:20px;margin-top:8px'>Coverage says a line ran. It does not say a test would notice if the line were wrong.</p>"
        "<div class='cond' style='font-size:30px;font-weight:600;color:var(--ember);margin-top:24px'>How it works</div><p style='font-size:20px;margin-top:8px'>A tool makes many such copies, one change each, and runs the test suite against every copy.</p>"),
    D(64, 596, 1152, None, "note", "No test covered this boundary before this session. A new test, &quot;a score equal to the training threshold is not an alert&quot;, now fails on the mutant."),
    D(64, 678, 1152, None, "src", "research/tests/test_alert_budget.py &nbsp;·&nbsp; mutmut 3.8.0, raw focused counts"),
]))

# ---------------------------------------------------------------- M2 killed / survived (photograph carries the idea)
slide("Mutation: killed or survived", "".join([
    photo(0, 0, 1280, 720, "50% 50%", "cover", "flush-plate"),
    D(0, 0, 1280, 190, "scrim", "", "background:linear-gradient(rgba(10,10,10,.88),rgba(10,10,10,0))"),
    D(0, 430, 1280, 290, "scrim", "", "background:linear-gradient(rgba(10,10,10,0),rgba(10,10,10,.93) 45%)"),
    D(64, 36, 700, None, "k", "Mutation testing, 2 of 5"),
    D(64, 62, 1100, None, "", "<h2 style='font-size:46px'>The tests are the light. A mutant is killed when a test sees it</h2>"),
    D(500, 178, 330, None, "", "<div class='cond' style='font-size:26px;font-weight:700;color:var(--steel)'>killed</div><div style='font:500 16px/1.3 var(--sans)'>a test fails, so the change is noticed</div>", "background:rgba(10,10,10,.78);padding:8px 12px"),
    D(583, 256, 2, 14, "", "", "background:var(--steel)"),
    D(330, 396, 340, None, "", "<div class='cond' style='font-size:26px;font-weight:700;color:var(--ember)'>survived</div><div style='font:500 16px/1.3 var(--sans)'>every test passes, so nothing noticed the change</div>", "background:rgba(10,10,10,.78);padding:8px 12px"),
    D(458, 382, 2, 14, "", "", "background:var(--ember)"),
    D(409, 289, 98, 98, "", "", "border:2px solid var(--ember);border-radius:50%"),
    D(536, 264, 100, 100, "", "", "border:2px solid var(--steel);border-radius:50%"),
    D(64, 516, 1152, None, "", "<p style='font-size:23px;max-width:1040px'>A survivor matters because it is either a <b>behaviour no test protects</b> (a gap to close with a new test), or a <b>change that cannot be observed</b> (an equivalent mutant, next slide). It stays in the count of eligible mutants (the denominator of killed / eligible) until one of the two is shown.</p>"),
    D(64, 664, 1152, None, "note", "Metaphor, not data: a generated still life. The raised pad casts a shadow; the cracked pad sits flush and casts none."),
]))

# ---------------------------------------------------------------- M3 equivalent mutants and owner approval
slide("Mutation: equivalent", "".join([
    D(64, 52, 700, None, "k", "Mutation testing, 3 of 5"),
    D(64, 84, 1152, None, "", "<h2 style='font-size:50px'>Some changes cannot be seen, and only the owner may say so</h2>"),
    D(64, 232, 540, None, "", "<div class='cond' style='font-size:30px;font-weight:600;color:var(--ember)'>Equivalent mutant</div><p style='font-size:20px;margin-top:8px'>A change that does not alter what the program does, so no test can fail on it. Example: changing <span style='font-family:var(--mono);font-size:17px'>x &gt; 0</span> to <span style='font-family:var(--mono);font-size:17px'>x &gt;= 0</span> where x can never be 0. Candidates in this work: a dtype coercion on an array that is already float, <span style='font-family:var(--mono);font-size:17px'>zip(strict=)</span> on lists of equal length, a <span style='font-family:var(--mono);font-size:17px'>flush=</span> on a print.</p>"),
    D(664, 232, 552, None, "", "<div class='cond' style='font-size:30px;font-weight:600;color:var(--ember)'>Why approval is required</div><p style='font-size:20px;margin-top:8px'>Calling a survivor equivalent removes it from the denominator and raises the score. If the author of the tests could do that alone, the author would grade their own work. The repository records each equivalence, with its reason, as accepted by the owner.</p>"),
    D(64, 470, 1152, 1, "hair"),
    D(64, 490, 1152, None, "", "<p style='font-size:21px;max-width:1000px'><b>Status here:</b> the candidates above are <b class='ember'>not approved</b> and stay in the denominator. The four equivalences accepted earlier for the LSTM autoencoder were accepted by the repository owner, who is also the sole author and reviewer: that is owner approval, not independent review.</p>"),
    D(64, 678, 1152, None, "src", "docs/thesis-remediation/MUTATION_FOCUSED_DIAGNOSTICS_2026-11-11.md"),
]))

# ---------------------------------------------------------------- M4 risk tiers
tiers = [("L4", 98, "code that produces the reported numbers"), ("L3", 95, ""), ("L2", 90, ""), ("L1", 80, "")]
lad = []
for i, (t, v, s) in enumerate(tiers):
    y = 230 + i * 92
    lad.append(D(64, y, 100, None, "", f"<span class='num {'ember' if t=='L4' else ''}' style='font-size:64px'>{t}</span>"))
    lad.append(D(190, y + 6, v * 5.0, 14, "", "", f"background:{'var(--ember)' if t=='L4' else 'var(--steel)'};opacity:{1 if t=='L4' else .55}"))
    lad.append(D(190 + v * 5.0 + 14, y - 4, 140, None, "", f"<span class='num' style='font-size:44px'>{v}%</span>"))
slide("Mutation: tiers", "".join([
    D(64, 52, 700, None, "k", "Mutation testing, 4 of 5"),
    D(64, 84, 1152, None, "", "<h2 style='font-size:50px'>The bar rises with the scientific risk of the code</h2>"),
    *lad,
    D(930, 230, 286, None, "", "<p style='font-size:19px'>Each module has a risk level, and each level a minimum share of mutants that tests must kill.</p><p style='font-size:19px;margin-top:14px'><b>L4</b>, the highest, is code whose bug would change a reported result. Its bar is <b>98%</b>.</p><p style='font-size:19px;margin-top:14px;color:var(--ember)'>The thresholds were not changed and no module was reclassified.</p>"),
    D(64, 678, 1152, None, "src", "verification/mutation_risk_policy.json &nbsp;·&nbsp; thresholds L1 80, L2 90, L3 95, L4 98"),
]))

# ---------------------------------------------------------------- M5 chart
mods = [("pool_check", 118/180, 178/180), ("alert_budget", 427/780, 766/780), ("alert_budget_summary", 0/123, 123/123),
        ("matched_alert", 247/322, 317/322), ("prevalence_shift", 265/369, 363/369), ("score_shift", 492/806, 795/806),
        ("source_clustered", 286/337, 333/337), ("normalise", 175/193, 188/197), ("paired_bootstrap", 77/100, 94/100)]
cx0, cx1, cy0, rh2 = 330, 1120, 170, 46
def X(p): return cx0 + (cx1 - cx0) * (max(p, .4) - .4) / .6
ch = []
for p, lab in [(.4, "40"), (.6, "60"), (.8, "80"), (1, "100%")]:
    ch.append(f"<line x1='{X(p)}' x2='{X(p)}' y1='{cy0-10}' y2='{cy0+rh2*9}' stroke='#15161722'/><text x='{X(p)}' y='{cy0+rh2*9+22}' fill='#55534d' font-size='14' text-anchor='middle' font-family='SF Mono, Menlo'>{lab}</text>")
for p, lab in [(.80, "L1 80"), (.90, "L2 90"), (.95, "L3 95")]:
    ch.append(f"<line x1='{X(p)}' x2='{X(p)}' y1='{cy0-10}' y2='{cy0+rh2*9}' stroke='#35505b' stroke-dasharray='3 4' opacity='.6'/><text x='{X(p)}' y='{cy0-16}' fill='#35505b' font-size='13' text-anchor='middle' font-family='SF Mono, Menlo'>{lab}</text>")
ch.append(f"<line x1='{X(.98)}' x2='{X(.98)}' y1='{cy0-10}' y2='{cy0+rh2*9}' stroke='#94490a' stroke-width='2'/><text x='{X(.98)}' y='{cy0-34}' fill='#94490a' font-size='15' font-weight='700' text-anchor='middle' font-family='SF Mono, Menlo'>L4 98%</text>")
for i, (n, b, a) in enumerate(mods):
    y = cy0 + i * rh2 + rh2 / 2
    ok = a >= .98
    col = "#35505b" if ok else "#94490a"
    ch.append(f"<text x='{cx0-14}' y='{y+5}' fill='#151617' font-size='17' text-anchor='end' font-family='SF Mono, Menlo'>{n}</text>")
    ch.append(f"<line x1='{X(b)}' x2='{X(a)}' y1='{y}' y2='{y}' stroke='{col}' stroke-width='3' opacity='.55'/>")
    ch.append(f"<circle cx='{X(b)}' cy='{y}' r='7' fill='#f4f3ee' stroke='{col}' stroke-width='2.5'><title>{n} before: {b*100:.1f}%</title></circle>")
    ch.append(f"<circle cx='{X(a)}' cy='{y}' r='7.5' fill='{col}'><title>{n} after: {a*100:.2f}%</title></circle>")
    ch.append(f"<text x='1236' y='{y+5}' fill='{col}' font-size='16' font-weight='700' text-anchor='end' font-family='SF Mono, Menlo'>{a*100:.1f}%</text>")
    if b < .4:
        ch.append(f"<text x='{X(b)+12}' y='{y-10}' fill='#55534d' font-size='13' font-family='SF Mono, Menlo'>before: 0% (axis cut at 40)</text>")
slide("Mutation: chart", "".join([
    D(64, 34, 700, None, "k", "Mutation testing, 5 of 5 &nbsp;·&nbsp; raw focused score per module"),
    D(64, 60, 1152, None, "", "<h2 style='font-size:40px'>Nine chosen modules: seven reach the 98% bar, two do not</h2>"),
    f"<svg style='position:absolute;left:0;top:0' width='1280' height='720' viewBox='0 0 1280 720' role='img' aria-label='Raw focused mutation score per module before and after new tests'>{''.join(ch)}</svg>",
    D(64, 618, 760, None, "legend", "<svg width='16' height='16' style='vertical-align:-3px'><circle cx='8' cy='8' r='6' fill='#f4f3ee' stroke='#35505b' stroke-width='2.5'/></svg> before &nbsp; <svg width='16' height='16' style='vertical-align:-3px'><circle cx='8' cy='8' r='7' fill='#35505b'/></svg> after, at or above 98% &nbsp; <svg width='16' height='16' style='vertical-align:-3px'><circle cx='8' cy='8' r='7' fill='#94490a'/></svg> after, below 98%"),
    D(64, 642, 1152, None, "note", "Local run, 2026-11-11. All nine are L4 modules (9 of 82), chosen by the author. Axis starts at 40%, one module began at 0%. Before: seven from this session's first run, normalise and paired_bootstrap from the 2026-11-07 campaign. Not a certification."),
    D(64, 690, 1152, None, "src", "docs/thesis-remediation/MUTATION_FOCUSED_DIAGNOSTICS_2026-11-11.md &nbsp;·&nbsp; thresholds not changed"),
]), tone="bone")

# ---------------------------------------------------------------- raw vs adjusted
slide("Raw versus adjusted", "".join([
    D(64, 52, 900, None, "k", "What a score means &nbsp;·&nbsp; LSTM autoencoder, one module, one shard"),
    D(64, 84, 1152, None, "", "<h2 style='font-size:48px'>Raw and adjusted scores differ, and the raw one leads</h2>"),
    D(64, 232, 560, None, "", "<div class='num ember' style='font-size:130px'>97.61%</div><div class='cond' style='font-size:30px;font-weight:600;margin-top:6px'>raw: 368 of 377 killed</div><p style='font-size:19px;margin-top:8px'>Below the 98% bar for L4. Every survivor counts.</p>"),
    D(664, 232, 552, None, "", "<div class='num' style='font-size:84px;color:var(--steel);margin-top:46px'>98.66%</div><div class='cond' style='font-size:30px;font-weight:600;margin-top:6px'>adjusted: 368 of 373</div><p style='font-size:19px;margin-top:8px'>Four mutants removed as equivalent. They were accepted by the repository owner, who is the sole author and reviewer: not an independent review.</p>"),
    D(64, 560, 1152, None, "note", "Five inconclusive mutants stay eligible. No timeout. The adjusted figure depends on a human judgement that raw counts do not need."),
    D(64, 678, 1152, None, "src", "focused LSTM diagnostic &nbsp;·&nbsp; verification/mutation_risk_policy.json"),
]))

# ---------------------------------------------------------------- not certification
bar = []
x = 0
for n, lab, col, op in [(26, "pass", "var(--steel)", 1), (31, "fail", "var(--ember)", 1), (25, "incomplete", "#ffffff", .25)]:
    w = n / 82 * 1152
    bar.append(f"<div style='position:absolute;left:{x}px;top:0;width:{w-3}px;height:54px;background:{col};opacity:{op}'></div><div style='position:absolute;left:{x}px;top:64px;width:{w}px'><span class='num' style='font-size:44px'>{n}</span> <span style='font:500 18px var(--sans)'>{lab}</span></div>")
    x += w
slide("Not certification", "".join([
    D(64, 44, 700, None, "k", "What the evidence does not cover"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:48px'>A focused pass does not certify the repository</h2>"),
    D(64, 180, 1152, 120, "", "".join(bar)),
    D(64, 300, 1152, None, "note", "First complete native campaign, 2026-11-07: 82 L4 modules. 65.5% of L4 mutants killed against 98% required; 7,501 further mutants had no covering test. Bars count modules, the percentage counts mutants, and the 98.66% of the previous slide covers one module of the 82. Not re-measured here."),
    D(64, 382, 1152, 1, "hair"),
    D(64, 398, 360, None, "", "<div class='k ember'>Open</div><p style='font-size:19px;margin-top:8px'>31 L4 modules below threshold and 25 incomplete in that campaign.</p>"),
    D(464, 398, 360, None, "", "<div class='k ember'>Open</div><p style='font-size:19px;margin-top:8px'>Survivors that look inert (dtype coercions, zip strict) await an owner decision.</p>"),
    D(864, 398, 352, None, "", "<div class='k ember'>Found</div><p style='font-size:19px;margin-top:8px'>The minimum anomaly count, 3, is below the 6 a stratified 70 / 15 / 15 split needs. No archived result changes.</p>"),
    D(64, 560, 1152, None, "", "<p style='font-size:24px;font-family:var(--cond);font-weight:600'>The release gate fails and stays closed. No full campaign was run in this phase.</p>"),
    D(64, 678, 1152, None, "src", "verification/mutation_risk_policy.json &nbsp;·&nbsp; risk-native-campaign-2026-11-07.json"),
]))

# ---------------------------------------------------------------- where it stands
done = ["held-out split, 5 seeds, chronological and LSTM pilots, cost study", "pool of 152 sets (#66), typed injection on 42 tables (#65)", "benchmark on the 100 labelled pool problems",
        "deep rows (#64), multi-schema generator (#67)", "IMRaD restructuring (#68, #69, #85); bibliography audit remains #101", "decision-level study under shift (#63)",
        "complete registry of 17 detectors, every study rerun", "every study extended to the 152-dataset pool, six hypotheses"]
slide("Where it stands", "".join([
    D(64, 44, 700, None, "k", "Where it stands"),
    D(64, 72, 1152, None, "", "<h2 style='font-size:46px'>Experiments run, paper in IMRaD form</h2>"),
    D(64, 160, 640, None, "", "<div class='k steel' style='margin-bottom:10px'>Done</div>" + "".join(f"<p style='font-size:20px;line-height:1.3;margin-bottom:12px'>{d}</p>" for d in done)),
    D(760, 160, 456, None, "", "<div class='k ember' style='margin-bottom:10px'>Next: P0 remediation</div><p style='font-size:19px'>Detector and source audits, source-aware statistics, archive replay, publication corrections (issues #89, #91, #100, #103).</p>"
        "<div class='hair' style='position:relative;margin:20px 0'></div><p style='font-size:18px'>The roadmap preserves T001 to T415. <b>91 of 415</b> are checked as of 2026-11-11, including T163 to T171 of #94. T172, T062 and T063 remain open, as do the issues.</p><p class='note' style='margin-top:12px;font-size:15px'>Optional P2 research is outside the active scope.</p>"),
    D(64, 678, 1152, None, "src", "docs/thesis-remediation/ &nbsp;·&nbsp; this deck is updated with every merged step"),
]), tone="bone")

# ---------------------------------------------------------------- takeaway
slide("Takeaway", "".join([
    photo(0, 0, 1280, 720, "30% 55%", "230%", "cover-plate", 0.45),
    D(0, 0, 1280, 720, "scrim", "", "background:linear-gradient(90deg,rgba(10,10,10,.92) 0%,rgba(10,10,10,.7) 55%,rgba(10,10,10,.25) 100%)"),
    D(64, 56, 700, None, "k", "Takeaway"),
    D(64, 120, 1000, None, "", "<h1 style='font-size:80px;line-height:1.0'>Rules and machine learning are complementary <span class='ember'>by anomaly type</span>.</h1>"),
    D(64, 400, 760, None, "", "<p style='font-size:21px'>Across the three examples, unsupervised detection pays off only on Cardio, where anomalies are rare outliers. On 100 labelled pool problems, rankings need train-only revalidation. On 42 real tables with injected types, the synthetic pattern holds only in part, which is why the real-data matrix is the differentiator.</p>"),
    D(64, 600, 900, None, "note", "The pipeline, the 152-dataset pool, the protocols and the verification layer are in place. The IMRaD write-up and the remaining studies are what remains."),
    D(64, 664, 1152, None, "src", "github.com/theobigand/etl-anomaly-benchmark &nbsp;·&nbsp; bounded verification &nbsp;·&nbsp; 152 datasets &nbsp;·&nbsp; 17 detectors"),
]))


def assemble():
    secs = []
    out = []
    for i, (sec, tone, cls, body) in enumerate(SLIDES):
        pg = f"<div class='pg' style='position:absolute'>{i+1}</div>" if sec not in ("Cover",) else ""
        out.append(f"<section class='slide {tone} {cls}' data-sec='{sec}' aria-label='Slide {i+1}, {sec}'>{body}{pg}</section>")
    js = """
const slides=[...document.querySelectorAll('.slide')];const stage=document.getElementById('stage');
const dots=document.getElementById('dots'),count=document.getElementById('count');let i=0;
slides.forEach((s,n)=>{const b=document.createElement('button');b.type='button';b.setAttribute('aria-label','Slide '+(n+1)+', '+(s.dataset.sec||''));b.addEventListener('click',()=>go(n));dots.appendChild(b);});
function fit(){const s=Math.min(innerWidth/1280,innerHeight/720);stage.style.transform='translate('+(-640*s)+'px,'+(-360*s)+'px) scale('+s+')';}
addEventListener('resize',fit);fit();
function go(n){i=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,k)=>s.classList.toggle('on',k===i));[...dots.children].forEach((d,k)=>d.setAttribute('aria-current',k===i?'true':'false'));count.textContent=(i+1)+' / '+slides.length;try{history.replaceState(null,'','#'+(i+1));}catch(e){}}
const next=()=>go(i+1),prev=()=>go(i-1);
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();next();}else if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();prev();}else if(e.key==='Home')go(0);else if(e.key==='End')go(slides.length-1);});
let tx=null;addEventListener('touchstart',e=>tx=e.changedTouches[0].clientX,{passive:true});
addEventListener('touchend',e=>{if(tx===null)return;const d=e.changedTouches[0].clientX-tx;if(Math.abs(d)>50)(d<0?next:prev)();tx=null;},{passive:true});
go(parseInt(location.hash.slice(1))-1||0);
"""
    html = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Anomaly detection in the ETL pipeline, progress deck</title><style>" + CSS + "</style></head><body>"
            "<div id='stage'>" + "".join(out) + "</div><nav id='dots' aria-label='slides'></nav><div id='count'></div><script>" + js + "</script></body></html>")
    (HERE / "thesis_progress.html").write_text(html)
    print(len(SLIDES), "slides,", len(html) // 1024, "KB")
