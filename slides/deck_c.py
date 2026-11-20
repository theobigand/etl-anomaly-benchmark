# ruff: noqa: E501
"""Slides for verification, mutation testing, status and the takeaway."""

from deck_lib import D, flow, foot, photo, slide, tbl


def kicker(s):
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


# opener part 4 --------------------------------------------------------
slide(
    "Part 4",
    "".join(
        [
            photo(0, 0, 1280, 720, "50% 50%", "cover", "flush-plate"),
            D(
                0,
                0,
                1280,
                720,
                "scrim",
                "",
                "background:linear-gradient(0deg,rgba(10,10,10,.9) 0,rgba(10,10,10,.72) 24%,rgba(10,10,10,0) 48%),linear-gradient(90deg,rgba(10,10,10,.75) 0%,rgba(10,10,10,.4) 50%,rgba(10,10,10,0) 100%)",
            ),
            D(64, 56, 600, None, "k", "Part 4 of 4"),
            D(
                64,
                92,
                900,
                None,
                "",
                "<h1 style='font-size:84px;line-height:.98'>What the tests <span class='em'>protect</span>,<br>and what they do not</h1>",
            ),
            D(
                64,
                540,
                640,
                None,
                "",
                "<p class='lede' style='color:#c4bfb3'>Verification of the code that produces the numbers, and mutation testing as a way to see its blind spots.</p>",
            ),
        ]
    ),
    role="transition",
    family="image-led",
    dominant="photograph",
    density="low",
    image="photo 1672px, uncropped",
    light="raking, lower left",
)

# historical verification ----------------------------------------------
slide(
    "Historical verification",
    "".join(
        [
            D(
                64,
                40,
                900,
                None,
                "k",
                "Implemented and tested &nbsp;<span class='tag anom'>historical run, defined scope</span>",
            ),
            title("Historical verification has a defined scope", 44, 68),
            flow(
                64,
                144,
                740,
                [
                    "<div class='sheet' style='position:static;padding:6px 10px'>"
                    + tbl(
                        ["Check", "Result", "Scope"],
                        [
                            [
                                "line coverage",
                                "1,790 / 1,790",
                                "pipeline modules and experiment scripts",
                            ],
                            ["branch coverage", "350 / 350", "same scope"],
                            [
                                "mutation, computing code",
                                "95.68%",
                                "split, metrics, generator, detectors",
                            ],
                            ["mutation, input / output", "98.87%", "readers, writers, scripts"],
                            ["fault injection", "23 / 23", "four went through every earlier test"],
                            ["real-data check", "pass", "three CSV files, manuscript tables match"],
                        ],
                        text_cols=(2,),
                    )
                    + "</div>",
                    "<p class='note'>Survivors (122) count as failures and were classified by reading the changes, not by proof. This run predates the risk-tiered bars of slide 46 and was not scored against them.</p>",
                ],
                maxh=520,
                gap=14,
            ),
            flow(
                844,
                144,
                372,
                [
                    "<p style='font-size:20px'>These measurements belong to local run <b>d4304c5</b>. They cover the core pipeline and experiment scripts, with separate verifier checks.</p><p style='font-size:19px;margin-top:12px'><span class='tag anom'>limit</span> They do not certify the new research modules or establish scientific validity. The run is not independently attested.</p>",
                    "<div style='display:flex;gap:22px;flex-wrap:wrap'><div class='stat sm' style='position:static'><span class='num'>1,292</span><span class='lab' style='font-size:15px'>tests, plus 3 on full datasets</span></div><div class='stat sm' style='position:static'><span class='num'>97.61%</span><span class='lab' style='font-size:15px'>mutants killed, 4,980 of 5,102 (historical run, core code)</span></div></div>",
                ],
                maxh=520,
                gap=22,
            ),
            foot(
                "make verify-all &nbsp;·&nbsp; .github/workflows &nbsp;·&nbsp; main, local run sealed at d4304c5"
            ),
        ]
    ),
    tone="bone",
    role="context",
    family="table + scope",
    dominant="table",
    density="medium",
    colour="amber for limit",
)

# M1: mutant, with a behaviour trace ------------------------------------
trace = tbl(
    [
        "score",
        "threshold",
        "original: score &gt; threshold",
        "mutant: score &gt;= threshold",
        "the test expects",
        "test result",
    ],
    [
        ["0.70", "0.50", "alert", "alert", "alert", "pass"],
        ["0.30", "0.50", "no alert", "no alert", "no alert", "pass"],
        [
            "0.50",
            "0.50",
            "no alert",
            "alert",
            "no alert",
            "<b class='ok'>test fails: mutant killed</b>",
        ],
    ],
    text_cols=(2, 3, 4, 5),
    compact=1,
)
slide(
    "Mutation: mutant",
    "".join(
        [
            kicker("Mutation testing, 1 of 5"),
            title("A mutant is a deliberately broken copy of the code", 48, 64),
            D(
                64,
                150,
                560,
                150,
                "sheet",
                "<pre style='padding:20px 22px;font-size:21px;line-height:1.65'><span style='color:#8b887f'># research/alert_budget.py</span>\n<span class='del'>- flags = scores &gt; info[\"threshold\"]</span>\n<span class='add'>+ flags = scores &gt;= info[\"threshold\"]</span></pre>",
            ),
            D(
                664,
                150,
                552,
                None,
                "",
                "<p style='font-size:20px'>A tool makes many copies, each with one small plausible bug, and runs the test suite on every copy. The change here is real: a score <b>equal</b> to the training threshold would now raise an alert.</p><p style='font-size:19px;margin-top:12px'>Why bother: coverage says a line ran, not that a test would notice if the line were wrong.</p>",
            ),
            D(64, 340, 1152, None, "k", "what the tests see"),
            D(64, 366, 1152, None, "sheet", trace, "padding:6px 10px"),
            D(
                64,
                560,
                1152,
                None,
                "",
                "<p style='font-size:21px;max-width:1040px'>The first two tests pass on both versions, so they cannot tell original from mutant. Only the equality case does, and no test covered it before this session. The new test, &quot;a score equal to the training threshold is not an alert&quot;, kills this mutant.</p>",
            ),
            foot(
                "research/tests/test_alert_budget.py &nbsp;·&nbsp; mutmut 3.8.0, raw focused counts"
            ),
        ]
    ),
    tone="bone",
    role="definition",
    family="code + behaviour trace",
    dominant="three-row trace",
    density="medium",
    colour="steel for the killed mutant",
)

# M2: killed or survived (photo) ---------------------------------------
slide(
    "Mutation: killed or survived",
    "".join(
        [
            photo(0, 0, 1280, 720, "50% 50%", "cover", "flush-plate"),
            D(
                0,
                0,
                1280,
                240,
                "scrim",
                "",
                "background:linear-gradient(rgba(10,10,10,.96) 55%,rgba(10,10,10,0))",
            ),
            D(
                0,
                430,
                1280,
                290,
                "scrim",
                "",
                "background:linear-gradient(rgba(10,10,10,0),rgba(10,10,10,.93) 45%)",
            ),
            D(64, 36, 700, None, "k", "Mutation testing, 2 of 5"),
            D(
                64,
                62,
                1100,
                None,
                "",
                "<h2 class='fit1' style='font-size:46px'>The tests are the light. A mutant is killed when a test sees it</h2>",
            ),
            D(
                500,
                178,
                330,
                None,
                "",
                "<div class='cond' style='font-size:26px;font-weight:700;color:var(--steel)'>killed</div><div style='font:500 16px/1.3 var(--sans)'>a test fails, so the change is noticed</div>",
                "background:rgba(10,10,10,.78);padding:8px 12px",
            ),
            D(583, 256, 2, 14, "", "", "background:var(--steel)"),
            D(
                330,
                396,
                340,
                None,
                "",
                "<div class='cond' style='font-size:26px;font-weight:700;color:var(--ember)'>survived</div><div style='font:500 16px/1.3 var(--sans)'>every test passes, so nothing noticed the change</div>",
                "background:rgba(10,10,10,.78);padding:8px 12px",
            ),
            D(458, 382, 2, 14, "", "", "background:var(--ember)"),
            D(409, 289, 98, 98, "", "", "border:2px solid var(--ember);border-radius:50%"),
            D(536, 264, 100, 100, "", "", "border:2px solid var(--steel);border-radius:50%"),
            D(
                64,
                516,
                1152,
                None,
                "",
                "<p style='font-size:23px;max-width:1040px'>A survivor matters because it is either a <b>behaviour no test protects</b> (a gap to close with a new test), or a <b>change that cannot be observed</b> (an equivalent mutant, next slide). It stays in the count of eligible mutants (the denominator of killed / eligible) until one of the two is shown.</p>",
            ),
        ]
    ),
    role="definition",
    family="image-led annotation",
    dominant="photograph with two rings",
    density="medium",
    image="photo 1672px, uncropped",
    light="raking, lower left",
    colour="steel killed, amber survived",
)

# M3: equivalent mutants -----------------------------------------------
eq = tbl(
    ["n", "n &gt; 0", "n &gt;= 1 (mutant)"],
    [
        ["-1", "False", "False"],
        ["0", "False", "False"],
        ["1", "True", "True"],
        ["2", "True", "True"],
    ],
    compact=1,
)
slide(
    "Mutation: equivalent",
    "".join(
        [
            kicker("Mutation testing, 3 of 5"),
            title("Some changes cannot be seen, and only the owner may say so", 42, 64),
            flow(
                64,
                150,
                540,
                [
                    "<div class='cond' style='font-size:34px;font-weight:600'>Equivalent mutant</div>",
                    "<p style='font-size:22px;line-height:1.4'>A change that does not alter what the program does, so no test can fail on it. For an integer count <span style='font-family:var(--mono);font-size:20px'>n</span>, changing <span style='font-family:var(--mono);font-size:20px'>n &gt; 0</span> to <span style='font-family:var(--mono);font-size:20px'>n &gt;= 1</span> gives the same answer for every input.</p>",
                    "<div class='sheet' style='position:static;padding:10px 14px;font-size:20px'>"
                    + eq
                    + "</div>",
                    "<p class='note' style='font-size:17px;line-height:1.4'>Candidates in this work, each needing the owner's approval: a dtype coercion on an array that is already float, zip(strict=) on lists of equal length, flush= on a print.</p>",
                ],
                maxh=540,
                gap=18,
            ),
            flow(
                664,
                150,
                552,
                [
                    "<div class='cond' style='font-size:34px;font-weight:600'>Why approval is required</div>",
                    "<p style='font-size:22px;line-height:1.4'>Calling a survivor equivalent removes it from the denominator and raises the score. If the author of the tests could do that alone, the author would grade their own work. The repository records each equivalence, with its reason and source. The owner decides, here by delegation.</p>",
                    "<div class='cond' style='font-size:34px;font-weight:600;margin-top:10px'>Status here</div>",
                    "<p style='font-size:22px;line-height:1.4'>Until approved, a candidate stays in the denominator. The four equivalences accepted earlier for the LSTM autoencoder were accepted by the repository owner, who is also the sole author and reviewer: owner approval, not independent review.</p>",
                ],
                maxh=540,
                gap=14,
            ),
            foot("docs/thesis-remediation/MUTATION_FOCUSED_DIAGNOSTICS_2026-11-11.md"),
        ]
    ),
    tone="bone",
    role="definition",
    family="example table + argument",
    dominant="equivalence table",
    density="medium",
)

# M4: tiers -------------------------------------------------------------
lad = []
for i, (t, v) in enumerate([("L4", 98), ("L3", 95), ("L2", 90), ("L1", 80)]):
    y = 190 + i * 100
    lad += [
        D(64, y, 100, None, "", f"<span class='num' style='font-size:64px'>{t}</span>"),
        D(
            190,
            y + 8,
            v * 5.0,
            14,
            "",
            "",
            f"background:{'var(--paper)' if t == 'L4' else 'var(--steel)'};opacity:{1 if t == 'L4' else 0.55}",
        ),
        D(
            190 + v * 5.0 + 14,
            y - 2,
            140,
            None,
            "",
            f"<span class='num' style='font-size:44px'>{v}%</span>",
        ),
    ]
slide(
    "Mutation: tiers",
    "".join(
        [
            kicker("Mutation testing, 4 of 5"),
            title("The bar rises with the scientific risk of the code", 48, 64),
            *lad,
            D(
                930,
                190,
                286,
                None,
                "",
                "<p style='font-size:19px'>Each module has a risk level, and each level a minimum share of eligible mutants (those counted in the score) that tests must kill.</p><p style='font-size:19px;margin-top:14px'><b>L4</b>, the highest, is code whose bug would change a reported result. Its bar is <b>98%</b>.</p><p style='font-size:19px;margin-top:14px'>The thresholds were not changed; 12 modules moved from L4 to L3 on 13 November, none since.</p>",
            ),
            foot(
                "verification/mutation_risk_policy.json &nbsp;·&nbsp; thresholds L1 80, L2 90, L3 95, L4 98"
            ),
        ]
    ),
    role="definition",
    family="threshold ladder",
    dominant="four bars",
    density="low",
)

# M5: final campaign ---------------------------------------------------
slide(
    "Mutation: chart",
    "".join(
        [
            D(
                64,
                34,
                900,
                None,
                "k",
                "Mutation testing, 5 of 5 &nbsp;·&nbsp; final campaign, 2026-11-18",
            ),
            title("One campaign, 100 modules: all 97 with mutants meet their bar", 40, 58),
            flow(
                64,
                160,
                720,
                [
                    "<div class='sheet' style='position:static;padding:6px 10px'>"
                    + tbl(
                        ["Level", "Modules", "Bar", "Raw", "Adjusted"],
                        [
                            ["L2", "3", "90%", "100.00%", "100.00%"],
                            ["L3", "18", "95%", "98.71%", "98.71%"],
                            ["L4", "78", "98%", "98.68%", "99.01%"],
                        ],
                        best=((0, 4), (1, 4), (2, 4)),
                    )
                    + "</div>",
                    "<p class='note'>Linux, 45 parallel shards of one commit, every execution bound by a controller proof and the digest of every tracked file. Three modules have no function body. The adjusted score counts only exclusions that are bound to the source and to the dependency versions.</p>",
                ],
                maxh=470,
                gap=20,
            ),
            flow(
                832,
                160,
                384,
                [
                    "<div class='stat'><span class='num'>35,255</span><span class='lab'>mutants: 34,791 killed, 460 survived, 4 timed out</span></div>",
                    "<div class='stat'><span class='num ember'>98</span><span class='lab'>excluded as equivalent, in 21 modules. 92 carry an argument, 6 rest on the owner's word</span></div>",
                    "<p class='note'>The other 362 survivors and the 4 timeouts still count against their modules.</p>",
                ],
                maxh=470,
                gap=18,
            ),
            foot(
                "docs/thesis-remediation/MUTATION_CLOSURE_2026-11-17.md &nbsp;·&nbsp; thresholds not changed"
            ),
        ]
    ),
    tone="bone",
    role="evidence",
    family="table + two figures",
    dominant="two large numbers",
    density="high",
    colour="steel adjusted, amber exclusions",
)

# raw vs adjusted --------------------------------------------------------
slide(
    "Raw versus adjusted",
    "".join(
        [
            kicker("What a score means &nbsp;·&nbsp; LSTM autoencoder, one module, one shard"),
            title("One module, two scores: raw 97.61%, adjusted 98.66%", 48, 64),
            D(
                64,
                220,
                560,
                None,
                "",
                "<div class='num' style='font-size:112px'>97.61%</div><div class='cond' style='font-size:30px;font-weight:600;margin-top:6px'>raw: 368 of 377 killed</div><p style='font-size:19px;margin-top:8px'><span class='tag anom'>below 98%</span> Every survivor counts.</p>",
            ),
            D(
                664,
                220,
                552,
                None,
                "",
                "<div class='num ok' style='font-size:112px'>98.66%</div><div class='cond' style='font-size:30px;font-weight:600;margin-top:6px'>adjusted: 368 of 373</div><p style='font-size:19px;margin-top:8px'>Four mutants removed as equivalent, a smaller denominator by decision. They were accepted by the repository owner, who is the sole author and reviewer: not an independent review.</p>",
            ),
            D(
                64,
                560,
                1152,
                None,
                "note",
                "Five inconclusive mutants stay eligible. No timeout. The adjusted figure depends on a human judgement that raw counts do not need.",
            ),
            foot("focused LSTM diagnostic &nbsp;·&nbsp; verification/mutation_risk_policy.json"),
        ]
    ),
    role="definition",
    family="typographic contrast",
    dominant="two scores",
    density="low",
    colour="amber for below bar",
)

# not certification ------------------------------------------------------
bar = []
x = 0
for n, lab, style in [
    (97, "pass", "background:var(--steel)"),
    (3, "no function body", "background:transparent;border:2px dashed var(--paper-soft)"),
]:
    w = n / 100 * 1152
    bar.append(
        f"<div style='position:absolute;left:{x}px;top:0;width:{w - 4}px;height:54px;{style}'></div><div style='position:absolute;left:{x if n > 50 else x + w - 200}px;top:64px;width:200px;text-align:{'left' if n > 50 else 'right'}'><span class='num' style='font-size:44px'>{n}</span> <span style='font:500 17px var(--sans)'>{lab}</span></div>"
    )
    x += w
slide(
    "Not certification",
    "".join(
        [
            kicker("What the evidence does not cover"),
            title("A certification names one revision, not the findings", 48, 60),
            D(64, 180, 1152, 120, "", "".join(bar)),
            D(
                64,
                300,
                1152,
                None,
                "note",
                "Final campaign, 2026-11-18: 100 classified modules, 97 with mutants all meeting their own bar, 3 without a function body. Bars count modules; the score counts mutants.",
            ),
            D(64, 382, 1152, 1, "hair"),
            D(
                64,
                398,
                360,
                None,
                "",
                "<div class='k anom'>Open</div><p style='font-size:19px;margin-top:8px'>20 modules need exclusions to pass, decided by delegation and not by independent review; 362 survivors still count.</p>",
            ),
            D(
                464,
                398,
                360,
                None,
                "",
                "<div class='k anom'>Open</div><p style='font-size:19px;margin-top:8px'>The release script certified commit 7c0af40d, as a CI run only, not independently attested. A squash-merged commit needs its own run.</p>",
            ),
            D(
                864,
                398,
                352,
                None,
                "",
                "<div class='k anom'>Found</div><p style='font-size:19px;margin-top:8px'>A score belongs to its host: runner images, a numerical test and a slow assertion each changed evidence before they were fixed.</p>",
            ),
            D(
                64,
                560,
                1152,
                None,
                "",
                "<p style='font-size:24px;font-family:var(--cond);font-weight:600'>Certified for one revision (7c0af40d), not for the findings. The pull request is merged.</p>",
            ),
            foot(
                "docs/thesis-remediation/MUTATION_CLOSURE_2026-11-17.md &nbsp;·&nbsp; verification/mutation_risk_policy.json"
            ),
        ]
    ),
    role="caveat",
    family="segmented bar + findings",
    dominant="100-module bar",
    density="medium",
    colour="steel pass, dashed no function body",
)

# where it stands --------------------------------------------------------
done = [
    "held-out split, 5 seeds, chronological and LSTM pilots, cost study",
    "pool of 152 sets (#66), typed injection on 42 tables (#65)",
    "benchmark on the 100 labelled pool problems",
    "deep rows (#64), multi-schema generator (#67)",
    "IMRaD restructuring (#68, #69, #85); bibliography audit remains #101",
    "decision-level study under shift (#63)",
    "complete registry of 17 detectors, every study rerun",
    "every study extended to the 152-dataset pool, six hypotheses",
    "coverage matrix, mixed-schema injection on 86 more tables, 7 real time series",
]
slide(
    "Where it stands",
    "".join(
        [
            kicker("Where it stands"),
            title("Experiments run, paper in IMRaD form", 46, 62),
            flow(
                64,
                160,
                740,
                [
                    "<div class='k ok'>Done</div>",
                    "<div style='border-top:1px solid var(--bone-line)'>"
                    + "".join(
                        f"<p style='font-size:22px;line-height:1.28;margin:0;padding:9px 0;border-bottom:1px solid var(--bone-line)'>{d}</p>"
                        for d in done
                    )
                    + "</div>",
                ],
                maxh=540,
                gap=10,
            ),
            flow(
                840,
                160,
                376,
                [
                    "<div class='k anom'>Next: P0 remediation</div>",
                    "<p style='font-size:22px;line-height:1.38'>Detector and source audits, source-aware statistics, archive replay, publication corrections (issues #89, #91, #100, #103).</p>",
                    "<div style='height:1px;background:var(--bone-line)'></div>",
                    "<p style='font-size:21px;line-height:1.38'>The roadmap preserves T001 to T415. <b>91 of 415</b> are checked as of <span style='white-space:nowrap'>2026-11-11</span>, including T163 to T171 of #94. T172, T062 and T063 remain open, as do the issues.</p>",
                    "<p class='note' style='font-size:17px'>Optional P2 research is outside the active scope.</p>",
                ],
                maxh=540,
                gap=16,
            ),
            foot(
                "docs/thesis-remediation/ &nbsp;·&nbsp; this deck is updated with every merged step"
            ),
        ]
    ),
    tone="bone",
    role="status",
    family="two lists",
    dominant="done list",
    density="medium",
)

# coverage ---------------------------------------------------------------
import json as _json  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_cov = _json.loads(
    (
        _Path(__file__).resolve().parents[1] / "verification/evidence/coverage/coverage_matrix.json"
    ).read_text()
)["summary"]
_cov_rows = [
    ("Catalog entries", f"{_cov['datasets']}", "versions of one source count once below"),
    ("Independent sources", f"{_cov['independent_sources']}", "units of inference"),
    (
        "With a detector-quality measurement",
        f"{_cov['with_detector_quality_measurement']}",
        "was 120 before the extensions",
    ),
    ("Numeric typed injection", "58", "unchanged, reported separately"),
    ("Mixed-schema typed injection", "86", "new, protocol written first, categorical faults"),
    ("Real time series, injected faults", "7", "4 labelled chronological tables as before"),
    ("Pipeline runs that succeed", "304 of 304", "14 failures repaired in seven readers"),
]
slide(
    "Coverage",
    "".join(
        [
            kicker("Coverage"),
            title("A dataset counts only if it has a measurement", 44, 62),
            flow(
                64,
                160,
                1152,
                [
                    "<div style='border-top:1px solid var(--bone-line)'>"
                    + "".join(
                        f"<div style='display:flex;gap:24px;align-items:baseline;padding:10px 0;border-bottom:1px solid var(--bone-line)'>"
                        f"<span style='flex:0 0 430px;font-size:24px'>{a}</span>"
                        f"<b style='flex:0 0 190px;font-size:30px'>{b}</b>"
                        f"<span class='note' style='font-size:19px'>{c}</span></div>"
                        for a, b, c in _cov_rows
                    )
                    + "</div>",
                    "<p class='note' style='font-size:18px'>Labels are minority-class proxies; injected faults are artificial. One table is retired.</p>",
                ],
                maxh=540,
                gap=14,
            ),
            foot(
                "verification/evidence/coverage/ &nbsp;·&nbsp; generated by research/coverage_matrix.py"
            ),
        ]
    ),
    tone="bone",
    role="status",
    family="table",
    dominant="coverage counts",
    density="medium",
)

# takeaway ---------------------------------------------------------------
slide(
    "Takeaway",
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
                "background:linear-gradient(0deg,rgba(10,10,10,.9) 0,rgba(10,10,10,.72) 24%,rgba(10,10,10,0) 48%),linear-gradient(90deg,rgba(10,10,10,.92) 0%,rgba(10,10,10,.78) 52%,rgba(10,10,10,.25) 100%)",
            ),
            flow(
                64,
                52,
                1040,
                [
                    "<div class='k'>Takeaway</div>",
                    "<h1 style='font-size:62px;line-height:1.04'>Rules and machine learning<br>are complementary <span class='em'>by anomaly type</span>.</h1>",
                    "<p style='font-size:21px;max-width:760px'>Across the three examples, unsupervised detection pays off only on Cardio, where anomalies are rare outliers. On 100 labelled pool problems, rankings need train-only revalidation. On 42 real tables with injected types, the synthetic pattern holds only in part, which is why the real-data matrix is the differentiator.</p>",
                    "<div class='note' style='max-width:760px'>The pipeline, the 152-dataset pool, the protocols and the verification layer are in place. The remaining P0 corrections and the train-only replay are what remains. The photograph is the cover illustration again: one raised pad.</div>",
                ],
                maxh=620,
                gap=24,
            ),
            foot(
                "github.com/theobigand/etl-anomaly-benchmark &nbsp;·&nbsp; bounded verification &nbsp;·&nbsp; 152 datasets &nbsp;·&nbsp; 17 detectors"
            ),
        ]
    ),
    role="close",
    family="image-led bookend",
    dominant="photograph",
    density="low",
    image="photo 1672px, 128% crop",
    light="raking, lower left",
)
