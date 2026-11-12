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
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
CHROME_CANDIDATES = [
    "~/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell",
    "chrome-headless-shell",
    "chromium",
    "google-chrome",
]


def find_chrome(explicit=None):
    for c in [explicit, os.environ.get("CHROME"), *CHROME_CANDIDATES]:
        if c:
            p = pathlib.Path(c).expanduser()
            if p.exists():
                return str(p)
    return None


def probe(path, chrome, stress=False):
    url = f"file://{pathlib.Path(path).resolve()}?check" + ("&stress" if stress else "")
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
    ap.add_argument("--chrome")
    ap.add_argument("--html", default=str(HERE / "thesis_progress.html"))
    a = ap.parse_args(argv)
    chrome = find_chrome(a.chrome)
    if not chrome:
        print("no Chromium found; layout check NOT RUN")
        return 2
    issues = probe(a.html, chrome, a.stress)
    for i in issues:
        print(f"slide {i['slide']:>2} {i['kind']:<16} {i['text']}")
    print(f"{len(issues)} layout issue(s)" + (" (stress fonts)" if a.stress else ""))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
