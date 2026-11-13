"""The generated sections of the manuscript are what their generators write from the archive."""

import shutil
import sys
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paper_appendix as pa  # noqa: E402
import paper_tables as pt  # noqa: E402
import pool_extension_paper as pe  # noqa: E402

TEX = pt.ROOT / "paper" / "main.tex"


@pytest.mark.parametrize("module", [pa, pe], ids=["matrices appendix", "pool extension"])
def test_regenerating_a_section_leaves_the_manuscript_unchanged(module, tmp_path):
    copy = tmp_path / "main.tex"
    shutil.copy(TEX, copy)
    module.write(copy, pt.EVIDENCE)
    assert copy.read_text() == TEX.read_text()


def test_the_generators_use_the_displayed_metric_name_of_the_manuscript():
    for generated in (pe.main_block(pt.EVIDENCE), pe.appendix_block(pt.EVIDENCE)):
        assert "PR-AUC" not in generated
