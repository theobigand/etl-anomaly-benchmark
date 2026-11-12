"""Browser-based layout tests: deselected without Chromium, mandatory in the slide-quality job.

Tests are deselected, not skipped, because the fast verification counts a skip as a failure.
The dedicated slide-quality job sets SLIDES_REQUIRE_BROWSER=1; then a missing Chromium is an error,
so the check cannot silently not run there. Install Chromium or set CHROME to run them locally.
"""

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import check_layout  # noqa: E402


def pytest_collection_modifyitems(config, items):
    if check_layout.find_chrome() is not None:
        return
    if os.environ.get("SLIDES_REQUIRE_BROWSER") == "1":
        raise pytest.UsageError("SLIDES_REQUIRE_BROWSER=1 but no Chromium binary was found")
    drop = [i for i in items if i.get_closest_marker("browser")]
    if drop:
        config.hook.pytest_deselected(items=drop)
        items[:] = [i for i in items if i not in drop]
