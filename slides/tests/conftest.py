"""Browser-based layout tests run only in the slide-quality gate, never in FAST.

FAST must not depend on a browser and counts a skipped test as a failure, so the `browser` tests are
deselected, not skipped, unless SLIDES_REQUIRE_BROWSER=1 (set by `make verify-slides` and the
`slides` CI job). That holds even when a Chrome happens to be installed: results depend on the exact
Chromium build and fonts, which only the dedicated job pins. With the variable set, a missing
Chromium is an error, so the check cannot silently not run there.
"""

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import check_layout  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SLIDES_REQUIRE_BROWSER") == "1":
        if check_layout.find_chrome() is None:
            raise pytest.UsageError("SLIDES_REQUIRE_BROWSER=1 but no Chromium binary was found")
        return
    drop = [i for i in items if i.get_closest_marker("browser")]
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = [i for i in items if i not in drop]
