#!/usr/bin/env python3
"""Run the in-page layout probe in a headless Chromium and report layout defects.

Usage:  python3 slides/check_layout.py [--stress] [--chrome PATH]
Exit status 1 when any text collides, is clipped or leaves its slide or svg.
"""

import argparse
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.parse

HERE = pathlib.Path(__file__).parent
CHROME_NAMES = ["chrome-headless-shell", "headless_shell", "chromium", "google-chrome"]
PLAYWRIGHT_CACHES = ["~/Library/Caches/ms-playwright", "~/.cache/ms-playwright"]

# One configuration per realistic font situation. "default" is the deck's own stack: the intended
# fonts where installed, the platform fallback otherwise. The others force one family: Arial
# (stress), a generic sans-serif, wide faces (Verdana, DejaVu Sans), a Helvetica alias and a
# serif. A family the machine lacks falls back by the platform's rules, so wrapping is measured.
FONT_MATRIX = [
    ("default", {}),
    ("arial", {"stress": True}),
    ("sans-serif", {"fonts": "sans-serif"}),
    ("verdana", {"fonts": "Verdana"}),
    ("dejavu", {"fonts": "DejaVu Sans"}),
    ("helvetica", {"fonts": "Helvetica"}),
    ("georgia", {"fonts": "Georgia"}),
]


def find_chrome(explicit=None):
    for c in [explicit, os.environ.get("CHROME")]:
        if c:
            p = pathlib.Path(c).expanduser()
            if p.exists():
                return str(p)
    for cache in PLAYWRIGHT_CACHES:
        root = pathlib.Path(cache).expanduser()
        for name in CHROME_NAMES[:2]:
            hits = sorted(root.glob(f"chromium_headless_shell-*/*/{name}")) if root.exists() else []
            if hits:
                return str(hits[-1])
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def probe(path, chrome, stress=False, fonts=None):
    url = f"file://{pathlib.Path(path).resolve()}?check" + ("&stress" if stress else "")
    if fonts:
        url += "&fonts=" + urllib.parse.quote(fonts)
    out = subprocess.run(
        [
            chrome,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--window-size=1280,720",
            "--virtual-time-budget=4000",
            "--dump-dom",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    ).stdout
    m = re.search(r'<pre id="layout-report">(.*?)</pre>', out, re.S)
    if not m:
        raise RuntimeError("layout probe produced no report")
    return json.loads(html.unescape(m.group(1)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stress", action="store_true")
    ap.add_argument("--fonts", help="force this font family (e.g. sans-serif, Verdana)")
    ap.add_argument("--matrix", action="store_true", help="run every font configuration")
    ap.add_argument("--report-dir", help="write one JSON report per configuration here")
    ap.add_argument("--chrome")
    ap.add_argument("--html", default=str(HERE / "thesis_progress.html"))
    a = ap.parse_args(argv)
    chrome = find_chrome(a.chrome)
    if not chrome:
        print("no Chromium found; layout check NOT RUN")
        return 2
    if a.matrix:
        return run_matrix(a.html, chrome, a.report_dir)
    issues = probe(a.html, chrome, a.stress, a.fonts)
    for i in issues:
        print(f"slide {i['slide']:>2} {i['kind']:<16} {i['text']}")
    mode = (" (stress fonts)" if a.stress else "") + (f" (fonts: {a.fonts})" if a.fonts else "")
    print(f"{len(issues)} layout issue(s)" + mode)
    return 1 if issues else 0


def run_matrix(html_path, chrome, report_dir=None):
    """Run every FONT_MATRIX configuration; the exit status is 1 if any reports an issue."""
    failed = 0
    for name, opts in FONT_MATRIX:
        issues = probe(html_path, chrome, opts.get("stress", False), opts.get("fonts"))
        for i in issues:
            print(f"[{name}] slide {i['slide']:>2} {i['kind']:<16} {i['text']}")
        print(f"[{name}] {len(issues)} layout issue(s)")
        failed += bool(issues)
        if report_dir:
            out = pathlib.Path(report_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / f"layout-{name}.json").write_text(json.dumps(issues, indent=1))
    print(f"{len(FONT_MATRIX)} font configurations, {failed} with issues")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
